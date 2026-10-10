# -*- coding: utf-8 -*-
"""
排盘核对器 v2（rtq-panshu · v2.4.0「排盘核对层」）

依赖：lunar_python（6tail《lunar》纯 Python 版，MIT License）
安装：pip install lunar_python          # 纯 Python，无需编译器

────────────────────────────────────────────────────────────────────────
⚠ 定位：本工具是「核对器」，不是「定盘器」
────────────────────────────────────────────────────────────────────────
本包以**用户自己排盘工具确认过的四柱八字**为唯一排盘入口。本工具只在
「用户没给大运」时作**参考推算**，其结果一律标「待核」；**不得**拿它回改
用户给的盘。用户提供的大运与本工具推算不一致时，**一律以用户为准**。

────────────────────────────────────────────────────────────────────────
⚠ 「排大运」其实是两件事，可推性天差地别
────────────────────────────────────────────────────────────────────────
(a) **大运干支序列**（丙子→丁丑→戊寅…）——**四柱 ＋ 性别即可唯一确定**：
    顺逆 =「年干阴阳 × 性别」，起排 = 月柱。四柱里年干、月柱都有，故
    **只要给了四柱与性别，这一串就是读出来的，不是算出来的，不会错**。
    → 用 `--four` 直接推（不需要出生时刻）。

(b) **起运岁数 / 交运年份**——**四柱里没有这个信息，推不出来**：
    岁数 =「出生时刻 → 最近节」的天数按 3 日折 1 年。而四柱的时柱只有
    **2 小时精度**（且未做真太阳时校正），加上各家软件「虚岁/周岁」口径不一，
    同一盘报出「9 岁起运」「10 岁起运」都不奇怪。
    → 故 `--four` **不给岁数**；须给出生时刻才由本工具参考推算，并标「据推待核」。

(c) **四柱本身对不对**——本工具**默认采信**（铁律 11：以用户为准）。
    时辰记错 / 未校正真太阳时 / 生于交节前后数小时，都会让**用户自己的**四柱
    出错，本工具看不出来。→ 只有用户**另给生辰**时，本工具才能排出自己的版本
    回请核对，起**交叉验证**作用（`--check`）。

────────────────────────────────────────────────────────────────────────
⚠ 大运四大误差源（每一条都足以让整排大运错掉，务必逐项核对）
────────────────────────────────────────────────────────────────────────
1) **性别**——大运顺逆由「年干阴阳 × 性别」定：阳男阴女顺排、阴男阳女逆排。
   性别错或缺失 → 整个大运序列反向，一错到底。
   → 故本工具**性别为必填、无默认值**；不传即不出大运。

2) **交节边界**——生于交节当日、或交节前后数小时者，**月柱**可能整体错位；
   而月柱正是大运起排之基（大运自月柱干支顺/逆推）。
   → 本工具输出「距节天数」，请核对月柱是否与你的排盘一致。

3) **起运折算**——起运岁数＝「出生时刻 → 最近节」的天数，按 3 日折 1 年。
   出生时辰差一刻、交节时刻差一分，起运就可能差一月甚至一年。
   且各排盘软件对「起运虚岁 / 周岁」口径不同。
   → 本工具同时给出「起运年月日」与「起运虚岁」，请按你惯用口径取用。

4) **真太阳时**——本工具按**北京时间**排盘，**未做经度时差校正**。
   出生地偏东/偏西较多者，时柱（乃至临界日的日柱）可能整体位移。
   → 请用户以自己的真太阳时排盘结果为准。

────────────────────────────────────────────────────────────────────────
用法
────────────────────────────────────────────────────────────────────────
    python paipan_tool.py 1984 11 12 14 0 男            # 排盘（四柱/节气/司令/大运）
    python paipan_tool.py 1984 11 12 14 0 男 --check    # 附「排盘核对清单」（贴给用户核对）
    python paipan_tool.py --no-gender 1984 11 12 14 0   # 只出四柱/节气（不出大运）
    python paipan_tool.py --four 甲子 乙亥 庚戌 癸未 男  # 只给四柱：判顺逆 ＋ 推大运干支序列（不给岁数）

性别写法：男 / 女 / 1（男） / 0（女）
分隔符：空格、逗号、顿号、斜杠皆可（如「甲子,乙亥,庚戌,癸未 男」）
自洽校验：`--four` 会以**五虎遁**验「年柱↔月柱」、以**五鼠遁**验「日柱↔时柱」，
         不自洽即告警——专抓「年柱配错月柱」这类手误（不阻断，仅提示核对）。
"""
from __future__ import annotations

