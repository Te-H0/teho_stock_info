"""
리서치한 종목 심볼을 토스 stocks API로 검증한다.
- 응답에 없으면 MISSING (오타/미상장/토스 미취급)
- status != ACTIVE 면 INACTIVE
- API 종목명과 우리 종목명이 다르면 NAME_DIFF (눈으로 확인용)
실행: python scripts/verify_symbols.py
"""

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

BASE_URL = "https://openapi.tossinvest.com"
ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"


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
    """symbol -> StockInfo dict. 200개씩 끊어 조회."""
    out = {}
    for i in range(0, len(symbols), 200):
        batch = symbols[i:i + 200]
        url = f"{BASE_URL}/api/v1/stocks?" + urllib.parse.urlencode({"symbols": ",".join(batch)})
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=20, context=SSL_CONTEXT) as resp:
            for item in json.loads(resp.read())["result"]:
                out[item["symbol"]] = item
    return out


def main() -> None:
    env = load_env(ENV_PATH)
    token = get_token(env["TOSS_CLIENT_ID"], env["TOSS_CLIENT_SECRET"])

    stocks = []
    for f in ["_research_kr.json", "_research_us.json"]:
        stocks += json.loads((ROOT / "scripts" / f).read_text(encoding="utf-8"))
    print(f"리서치 종목: {len(stocks)}개")

    symbols = [s["symbol"] for s in stocks]
    info = fetch_stocks(token, symbols)
    print(f"API 응답 종목: {len(info)}개\n")

    missing, inactive, name_diff, ok = [], [], [], 0
    for s in stocks:
        sym, name = s["symbol"], s["name"]
        api = info.get(sym)
        if api is None:
            missing.append((sym, name, s["country"]))
            continue
        if api.get("status") != "ACTIVE":
            inactive.append((sym, name, api.get("status")))
            continue
        if api["name"].replace(" ", "") != name.replace(" ", ""):
            name_diff.append((sym, name, api["name"], api.get("market"), api.get("securityType")))
        ok += 1

    print(f"✅ OK(ACTIVE): {ok}")
    print(f"❌ MISSING(응답없음): {len(missing)}")
    for sym, name, ctry in missing:
        print(f"    {sym}  {name}  ({ctry})")
    print(f"⛔ INACTIVE: {len(inactive)}")
    for sym, name, st in inactive:
        print(f"    {sym}  {name}  status={st}")
    print(f"⚠️ NAME_DIFF (우리이름 → API이름 [market/type]): {len(name_diff)}")
    for sym, ours, api_name, market, stype in name_diff:
        print(f"    {sym}  {ours}  ->  {api_name}  [{market}/{stype}]")


if __name__ == "__main__":
    main()
