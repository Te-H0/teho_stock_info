"""종목별 지표 계산. 캔들(오름차순) + 종목정보(발행주식수)로 metric dict 생성.

모든 입력 숫자는 토스 API의 문자열이므로 float 변환해서 다룬다(CLAUDE.md 규칙).
"""


def _f(x) -> float:
    return float(x)


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains, losses = 0.0, 0.0
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain, avg_loss = gains / period, losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute(candles: list[dict], info: dict, cfg: dict) -> dict | None:
    """일봉 기준 지표. candles는 오름차순(과거→오늘). 마지막이 당일."""
    if len(candles) < 2:
        return None
    closes = [_f(c["closePrice"]) for c in candles]
    highs = [_f(c["highPrice"]) for c in candles]
    volumes = [_f(c["volume"]) for c in candles]
    trading_values = [closes[i] * volumes[i] for i in range(len(closes))]

    close = closes[-1]
    prev_close = closes[-2]
    change_rate = (close - prev_close) / prev_close * 100 if prev_close else 0.0

    ma_periods = cfg["moving_averages"]
    mas = {f"ma{p}": sma(closes, p) for p in ma_periods}

    vol_p = cfg["volume"]["avg_period"]
    tv_p = cfg["trading_value"]["avg_period"]
    vol_avg = sma(volumes[:-1], vol_p)            # 당일 제외 직전 평균 대비
    tv_avg = sma(trading_values[:-1], tv_p)
    volume_ratio = volumes[-1] / vol_avg if vol_avg else None
    tv_ratio = trading_values[-1] / tv_avg if tv_avg else None

    short_n = cfg["high"]["short"]
    long_n = cfg["high"]["long"]
    # 기간이 충분히 쌓였을 때만 신고가 계산 (상장 초기 종목의 거짓 '신고가' 방지)
    high20 = max(highs[-short_n:]) if len(highs) >= short_n else None
    high_long = max(highs[-long_n:]) if len(highs) >= long_n else None

    shares = _f(info["sharesOutstanding"]) if info.get("sharesOutstanding") else 0.0
    market_cap = shares * close

    today = candles[-1]
    return {
        # 거래일(캔들 실제 날짜). 한국 월요일 아침에 미국 금요일 데이터를 수집해도 history는 거래일로 저장.
        "tradeDate": str(today["timestamp"])[:10],
        # OHLCV 원본 보존 (주간 리포트에서 가격흐름 분석용)
        "open": _f(today["openPrice"]),
        "high": _f(today["highPrice"]),
        "low": _f(today["lowPrice"]),
        "close": close,
        "volume": volumes[-1],
        "changeRate": round(change_rate, 2),
        "tradingValue": round(trading_values[-1], 0),
        "marketCap": round(market_cap, 0),
        **{k: (round(v, 2) if v is not None else None) for k, v in mas.items()},
        "rsi14": (lambda r: round(r, 1) if r is not None else None)(rsi(closes, cfg["rsi"]["period"])),
        # is not None: 비율이 정확히 0.0(거래정지 등)일 때 None으로 뭉개지 않도록
        "volumeRatio20d": round(volume_ratio, 2) if volume_ratio is not None else None,
        "tradingValueRatio20d": round(tv_ratio, 2) if tv_ratio is not None else None,
        "high20": high20,
        "highLong": high_long,
        # relativeStrength는 시장 벤치마크 확정 후 main에서 주입
    }
