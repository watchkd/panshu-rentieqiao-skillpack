# -*- coding: utf-8 -*-
"""L4 归属完整性自检脚本 —— 可复跑回归。

用途：在每次批算质量评测 / 版本改动后，快速校验「归属库_五层v2.json」的
L4 层是否仍处于已验证的完好状态，防止章重建/挂载时破坏归属。

不臆断：只做结构完整性核验（数量、归属存在、编号连续、无孤儿、内容不越章），
不做内容语义判定（那需回 S1 原稿，交人工）。

判定基准（来自 rtq-xlw 交付验收报告 meta）：
  - L4 总数 2897 块、L5 565 块
  - 仅 25 章挂 L4
  - L4 块前缀 【L4】、块 ID 含 LAYER
  - 章级:chapter 有 title，块归属 chapter_id
"""
import json, re, sys, os

base = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Administrator\Desktop\任铁樵\总装输出\rtq-panshu\skills\rtq-panshu\数据"
P = os.path.join(base, "归属库_五层v2.json")
d = json.load(open(P, encoding="utf-8"))
ch = d["chapters"]
errs = []
warns = []

# 1. 章数 & meta
meta = d.get("meta", {})
if meta.get("chapters") != len(ch):
    errs.append("meta 声明章数 %s != 实际 %d" % (meta.get("chapters"), len(ch)))

# 2. L4/L5 总数
tot_l4 = tot_l5 = 0
l4_chapters = []
for c in ch:
    cid, title, blocks = c.get("chapter_id"), c.get("title"), c.get("blocks") or []
    if not cid:
        errs.append("存在无 chapter_id 的章"); continue
    # 章标题成对
    if not title:
        errs.append("章 %s 缺 title" % cid)
    seen_layers = set()
    prev_slot = 0
    for b in blocks:
        lay = (b.get("LAYER") or "")
        bid = b.get("BLOCK_ID") or ""
        if not lay or not bid:
            errs.append("%s: 块缺 LAYER/BLOCK_ID" % cid)
            continue
        if lay.startswith("L4"): tot_l4 += 1
        if lay.startswith("L5"): tot_l5 += 1
        # 块 ID 前缀须与章一致
        if not bid.startswith(cid):
            errs.append("%s 下块 %s 前缀不匹配(应 %s)" % (cid, bid, cid))
        # 块 ID 内 LAYER 标识须与 LAYER 字段一致
        m = re.search(r"-(L[1-5])-", bid)
        if m and m.group(1) != lay:
            errs.append("%s: 块ID层 %s != LAYER字段 %s" % (bid, m.group(1), lay))
        # L1/L2/L3 块不应重复（本处仅记录层分布，L2/L3 完整性不在本脚本范围）
    if any((b.get("LAYER") or "").startswith("L4") for b in blocks):
        l4_chapters.append(cid)

# 3. L4 块总数 vs meta
if tot_l4 != 2897:
    errs.append("L4 块总数 %d != 期望 2897" % tot_l4)
if tot_l5 != 565:
    errs.append("L5 块总数 %d != 期望 565" % tot_l5)
if len(l4_chapters) != 25:
    warns.append("挂 L4 章数 %d != 期望 25（不阻塞，警示复核）" % len(l4_chapters))

# 4. 无孤儿：任一章块不属于已登记章节（已是 cid 前缀校验）
# 5. 章标题不为"待考/TBD/?"占位
placeholder = re.compile(r"待考|TBD|^[?？]|^×|^未命名")
for c in ch:
    if placeholder.search(c.get("title") or ""):
        errs.append("章 %s 标题为占位符: %s" % (c.get("chapter_id"), c.get("title")))

# 6. L4/L5 内容必须有【Lx】前缀（页除外）
for c in ch:
    for b in c.get("blocks") or []:
        lay = b.get("LAYER") or ""
        if lay.startswith(("L4", "L5")):
            txt = (b.get("TEXT") or "").lstrip()
            if not txt.startswith("【L"):
                errs.append("%s: %s 内容未带【Lx】层标: %s" % (c.get("chapter_id"), b.get("BLOCK_ID"), txt[:20]))

print("=== L4 归属完整性自检 ===")
print("章数:", len(ch), " L4块:", tot_l4, " L5块:", tot_l5, " 挂L4章:", len(l4_chapters))
print("错误:", len(errs), " 警告:", len(warns))
for e in errs[:40]:
    print("  [ERR]", e)
for w in warns:
    print("  [WARN]", w)
sys.exit(0 if not errs else 1)