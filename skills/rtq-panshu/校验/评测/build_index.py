# -*- coding: utf-8 -*-
"""命例多维索引生成器 —— 从 L3 命例「判断依据/任铁樵原断/最终结论」抽取可检索维度标签。

目的：承接规则回填，做「命例互验」的检索面——从全文搜 → 按「格局×日主×病×药×寒暖」命中。

防幻觉铁律：只标高频、可靠、成句的信号；一概不做句意推断。抽不到就标 null，不硬造。

五维抽取规则（全部基于稳定词面／字段，防幻觉）：
  T1 日主   ：取命例「八字」字段日柱（权威、近全覆盖）；不足则文本「日主X/X生于」降级
  T2 寒暖   ：出现「寒/冷/湿/燥/暖/炎/热」+ 调候字面 → 记 {season: 寒暖}
  T3 病     ：句子含「所忌者/所嫌者 (X)/X克Y为病/X之为病/病在X」→ 抓干/支/五行方；健康字面病(病患/痨病/痊愈)一律排除
  T4 药/用  ：句子含「全赖/喜其/最喜/赖X/以X为用/取X为用」→ 抓干/支/五行
  T5 格局   ：词面专名细分——从财/从杀/从官/从儿/从势/五专旺(稼穑曲直炎上从革润下)＋
              羊刃/建禄/食神制杀/伤官配印/杀印相生/印格/财官/正官（命理语境才取，不点"格"立案；
              须成词面 token，不用单字"从"宽化）；日主强弱＝词面(坐禄得禄→得根/身弱无根→弱)+八字日柱坐禄查表
输出：{CASE_ID: {日主:五行, 寒暖, 病:[五行...], 药:[五行...], 格局, 原断首句}}
"""
import json, re, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from wxmap import GAN_WX, ZHI_WX, WX_SET, gan_to_wx, stem_branch_wx

