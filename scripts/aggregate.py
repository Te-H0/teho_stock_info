"""종목별 결과 → 소섹터 집계 + 시장 요약.
- 시총가중 등락률(자금흐름 대표성)
- leader 시총 자동 산정
- 상대강도(섹터 등락률 - 시장 등락률)
"""

from collections import defaultdict

import signals as sig
from lib.config import sector_names


def weighted_change(members: list[dict]) -> float:
    """시총가중 평균 등락률 (시장/섹터 공통 산식)."""
    den = sum(m["metrics"]["marketCap"] for m in members)
    if not den:
        return 0.0
    num = sum(m["metrics"]["marketCap"] * m["metrics"]["changeRate"] for m in members)
    return round(num / den, 2)


def market_change(stocks: list[dict]) -> float:
    """관측 종목 시총가중 평균 등락률 = 시장 벤치마크."""
    return weighted_change(stocks)


def assign_leaders(stocks: list[dict], indicators_cfg: dict) -> dict:
    """소분류별 시총 상위 top_n symbol 집합. {subId: set(symbols)}."""
    top_n = indicators_cfg["leader"]["top_n"]
    by_sub = defaultdict(list)
    for s in stocks:
        for tag in s["tags"]:
            by_sub[tag].append(s)
    leaders = {}
    for sub, members in by_sub.items():
        ranked = sorted(members, key=lambda x: x["metrics"]["marketCap"], reverse=True)
        leaders[sub] = {m["symbol"] for m in ranked[:top_n]}
    return leaders


def build_sectors(stocks: list[dict], sectors_cfg: dict, signals_cfg: dict,
                  indicators_cfg: dict, mkt_change: float, country: str | None = None) -> list[dict]:
    sub_name, sub_parent = sector_names(sectors_cfg)
    leaders = assign_leaders(stocks, indicators_cfg)

    by_sub = defaultdict(list)
    for s in stocks:
        for tag in s["tags"]:
            by_sub[tag].append(s)

    summaries = []
    for sub_id, members in by_sub.items():
        if sub_id not in sub_name:
            continue
        avg_change = weighted_change(members)

        # 섹터 거래대금 비율: sum(today) / sum(today/ratio). ratio가 0/None인 종목은 제외(0 division 방지)
        tv_today = sum(m["metrics"]["tradingValue"] for m in members)
        tv_base = sum(m["metrics"]["tradingValue"] / m["metrics"]["tradingValueRatio20d"]
                      for m in members if m["metrics"].get("tradingValueRatio20d"))
        tv_ratio = round(tv_today / tv_base, 2) if tv_base else None

        up = [m for m in members if m["metrics"]["changeRate"] > 0]
        up_ratio = round(len(up) / len(members), 2)
        breakout_count = sum(1 for m in members if "breakout_20d_high" in m["signals"])
        leader_syms = leaders.get(sub_id, set())
        leader_up = sum(1 for m in members if m["symbol"] in leader_syms and m["metrics"]["changeRate"] > 0)

        rel_strength = round(avg_change - mkt_change, 2)

        sector_metrics = {
            "relativeStrength": rel_strength,
            "tradingValueRatio20d": tv_ratio,
            "upRatio": up_ratio,
            "leaderUpCount": leader_up,
            "breakoutCount": breakout_count,
        }
        sig_ids, sig_score = sig.evaluate_sector(sector_metrics, signals_cfg, country)
        avg_stock_score = sum(m["score"] for m in members) / len(members)
        score = round(sig_score + avg_stock_score)

        top_stocks = sorted(members, key=lambda x: x["score"], reverse=True)[:3]
        parent_id, parent_name = sub_parent[sub_id]
        summaries.append({
            "sectorId": sub_id,
            "sectorName": sub_name[sub_id],
            "parentSectorId": parent_id,
            "parentSectorName": parent_name,
            "score": score,
            "avgChangeRate": round(avg_change, 2),
            "relativeStrength": rel_strength,
            "totalTradingValue": round(tv_today, 0),
            "tradingValueRatio20d": tv_ratio,
            "upCount": len(up),
            "downCount": len(members) - len(up),
            "upRatio": up_ratio,
            "leaderStocks": sorted(leader_syms),
            "leaderUpCount": leader_up,
            "topStocks": [{"symbol": m["symbol"], "name": m["name"],
                           "changeRate": m["metrics"]["changeRate"], "score": m["score"]}
                          for m in top_stocks],
            "signals": sig_ids,
        })
    summaries.sort(key=lambda x: x["score"], reverse=True)
    return summaries


def build_market(stocks: list[dict], sectors: list[dict], mkt_change: float,
                 date: str, session: str, strong_score: int = 40) -> dict:
    up = sum(1 for s in stocks if s["metrics"]["changeRate"] > 0)
    total = len(stocks)
    breadth = up / total if total else 0

    strong = [s for s in sectors if s["score"] >= strong_score][:5]
    weak = sorted(sectors, key=lambda x: x["avgChangeRate"])[:3]

    return {
        "date": date,
        "session": session,
        "marketChange": mkt_change,
        "upCount": up,
        "downCount": total - up,
        "totalCount": total,
        "upRatio": round(breadth, 2),
        "strongSectors": [s["sectorId"] for s in strong],
        "weakSectors": [s["sectorId"] for s in weak],
        "summary": _summary_text(strong, mkt_change),
    }


def _summary_text(strong: list[dict], mkt_change: float) -> str:
    tone = "강세" if mkt_change > 0.3 else ("약세" if mkt_change < -0.3 else "혼조")
    if strong:
        names = ", ".join(s["sectorName"] for s in strong[:3])
        return f"시장 {tone}({mkt_change:+.2f}%). {names} 섹터로 자금 유입 감지."
    return f"시장 {tone}({mkt_change:+.2f}%). 뚜렷한 주도 섹터 없음."
