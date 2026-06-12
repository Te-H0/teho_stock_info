"""토스 API에서 종목 데이터 수집 + 지표 계산까지."""

import time

import indicators


def collect(toss, stocks: list[dict], indicators_cfg: dict, throttle: float = 0.0) -> tuple:
    """returns (enriched_stocks, prices_raw, candles_raw).
    enriched: 각 종목에 'metrics' 추가. info/캔들 부족 종목은 제외.
    """
    symbols = [s["symbol"] for s in stocks]
    prices = toss.prices(symbols)          # 1콜(다건)
    info = toss.stocks(symbols)            # 1콜(다건)

    enriched, candles_raw = [], {}
    for s in stocks:
        sym = s["symbol"]
        if sym not in info:
            continue
        candles = toss.candles(sym, "1d", 200)   # 종목당 1콜
        candles_raw[sym] = candles
        metrics = indicators.compute(candles, info[sym], indicators_cfg)
        if metrics is None or not metrics.get("marketCap"):
            print(f"  [제외] {sym}({s['name']}): 캔들 부족 또는 발행주식수 없음")
            continue
        enriched.append({**s, "metrics": metrics})
        if throttle:
            time.sleep(throttle)
    return enriched, prices, candles_raw
