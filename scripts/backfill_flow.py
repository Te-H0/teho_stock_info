"""투자자별 수급 이력 백필 (1회성).

평소대비·연속 표시는 시장별 수급 시계열이 필요한데 신규 도입이라 과거 데이터가 없다.
KRX에서 최근 N거래일치 코스피/코스닥 외국인·기관·개인 순매수를 받아
data/market/flow_history.json 에 채워 넣는다.

사용: python scripts/backfill_flow.py [거래일수]   (기본 30)
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import flow_history
from lib.config import load_env
from lib.flow import INVESTORS


def main(n_days: int = 30) -> None:
    env = load_env()
    if env.get("KRX_ID"):
        os.environ["KRX_ID"] = env["KRX_ID"]
        os.environ["KRX_PW"] = env.get("KRX_PW", "")
    from pykrx import stock

    today = stock.get_nearest_business_day_in_a_week()
    # 거래일 목록: KOSPI 지수(1001) 일봉 인덱스에서 마지막 n_days개
    cal_from = f"{int(today[:4]) - 1}{today[4:]}"   # 1년 전부터 넉넉히
    bdays = [d.strftime("%Y%m%d")
             for d in stock.get_index_ohlcv_by_date(cal_from, today, "1001").index][-n_days:]
    print(f"백필 대상 {len(bdays)}거래일: {bdays[0]} ~ {bdays[-1]}")

    rows = []
    for d in bdays:
        by_market = {}
        for mkt in ("KOSPI", "KOSDAQ"):
            df = stock.get_market_trading_value_by_investor(d, d, mkt)
            col = "순매수" if "순매수" in df.columns else df.columns[-1]
            by_market[mkt] = {key: float(df.loc[krx, col]) for key, krx, _ in INVESTORS}
        rows.append((d, by_market))
        print(f"  {d} OK", flush=True)

    flow_history.append_many(rows)
    print(f"저장 완료 → {flow_history.PATH}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
