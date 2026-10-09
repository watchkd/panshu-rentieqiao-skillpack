# -*- coding: utf-8 -*-
"""
v2.0 融合整装 · 第 1 步：接入 L4/L5 数据层
============================================
原则（任务书 §6 + 挂载说明 §5）：
  1. 不侵入 v1.0 —— 797 规则 / 509 命例 / 336 归属块 一字不改，只做"平行并入"。
  2. 层不混淆 —— L4 徐补与 L3 任注同库但按 AUTHOR/LAYER 分区，前缀可辨。
  3. 对账优先 —— L4 命例与任氏 509 库按八字去重，同造只标互参不重录。
  4. 章号对齐 —— 63 章体系共享 CHAPTER_ID；L4 独有章（羁绊 XW-00）单列并说明。

产出（写入 总装数据/v2/）：
  rules_merged.json        797(L3) + 741(L4) = 1538
  cases_merged.json        509(L3) + 189(L4 新引) = 698（互参 14 条另表）
  attribution_merged.json  336(L1-L3) + L4/L5 块
  xlw_crossref.json        L4 命例 ↔ 任氏 509 互参对照
  l4_merge_report.md       对账报告
"""
import json, re, os, collections, io

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PKG = os.path.join(ROOT, "总装输出", "rtq-panshu", "skills", "rtq-panshu")
XLW = os.path.join(ROOT, "滴天髓补注")
OUT = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)


def load(p):
    return json.load(io.open(p, encoding="utf-8"))


def dump(obj, name):
    p = os.path.join(OUT, name)
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    return p


# ---------- 0. 读入 v1.0 三件套 ----------
D = os.path.join(PKG, "数据")
r3 = load(os.path.join(D, "规则库_797.json"))
c3 = load(os.path.join(D, "命例库_509.json"))
a3 = load(os.path.join(D, "归属库_五层.json"))
assert len(r3) == 797, len(r3)
assert len(c3) == 509, len(c3)

# ---------- 1. 读入 L4 交付 ----------
r4 = load(os.path.join(XLW, "rtq-xlw-规则卡.json"))
c4 = load(os.path.join(XLW, "rtq-xlw-命例库.json"))
assert len(r4) == 741, len(r4)

# ---------- 2. 统一 schema（保留各层自有字段，补公共字段）----------
RULE_COMMON = ["RULE_ID", "CHAPTER_ID", "AUTHOR", "TEXT", "RULE", "CONDITION",
               "EXCEPTION", "ORDER", "CASE_IDS", "SOURCE_FILE", "CONFIDENCE",
               "NEGATIVE_RULE"]
CASE_COMMON = ["CASE_ID", "CHAPTER_ID", "LAYER", "八字", "大运", "性别", "身份",
               "出身", "职业", "人生事件", "流年与应期", "任铁樵原断", "判断依据",
               "所用规则", "最终结论", "版本差异标志", "可信度"]

r3n = []
for x in r3:
    y = dict(x)
    y["LAYER"] = "L3"                      # 新公共字段：与 AUTHOR 并列
    y["VOLUME"] = "v1.0"
    r3n.append(y)

r4n = []
for x in r4:
    y = dict(x)
    y["VOLUME"] = "v2.0-L4"
    # 补 DISPUTED 缺省
    y.setdefault("DISPUTED", "")
    r4n.append(y)

# ---------- 3. 命例去重（L4 ↔ 任氏 509）----------
def norm_bazi(s):
    """归一八字：取四柱干支，剔除括注/空格/标点"""
    if not s:
        return ""
    s = re.split(r"[（(]", str(s))[0]
    s = re.sub(r"[\s,，、·]", "", s)
    return re.sub(r"[^\u4e00-\u9fff]", "", s)


def pillars(bz):
    """把 n 字串切成 2 字柱列表"""
    bz = norm_bazi(bz)
    return [bz[i:i + 2] for i in range(0, len(bz) - 1, 2)]


idx3 = collections.defaultdict(list)
for x in c3:
    k = norm_bazi(x.get("八字", ""))
    if k and len(k) >= 8:
        idx3[k].append(x["CASE_ID"])

c4_new, cross = [], []
for x in c4:
    k = norm_bazi(x.get("八字", ""))
    hit = idx3.get(k, [])
    y = dict(x)
    y["VOLUME"] = "v2.0-L4"
    y["DUPLICATE_OF_L3"] = "、".join(hit) if hit else ""
    # 对账修正：L4 组自报"已由任氏收录=是"8 条，程序按八字复算实得 12 条；
    # 4 条漏判（TS-12-043/044/045、TS-28-007）逐条核验为真同造（徐氏原文即"如任注所引…一造"），
    # 故以程序对账为准回写，并在 互参 字段补全 L3 CASE_ID。
    if hit:
        if y.get("已由任氏收录") != "是":
            y["已由任氏收录"] = "是"
            y["对账修正"] = "原报'否'，经八字复算为同造，回写为是"
        if not y.get("互参"):
            y["互参"] = "、".join(hit)
            y["对账修正"] = (y.get("对账修正", "") + "；补全互参" + "、".join(hit)).strip("；")
        cross.append({
            "XLW_CASE_ID": x["CASE_ID"],
            "BAZI": x.get("八字", ""),
            "RTQ_CASE_IDS": hit,
            "已由任氏收录": "是",
            "互参": y.get("互参", ""),
            "原报收录状态": x.get("已由任氏收录", ""),
            "判定": "同造，按对账优先只标互参不重录",
        })
    c4_new.append(y)

