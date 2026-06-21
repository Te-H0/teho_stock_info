"""JSON 저장/로드. 데이터 계층(raw/stocks/sectors/market) 경로 관리 + 멱등 history."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
REPORTS = ROOT / "reports"


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _read(path: Path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def save_raw(kind: str, date: str, session: str, payload) -> None:
    """kind: 'candles' | 'prices'. API 원본 그대로."""
    _write(DATA / "raw" / kind / date / f"{session}.json", payload)


def save_sectors(date: str, session: str, payload) -> None:
    _write(DATA / "sectors" / date / f"{session}.json", payload)


def save_market(date: str, session: str, payload) -> None:
    _write(DATA / "market" / date / f"{session}.json", payload)


def save_report(date: str, session: str, markdown: str) -> Path:
    path = REPORTS / date / f"{session}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path


def stock_path(country: str, symbol: str) -> Path:
    return DATA / "stocks" / country / f"{symbol}.json"


def update_stock_history(country: str, symbol: str, meta: dict, entry: dict) -> dict:
    """종목별 history에 (date, session) 엔트리를 멱등 갱신(있으면 교체)."""
    path = stock_path(country, symbol)
    doc = _read(path) or {**meta, "history": []}
    hist = doc["history"]
    key = (entry["date"], entry["session"])
    for i, h in enumerate(hist):
        if (h["date"], h["session"]) == key:
            hist[i] = entry
            break
    else:
        hist.append(entry)
    hist.sort(key=lambda h: (h["date"], 0 if h["session"] == "morning" else 1))
    doc.update(meta)
    doc["history"] = hist
    _write(path, doc)
    return doc


def update_index_history(item: dict, date: str) -> None:
    """지수도 종목처럼 날짜별 history로 누적(멱등). data/indices/{key}.json"""
    path = DATA / "indices" / f"{item['key']}.json"
    doc = _read(path) or {"key": item["key"], "name": item["name"],
                          "symbol": item.get("symbol"), "history": []}
    entry = {"date": date, "value": item["value"], "changeRate": item["changeRate"]}
    hist = [h for h in doc["history"] if h["date"] != date]
    hist.append(entry)
    hist.sort(key=lambda h: h["date"])
    doc["history"] = hist
    _write(path, doc)


def last_sent_date(session: str) -> str | None:
    """해당 session으로 마지막에 '실제 발송'한 데이터의 거래일. 없으면 None."""
    doc = _read(DATA / "state" / "last_sent.json") or {}
    return doc.get(session)


def mark_sent(session: str, trade_date: str) -> None:
    """발송 완료한 데이터의 거래일을 기록(다음 실행의 신선도 비교 기준)."""
    path = DATA / "state" / "last_sent.json"
    doc = _read(path) or {}
    doc[session] = trade_date
    _write(path, doc)


def load_prev_metrics(country: str, symbol: str, date: str) -> dict | None:
    """직전(date 이전) history 엔트리의 지표 — RSI 돌파 등 전일 비교용."""
    doc = _read(stock_path(country, symbol))
    if not doc:
        return None
    prev = [h for h in doc["history"] if h["date"] < date]
    return prev[-1] if prev else None
