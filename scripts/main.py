"""Market Radar 전체 실행.

사용법:
    python scripts/main.py                # 시각으로 세션 자동판별
    python scripts/main.py close          # 세션 강제 (close=한국마감 / morning=미국리뷰)
    python scripts/main.py close --force  # 휴장이어도 강제 실행(테스트용)
    python scripts/main.py close --no-store  # data 저장 생략
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/ 를 import 루트로

import collect
import aggregate
import report
from lib import flow, flow_history, indices, sessions, store
from lib.config import (load_benchmarks, load_env, load_indicators, load_sectors,
                        load_signals, load_stocks, sector_names)
from lib.toss import TossClient
from notify import Notifier
from signals import evaluate_stock


def run() -> None:
    args = sys.argv[1:]
    force = "--force" in args
    do_store = "--no-store" not in args
    session = next((a for a in args if a in ("morning", "close")), None) or sessions.detect_session()
    country = sessions.SESSION_COUNTRY[session]
    now = sessions.now_kst()
    date = sessions.today_str(now)
    time_str = now.strftime("%H:%M")   # 발송(실행) 시각 — KST

    env = load_env()
    if not env.get("TOSS_CLIENT_ID") or not env.get("TOSS_CLIENT_SECRET"):
        print("[!] .env 에 TOSS_CLIENT_ID / TOSS_CLIENT_SECRET 필요")
        return

    toss = TossClient(env["TOSS_CLIENT_ID"], env["TOSS_CLIENT_SECRET"])

    # 발송일 판정:
    #  - close(한국): 한국 영업일(평일·비공휴일)
    #  - morning(미국): 미국장 다음 한국 아침(화~토). 월요일·일요일 아침엔 미국을 보내지 않음.
    if session == "close":
        ok = sessions.is_market_open("KR", toss)
    else:
        ok = sessions.is_us_review_day()
    if not force and not ok:
        print(f"[휴장] {date} {session} 발송일 아님 → 수집/발송 생략")
        return

    sectors_cfg = load_sectors()
    signals_cfg = load_signals()
    indicators_cfg = load_indicators()
    stocks = load_stocks(country)
    print(f"[{date} {session}/{country}] 종목 {len(stocks)}개 수집 시작...")

    enriched, prices, candles_raw = collect.collect(toss, stocks, indicators_cfg, throttle=0.03)
    print(f"수집/지표 완료: {len(enriched)}개")
    if not enriched:
        print("[!] 유효 종목 없음")
        return

    # 신선도 가드: 수집 데이터의 최신 거래일이 직전 발송과 같으면(=새 장 데이터 없음:
    # 공휴일·임시휴장 등) 발송 생략. 토스는 휴장일에 직전 거래일 캔들을 그대로 주므로
    # 캘린더 타임존에 의존하지 않고 데이터 자체로 판정한다.
    data_date = collect.latest_trade_date(enriched)
    last_sent = store.last_sent_date(session)
    if not force and data_date and last_sent and data_date <= last_sent:
        print(f"[데이터 미갱신] {session}: 최신 거래일 {data_date} 가 직전 발송({last_sent})과 동일 → 발송 생략")
        return

    # 시장 벤치마크 → 상대강도 주입 → 종목 시그널/점수
    mkt_change = aggregate.market_change(enriched)
    for s in enriched:
        s["metrics"]["relativeStrength"] = round(s["metrics"]["changeRate"] - mkt_change, 2)
        ids, score = evaluate_stock(s["metrics"], signals_cfg, country)
        s["signals"] = ids
        s["score"] = score

    strong_score = indicators_cfg.get("scoring", {}).get("sector_strong_score", 40)
    sectors = aggregate.build_sectors(enriched, sectors_cfg, signals_cfg, indicators_cfg, mkt_change, country)
    market = aggregate.build_market(enriched, sectors, mkt_change, date, session, strong_score)

    # 헤드라인 지수 (yfinance). 실패해도 본문 진행.
    headline = indices.fetch_headline(session, load_benchmarks())
    market["headline"] = headline

    # 투자자별 수급 (한국 close 전용, pykrx). 실패해도 본문 진행.
    if session == "close" and env.get("KRX_ID"):
        os.environ["KRX_ID"] = env["KRX_ID"]
        os.environ["KRX_PW"] = env.get("KRX_PW", "")
        sub_name, _ = sector_names(sectors_cfg)
        market["flow"] = flow.fetch_flows(stocks, sub_name, indicators_cfg.get("pinned_stocks", []))
        # 평소대비 위치·연속일수 (시장별 수급 이력 기준)
        fl = market["flow"]
        if fl and fl.get("byMarket"):
            fcfg = indicators_cfg.get("flow", {})
            fl["context"] = flow_history.context(
                fl["byMarket"], fl["date"],
                fcfg.get("baseline_window", 20), fcfg.get("baseline_min_days", 8))

    if do_store:
        store.save_raw("prices", date, session, prices)
        store.save_raw("candles", date, session,
                       {sym: c for sym, c in candles_raw.items()})
        store.save_sectors(date, session, sectors)
        store.save_market(date, session, market)
        _fl = market.get("flow")
        if _fl and _fl.get("byMarket"):
            flow_history.append(_fl["byMarket"], _fl["date"])
        for h in headline:
            store.update_index_history(h, h["date"])
        for s in enriched:
            meta = {k: s[k] for k in ("symbol", "name", "country", "market",
                                      "primarySector", "tags")}
            m = dict(s["metrics"])
            trade_date = m.pop("tradeDate", date)   # 종목 시계열은 실제 거래일 기준 (KST 발송일 아님)
            entry = {"date": trade_date, "session": session, **m,
                     "signals": s["signals"], "score": s["score"]}
            store.update_stock_history(country, s["symbol"], meta, entry)

    md = report.render(market, sectors, enriched, signals_cfg, sectors_cfg, date, session,
                       strong_score, time_str=time_str, flow_cfg=indicators_cfg.get("flow", {}))
    if do_store:
        path = store.save_report(date, session, md)
        print(f"리포트 저장: {path}")

    Notifier(env).send(md)
    if do_store and data_date:
        store.mark_sent(session, data_date)   # 다음 실행의 신선도 비교 기준 갱신


if __name__ == "__main__":
    run()
