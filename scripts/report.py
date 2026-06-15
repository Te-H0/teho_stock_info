"""텔레그램 친화 브리핑 (parse_mode=Markdown, legacy).
- 헤더 문법(#) 없음 → 이모지+*볼드*로 구조화. 표 없음(모바일).
- 모든 config 문자열(종목/섹터명)은 _esc()로 escape (특수문자로 인한 parse 깨짐 방지).
- session: 아침(미국 리뷰)/마감(한국 정리).
"""

import re

from lib.config import sector_names

DIVIDER = "━━━━━━━━━━━━━━━"

# 종목 줄 변별력 시그널 아이콘 (거래대금은 💰규모로 따로 표시하므로 라벨 생략)
SIG_ICON = {
    "breakout_52w_high": "🏆52주신고가",
    "near_52w_high": "🏆52주근접",
    "breakout_20d_high": "🚀신고가돌파",
    "ma_bullish_alignment": "📐정배열",
    "near_20d_high": "🎯신고가근접",
    "relative_strength_strong": "💪시장강세",
    "volume_surge": "📊거래량급증",
    "ma_bearish_alignment": "🔻역배열",
    "ma20_breakdown": "📛20일선이탈",
}
SIG_ORDER = ["breakout_52w_high", "breakout_20d_high", "ma_bullish_alignment",
             "relative_strength_strong", "near_52w_high", "near_20d_high", "volume_surge"]
WEAK_ORDER = ["ma_bearish_alignment", "ma20_breakdown"]


def _esc(s) -> str:
    """Telegram legacy Markdown에서 깨지는 문자만 escape."""
    return re.sub(r"([_*\[`])", r"\\\1", str(s))


def _sig_names(signals_cfg: dict) -> dict:
    return {s["id"]: s["name"] for s in signals_cfg["stockSignals"] + signals_cfg["sectorSignals"]}


def _won(v: float) -> str:
    if v >= 1e12:
        return f"{v / 1e12:.1f}조"
    if v >= 1e8:
        return f"{v / 1e8:,.0f}억"
    return f"{v:,.0f}"


def _won_flow(v) -> str:
    v = float(v)
    sign = "+" if v >= 0 else "-"
    a = abs(v)
    return f"{sign}{a / 1e12:.1f}조" if a >= 1e12 else f"{sign}{a / 1e8:,.0f}억"


def _headline(market: dict) -> list[str]:
    items = market.get("headline", [])
    idx = [h for h in items if h["key"] != "usdkrw"]
    fx = [h for h in items if h["key"] == "usdkrw"]
    lines = []
    if idx:
        lines.append("  ·  ".join(
            f"{h['name']} *{h['value']:,.0f}* _{h['changeRate']:+.1f}%_" for h in idx))
    if fx:
        h = fx[0]
        lines.append(f"💵 환율 *{h['value']:,.0f}{h['unit']}* _{h['changeRate']:+.1f}%_")
    lines.append(f"📈 오른 종목 *{market['upCount']}/{market['totalCount']}* "
                 f"_({int(market['upRatio'] * 100)}%)_")
    return lines


def _stock_lines(s: dict, icons: list[str], sub_name: dict) -> list[str]:
    """종목 줄: '이름 등락률 · 💰거래대금 · 섹터' (+시그널 있으면 아이콘 줄). US는 거래대금 생략."""
    m = s["metrics"]
    tag0 = s["tags"][0]
    sector = _esc(sub_name.get(tag0, ""))
    tv = "" if s["country"] == "US" else f" · 💰{_won(m['tradingValue'])}"
    lines = [f"*{_esc(s['name'])}* {m['changeRate']:+.1f}%{tv} · _{sector}_"]
    if icons:
        lines.append(f"  {' · '.join(icons)}")   # 표시할 시그널 없으면 줄 생략(빈 '—' 제거)
    return lines


def _flow_ann(v: float, ctx: dict | None, emphasize_z: float, streak_min: int) -> str:
    """수급 한 칸 옆 주석: ' · 4일연속 · 🔥한달최고' 형태(없으면 '')."""
    if not ctx:
        return ""
    parts = []
    z, rank, n = ctx.get("z"), ctx.get("rank"), ctx.get("n")
    if z is not None and abs(z) >= emphasize_z and rank:
        if v >= 0:
            parts.append("🔥20일최고" if rank == 1 else f"🔥상위{rank}위" if rank <= 3 else "🔥상위권")
        else:
            rb = n - rank + 1   # 아래에서 센 순위(1=가장 많이 판)
            parts.append("🧊20일최저" if rb == 1 else f"🧊하위{rb}위" if rb <= 3 else "🧊하위권")
    streak = ctx.get("streak", 1)
    if streak >= streak_min:
        parts.append(f"{streak}일연속")
    return ("  " + " · ".join(f"_{p}_" for p in parts)) if parts else ""


