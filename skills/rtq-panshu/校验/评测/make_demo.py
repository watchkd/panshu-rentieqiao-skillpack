# -*- coding: utf-8 -*-
"""金标准用神标签分布 + 生成一份"错误预测演示"文件 eval_demo_pred.json
演示：故意把 RTQ-CASE-TS-09-015 任氏"以丙火为用"预测成"金"，评测应抓出不一致。"""
import json, collections, os
HERE = os.path.dirname(os.path.abspath(__file__))
GOLD = os.path.join(HERE, "评测集_金标准.json")
d = json.load(open(GOLD, encoding="utf-8"))

use_map = {"金": 0, "木": 0, "水": 0, "火": 0, "土": 0, "多": 0}
gold_use = {}
for c in d["cases"]:
    us = (c.get("tags") or {}).get("用", [])
    if c["state"] == "gold" and us:
        gold_use[c["CASE_ID"]] = us
        if len(us) == 1:
            use_map[us[0]] += 1
        else:
            use_map["多"] += 1
report = []  # for written body
print("金标准用神命例:", len(gold_use))
print("五行分布:", {k: v for k, v in use_map.items()})

# 生成错误演示预测：大部分正确，故意一条错
outputs = {}
for cid, us in gold_use.items():
    outputs[cid] = {"用": us}  # 全部照着金标准=满分演示
# 故意错一条
cid_err = "RTQ-CASE-TS-09-015"
if cid_err in outputs:
    outputs[cid_err] = {"用": ["金"]}  # 任氏：以丙火为用 → 错给金

demo = {"_meta": {"note": "演示：故意错1条验证评测能力", "generated": "2026-10-09"}, "outputs": outputs}
DEMO = os.path.join(HERE, "eval_demo_pred.json")
json.dump(demo, open(DEMO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("已生成 demo:", DEMO)
print("故意错误条目:", cid_err, "→ 预测[金]")