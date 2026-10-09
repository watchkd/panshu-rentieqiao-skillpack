# -*- coding: utf-8 -*-
"""金标准抽取器 —— 从任氏原断自动抽取「用神/喜忌/病药」标签。

设计原则（对应评测的"可度量、防幻觉"）：
  * 只认 **显式** 词面：任氏说"用火敌寒""取X为用""喜其X""所忌X""X为病""全赖X""药在X"。
  * 命例原文未显式给者，标 state=weak，不冒充确证 → 进"待核"，不强给标签。
  * 每条断言锚定原文证据（evidence 原句），供人工复核。
  * gold 门槛：原文含"用/喜/病/药"任一显式正向要素，且成功抽取到非空标签。
    （四类不必齐全；只有一句"忌X"而无任一正向者的弱例仍归 weak，避免把仅负面当金标准。）
产物：评测/评测集_金标准.json
"""
import json, re, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(ROOT, "数据", "命例库_712_双层.json")
OUT = os.path.join(HERE, "评测集_金标准.json")

sys.path.insert(0, HERE)
from wxmap import GAN_WX, WX_SET
GAN_BR = "甲乙丙丁戊己庚辛壬癸"
TOK = "[%s]?[金木水火土]" % GAN_BR   # 单元素 token：甲/木/甲木/火/癸水

# (正则, 类别)。用 finditer + 捕获 token。
DIRECT = [
    # 用神系
    (re.compile(r"取\s*(%s)\s*为用" % TOK), "用"),
    (re.compile(r"以\s*(%s)\s*为用" % TOK), "用"),
    (re.compile(r"用\s*(%s)\s*敌寒" % TOK), "用"),
    (re.compile(r"用\s*(%s)\s*(?:为用|也|者|的|只得|更)?" % TOK), "用"),
    (re.compile(r"用神\s*(?:必\s*)?(?:在|为|是)\s*([甲乙丙丁戊己庚辛壬癸]?[金木水火土])"), "用"),
    (re.compile(r"非\s*(%s)\s*为用" % TOK), "用"),   # 取火为用者十无一二→非取为用
    (re.compile(r"取\s*(%s)\s*者" % TOK), "用"),
    # 喜神系
    (re.compile(r"喜其\s*(%s)" % TOK), "喜"),
    (re.compile(r"最喜\s*(%s)" % TOK), "喜"),
    (re.compile(r"所喜\s*(?:者|[在是])\s*(%s)?" % TOK), "喜"),
    (re.compile(r"喜\s*(%s)\s*(?:也|者|，|。)" % TOK), "喜"),
    (re.compile(r"喜神\s*即是\s*([^，。；]{1,6})"), "喜"),
    (re.compile(r"喜\s*(%s)\s*(?:忌|者)" % TOK), "喜"),
    # 病系
    (re.compile(r"(%s)\s*为病" % TOK), "病"),
    (re.compile(r"病\s*在\s*(%s)" % TOK), "病"),
    (re.compile(r"所忌.*?(%s)\s*为病" % TOK), "病"),
    (re.compile(r"嫌\s*[^。；]*?(%s)\s*为病" % TOK), "病"),
    (re.compile(r"(%s)\s*为祸" % TOK), "病"),
    # 忌系
    (re.compile(r"所忌者\s*[，:：]?\s*(%s|[%s])" % (TOK, GAN_BR)), "忌"),
    (re.compile(r"忌\s*(%s)" % TOK), "忌"),
    # 药系
    (re.compile(r"药\s*[在自]?\s*(%s)" % TOK), "药"),
    (re.compile(r"全赖\s*(%s|[%s]{1,2}木|[%s]{1,2}火)" % (TOK, GAN_BR, GAN_BR)), "药"),
    (re.compile(r"全仗\s*(%s)" % TOK), "药"),
]

def _normalize(tok):
    tok = tok.replace(" ", "").strip("，。；、")
    if len(tok) == 1 and tok in "金木水火土":
        return tok
    if len(tok) == 2 and tok[0] in GAN_WX and tok[1] in "金木水火土":
        return tok[1]  # 癸水→水
    if len(tok) == 1 and tok in GAN_WX:
        return GAN_WX[tok]  # 癸→水
    return tok[0] if len(tok) and tok[0] in "金木水火土" else (tok if tok else "")

QUOTE_PAIRS = ["“”", "「」", "『』", "《》", "'\"()（）"]

