# -*- coding: utf-8 -*-
"""金标准回归评测器—— 用神一致率。

用法：
  python eval.py --gold 评测集_金标准.json --pred <预测文件.json>
  (也可 --quick 用内置最小 baseline，仅演示流程)

预测文件格式（模型跑 rtq-panshu pipeline 后，把 P2 取用落定的"用神"喂入）：
{
  "_meta": {"note": "rtq-panshu P2 输出", "generated": "2026-10-09"},
  "outputs": {
     "RTQ-CASE-LQ-05-010": {"用": ["火"]},
     "RTQ-CASE-TS-27-002": {"用": ["火", "木"]},
     ...                     # 可只给有用神的子集
  }
}

口径：
  * 金标准只用 state=="gold" 且含「用」标签的命例（当前 35 例）。
  * 命中判定：谓词的「用」五行 与 金标「用」五行集合 有交集即算一致。
  * 输出：报告 覆盖率 / 用神一致率 / 逐例误例清单（附 gold evidence）。
  * 未覆盖或弱标命例不计分 —— 诚实记"未纳入"。
"""
import json, os, sys, argparse

def load(path):
    d = json.load(open(path, encoding="utf-8"))
    return d

def get_gold_use(gold_case):
    tags = gold_case.get("tags", {}) or {}
    return tags.get("用", [])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "评测集_金标准.json"))
    ap.add_argument("--pred", default=None)
    ap.add_argument("--quick", action="store_true", help="用内置最小 sample 跑通演示")
    args = ap.parse_args()

    gold = load(args.gold)
    gold_cases = {c["CASE_ID"]: c for c in gold["cases"]}
    gold_use = {cid: get_gold_use(c) for cid, c in gold_cases.items() if c.get("state") == "gold" and get_gold_use(c)}
    print("金标准可用（gold 且含用神标签）:", len(gold_use), "例")

    if args.quick:
        # 最小内置预测：只对 3 条手写"正确"答案，演示报告形态
        outputs = {
            "RTQ-CASE-LQ-05-010": {"用": ["火"]},
            "RTQ-CASE-TS-27-002": {"用": ["火"]},
            "RTQ-CASE-LQ-01-001": {"用": ["火"]},
        }
        pred = {"_meta": {"note": "quick demo"}, "outputs": outputs}
    else:
        if not args.pred:
            print("请用 --pred 提供预测文件，或用 --quick 演示。"); return
        pred = load(args.pred)
    outputs = pred.get("outputs", {})

    correct, tested, gold_tested = 0, 0, 0
    misses = []
    skip_uncovered = 0
    for cid, goldws in gold_use.items():
        if isinstance(goldws, str):
            goldws = [goldws]
        if cid not in outputs or not outputs[cid].get("用"):
            skip_uncovered += 1
            continue
        predws = outputs[cid]["用"]
        if isinstance(predws, str):
            predws = [predws]
        tested += 1
        gold_tested += 1
        hit = bool(set(predws) & set(goldws))
        if hit:
            correct += 1
        else:
            misses.append((cid, gold_cases[cid]["八字"], goldws, predws,
                           [e for e in gold_cases[cid].get("evidence", []) if e[0] == "用"]))

    print()
    print("=" * 70)
    print("评测报告 · 用神一致率")
    print("=" * 70)
    print("金标准可用命例           : %d" % len(gold_use))
    print("模型覆盖并计分命例       : %d (覆盖率 %.0f%%)" % (tested, 100*tested/max(len(gold_use),1)))
    print("未覆盖(不计分)           : %d" % skip_uncovered)
    print("   └ 金标准用神           : %s" % (",".join(gold_use.keys())))
    if tested:
        print("   └ 一致              : %d" % correct)
        print("   └ 不一致            : %d" % (tested - correct))
        print("   └ 用神一致率         : %.1f%%" % (100*correct/max(tested,1)))
    print()
    if misses:
        print("== 误例明细（金标 vs 预测）==")
        for cid, bz, gw, pw, ev in misses:
            print("-" * 60)
            print(" %s  %s" % (cid.replace("RTQ-CASE-",""), bz))
            print("   金标准用:%s  预测用:%s" % (gw, pw))
            for cat, w, s in ev[:2]:
                print("   任氏原文: %s" % s)

if __name__ == "__main__":
    main()