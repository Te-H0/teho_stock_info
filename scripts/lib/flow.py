"""투자자별 수급 (pykrx, 한국 전용). 외국인/기관/개인의 시장 전체 + 주체별 담은·판 섹터.

KRX_ID/KRX_PW 환경변수 필요. 실패 시 None 반환(본문은 정상 진행).
미국은 이런 투자자별 수급을 공개하지 않으므로 close(한국)에서만 호출.
"""

import os
from collections import defaultdict

# (표시키, KRX 투자자명, 이모지)
INVESTORS = [("외국인", "외국인", "🌍"), ("기관", "기관합계", "🏦"), ("개인", "개인", "👤")]


def fetch_flows(stocks: list[dict], sub_name: dict, pinned: list[str] | None = None) -> dict | None:
    if not (os.environ.get("KRX_ID") and os.environ.get("KRX_PW")):
        return None
    try:
        from pykrx import stock
    except ImportError:
        return None
    try:
        pinned = pinned or []
        d = stock.get_nearest_business_day_in_a_week()
        sym2tags = {s["symbol"]: s["tags"] for s in stocks}
        total = defaultdict(float)
        by_market = {"KOSPI": {}, "KOSDAQ": {}}   # 시장별 주체 순매수 (합치지 않음)
        netsec = {key: defaultdict(float) for key, _, _ in INVESTORS}
        pinned_flow = {sym: {} for sym in pinned}   # 고정 종목별 투자자 순매수

        for mkt in ("KOSPI", "KOSDAQ"):
            inv_df = stock.get_market_trading_value_by_investor(d, d, mkt)
            col = "순매수" if "순매수" in inv_df.columns else inv_df.columns[-1]
            for key, krx, _ in INVESTORS:
                v = float(inv_df.loc[krx, col])
                total[key] += v
                by_market[mkt][key] = v
                df = stock.get_market_net_purchases_of_equities(d, d, mkt, krx)
                for tk, row in df.iterrows():
                    val = float(row["순매수거래대금"])
                    if tk in sym2tags:
                        for tag in sym2tags[tk]:
                            netsec[key][tag] += val
                    if tk in pinned_flow:
                        pinned_flow[tk][key] = val

        by_investor = {}
        for key, _, emoji in INVESTORS:
            s = netsec[key]
            if not s:
                continue
            top = max(s.items(), key=lambda x: x[1])   # 담은(순매수 최대)
            bot = min(s.items(), key=lambda x: x[1])   # 판(순매수 최소=순매도)
            by_investor[key] = {
                "emoji": emoji,
                "buy": {"sector": sub_name.get(top[0], top[0]), "value": round(top[1])},
                "sell": {"sector": sub_name.get(bot[0], bot[0]), "value": round(bot[1])},
            }
        return {
            "date": d,
            "market": {k: round(v) for k, v in total.items()},
            "byMarket": {mkt: {k: round(v) for k, v in vals.items()}
                         for mkt, vals in by_market.items() if vals},
            "byInvestor": by_investor,
            "pinnedStocks": {s: {k: round(v) for k, v in fl.items()}
                             for s, fl in pinned_flow.items() if fl},
        }
    except Exception as e:
        print(f"[수급 조회 실패] {e}")
        return None
