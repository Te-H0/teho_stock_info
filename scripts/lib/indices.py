"""헤드라인 지수 조회 (yfinance). 실패해도 본문은 진행되게 graceful."""


def _fetch_one(symbol: str) -> dict | None:
    import yfinance as yf
    h = yf.Ticker(symbol).history(period="7d")["Close"].dropna()
    if len(h) < 2:
        return None
    cur, prev = float(h.iloc[-1]), float(h.iloc[-2])
    return {
        "value": round(cur, 2),
        "changeRate": round((cur - prev) / prev * 100, 2),
        "date": str(h.index[-1].date()),
    }


def fetch_headline(session: str, cfg: dict) -> list[dict]:
    """세션에 맞는 지수 + 공통(환율) 조회. 실패 항목은 조용히 제외."""
    items = list(cfg["headline"].get(session, [])) + list(cfg["headline"].get("always", []))
    out = []
    for it in items:
        try:
            r = _fetch_one(it["symbol"])
        except Exception as e:
            print(f"[지수 조회 실패] {it['name']}({it['symbol']}): {e}")
            r = None
        if r is None:
            continue
        out.append({"key": it["key"], "name": it["name"], "symbol": it["symbol"],
                    "unit": it.get("unit", ""), **r})
    return out
