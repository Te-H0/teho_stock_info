"""
리서치 JSON + 토스 stocks API 검증 결과로 config/stocks.kr.yaml / stocks.us.yaml 생성.

- 종목명은 토스 공식명으로 통일 (신뢰소스).
- DELISTED 및 부적합 종목은 DROP.
- market/securityType 은 API 기준.
실행: python scripts/build_stocks_yaml.py
"""

import json
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

BASE_URL = "https://openapi.tossinvest.com"
ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"

# 검증으로 확인된 제거 대상
DROP = {
    "048260",  # 오스템임플란트 - DELISTED
    "042670",  # HD현대인프라코어 - DELISTED(통합)
    "377030",  # 비트맥스(舊 맥스트) - XR→가상자산 성격변경, XR 부적합
}


def load_env(path: Path) -> dict:
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def get_token(cid: str, csec: str) -> str:
    body = urllib.parse.urlencode(
        {"grant_type": "client_credentials", "client_id": cid, "client_secret": csec}
    ).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/oauth2/token", data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=15, context=SSL_CONTEXT) as resp:
        return json.loads(resp.read())["access_token"]


def fetch_stocks(token: str, symbols: list[str]) -> dict:
    out = {}
    for i in range(0, len(symbols), 200):
        batch = symbols[i:i + 200]
        url = f"{BASE_URL}/api/v1/stocks?" + urllib.parse.urlencode({"symbols": ",".join(batch)})
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=20, context=SSL_CONTEXT) as resp:
            for item in json.loads(resp.read())["result"]:
                out[item["symbol"]] = item
    return out


def build(stocks: list[dict], info: dict) -> list[dict]:
    rows = []
    for s in stocks:
        sym = s["symbol"]
        api = info.get(sym)
        if sym in DROP or api is None or api.get("status") != "ACTIVE":
            continue
        rows.append({
            "symbol": sym,
            "name": api["name"],            # 토스 공식명으로 통일
            "country": s["country"],
            "market": api["market"],        # API 기준 (KOSPI/KOSDAQ/NASDAQ/NYSE)
            "primarySector": s["primarySector"],
            "tags": s["tags"],
            "leader": bool(s.get("leader", False)),
            "enabled": True,
        })
    return rows


def dump_yaml(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("# 토스 stocks API로 심볼·상장상태·종목명 검증 완료. 종목명은 토스 공식명.\n")
        f.write("# 한 종목은 primarySector(대분류) 1개 + tags(소분류) 여러 개.\n")
        yaml.safe_dump({"stocks": rows}, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


def main() -> None:
    env = load_env(ENV_PATH)
    token = get_token(env["TOSS_CLIENT_ID"], env["TOSS_CLIENT_SECRET"])

    stocks, seen = [], set()
    for f in ["_research_kr.json", "_research_us.json", "_research_add_kr.json", "_research_add_us.json"]:
        p = ROOT / "scripts" / f
        if not p.exists():
            continue
        for s in json.loads(p.read_text(encoding="utf-8")):
            if s["symbol"] in seen:
                continue
            seen.add(s["symbol"])
            stocks.append(s)
    info = fetch_stocks(token, [s["symbol"] for s in stocks])
    rows = build(stocks, info)

    kr = [r for r in rows if r["country"] == "KR"]
    us = [r for r in rows if r["country"] == "US"]
    (ROOT / "config").mkdir(exist_ok=True)
    dump_yaml(ROOT / "config" / "stocks.kr.yaml", kr)
    dump_yaml(ROOT / "config" / "stocks.us.yaml", us)
    print(f"stocks.kr.yaml: {len(kr)}종목, stocks.us.yaml: {len(us)}종목 생성")
    print(f"(DROP {len(DROP)}개 제외)")


if __name__ == "__main__":
    main()