def _inside_quote(text, pos):
    """pos 是否落在成对引号/括号内？任一配对左闭右开成立即 True。"""
    for pair in QUOTE_PAIRS:
        if len(pair) == 2 and pair[0] != pair[1]:
            l, r = pair[0], pair[1]
            lefts = [i for i in range(len(text)) if text[i] == l and i <= pos]
            rights = [i for i in range(len(text)) if text[i] == r and i <= pos]
            if lefts and (not rights or rights[-1] < lefts[-1]):
                return True
        elif len(pair) == 2 and pair[0] == pair[1]:
            c = pair[0]
            n = sum(1 for i in range(len(text)) if text[i] == c and i <= pos)
            if n % 2 == 1:
                return True
    return False

NEG_CONTEXT = ("俗", "旧", "所谓", "谓", "者", "或", "且", "恐", "似", "如", "若", "设", "则")
def _is_negated(text, pos):
    """match 起点前窗口含否定/泛论/假设语境 → 非本命直陈。"""
    w = max(0, pos - 4)
    pre = text[w:pos]
    for k in NEG_CONTEXT:
        if k in pre:
            return True
    return False

def extract_one(text):
    tagset = collections.defaultdict(list)
    evidences = []
    excluded = []
    for pat, cat in DIRECT:
        for m in pat.finditer(text):
            tok = m.group(1).replace(" ", "") if m.lastindex else ""
            w = _normalize(tok)
            if not w or w not in WX_SET:
                continue
            if _inside_quote(text, m.start()):
                continue  # 引用/括注不作本命金标
            if _is_negated(text, m.start()):
                excluded.append((cat, w, text[max(0, m.start()-8):m.end()+6].strip()))
                continue
            if w not in tagset[cat]:
                tagset[cat].append(w)
                evidences.append((cat, w, text[max(0, m.start()-8):m.end()+6].strip()))
    return dict(tagset), evidences, excluded

# 显式正向要素判定：原文出现这些信号词（排除纯负面/引用句）
POSITIVE_SIGNALS = ("用神", "取", "为用", "喜其", "最喜", "所喜", "喜", "为病",
                    "病在", "为祸", "全赖", "药在", "全仗")
NEGATIVE_ONLY = ("忌", "嫌")

if __name__ == "__main__":
    data = json.load(open(DATA, encoding="utf-8"))
    cases = data if isinstance(data, list) else next(v for v in data.values() if isinstance(v, list))
    l3 = [c for c in cases if c.get("LAYER") == "L3"]
    print("L3:", len(l3))

    stats = collections.Counter()
    n_excl = 0
    out = {"_meta": {"source": "命例库_712_双层.json", "layer": "L3", "total": len(l3),
                     "method": "显式词面抽取；gold=含任一正向五要素且抽取非空；其余待核",
                     "generated": "2026-10-09"},
           "cases": []}
    for c in l3:
        text = (c.get("任铁樵原断") or "") + "\n" + (c.get("判断依据") or "")
        tags, evs, excl = extract_one(text)
        has_pos = any(tags.get(k) for k in ("用", "喜", "病", "药"))
        # 双保险：文法上验证确实出现正向信号词（避免正则漏但原文确有多元素）
        has_pos_signal = any(s in text for s in POSITIVE_SIGNALS)
        state = "gold" if (has_pos and has_pos_signal) else "weak"
        case = {"CASE_ID": c["CASE_ID"], "八字": c.get("八字"), "性别": c.get("性别") or "",
                "tags": tags, "evidence": evs[:10], "excluded": excl[:6], "state": state}
        if excl:
            n_excl += 1
        stats[state] += 1
        out["cases"].append(case)

    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("state:", dict(stats))
    gold = [c for c in out["cases"] if c["state"] == "gold"]
    weak = [c for c in out["cases"] if c["state"] == "weak"]
    print("gold:", len(gold), "weak:", len(weak))
    print("\n== gold 标签覆盖（需≥门槛）==")
    has_use = sum(1 for c in gold if c["tags"].get("用"))
    has_bing = sum(1 for c in gold if c["tags"].get("病"))
    has_xi = sum(1 for c in gold if c["tags"].get("喜"))
    print("  有用:", has_use, " 有病:", has_bing, " 有喜:", has_xi,
          " 有病+用+喜三全:", sum(1 for c in gold if c["tags"].get("用") and c["tags"].get("病") and c["tags"].get("喜")))
    print("\n== 样本（gold 前 8）==")
    for c in gold[:8]:
        print("-" * 66)
        print(c["CASE_ID"].replace("RTQ-CASE-", ""), c["八字"], "\n  tags:", c["tags"])
        for cat, w, ev in c["evidence"][:4]:
            print("    [%s] %s | %s" % (cat, w, ev))
    print("\nOUT ->", OUT)
    print("被排除歧义语境数(命例):", n_excl)