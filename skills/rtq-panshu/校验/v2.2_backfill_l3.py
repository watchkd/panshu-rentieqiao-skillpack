# -*- coding: utf-8 -*-
"""
L3 出处回填脚本（v2.2）
--------------------------------
目标：
  1. 用 归属库_五层v2.json 的 L3 逐字原文块（归属库 BLOCK_ID: <章>-L3-NN）匹配
     规则库_1538_双层.json 中 AUTHOR==L3 的规则 TEXT，
     回填 SOURCE_FILE = "归属库_五层v2.json#<章>#<BLOCK_ID>"（与 L4 的 file#章#LINE 同构）
     并在 _l3_match 字段记录匹配方式与相似度。
  2. 用规则 TEXT / RULE 关键词命中命例库的 任铁樵原断 / 判断依据，
     回填 CASE_IDS（仅当原 CASE_IDS 为空或"（无）"时）。

方法：滑动 n-gram 字符相似度（difflib）——不引入外部依赖。
输出：原地更新 规则库_1538_双层.json，并打印统计。
"""
import io, json, re, difflib, collections, os

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "..", "数据")
RULES_F = os.path.join(DATA, "规则库_1538_双层.json")
CASES_F = os.path.join(DATA, "命例库_712_双层.json")
ATTR_F  = os.path.join(DATA, "归属库_五层v2.json")

def load(p):
    with io.open(p, encoding="utf-8") as f:
        return json.load(f)

def save(p, obj):
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)

# ---------- 归一化 ----------
_NORM = re.compile(r"[\s，。；：、！？「」『』（）()《》〈〉\"'’‘“”·．,.;:!?—\-…\n\r]")
def norm(s):
    return _NORM.sub("", s or "")

# ---------- 载入 ----------
rules = load(RULES_F)
cases = load(CASES_F)
attr  = load(ATTR_F)

# 归属库 L3 块：{章: [(BLOCK_ID, TEXT_norm, TEXT)]}
l3_blocks = collections.defaultdict(list)
for ch in attr["chapters"]:
    cid = ch["chapter_id"]
    for b in ch["blocks"]:
        if b.get("LAYER") == "L3":
            l3_blocks[cid].append((b["BLOCK_ID"], norm(b["TEXT"]), b["TEXT"]))

print("归属库 L3 块总数 =", sum(len(v) for v in l3_blocks.values()))

# ---------- 1) 回填 SOURCE_FILE ----------
STAT = collections.Counter()
def best_block(rule_text_n, cid):
    """在 cid 章的 L3 块中找最佳匹配。"""
    pool = l3_blocks.get(cid) or []
    if not pool:
        # 章内无 L3 块（合并区）→ 退化为全库搜索
        pool = [it for v in l3_blocks.values() for it in v]
        if not pool:
            return None, 0.0
        fallback = True
    else:
        fallback = False
    rt = rule_text_n
    if len(rt) < 8:
        return None, 0.0
    # 用 rule 的连续 12 字窗口去池中找子串命中（快），命中多者取匹配
    best_id, best_t, best_ratio = None, None, 0.0
    anchor = rt[:24]                       # 取前 24 字做锚
    for bid, tn, torig in pool:
        if anchor and anchor in tn:
            r = 1.0
        else:
            # 双向 containment 快速判断
            if len(rt) <= len(tn):
                r = difflib.SequenceMatcher(None, rt, tn).ratio()
            else:
                r = difflib.SequenceMatcher(None, rt[:len(tn)], tn).ratio()
        if r > best_ratio:
            best_ratio, best_id, best_t = r, bid, torig
        if best_ratio == 1.0:
            break
    return best_id, best_ratio

backfilled = 0
for r in rules:
    if r.get("AUTHOR") != "L3":
        continue
    old = (r.get("SOURCE_FILE") or "").strip()
    if old:
        STAT["已有"] += 1
        continue
    cid = r.get("CHAPTER_ID")
    bid, ratio = best_block(norm(r.get("TEXT")), cid)
    if bid and ratio >= 0.55:
        r["SOURCE_FILE"] = u"归属库_五层v2.json#%s#%s" % (cid, bid)
        r["_l3_match"] = u"sim=%.3f" % ratio
        backfilled += 1
        STAT["回填"] += 1
    else:
        STAT["未匹配"] += 1

print("SOURCE_FILE 回填：", dict(STAT), "→ 新增", backfilled)

# ---------- 2) 回填 CASE_IDS ----------
# 建 命例索引：L3 命例，取「任铁樵原断」「判断依据」归一化
case_pool = []
for c in cases:
    if c.get("LAYER") != "L3":
        continue
    hay = norm((c.get("任铁樵原断") or "") + (c.get("判断依据") or ""))
    if hay:
        case_pool.append((c["CASE_ID"], hay))

def find_cases(rule, limit=3):
    rt = norm(rule.get("TEXT"))
    if len(rt) < 12:
        return []
    outs = []
    # 取 rule 中 15 字窗口，命中命例文本者算相关
    windows = [rt[i:i+15] for i in range(0, min(len(rt), 90), 10)]
    for cid, hay in case_pool:
        hit = sum(1 for w in windows if w and w in hay)
        if hit:
            outs.append((cid, hit))
    outs.sort(key=lambda x: -x[1])
    return [c for c, _ in outs[:limit]]

filled_cases = 0
for r in rules:
    if r.get("AUTHOR") != "L3":
        continue
    old = (r.get("CASE_IDS") or "").strip()
    if old and old not in (u"（无）", u"无", u"-"):
        continue
    hits = find_cases(r)
    if hits:
        r["CASE_IDS"] = "、".join(hits)
        filled_cases += 1

print("CASE_IDS 回填：", filled_cases)

# ---------- 3) CONDITION_STATUS 标记 ----------
cstat = 0
for r in rules:
    if r.get("AUTHOR") != "L3":
        continue
    cond = (r.get("CONDITION") or "").strip()
    if cond in (u"", u"（无）", u"无", u"-"):
        if "_cond_status" not in r:
            r["_cond_status"] = "该规则无此维度"
            cstat += 1
print("CONDITION_STATUS 标记：", cstat)

save(RULES_F, rules)
print("\n已写回:", RULES_F)

# ---------- 复核统计 ----------
l3 = [r for r in rules if r.get("AUTHOR") == "L3"]
empty_sf = sum(1 for r in l3 if not (r.get("SOURCE_FILE") or "").strip())
empty_ci = sum(1 for r in l3 if (r.get("CASE_IDS") or "").strip() in ("", u"（无）", u"无"))
print("\n=== L3 复核 ===")
print("L3 规则总数 =", len(l3))
print("SOURCE_FILE 空 = %d (%.1f%%)" % (empty_sf, 100.0*empty_sf/len(l3)))
print("CASE_IDS   空 = %d (%.1f%%)" % (empty_ci, 100.0*empty_ci/len(l3)))