def render(market: dict, sectors: list[dict], stocks: list[dict],
           signals_cfg: dict, sectors_cfg: dict, date: str, session: str,
           strong_score: int = 40, time_str: str = "", flow_cfg: dict | None = None) -> str:
    sub_name, _ = sector_names(sectors_cfg)
    is_morning = session == "morning"
    title = "🇺🇸 🌅 아침 시장 레이더 · 미국 마감" if is_morning else "🇰🇷 🌆 오늘 시장 정리 · 한국 마감"
    market_label = "미국" if is_morning else "한국"

    when = f"{date} {time_str}".strip()
    L = [title, f"_{when} · {market_label} · 정규장 종가_", ""]
    L += _headline(market)
    L.append("")
    L.append(f"💬 {market['summary']}")
    L.append("")

    flow = market.get("flow")
    # 대장주 고정 — 주가 + 투자자별 수급 (한국 close 전용)
    if flow and flow.get("pinnedStocks"):
        by_sym = {s["symbol"]: s for s in stocks}
        L.append(DIVIDER)
        L.append("📌 *대장주*")
        for sym, pf in flow["pinnedStocks"].items():
            s = by_sym.get(sym)
            if not s:
                continue
            m = s["metrics"]
            parts = [f"{e}{_won_flow(pf[k])}" for k, e in
                     (("외국인", "🌍"), ("기관", "🏦"), ("개인", "👤")) if k in pf]
            L.append(f"*{_esc(s['name'])}* {m['changeRate']:+.1f}% {m['close']:,.0f}원")
            if parts:
                L.append(f"  {' · '.join(parts)}")
        L.append("")

    # 투자자별 수급 — 코스피/코스닥 각각 외국인·기관·개인 순매수 (+평소대비·연속)
    if flow and flow.get("byMarket"):
        fc = flow_cfg or {}
        emph = fc.get("emphasize_z", 1.3)
        smin = fc.get("streak_min", 2)
        ctx = flow.get("context") or {}
        L.append(DIVIDER)
        L.append("💰 *투자자별 수급* _(순매수 · 20일대비/연속)_")
        rendered = False
        for mkt, mlabel in (("KOSPI", "🇰🇷 코스피"), ("KOSDAQ", "💹 코스닥")):
            mvals = flow["byMarket"].get(mkt)
            if not mvals:
                continue
            if rendered:
                L.append("")          # 코스피 ↔ 코스닥 사이 빈 줄
            L.append(f"*{mlabel}*")
            mctx = ctx.get(mkt, {})
            for key, e in (("외국인", "🌍"), ("기관", "🏦"), ("개인", "👤")):
                if key not in mvals:
                    continue
                v = mvals[key]
                L.append(f"{e} {key} {_won_flow(v)}{_flow_ann(v, mctx.get(key), emph, smin)}")
            rendered = True
        L.append("")

    # 주체별 담은(🟢) / 판(🔴) 섹터 — 우리 관측 종목 기준
    if flow and flow.get("byInvestor"):
        L.append(DIVIDER)
        L.append("🧭 *주체별 담은·판 섹터* _(🟢산 / 🔴판)_")
        for key in ("외국인", "기관", "개인"):
            bi = flow["byInvestor"].get(key)
            if not bi:
                continue
            L.append(f"{bi['emoji']} *{key}*  🟢{_esc(bi['buy']['sector'])} {_won_flow(bi['buy']['value'])}"
                     f"  🔴{_esc(bi['sell']['sector'])} {_won_flow(bi['sell']['value'])}")
        L.append("")

    # 강세 섹터
    strong = [s for s in sectors if s["score"] >= strong_score][:5] or sectors[:3]
    L.append(DIVIDER)
    L.append("🔥 *강세 섹터* _(시장 대비 · 🏅대장주 🚀신고가)_")
    for i, s in enumerate(strong, 1):
        flags = ""
        if "sector_leaders_strong" in s["signals"]:
            flags += " 🏅"
        if "sector_breakout_many" in s["signals"]:
            flags += "🚀"
        L.append(f"{i}. *{_esc(s['sectorName'])}* _{_esc(s['parentSectorName'])}_  "
                 f"{s['avgChangeRate']:+.1f}% · RS{s['relativeStrength']:+.1f}{flags}")
    L.append("")

    # 약세 섹터
    weak = sorted(sectors, key=lambda x: x["avgChangeRate"])[:3]
    L.append("🧊 *약세 섹터*")
    for i, s in enumerate(weak, 1):
        L.append(f"{i}. *{_esc(s['sectorName'])}* _{_esc(s['parentSectorName'])}_  "
                 f"{s['avgChangeRate']:+.1f}% · RS{s['relativeStrength']:+.1f}")
    L.append("")

    # 대표 종목
    L.append(DIVIDER)
    L.append("⭐ *대표 종목*")
    for s in sorted(stocks, key=lambda x: x["score"], reverse=True)[:6]:
        icons = [SIG_ICON[i] for i in SIG_ORDER if i in s["signals"]][:2]
        if "rsi_overheated" in s["signals"]:
            icons.append("⚠️과열")
        L += _stock_lines(s, icons, sub_name)
        L.append("")

    # 낙폭 주도 종목
    losers = sorted([s for s in stocks if s["metrics"]["changeRate"] < 0],
                    key=lambda x: x["metrics"]["changeRate"])[:4]
    if losers:
        L.append(DIVIDER)
        L.append("🩸 *낙폭 주도*")
        for s in losers:
            icons = [SIG_ICON[i] for i in WEAK_ORDER if i in s["signals"]]
            L += _stock_lines(s, icons, sub_name)
            L.append("")

    # 주목 섹터
    watch_label = "오늘 한국장 주목" if is_morning else "내일 주목"
    watch = list(dict.fromkeys(s["parentSectorName"] for s in strong))[:4]
    L.append(DIVIDER)
    L.append(f"👀 *{watch_label}*")
    L.append("  " + "  ·  ".join(_esc(w) for w in watch) if watch else "  뚜렷한 주도 섹터 없음")
    L.append("")
    L.append("_Market Radar · 섹터 자금흐름 레이더_")
    return "\n".join(L)
