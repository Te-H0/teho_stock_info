"""투자자별 수급의 시장(코스피/코스닥)·주체별 일자 이력.

수급 숫자에 '평소 대비 위치'(최근 N거래일 중 순위·z) 와 '연속 일수'(같은 방향 며칠째)를
붙이기 위한 시계열을 data/market/flow_history.json 에 누적(멱등)한다.

구조:
  {"KOSPI": {"외국인": [["20260615", 1103319046108], ...], "기관": [...], "개인": [...]},
   "KOSDAQ": {...}}
값은 순매수 거래대금(원). 날짜는 pykrx와 동일한 YYYYMMDD.
"""

import json
from pathlib import Path
from statistics import mean, pstdev

DATA = Path(__file__).resolve().parent.parent.parent / "data"
PATH = DATA / "market" / "flow_history.json"

INVESTORS = ("외국인", "기관", "개인")
MARKETS = ("KOSPI", "KOSDAQ")


def _load() -> dict:
    if PATH.exists():
        return json.loads(PATH.read_text(encoding="utf-8"))
    return {}


def _save(doc: dict) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def append(by_market: dict, date: str) -> None:
    """오늘 시장별 수급을 이력에 멱등 추가(같은 날짜 있으면 교체)."""
    doc = _load()
    for mkt, vals in by_market.items():
        for inv, val in vals.items():
            series = doc.setdefault(mkt, {}).setdefault(inv, [])
            series[:] = [e for e in series if e[0] != date]
            series.append([date, float(val)])
            series.sort(key=lambda e: e[0])
    _save(doc)


def append_many(rows: list[tuple]) -> None:
    """백필용. rows = [(date, by_market), ...] 를 한 번에 누적."""
    doc = _load()
    for date, by_market in rows:
        for mkt, vals in by_market.items():
            for inv, val in vals.items():
                series = doc.setdefault(mkt, {}).setdefault(inv, [])
                series[:] = [e for e in series if e[0] != date]
                series.append([date, float(val)])
    for mkt in doc:
        for inv in doc[mkt]:
            doc[mkt][inv].sort(key=lambda e: e[0])
    _save(doc)


def _stats(today: float, series: list[float], min_days: int) -> dict:
    """오늘 값을 과거 series(오름차순) 대비 평가. series는 today 이전 값들."""
    # 연속 일수: 과거를 최근부터 거꾸로, 오늘과 같은 부호인 동안 카운트 (+오늘 1)
    sign = 1 if today >= 0 else -1
    streak = 1
    for v in reversed(series):
        if (1 if v >= 0 else -1) == sign:
            streak += 1
        else:
            break
    if len(series) < min_days:
        return {"streak": streak, "z": None, "rank": None, "n": len(series) + 1}
    m, sd = mean(series), pstdev(series)
    z = (today - m) / sd if sd > 0 else 0.0
    rank = 1 + sum(1 for v in series if v > today)   # 1 = 가장 큰 순매수
    return {"streak": streak, "z": z, "rank": rank, "n": len(series) + 1}


def context(by_market: dict, date: str, window: int, min_days: int) -> dict:
    """시장×주체별로 {streak, z, rank, n} 계산. date 이전 window개만 기준으로."""
    doc = _load()
    out = {}
    for mkt, vals in by_market.items():
        out[mkt] = {}
        for inv, today in vals.items():
            hist = [v for d, v in doc.get(mkt, {}).get(inv, []) if d < date][-window:]
            out[mkt][inv] = _stats(float(today), hist, min_days)
    return out