import datetime
import re
import sys

try:
    from lunar_python import Solar, Lunar
except ImportError:  # pragma: no cover
    sys.stderr.write(
        "[排盘核对器] 缺少依赖 lunar_python。请先安装：\n"
        "    pip install lunar_python\n"
        "（纯 Python 包，无需编译器；装不上则本工具不可用，"
        "此时一律改为请用户提供其已确认的四柱与大运。）\n"
    )
    raise SystemExit(2)

# 立春→对应地支月（人元司令以「节」定月建，跨年界正确）
JIE_ZHI = {"立春": "寅", "惊蛰": "卯", "清明": "辰", "立夏": "巳", "芒种": "午",
           "小暑": "未", "立秋": "申", "白露": "酉", "寒露": "戌", "立冬": "亥",
           "大雪": "子", "小寒": "丑"}

# 十二「节」（不含中气）——月建由此定
JIE = ("立春", "惊蛰", "清明", "立夏", "芒种", "小暑",
       "立秋", "白露", "寒露", "立冬", "大雪", "小寒")

# 人元司令分日 —— 依《渊海子平》/《三命通会》口径。
# 存「累计天数边界」：距节 X 日内司令为何，取第一个 cum(边界) >= X 者。
# 例：寅 = 1-7 戊土、8-14 丙火、15-30 甲木。亥 = 1-7 戊土、8-12 甲木、13-30 壬水。
SI_LING = {
    "寅": [("戊土", 7), ("丙火", 14), ("甲木", 30)],
    "卯": [("甲木", 10), ("乙木", 30)],
    "辰": [("乙木", 9), ("癸水", 12), ("戊土", 30)],
    "巳": [("戊土", 7), ("庚金", 14), ("丙火", 30)],
    "午": [("丙火", 10), ("己土", 19), ("丁火", 30)],
    "未": [("丁火", 9), ("乙木", 12), ("己土", 30)],
    "申": [("戊土", 7), ("壬水", 14), ("庚金", 30)],
    "酉": [("庚金", 10), ("辛金", 30)],
    "戌": [("辛金", 9), ("丁火", 12), ("戊土", 30)],
    "亥": [("戊土", 7), ("甲木", 12), ("壬水", 30)],
    "子": [("壬水", 10), ("癸水", 30)],
    "丑": [("癸水", 9), ("辛金", 12), ("己土", 30)],
}

YANG_GAN = set("甲丙戊庚壬")   # 阳干；余为阴干


def norm_gender(g) -> int:
    """把 男/女/1/0 归一为 1（男）/ 0（女）。无法识别则抛错——不默认男。"""
    if g in (1, "1", "男", "m", "M", True):
        return 1
    if g in (0, "0", "女", "f", "F", False):
        return 0
    raise ValueError("性别必须为 男/女（或 1/0）；本工具不设默认性别——"
                     "性别决定大运顺逆，缺则整排大运皆不可信。")


