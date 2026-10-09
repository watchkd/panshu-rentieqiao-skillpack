# -*- coding: utf-8 -*-
"""
v2.0 复核修正 · 修正项 1 + 2
=============================
修正项 1：L4 命例补齐契约 §3.2 的 10 个缺失字段，并统一 `可信度` 字段名。
修正项 2：为 L4 命例/规则补 CHAPTER_GROUP（合并区）标记，使"第二编下/开篇"两区
          的粗粒度章归属显式可见（降级项 1 的最低成本处置）。

原则：只增字段、不改既有值；L3 主干与 L4 既有字段一字不动。
"""
import json, io, os, collections

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
D = os.path.join(ROOT, "总装输出", "rtq-panshu", "skills", "rtq-panshu", "数据")
OUT = os.path.dirname(os.path.abspath(__file__))


def load(p):
    return json.load(io.open(os.path.join(D, p), encoding="utf-8"))


def dump(obj, p):
    with io.open(os.path.join(D, p), "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


C = load("命例库_712_双层.json")
R = load("规则库_1538_双层.json")

# —— 合并区映射（依 rtq-xlw-章节映射表.md：无二级章号的区段）——
GROUP = {
    "TS-13": "第二编中·（开篇）体用精神",   # 实含 TS-13~16
    "TS-27": "第二编下·（总论，无二级章号）",  # 实含 TS-27,29~34,LQ-08,09,28,29
}
GROUP_MEMBERS = {
    "第二编中·（开篇）体用精神": ["TS-13", "TS-14", "TS-15", "TS-16"],
    "第二编下·（总论，无二级章号）": ["TS-27", "TS-29", "TS-30", "TS-31", "TS-32",
                                "TS-33", "TS-34", "LQ-08", "LQ-09", "LQ-28", "LQ-29"],
}
# 补注实际与任氏原章号的对应（映射表 §二）
ACTUAL = {
    "TS-13": "TS-13~16（体用/精神/月令/生时）",
    "TS-27": "TS-27,29~34,LQ-08,09,28,29（刚柔/寒暖/燥湿/隐显/众寡/震兑/坎离/才德/奋郁/岁运/贞元）",
}

# L4 命例需补的契约 §3.2 字段
L4_FILL = {
    "ADDED_BY_EDITOR": "不适用（L4 徐氏补注层）",
    "SELF_REFERENCE": "不适用（L4 徐氏补注层；任氏自述字段仅 L3 适用）",
    "出身": "原书未载",
    "职业": "原书未载",
    "人生事件": "原书未载（徐氏补注以理法为主，未分项叙事件）",
    "流年与应期": "原书未推（徐氏补注未系应期）",
    "所用规则": "参照同章 L3 规则卡（L4 补注主于义理辨正，未逐条挂规则）",
    "最终结论": "见「徐乐吾补注」字段",
    "版本差异标志": "见 SOURCE_FILE 底本行号",
}

n_fill = 0
n_conf = 0
for x in C:
    if x.get("LAYER") != "L4":
        continue
    # 补 10 字段（可信度单独处理）
    for k, v in L4_FILL.items():
        if k not in x:
            x[k] = v
            n_fill += 1
    # 可信度统一：CONFIDENCE -> 可信度（保留原字段兼容）
    if "可信度" not in x and "CONFIDENCE" in x:
        x["可信度"] = x["CONFIDENCE"]
        n_conf += 1
    # 合并区标记
    if x.get("CHAPTER_ID") in GROUP:
        x["CHAPTER_GROUP"] = GROUP[x["CHAPTER_ID"]]
        x["CHAPTER_GROUP_MEMBERS"] = GROUP_MEMBERS[GROUP[x["CHAPTER_ID"]]]
        x["CHAPTER_ACTUAL"] = ACTUAL[x["CHAPTER_ID"]]

for x in R:
    if x.get("AUTHOR") != "L4":
        continue
    if x.get("CHAPTER_ID") in GROUP:
        x["CHAPTER_GROUP"] = GROUP[x["CHAPTER_ID"]]
        x["CHAPTER_GROUP_MEMBERS"] = GROUP_MEMBERS[GROUP[x["CHAPTER_ID"]]]
        x["CHAPTER_ACTUAL"] = ACTUAL[x["CHAPTER_ID"]]

dump(C, "命例库_712_双层.json")
dump(R, "规则库_1538_双层.json")

# 复核
c4 = [x for x in C if x.get("LAYER") == "L4"]
REQ = ['CASE_ID', 'CHAPTER_ID', 'LAYER', 'ADDED_BY_EDITOR', 'SELF_REFERENCE', '八字', '大运',
       '性别', '身份', '出身', '职业', '人生事件', '流年与应期', '任铁樵原断', '判断依据',
       '所用规则', '最终结论', '版本差异标志', '可信度']
miss = {f: sum(1 for x in c4 if f not in x) for f in REQ}
print("补字段次数:", n_fill, "｜ 可信度统一:", n_conf)
print("L4 命例契约字段缺失:", {k: v for k, v in miss.items() if v} or "0（全齐）")
r4g = sum(1 for x in R if x.get("AUTHOR") == "L4" and "CHAPTER_GROUP" in x)
print("L4 规则带合并区标记:", r4g)
print("L4 命例带合并区标记:", sum(1 for x in c4 if "CHAPTER_GROUP" in x))