# v2.4.0：路径改为相对脚本解析（本脚本在 校验/评测/，技能根为其上两级），
# 使包被移动 / 安装到别处后仍可重跑（旧版硬编码 Desktop 绝对路径）。
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CP = os.path.join(SKILL_ROOT, "数据", "命例库_712_双层.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "命例多维索引.json")

G = set(GAN_WX)
Z = set(ZHI_WX)

def first_sentence(seg):
    # 去掉编号，取句首（至首个句号/冒号前）
    seg = re.sub(r"^\s*\d+[\.、）]\s*", "", seg)
    m = re.split(r"[，。；、]", seg)
    return m[0] if m else seg

def extract_tags(c):
    py = c.get("判断依据") or ""
    yuan = c.get("任铁樵原断") or ""
    zjl = (c.get("最终结论") or "")
    tail = py + " " + yuan
    tags = {}

    # T1 日主 —— 优先取「八字」字段日柱（权威、近全覆盖），文本句式降级补缺
    bazi = c.get("八字") or ""
    gz_list = re.findall(r"[甲乙丙丁戊己庚辛壬癸][寅卯辰巳午未申酉戌亥]", bazi)
    if len(gz_list) >= 3:
        tags["日主"] = GAN_WX[gz_list[2][0]]
    else:
        dm = re.search(r"日主([甲乙丙丁戊己庚辛壬癸])", py)
        if dm:
            tags["日主"] = GAN_WX[dm.group(1)]
        else:
            m = re.search(r"(此造|此命)?([甲乙丙丁戊己庚辛壬癸])(?:水|火|木|金|土)?生于", tail)
            if m and m.group(2) in G:
                tags["日主"] = GAN_WX[m.group(2)]

    # T2 寒暖 —— 调候四态 {寒,湿,燥,暖}（寒湿复合保留），只认调候组合词 / 单字湿燥暖炎；
    #        "寒"须为调候组合（寒金/金寒/水冷…），排除 贫寒/清寒/寒微/寒儒/寒士/寒门/困寒 等贫贱语义
    comb = [("寒湿","寒湿"),("火燥","燥"),("干热","燥"),("金寒","寒"),("寒金","寒"),("寒木","寒"),
            ("寒水","寒"),("水冷","寒"),("水寒","寒"),("寒局","寒"),("寒凝","寒"),("向阳","暖"),
            ("丙火通明","暖"),("炎上","暖"),("湿土","湿"),("燥土","燥")]
    hn = None
    for k, v in comb:
        if k in tail:
            hn = v; break
    if not hn:
        if re.search(r"湿", tail): hn = "湿"
        elif re.search(r"燥", tail): hn = "燥"
        elif re.search(r"暖|炎|热", tail): hn = "暖"
        elif re.search(r"寒", tail) and not re.search(r"贫寒|清寒|寒微|寒儒|寒士|寒门|困寒|寒素", tail):
            hn = "寒"
    if hn: tags["寒暖"] = hn

    # T3 病 —— 病方是"被忌/反致破"之神（格局/用神层面），只取命理病句式，绝不含健康字面病
    #   （病患/痨病/无灾无病/病愈/疾病/之症 等一律排除）。
    #   病方 = 标记词「X克Y为病／所忌者X…为病／X为病／X之为病／病在X／以X为病}_紧邻的干支。
    GZ = "甲乙丙丁戊己庚辛壬癸寅卯辰巳午未申酉戌亥"
    bing = []
    def _wxval(v):
        # 优先干支→五行（最精确）；否则退回五行字（金木水火土）
        for ch in v:
            if ch in G: return GAN_WX[ch]
            if ch in Z: return ZHI_WX[ch]
        for ch in v:
            if ch in WX_SET: return ch
        return None
    def _from_pats(pats, tail=tail):
        for pat in pats:
            m = re.search(pat, tail)
            if m:
                w = _wxval(m.group(1))
                if w: return w
        return None
    # 阶段1（施事精确）：所忌者/所嫌者 紧跟干支，或"X(刻)刻Y为病"取施事 X —— 命中即权威病方，不再叠加
    w = _from_pats([r"所[忌嫌]者[:：]?([甲乙丙丁戊己庚辛壬癸][甲乙丙丁戊己庚辛壬癸]?)",
                    r"([甲乙丙丁戊己庚辛壬癸])(?:水|火|木|金|土)?克[^为，。；]{0,4}为病"])
    if w:
        bing.append(w)
    else:
        # 阶段2（泛用干支/五行病方）—— (?<!克) 抑掉"刻Y为病"的被克方 Y
        w = _from_pats([r"(?<!克)(?:反以|以|悉以|但以|竟以|唯以|总嫌|只嫌)?([甲乙丙丁戊己庚辛壬癸寅卯辰巳午未申酉戌亥金木水火土])[^，。；]{0,3}为病",
                        r"(?<!克)([甲乙丙丁戊己庚辛壬癸寅卯辰巳午未申酉戌亥])[^，。；]{0,3}之为病",
                        r"(?:其)?病在([^，。；]{0,5})"])
        if w: bing.append(w)
    if bing: tags["病"] = bing

    # T4 药/用 —— 取"全赖/喜其/最喜/赖X/以X为用"里紧邻拿药的"X"
    yao = []
    for pat in [r"全赖[:：]?([甲乙丙丁戊己庚辛壬癸寅卯辰巳午未申酉戌亥金木水火土])[^，。；]{0,5}",
                r"喜其[:：]?([甲乙丙丁戊己庚辛壬癸寅卯辰巳午未申酉戌亥金木水火土])",
                r"最喜[:：]?([甲乙丙丁戊己庚辛壬癸寅卯辰巳午未申酉戌亥金木水火土])[^，。；]{0,6}",
                r"赖[:：]?([甲乙丙丁戊己庚辛壬癸寅卯辰巳午未申酉戌亥金木水火土])",
                r"以([甲乙丙丁戊己庚辛壬癸寅卯辰巳午未申酉戌亥金木水火土])为用",
                r"([甲乙丙丁戊己庚辛壬癸寅卯辰巳午未申酉戌亥金木水火土])为用神",
                r"喜[:：]?([甲乙丙丁戊己庚辛壬癸寅卯辰巳午未申酉戌亥金木水火土])",
                r"取([甲乙丙丁戊己庚辛壬癸寅卯辰巳午未申酉戌亥金木水火土])为用"]:
        m = re.search(pat, tail)
        if m:
            w = _wxval(m.group(1))
            if w and w not in yao:
                yao.append(w)
    if yao: tags["药"] = yao

    # T5 格局（细分·词面保守）：专名(from/专旺) > 特殊正格 > 一般正格；避免单字"从"宽化
    def _ge(keys):
        for kw, val in keys:
            if re.search(kw, tail):
                return val
        return None
    from_type = _ge([(r"从财", "从财格"), (r"从杀", "从杀格"), (r"从官", "从官格"),
                     (r"从儿", "从儿格"), (r"从势", "从势格"), (r"真从|假从", "从格"),
                     (r"稼穑", "稼穑格"), (r"曲直", "曲直格"), (r"炎上", "炎上格"),
                     (r"从革", "从革格"), (r"润下", "润下格"), (r"专旺|一行得气", "专旺格")])
    zheng_type = _ge([(r"食神制杀", "食神制杀格"), (r"伤官配印|伤官佩印", "伤官配印格"),
                      (r"杀印相生", "杀印相生格"), (r"印绶格|印格", "印格"),
                      (r"正财格|偏财格|财官双美|财官", "财官格"), (r"正官格|官印相生", "正官格"),
                      (r"建禄", "建禄格"), (r"羊刃|阳刃", "羊刃格")])
    if from_type:
        tags["格局"] = from_type
    elif zheng_type:
        tags["格局"] = zheng_type

    # 日主强弱 —— 词面（坐禄/得禄→得根；身弱/无根/虚脱/衰→弱）＋ 八字日柱坐禄查表辅助得根
    if "坐禄" in py or "得禄" in py:
        tags["日主强弱"] = "得根"
    elif (tags.get("日主") and len(gz_list) >= 3
          and gz_list[2][1] == {"甲":"寅","乙":"卯","丙":"巳","戊":"巳","丁":"午",
                                "己":"午","庚":"申","辛":"酉","壬":"亥","癸":"子"}
          .get(gz_list[2][0], "")):
        tags["日主强弱"] = "得根"
    elif re.search(r"(身弱|无根|虚脱|偏枯|日主.?[过偏弱废衰]|衰)", tail):
        tags["日主强弱"] = "弱"
    return tags

def main():
    d = json.load(open(CP, encoding="utf-8"))
    cases = d if isinstance(d, list) else next(v for v in d.values() if isinstance(v, list))
    l3 = [c for c in cases if c.get("LAYER")=="L3"]
    idx = {}
    stats = {"日主":0,"寒暖":0,"病":0,"药":0,"格局":0,"日主强弱":0}
    for c in l3:
        t = extract_tags(c)
        if t:
            idx[c["CASE_ID"]] = t
            for k in t: stats[k] = stats.get(k,0)+1
    # v2.4.0：meta 里记**相对路径**，不记绝对路径——否则索引会带上机器专属路径，
    # 一换机器就「漂移」（每次重建都 diff 出假差异）。
    _rel = os.path.relpath(os.path.abspath(__file__), SKILL_ROOT).replace("\\", "/")
    json.dump({"meta":{"来源":"判断依据+任铁樵原断+最终结论 词面抽取","生成":_rel,"n":len(idx),"维度统计":stats},
               "entries": idx},
              open(OUT,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print("多维索引已生成 ->", OUT, "命中命例", len(idx),"/",len(l3))
    print("维度覆盖:", stats)
    return idx, stats

if __name__=="__main__":
    idx, s = main()
    import collections
    # 抽样展示
    print("\n抽样 5 例:")
    for k in list(idx.keys())[:5]:
        print("  ", k.replace("RTQ-CASE-",""), idx[k])
    # 验证：能否按「病×药」组成命例互验组（同病同药，命中≥2 即可互验）
    grp = collections.defaultdict(list)
    for cid, t in idx.items():
        if t.get("病") and t.get("药"):
            grp[(tuple(t["病"]), tuple(t["药"]))].append(cid)
    inter = {k: v for k, v in grp.items() if len(v) >= 2}
    print(f"\n病×药 组合数：{len(grp)}，其中可互验组（≥2 例）{len(inter)} 组:")
    for (b, y), v in sorted(inter.items(), key=lambda x: -len(x[1]))[:8]:
        print("  病=%s 药=%s → %d 例: %s" % (",".join(b), ",".join(y), len(v),
              ", ".join(c.replace("RTQ-CASE-","") for c in v[:3])))
    # 再放宽：同「药」且同「日主」的互验组（不要求病，覆盖更实用）
    grp2 = collections.defaultdict(list)
    for cid, t in idx.items():
        if t.get("药") and t.get("日主"):
            grp2[(tuple(t["药"]), t["日主"])].append(cid)
    inter2 = {k: v for k, v in grp2.items() if len(v) >= 2}
    print(f"\n药×日主 互验组（≥2 例）{len(inter2)} 组，top5:")
    for (y, d), v in sorted(inter2.items(), key=lambda x: -len(x[1]))[:5]:
        print("  日主=%s 药=%s → %d 例" % (d, ",".join(y), len(v)))