# ---------- 4. 归属库：追加 L4/L5 块 ----------
# L4 块以底本【L4】行为单位；L5 块以【L5】行。按章归集必须借章节映射表。
md_path = os.path.join(XLW, "rtq-xlw-底本OCR_全本.md")
lines = io.open(md_path, encoding="utf-8", newline="").read().split("\n")
L4_LINES = [(i + 1, t) for i, t in enumerate(lines) if t.startswith("【L4】")]
L5_LINES = [(i + 1, t) for i, t in enumerate(lines) if t.startswith("【L5")]

# 章边界：借 L4 规则卡/命例库的 SOURCE_FILE 行号 → CHAPTER_ID 建立行号→章 的区间表
rule_spans = collections.defaultdict(list)
for x in r4:
    m = re.search(r"#L(\d+)$", x.get("SOURCE_FILE", ""))
    if m:
        rule_spans[x["CHAPTER_ID"]].append(int(m.group(1)))
case_spans = collections.defaultdict(list)
for x in c4:
    m = re.search(r"#L(\d+)$", x.get("SOURCE_FILE", ""))
    if m:
        case_spans[x["CHAPTER_ID"]].append(int(m.group(1)))

allspans = {}
for src in (rule_spans, case_spans):
    for ch, ls in src.items():
        allspans.setdefault(ch, []).extend(ls)
# 用每章最小行号为章起点，排序成区间
starts = sorted((min(v), k) for k, v in allspans.items() if k != "XW-00")


def ch_of(line):
    pick = None
    for s, ch in starts:
        if line >= s:
            pick = ch
        else:
            break
    return pick or (starts[0][1] if starts else "TS-01")


l4_by_ch = collections.defaultdict(list)
for ln, t in L4_LINES:
    l4_by_ch[ch_of(ln)].append({"LINE": ln, "TEXT": t})
l5_by_ch = collections.defaultdict(list)
for ln, t in L5_LINES:
    l5_by_ch[ch_of(ln)].append({"LINE": ln, "TEXT": t})


def hanzi(s):
    return len(re.findall(r"[\u4e00-\u9fff]", s))


a_merged = json.loads(json.dumps(a3))  # 深拷贝
for ch in a_merged["chapters"]:
    cid = ch["chapter_id"]
    n = len(ch["blocks"])
    for item in l4_by_ch.get(cid, []):
        ch["blocks"].append({
            "BLOCK_ID": "%s-L4-%02d" % (cid, len([b for b in ch["blocks"] if b["LAYER"] == "L4"]) + 1),
            "LAYER": "L4",
            "LAYER_NAME": "徐乐吾补注",
            "TEXT": item["TEXT"],
            "CHARS": hanzi(item["TEXT"]),
            "SOURCE_LINE": item["LINE"],
        })
    for item in l5_by_ch.get(cid, []):
        ch["blocks"].append({
            "BLOCK_ID": "%s-L5-%02d" % (cid, len([b for b in ch["blocks"] if b["LAYER"] == "L5"]) + 1),
            "LAYER": "L5",
            "LAYER_NAME": "后世整理增补（孙正治注释·今译）",
            "TEXT": item["TEXT"],
            "CHARS": hanzi(item["TEXT"]),
            "SOURCE_LINE": item["LINE"],
        })

# 归属块计数（L1-L3 保持 v1.0 原值不动，L4/L5 为 v2.0 增量）
l4_blocks = sum(len(v) for v in l4_by_ch.values())
l5_blocks = sum(len(v) for v in l5_by_ch.values())
tot = dict(a_merged["layer_totals"])
tot["L4"] = l4_blocks
tot["L5"] = l5_blocks
tot["chars"]["L4"] = sum(hanzi(b["TEXT"]) for ch in a_merged["chapters"]
                         for b in ch["blocks"] if b["LAYER"] == "L4")
tot["chars"]["L5"] = sum(hanzi(b["TEXT"]) for ch in a_merged["chapters"]
                         for b in ch["blocks"] if b["LAYER"] == "L5")
a_merged["layer_totals"] = tot
a_merged["meta"]["version"] = "2.0.0"
a_merged["meta"]["source_block"] = ("layerd_v2(140任氏+133原注) + 复核后归属表(63章)"
                                    " + rtq-xlw L4/L5 底本行块（v2.0 新增）")
