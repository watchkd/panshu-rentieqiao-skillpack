# -*- coding: utf-8 -*-
"""语体 QA 门禁 —— 元规则 05《任氏论命语体与输出范式》的机械校验。

用法 A（整篇输出稿，纯文本）：
    python qa_yuyi.py --draft 论命稿.txt
用法 B（带规则引用表，JSON[{"RULE_ID","CONFIDENCE"}]）：
    python qa_yuyi.py --draft 稿.txt --refs refs.json
用法 C（内部草稿，跳过收尾推送检查）：
    python qa_yuyi.py --draft 草稿.txt --no-push-check
用法 D（溯源版：附出处清单，跳过 G10 工程信息检查）：
    python qa_yuyi.py --draft 溯源稿.txt --trace

校验门禁（对应元规则 05 §七 自检清单，机械可判定者）：
  G1 首句立象　　  首句应以「此造/此则/此以/X生于Y月/此局」起，而非"根据…/以下…"
  G2 病药对举　　  正文须同时含 病方词(嫌其/所忌/为病/病在/泄…破) 与 药方词(喜其/全赖/宜/最喜)
  G3 强度词↔置信度 可判定强度词(必/定/主 … 似/恐/庶几/或 …) 与引用规则的 CONFIDENCE 匹配，
                    若整句强断言但 refs 全无 A 级 → 预警
  G4 混层检测　　  任氏正文段（【按】之前）不得含 【按】/徐乐吾/L4 文字(混层即错)
  G5 附表禁令　　  主断正文不得含 表格符(| / +---+ / ★ / ◆) 且不在附录段（前置「命盘」表不算）
  G6 白话/现代套语 不得含 「该命主」「用户」「您」「综合来看」「总而言之」「总体而言」
  G7 立象词频　　  正文是否过度(无任氏骨架词) → 提示"未仿任氏语体"
  G8 收尾推送完整  **交付稿末尾须含 赞赏码 + 盘叔微信 二维码图 + 苍盘命书体验邀请**（缺即 FAIL）
  G9 工程痕迹　　  交付稿不得内嵌「写给技能」等内部指令块（出现即 FAIL）
  G10 工程信息　   **交付稿不得出现编号/规则库/命例库/元规则/置信度/溯源/技能包/数据条数/机器口吻**
                    （出现即 FAIL；溯源版用 --trace 跳过）

任意违规 → 逐条列出并 exit 1；全部通过 → exit 0。
"""
import re, sys, json, os

# ---- 词表（来自元规则 05 §三）----
LIXIANG = ["此造", "此则", "此以", "生于", "此局", "此命"]   # 立象
BING = ["嫌其", "所忌", "为病", "病在", "所嫌", "病者", "破局"]   # 病方
YAO  = ["喜其", "全赖", "最喜", "宜", "所赖", "赖", "喜神"]        # 药方
GUFENG = ["所谓", "此之谓", "盖", "故", "所以", "是以", "主", "惜乎", "美", "更妙", "更喜", "妙在"]

STRONG_A = ["必", "定主", "主夫"]   # A级: 必/定/主
# 注意：不能把单个"主"当强词（"主"也作"日主/主…"），用语境
WEAK_C = ["似", "恐", "庶几", "或为", "大约", "未可", "姑断"]

BAN_MODERN = ["该命主", "用户", "您", "综合来看", "总而言之", "总体而言", "总结", "综上所述", "下面", "接下来", "以下分析"]
BAN_TABLE_CHAR = ["|", "★", "◆", "+--", "+---", "|---|---"]

PANWEN_HINT = ["根据检索", "基于规则", "规则显示", "经查", "如下", "列表", "评分", "打分"]

# ---- 前置区（命盘/大运/生辰）识别：正文从第一个「批语/正文/一、」标题起 ----
FRONT_RE = re.compile(r"^##\s*(批语|批命正文|正文|断语|论断|分析|一、)", re.M)

# ---- G8 收尾推送（元规则 05 §八；内容以主 SKILL.md 末节为准）----
PUSH_APPRECIATION = "appreciation.jpg"          # 赞赏码 CDN 图
PUSH_WECHAT = "wechat_qr.jpg"                   # 盘叔微信 CDN 图
PUSH_CANGPAN_LINK = "mp.weixin.qq.com/s/9NFaItizyhEpjDzmTyEcPQ"   # 苍盘命书直通
PUSH_CANGPAN_WORD = "苍盘命书"

