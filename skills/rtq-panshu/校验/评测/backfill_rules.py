# -*- coding: utf-8 -*-
"""回填「所用规则」脚本 v1.
来源优先级（防幻觉，宁缺勿滥）：
  S1 规则库 CASE_IDS 权威引用（库内既有映射，零幻觉）。
  S2 文本相似度兜底（仅对 S1 未能覆盖的命例），字符级 bigram Jaccard + 命理词置顶。
  仍低分者不动，标"待核"。
"""
import json, collections, re, os, sys

# v2.4.0：路径改为相对脚本解析（本脚本在 校验/评测/，技能根为其上两级）。
_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RP = os.path.join(_SKILL_ROOT, "数据", "规则库_1538_双层.json")
CP = os.path.join(_SKILL_ROOT, "数据", "命例库_712_双层.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "所用规则_回填.json")

def bigrams(s):
    s = re.sub(r"[\s，。；、？！：“”‘’（）《》·\-0-9A-Za-z]", "", s or "")
    return set(s[i:i+2] for i in range(max(0, len(s)-1)))

def jaccard(a, b):
    if not a or not b: return 0.0
    return len(a & b) / len(a | b)

rules = json.load(open(RP, encoding="utf-8"))
rules = rules if isinstance(rules, list) else next(v for v in rules.values() if isinstance(v, list))
cases = json.load(open(CP, encoding="utf-8"))
cases = cases if isinstance(cases, list) else next(v for v in cases.values() if isinstance(v, list))
l3 = [c for c in cases if c.get("LAYER")=="L3"]

l3rules = [r for r in rules if r.get("AUTHOR")=="L3"]
# 预计算每条 L3 规则的指纹
rule_fp = []
for r in l3rules:
    t = (r.get("TEXT") or "") + " " + (r.get("RULE") or "")
    rule_fp.append((r["RULE_ID"], bigrams(t), t))

cid2rules = collections.defaultdict(list)
for r in rules:
    for cid in (r.get("CASE_IDS") or "").split("、"):
        cid = cid.strip()
        if cid: cid2rules[cid].append(r["RULE_ID"])

EMPTY = ("未匹配","未匹配到","（未匹配）","(未匹配)","无","暂无","")
report = {"_meta": {"method":"S1 CASE_IDS权威回填(落地)；S2语义兜底→待核清单(不硬造)",
                    "generated":"2026-10-09",
                    "note":"任氏原断与规则为同义改写,bigram相似度不可靠(实测0.04-0.06)，"
                           "故117例不硬造，转人工语义核对"},
          "backfilled_S1": [], "keep_original": [], "needs_review_S2": []}

s1_n = review_n = 0
review_cases = []
for c in l3:
    orig = (c.get("所用规则") or "").strip()
    if orig not in EMPTY:
        report["keep_original"].append({"CASE_ID":c["CASE_ID"], "所用规则":orig})
        continue
    cid = c["CASE_ID"]
    # S1 权威
    if cid in cid2rules:
        ids = cid2rules[cid]
        report["backfilled_S1"].append({"CASE_ID":cid, "来源":"S1_CASE_IDS", "所用规则":"；".join(dict.fromkeys(ids))})
        # 记录待写回命例库
        report_c = {**{k:c.get(k) for k in ("CASE_ID","任铁樵原断","判断依据")},
                    "补充分配所用规则":"；".join(dict.fromkeys(ids))}
        review_cases.append(c)
        s1_n += 1
        continue
    # S2 「未匹配」的117例：转人工核对清单（附章节候选规则）
    ch = c.get("CHAPTER_ID")
    cand = [r["RULE_ID"]+":"+r["RULE"][:26] for r in l3rules if r.get("CHAPTER_ID")==ch][:8]
    report["needs_review_S2"].append({"CASE_ID":cid, "章":ch,
                                      "原断":(c.get("任铁樵原断") or "")[:120],
                                      "候选规则":cand})
    review_n += 1

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(report, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("S1 CASE_IDS 权威回填(将落地命例库):", s1_n)
print("保留原(已匹配):", len(report["keep_original"]))
print("S2 待人工语义核对(不硬造):", review_n)

# 落地：把 S1 写回命例库「所用规则」
CP_ABS = CP
data = json.load(open(CP_ABS, encoding="utf-8"))
clist = data if isinstance(data, list) else next(v for v in data.values() if isinstance(v, list))
s1_ids = {b["CASE_ID"]: b["所用规则"] for b in report["backfilled_S1"]}
written = 0
for c in clist:
    if isinstance(c, dict) and c.get("CASE_ID") in s1_ids:
        old = (c.get("所用规则") or "").strip()
        if old in EMPTY:
            c["所用规则"] = s1_ids[c["CASE_ID"]]
            c["_backfilled"] = {"来源":"S1_CASE_IDS权威","时间":"2026-10-09"}
            written += 1
# 写回（若顶层是dict包list需整体回写）
with open(CP_ABS, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)
print("已落地写回命例库:", written, "例")
print("\n回填报告 ->", OUT)