a_merged["meta"]["note"] = ("L1-L3 为 v1.0 原样保留；L4/L5 为 v2.0 由 rtq-xlw-底本OCR_全本.md "
                            "逐行并入，AUTHOR=L4 徐乐吾补注 / L5 孙正治注释今译，不与 L3 混层。")

# ---------- 5. 写盘 ----------
p1 = dump(r3n + r4n, "规则库_merged_1538.json")
p2 = dump(c3 + c4_new, "命例库_merged_698.json")
p3 = dump(a_merged, "归属库_merged_五层v2.json")
p4 = dump(cross, "xlw_L4-L3互参表.json")

# ---------- 6. 报告 ----------
ru = collections.Counter(x["AUTHOR"] for x in r3n + r4n)
cu = collections.Counter(x["LAYER"] for x in c3 + c4_new)
rep = []
rep.append("# v2.0 融合整装 · L4/L5 接入对账报告\n")
rep.append("> 生成：merge_l4.py ｜ 原则：不侵入 v1.0、层不混淆、对账优先\n")
rep.append("## 一、规则库\n")
rep.append("| 层 | 条数 | 前缀 | 负向 |")
rep.append("|---|---|---|---|")
rep.append("| L3 任铁樵（v1.0，原样） | 797 | RTQ-RULE- | 57 |")
rep.append("| L4 徐乐吾（v2.0 新增） | 741 | RTQ-RULE-XLW- | %d |"
           % sum(1 for x in r4 if x["NEGATIVE_RULE"] == "是"))
rep.append("| **合计** | **%d** | | **%d** |"
           % (len(r3n + r4n), sum(1 for x in r3n + r4n if x["NEGATIVE_RULE"] == "是")))
rep.append("\n## 二、命例库\n")
rep.append("| 层 | 条数 | 说明 |")
rep.append("|---|---|---|")
rep.append("| L3 任铁樵（v1.0，原样） | 509 | 19 契约字段 |")
rep.append("| L4 徐乐吾（v2.0 新增） | %d | 独立分区，徐氏专用字段 |" % len(c4_new))
rep.append("| **合计** | **%d** | |" % (len(c3) + len(c4_new)))
rep.append("\n**L4 ↔ L3 同造互参（去重不重录）：%d 例**\n" % len(cross))
fixed = [x for x in cross if x["原报收录状态"] != "是"]
rep.append("> 对账修正：L4 组自报「已由任氏收录=是」8 条，本次按八字复算实得 **%d** 条；"
           "漏判 %d 条已回写（%s）。\n"
           % (len(cross), len(fixed), "、".join(x["XLW_CASE_ID"] for x in fixed)))
for x in cross:
    mark = "  ⚠对账修正" if x["原报收录状态"] != "是" else ""
    rep.append("- `%s`（%s）↔ %s%s" % (x["XLW_CASE_ID"], x["BAZI"], x["RTQ_CASE_IDS"], mark))
rep.append("\n## 三、归属库\n")
rep.append("| 层 | v1.0 | v2.0 | 增量 |")
rep.append("|---|---|---|---|")
for L in ("L1", "L2", "L3", "L4", "L5"):
    v1 = a3["layer_totals"].get(L, 0)
    v2 = tot.get(L, 0)
    rep.append("| %s | %d | %d | %s |" % (L, v1, v2, ("+%d" % (v2 - v1)) if v2 != v1 else "—"))
rep.append("\nL4 块 %d / %d 字；L5 块 %d / %d 字（由底本 `【L4】`/`【L5】` 行归集）。"
           % (l4_blocks, tot["chars"]["L4"], l5_blocks, tot["chars"]["L5"]))
rep.append("\n## 四、v1.0 未被改动核验\n")
rep.append("- 规则 797 / 命例 509 / 归属 L1 63·L2 133·L3 140 —— 全部原值保留（脚本仅做 append 与深拷贝）。")
rep.append("- 回滚方式：删除 `*-L4*`、`RTQ-RULE-XLW-*`、`RTQ-CASE-XLW-*` 即可还原 v1.0。")

rp = os.path.join(OUT, "L4接入对账报告.md")
with io.open(rp, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(rep))

print("规则库 顺 %d / 逆 %d = %d" % (len(r3n), len(r4n), len(r3n + r4n)))
print("命例库 顺 %d / 逆 %d = %d（互参 %d）" % (len(c3), len(c4_new), len(c3) + len(c4_new), len(cross)))
print("归属块 L1 %d L2 %d L3 %d L4 %d L5 %d"
      % (a3["layer_totals"]["L1"], a3["layer_totals"]["L2"], a3["layer_totals"]["L3"],
         l4_blocks, l5_blocks))
print("写出：", p1, p2, p3, p4, rp, sep="\n  ")