# ---- G9 工程痕迹（内部指令块不得进交付稿）----
LEAK_MARKERS = ["写给技能", "写给技能，不是写给用户", "⚠ 使用规则", "使用规则（写给技能"]

# ---- G10 工程信息（交付稿不得出现；溯源版用 --trace 跳过）----
ENGINEERING_TERMS = [
    "RTQ-RULE", "RTQ-CASE", "RTQ-", "规则库", "命例库", "归属库", "元规则",
    "五层归属", "置信度", "CONFIDENCE", "SOURCE_FILE", "溯源", "技能包",
    "数字复原", "rtq-panshu", "ziping-panshu", "待核", "index_query",
    "MultiDimIndex", "paipan_tool", "qa_yuyi", "tonggen", "build_index",
    "门禁", "自动生成", "数据源自", "防幻觉", "章号", "子技能", "路由表",
]
ENGINEERING_RE = re.compile(r"(?<![0-9A-Za-z])L[1-5](?![0-9A-Za-z])")

def strip_marks(t):
    """去掉标注符#RID等再判断"""
    return re.sub(r"#L[0-9-A-Z]+|#RTQ-RULE-[A-Z0-9-]+|@[A-Za-z0-9-]+", "", t)

def qa(text, refs=None, push_check=True, trace=False):
    res = []  # (level, code, msg)
    body = strip_marks(text)

    # 前置区（命盘/大运）与正文分界：表格禁令只作用于正文
    m_front = FRONT_RE.search(body)
    front = body[: m_front.start()] if m_front else ""
    rest = body[m_front.start():] if m_front else body

    # 分离 附录区／收尾推送区（"附录"/"出处"/"存疑台账"/署名行/赞赏码表 之后视为非正文，禁表符不在此判定）
    m_appx = re.search(r"(附\s*录|出处|存疑台账|以上批语|以上分析由「任铁樵|\|\s*赞赏码)", rest)
    main = rest[: m_appx.start()] if m_appx else rest
    appx = rest[m_appx.start():] if m_appx else ""

    # G1 首句立象
    first = re.sub(r"[\s#]", "", main)[:40]
    lixiang_ok = any(k in first for k in LIXIANG) or bool(
        re.search(r"[甲乙丙丁戊己庚辛壬癸][水木火土金]?生[于]?[子丑寅卯辰巳午未申酉戌亥]月", first))
    if not lixiang_ok:
        res.append(("WARN", "G1", "首句未按任氏「立象」范式（此造/此则/生于X月），开头=「%s…」" % first[:16]))
    # G7 骨架词
    gk = [k for k in GUFENG if k in main]
    if not gk:
        res.append(("WARN", "G7", "正文无任何任氏骨架词（所谓/故/所以/以是/妙在/惜乎…），不像任氏语体"))
    # G2 病药对举
    has_b = any(k in main for k in BING)
    has_y = any(k in main for k in YAO)
    if not (has_b and has_y):
        res.append(("WARN", "G2", "缺「病药对举」：病方词%s 药方词%s" % ("有" if has_b else "无", "有" if has_y else "无")))

    # G5 附表禁令（主断正文禁表格/评级/清单；前置命盘表与附录表不计）
    for ch in BAN_TABLE_CHAR:
        if ch in main:
            res.append(("WARN", "G5", "主断正文含表格/评级符「%s」——表格只能进附录" % ch))
    if re.search(r"^\s*[-*]\s", main, re.M) and len(main.split("\n")) > 3:
        res.append(("WARN", "G5", "正文疑似清单体（-/* 行首）——任氏从不列清单"))

    # G6 现代套语
    for w in BAN_MODERN:
        if w in main:
            res.append(("FAIL", "G6", "正文含现代套语「%s」" % w))
    # G6b 现代白话主语
    if re.search(r"该命主|你的命|这个八字就是|您的", main):
        res.append(("FAIL", "G6", "正文含现代白话主语（该命主/您的）——任氏用「此造」"))

    # G4 混层检测：任氏正文段（【按】/【分歧】之前）不得掺 L4/徐乐吾/【按】文字
    m_press = re.search(r"^\s*【按】|^\s*【分歧】|^\s*##+\s*(按|徐补)", main, re.M)
    ren_body = main[: m_press.start()] if m_press else main
    if "#L4" in ren_body or "徐乐吾" in ren_body or "【按】" in ren_body:
        res.append(("FAIL", "G4", "疑似混层：任氏正文段掺入 L4/徐乐吾/【按】——任氏段须独立，徐补以「【按】」另起一段"))

    # G3 强度词↔置信度
    strong_used = [w for w in STRONG_A if re.search(r"%s(?![感])" % w, main)]
    weak_used = [w for w in WEAK_C if w in main]
    if strong_used and refs is not None:
        confs = [r.get("CONFIDENCE", "B") for r in refs]
        if "A" not in confs:
            res.append(("FAIL", "G3", "正文用强断言(%s)但所挂引用规则无 A 级（%s）——语气越级，须降为'多/宜/似'" % (
                "/".join(strong_used), sorted(set(confs)))))
    if strong_used and refs is None:
        res.append(("INFO", "G3", "正文含强断言(%s)；未附规则引用表，无法核置信度（建议传 --refs）" % "/".join(strong_used)))

    # PAN 提示
    for p in PANWEN_HINT:
        if p in main:
            res.append(("WARN", "G7", "正文含「%s」——学术审计味，任氏不这么写" % p))

    # G8 收尾推送完整性（元规则 05 §八：末尾推送不可省，纯净版亦保留）
    if push_check:
        miss = []
        if PUSH_APPRECIATION not in body:
            miss.append("赞赏码二维码图")
        if PUSH_WECHAT not in body:
            miss.append("盘叔微信二维码图")
        if PUSH_CANGPAN_LINK not in body or PUSH_CANGPAN_WORD not in body:
            miss.append("苍盘命书体验邀请（含直通链接）")
        if miss:
            res.append(("FAIL", "G8", "收尾推送不完整，缺：%s——每次交付末尾须附一次完整「关于盘叔」推送（赞赏码＋盘叔微信＋公众号＋苍盘命书）" % "、".join(miss)))
        else:
            res.append(("INFO", "G8", "收尾推送完整（赞赏码＋盘叔微信＋苍盘命书直通）"))

    # G9 工程痕迹（内部指令块泄漏进交付稿）
    for w in LEAK_MARKERS:
        if w in body:
            res.append(("FAIL", "G9", "交付稿泄漏内部指令块「%s」——使用规则只留技能内（主 SKILL.md / 元规则 05 §八·甲）" % w))
            break

    # G10 工程信息（交付稿默认不得出现任何编号/数据条数/机器口吻；溯源版加 --trace 跳过）
    if not trace:
        hits = [w for w in ENGINEERING_TERMS if w in body]
        m_l = ENGINEERING_RE.findall(body)
        if m_l:
            hits.append("层标 " + "/".join(sorted(set(m_l))))
        if hits:
            res.append(("FAIL", "G10", "交付稿含工程信息：%s——交付稿只应有「批命正文 ＋ 文末推送」；如确需附出处，改用 --trace 出溯源版" % "、".join(hits[:8])))
        else:
            res.append(("INFO", "G10", "交付稿无工程信息（无编号／无数据条数／无机器口吻）"))

    return res

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", required=True)
    ap.add_argument("--refs")
    ap.add_argument("--no-push-check", action="store_true", help="内部草稿：跳过 G8 收尾推送检查")
    ap.add_argument("--trace", action="store_true", help="溯源版：跳过 G10 工程信息检查（交付稿默认必查）")
    a = ap.parse_args()
    text = open(a.draft, encoding="utf-8").read()
    refs = None
    if a.refs:
        refs = json.load(open(a.refs, encoding="utf-8"))
    res = qa(text, refs, push_check=not a.no_push_check, trace=a.trace)
    print("=== 语体 QA 报告 ===")
    print("  判定口径:", "溯源版(--trace，不查 G10)" if a.trace else "交付稿（纯净，G1–G10 全查）")
    nfail = 0
    for lvl, code, msg in res:
        if lvl == "FAIL": nfail += 1
        print("  [%s] %s  %s" % (lvl, code, msg))
    print("结论:", "通过" if nfail == 0 else "失败(%d 项违规)" % nfail, "| 提醒 %d 条" % sum(1 for l,_,_ in res if l in ("WARN","INFO")))
    sys.exit(1 if nfail else 0)

if __name__ == "__main__":
    main()
