# -*- coding: utf-8 -*-
"""命例多维索引 检索接口 —— 按 日主/寒暖/病/药/格局 命中"结构相似"的 L3 命例，供命例互验环节调用。

用途：论命流水线输出命例互验（同造事例）时，除原文关键词检索外，
     可再用本索引按「病×药×格局×日主」命中"病药结构相同"的原书命例作为旁证。

与 build_gold.py 的分工：
  build_gold.py = 取用正确性的【评测金标准】（评流水线做对没有）
  build_index.py = 命例分类的【检索面索引】（找同病同药同格的旁证命例）
"""
import json, os
IDX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "命例多维索引.json")


class MultiDimIndex:
    def __init__(self, path=IDX):
        self.path = path
        d = json.load(open(path, encoding="utf-8"))
        self.meta = d.get("meta", {})
        self.entries = d.get("entries", {})  # {CASE_ID: {维度tags}}

    def query(self, 日主=None, 寒暖=None, 病=None, 药=None, 格局=None, 日主强弱=None):
        """按维度精确过滤；病/药 传五行子集（如 ['水']），命例须含这些五行才命中。未传维度=不限。"""
        want_sets = {"病": set(病 or []), "药": set(药 or [])}
        out = []
        for cid, t in self.entries.items():
            if 日主 is not None and t.get("日主") != 日主: continue
            if 寒暖 is not None and t.get("寒暖") != 寒暖: continue
            if 格局 is not None and t.get("格局") != 格局: continue
            if 日主强弱 is not None and t.get("日主强弱") != 日主强弱: continue
            if not all(w <= set(t.get(dim) or []) for dim, w in want_sets.items() if w):
                continue
            out.append(cid)
        return out

    def groups(self, keys=("药", "日主"), min_size=2):
        """按若干维度聚合，返回命中 ≥min_size 的可互验组合组 {key_tuple: [CASE_ID,...]}。"""
        import collections
        def _k(v):
            return tuple(v) if isinstance(v, (list, tuple)) else v
        g = collections.defaultdict(list)
        for cid, t in self.entries.items():
            k = tuple(_k(t.get(k)) for k in keys)
            if None in k:
                continue
            g[k].append(cid)
        return {k: v for k, v in g.items() if len(v) >= min_size}


if __name__ == "__main__":
    ix = MultiDimIndex()
    print("索引载入:", ix.meta.get("n"), "例 | 维度统计:", ix.meta.get("维度统计"))
    for b in (["水"], ["火"], ["木"]):
        c = ix.query(病=b)
        print(f"\n病={b} → {len(c)} 例:", ", ".join(x.replace("RTQ-CASE-", "") for x in c)[:80])
    print("\n可互验组（药×日主，≥2 例）：")
    for k, v in sorted(ix.groups(("药", "日主")).items(), key=lambda x: -len(x[1]))[:8]:
        print("  日主=%s 药=%s → %d 例" % (k[1], k[0], len(v)))