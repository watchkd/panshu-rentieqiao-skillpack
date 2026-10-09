# -*- coding: utf-8 -*-
"""五行/天干地支/十神 映射公用表 —— 建评测金标准用。

仅作词面规约工具：把任氏原断里的干支/五行/十神词面归一为:五行集合、十神集合、干支集合。
所有映射为"机械查表"，不掺任何命理推断（推断留给评测对照时比对）。
"""

# 天干 → 五行
GAN_WX = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
          "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
# 地支 → 五行（本气）
ZHI_WX = {"寅": "木", "卯": "木", "午": "火", "巳": "火", "申": "金", "酉": "金",
          "子": "水", "亥": "水", "辰": "土", "戌": "土", "丑": "土", "未": "土"}

GAN_SET = set(GAN_WX)
ZHI_SET = set(ZHI_WX)
WX_SET = {"金", "木", "水", "火", "土"}

# 十神 → 类（供相斥校验/映射）
SHISHEN_SUPER = {
    "正官": "官", "七杀": "杀",
    "正印": "印", "偏印": "印", "枭神": "印", "枭": "印",
    "比肩": "比劫", "劫财": "比劫", "比劫": "比劫", "兄弟": "比劫",
    "食神": "食伤", "伤官": "食伤", "食伤": "食伤",
    "正财": "财", "偏财": "财", "财星": "财", "财": "财",
    "偏印": "印",
}

def gan_to_wx(s):
    """取字符串中所有天干 → 五行列表（去重保序）"""
    out = []
    for ch in s:
        if ch in GAN_WX and GAN_WX[ch] not in out:
            out.append(GAN_WX[ch])
    return out

def zhi_to_wx(s):
    out = []
    for ch in s:
        if ch in ZHI_WX and ZHI_WX[ch] not in out:
            out.append(ZHI_WX[ch])
    return out

def stem_branch_wx(s):
    """归并干支→五行"""
    out = []
    for ch in s:
        if ch in GAN_WX:
            w = GAN_WX[ch]
        elif ch in ZHI_WX:
            w = ZHI_WX[ch]
        else:
            continue
        if w not in out:
            out.append(w)
    return out

if __name__ == "__main__":
    print(gan_to_wx("癸丁乙"))
    print(zhi_to_wx("丑丑申"))
    print(stem_branch_wx("癸乙庚丁丑"))