def _prev_jie(birth_dt: datetime.datetime):
    """返回出生时刻之前最近的「节」：(名, 时刻)。跨年回退上一年。"""

    def _pick(table):
        best = None
        for name in JIE:
            s = table.get(name)
            if s is None or not hasattr(s, "toYmdHms"):
                continue
            try:
                dt = datetime.datetime.strptime(s.toYmdHms(), "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            if dt <= birth_dt and (best is None or dt > best[1]):
                best = (name, dt)
        return best

    prev = _pick(Lunar.fromYmd(birth_dt.year, 1, 1).getJieQiTable())
    if prev is None:
        prev = _pick(Lunar.fromYmd(birth_dt.year - 1, 1, 1).getJieQiTable())
    return prev


def _shun_ni(year_gan: str, gender: int) -> str:
    """大运顺逆：阳男阴女顺排，阴男阳女逆排。"""
    yang = year_gan in YANG_GAN
    forward = (yang and gender == 1) or ((not yang) and gender == 0)
    return "顺排" if forward else "逆排"


GAN10 = "甲乙丙丁戊己庚辛壬癸"
ZHI12 = "子丑寅卯辰巳午未申酉戌亥"
JIAZI60 = [GAN10[i % 10] + ZHI12[i % 12] for i in range(60)]
_GZ_IDX = {gz: i for i, gz in enumerate(JIAZI60)}


def is_gz(s: str) -> bool:
    """是否合法干支（六十甲子之一）。"""
    return s in _GZ_IDX


def dayun_ganzhi(month_gz: str, forward: bool, n: int = 8):
    """由月柱起、按顺/逆推 n 步大运**干支序列**。

    仅需「月柱 ＋ 顺逆」——即四柱 ＋ 性别即可确定，**不涉及出生时刻**。
    起运**岁数**不在此列（四柱的时柱只有 2 小时精度，无法据以定岁数）。
    """
    i = _GZ_IDX.get(month_gz)
    if i is None:
        return []
    step = 1 if forward else -1
    return [JIAZI60[(i + step * k) % 60] for k in range(1, n + 1)]


# 五虎遁（年上起月）：年干 → 正月（寅月）天干
_WUHU = {"甲": "丙", "己": "丙", "乙": "戊", "庚": "戊", "丙": "庚",
         "辛": "庚", "丁": "壬", "壬": "壬", "戊": "甲", "癸": "甲"}
# 五鼠遁（日上起时）：日干 → 子时天干
_WUSHU = {"甲": "甲", "己": "甲", "乙": "丙", "庚": "丙", "丙": "戊",
          "辛": "戊", "丁": "庚", "壬": "庚", "戊": "壬", "癸": "壬"}


def expect_month_gan(year_gan: str, month_zhi: str) -> str:
    """五虎遁：由年干与月支推应有的月干（校验「年柱↔月柱」是否自洽）。"""
    head = _WUHU.get(year_gan)
    if head is None or month_zhi not in ZHI12:
        return ""
    off = (ZHI12.index(month_zhi) - 2) % 12       # 寅月为正月
    return GAN10[(GAN10.index(head) + off) % 10]


def expect_hour_gan(day_gan: str, hour_zhi: str) -> str:
    """五鼠遁：由日干与时支推应有的时干（校验「日柱↔时柱」是否自洽）。"""
    head = _WUSHU.get(day_gan)
    if head is None or hour_zhi not in ZHI12:
        return ""
    return GAN10[(GAN10.index(head) + ZHI12.index(hour_zhi)) % 10]


def split_args(argv):
    """参数归一：去首尾空白，并把「甲子,乙亥,庚戌,癸未」这类整体拆成四项。"""
    out = []
    for a in argv:
        for piece in re.split(r"[,，、;；/|]+", str(a)):
            piece = piece.strip()
            if piece:
                out.append(piece)
    return out


def paipan(y, m, d, h, mi=0, gender=None):
    """排盘。

    gender：**必填**（男/女 或 1/0）。传 None 则只出四柱与节气，**不出大运**。
    返回 dict，含 '待核' 键（True 表示大运系推算、须用户核对）。
    """
    birth_dt = datetime.datetime(y, m, d, h, mi, 0)
    so = Solar.fromYmdHms(y, m, d, h, mi, 0)
    lu = so.getLunar()
    ba = lu.getEightChar()

    year_gan = ba.getYear()[0]
    out = {
        "公历": "%04d-%02d-%02d %02d:%02d" % (y, m, d, h, mi),
        "农历": lu.toString(),
        "生肖": lu.getYearShengXiao(),
        "四柱": [ba.getYear(), ba.getMonth(), ba.getDay(), ba.getTime()],
        "年干": year_gan,
        "时柱口径": "北京时间（未做真太阳时校正）",
        "待核": True,
    }

    prev = _prev_jie(birth_dt)
    out["节气"] = prev[0] if prev else "?"
    out["交节时刻"] = prev[1].strftime("%Y-%m-%d %H:%M:%S") if prev else "?"
    out["月建"] = JIE_ZHI.get(prev[0], "") if prev else ""
    if prev:
        gap = (birth_dt - prev[1]).total_seconds() / 86400
        if gap < 0:
            gap = 0.0
        out["距节天数"] = round(gap, 3)
        stage = SI_LING.get(out["月建"], [])
        cmd = next((name for name, cum in stage if gap <= cum), None)
        if cmd is None and stage:
            cmd = stage[-1][0]
        out["司令"] = cmd

    # 大运：性别必填
    if gender is None:
        out["大运"] = None
        out["起运"] = None
        out["顺逆"] = None
        out["大运备注"] = "未传性别——按铁律「性别不明不出大运」，请先确认性别。"
        return out

    gender = norm_gender(gender)
    out["性别"] = "男" if gender == 1 else "女"
    out["顺逆"] = _shun_ni(year_gan, gender)

    yun = ba.getYun(1 if gender == 1 else 0)
    out["起运"] = "%d年%d月%d日" % (yun.getStartYear(), yun.getStartMonth(), yun.getStartDay())
    try:
        out["起运公历"] = yun.getStartSolar().toYmd()
    except Exception:
        out["起运公历"] = "?"
    out["顺逆核实"] = bool(yun.isForward())
    rows = []
    for dy in yun.getDaYun()[1:9]:          # [0] 为起运前，故取 1..8
        rows.append({
            "干支": dy.getGanZhi(),
            "起年": dy.getStartYear(),
            "止年": dy.getEndYear(),
            "起虚岁": dy.getStartAge(),
            "止虚岁": dy.getEndAge(),
        })
    out["大运"] = rows
    out["起运虚岁"] = rows[0]["起虚岁"] if rows else None
    out["大运备注"] = ("据 lunar_python 按 3 日折 1 年推算，**未经用户核对**；"
                       "各软件起运口径不一，一律以用户排盘为准。")
    return out


def checklist(r: dict) -> str:
    """生成可直接贴给用户核对的清单。"""
    L = []
    L.append("【排盘核对清单 · 请与你自己的排盘逐项核对】")
    L.append("1. 四柱        ：%s" % "  ".join(r["四柱"]))
    if r.get("性别"):
        L.append("2. 性别 / 顺逆 ：%s → 年干「%s」为%s → %s"
                 % (r["性别"], r["年干"], "阳" if r["年干"] in YANG_GAN else "阴", r["顺逆"]))
    else:
        L.append("2. 性别 / 顺逆 ：**性别未定** —— 大运顺逆无从判定，故本清单不出大运")
    L.append("3. 月建 / 交节 ：%s（交节 %s；距节 %s 日）"
             % (r.get("月建", "?"), r.get("交节时刻", "?"), r.get("距节天数", "?")))
    L.append("4. 人元司令   ：%s" % r.get("司令", "?"))
    if r.get("大运"):
        L.append("5. 起运        ：%s（起运公历 %s，起运虚岁 %s）"
                 % (r["起运"], r.get("起运公历", "?"), r.get("起运虚岁", "?")))
        L.append("6. 大运        ：%s"
                 % " → ".join("%s(%d岁)" % (x["干支"], x["起虚岁"]) for x in r["大运"]))
    L.append("")
    L.append("⚠ 第 1 项（尤以**时柱**）或第 2 项（**性别**）若与你的排盘不同，请以你的为准——"
             "把你自己排好的**四柱＋大运**发我，我按你的盘断。")
    L.append("⚠ 本清单按北京时间排，**未做真太阳时校正**；出生地经度与北京时差较大者，"
             "时柱可能整体位移，请自行确认。")
    L.append("⚠ 起运岁数各软件口径不一（虚岁/周岁），第 5 项仅供参考。")
    return "\n".join(L)


def _fmt(r: dict) -> str:
    L = []
    for k in ("公历", "农历", "生肖", "四柱", "节气", "交节时刻", "月建",
              "距节天数", "司令", "时柱口径"):
        if r.get(k) is not None:
            v = r[k]
            L.append("  %-6s：%s" % (k, "  ".join(v) if isinstance(v, list) else v))
    if r.get("性别"):
        L.append("  %-6s：%s → %s（年干%s为%s）"
                 % ("性别", r["性别"], r["顺逆"], r["年干"],
                    "阳" if r["年干"] in YANG_GAN else "阴"))
    if r.get("大运"):
        L.append("  %-6s：%s" % ("起运", r["起运"]))
        L.append("  %-6s：%s" % ("大运", " → ".join(
            "%s(%d岁)" % (x["干支"], x["起虚岁"]) for x in r["大运"])))
    elif r.get("大运备注"):
        L.append("  %-6s：%s" % ("大运", r["大运备注"]))
    if r.get("大运备注") and r.get("大运"):
        L.append("  ⚠ %s" % r["大运备注"])
    return "\n".join(L)


def _usage(msg=None):
    if msg:
        sys.stderr.write(msg + "\n")
    sys.stderr.write(__doc__.split("用法")[-1].strip() + "\n")
    raise SystemExit(1)


def main(argv):
    args = split_args(argv)
    if not args or "-h" in args or "--help" in args:
        print(__doc__.strip())
        return 0
    show_check = "--check" in args
    no_gender = "--no-gender" in args
    args = [a for a in args if a not in ("--check", "--no-gender")]

    if args and args[0] == "--four":
        rest = args[1:]
        if len(rest) < 5:
            _usage("--four 需要：年柱 月柱 日柱 时柱 性别")
        year, month, day, hour, gender = rest[:5]
        print("四柱：%s %s %s %s" % (year, month, day, hour))

        # ① 单柱合法性
        bad = [p for p in (year, month, day, hour) if not is_gz(p)]
        if bad:
            print("⚠ 非法干支：%s ——请检查四柱是否写错。" % "、".join(bad))

        # ② 四柱内部自洽（五虎遁 / 五鼠遁）——抓「年柱配错月柱」这类手误
        if is_gz(year) and is_gz(month):
            exp = expect_month_gan(year[0], month[1])
            if exp and exp != month[0]:
                print("⚠ 年柱与月柱**不自洽**：年干「%s」配月支「%s」，月干应为「%s」，"
                      "你给的是「%s」——请核对（或你的排盘用了非「立春分年」口径）。"
                      % (year[0], month[1], exp, month[0]))
        if is_gz(day) and is_gz(hour):
            exp = expect_hour_gan(day[0], hour[1])
            if exp and exp != hour[0]:
                print("⚠ 日柱与时柱**不自洽**：日干「%s」配时支「%s」，时干应为「%s」，"
                      "你给的是「%s」——请核对（「晚子时」口径差异亦可能致此）。"
                      % (day[0], hour[1], exp, hour[0]))

        # ③ 顺逆与干支序列（性别写法：男/女/1/0）
        if not is_gz(year):
            print("⚠ 年柱「%s」非法 → 无法由年干阴阳判顺逆，本工具不推大运。" % year)
            return 0
        try:
            g = norm_gender(gender)
        except ValueError:
            print("⚠ 性别「%s」无法识别（应为 男/女/1/0）→ 大运顺逆无从判定。" % gender)
            return 0
        sn = _shun_ni(year[0], g)
        print("性别：%s → 大运%s（年干「%s」为%s）"
              % ("男" if g == 1 else "女", sn, year[0],
                 "阳" if year[0] in YANG_GAN else "阴"))
        seq = dayun_ganzhi(month, sn == "顺排", 8)
        if seq:
            print("大运干支（自月柱「%s」%s推，共 8 步）：%s"
                  % (month, sn, " → ".join(seq)))
            print("  ⚠ **只给干支序列**：这一串由「月柱＋顺逆」唯一确定，不会错。")
            print("  ⚠ **不给起运岁数**：岁数需出生时刻，四柱的时柱只有 2 小时精度，"
                  "且各家虚岁/周岁口径不一——请以你的排盘为准。")
        else:
            print("⚠ 月柱「%s」不是合法干支，无法推大运。" % month)
        print("⚠ 已给四柱时**不重排**：四柱本身（尤以时柱）是否正确，"
              "请与你自己的排盘核对。")
        return 0

    if len(args) < 3:
        _usage()
    nums = []
    for a in args[:5]:
        try:
            nums.append(int(a))
        except ValueError:
            _usage("前五项须为数字：年 月 日 时 [分] [性别]")
    while len(nums) < 5:
        nums.append(0)
    y, m, d, h, mi = nums
    gender = None if no_gender else (args[5] if len(args) > 5 else None)
    if gender is None and not no_gender:
        sys.stderr.write("⚠ 未提供性别 → 按铁律「性别不明不出大运」，只出四柱与节气。\n"
                         "  （大运顺逆由性别定，缺性别排出来必错。）\n")

    r = paipan(y, m, d, h, mi, gender)
    print("=" * 60)
    print(_fmt(r))
    if show_check:
        print("-" * 60)
        print(checklist(r))
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
