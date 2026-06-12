"""
Toss Invest Open API 연결 검증용 PoC.

목적: 본격 구현 전에 (1) 토큰 발급, (2) 현재가, (3) 일봉, (4) 환율,
(5) 국내 장 캘린더 응답이 스펙대로 오는지 실제로 확인한다.

의존성 없음 (stdlib만). 실행:
    python scripts/poc_toss.py
키는 프로젝트 루트의 .env 에서 읽는다 (TOSS_CLIENT_ID / TOSS_CLIENT_SECRET).
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
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env(path: Path) -> dict:
    """아주 단순한 .env 파서 (KEY=VALUE)."""
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def get_token(client_id: str, client_secret: str) -> str:
    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/oauth2/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15, context=SSL_CONTEXT) as resp:
        data = json.loads(resp.read())
    return data["access_token"]


def api_get(token: str, path: str, params: dict | None = None) -> dict:
    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15, context=SSL_CONTEXT) as resp:
        return json.loads(resp.read())


def show(title: str, payload) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:1500])


def main() -> None:
    env = load_env(ENV_PATH)
    client_id = env.get("TOSS_CLIENT_ID", "").strip()
    client_secret = env.get("TOSS_CLIENT_SECRET", "").strip()

    if not client_id or client_id.startswith("여기에") or not client_secret:
        print("[!] .env 에 TOSS_CLIENT_ID / TOSS_CLIENT_SECRET 를 먼저 채워주세요.")
        return

    try:
        token = get_token(client_id, client_secret)
        print(f"[OK] 토큰 발급 성공 (len={len(token)})")
    except urllib.error.HTTPError as e:
        print(f"[X] 토큰 발급 실패 {e.code}: {e.read().decode(errors='replace')}")
        return

    # 1) 현재가 — KR 2종목 + US 1종목 한 번에
    try:
        prices = api_get(token, "/api/v1/prices", {"symbols": "005930,000660,AAPL"})
        show("현재가 /api/v1/prices", prices)
    except urllib.error.HTTPError as e:
        print(f"[X] prices 실패 {e.code}: {e.read().decode(errors='replace')}")

    # 2) 일봉 — 삼성전자 5봉
    try:
        candles = api_get(
            token, "/api/v1/candles",
            {"symbol": "005930", "interval": "1d", "count": "5"},
        )
        show("일봉 /api/v1/candles (005930, 5봉)", candles)
    except urllib.error.HTTPError as e:
        print(f"[X] candles 실패 {e.code}: {e.read().decode(errors='replace')}")

    # 3) 환율 — USD/KRW
    try:
        fx = api_get(
            token, "/api/v1/exchange-rate",
            {"baseCurrency": "USD", "quoteCurrency": "KRW"},
        )
        show("환율 /api/v1/exchange-rate (USD->KRW)", fx)
    except urllib.error.HTTPError as e:
        print(f"[X] exchange-rate 실패 {e.code}: {e.read().decode(errors='replace')}")

    # 4) 국내 장 캘린더 (오늘 개장 여부 판단용)
    try:
        cal = api_get(token, "/api/v1/market-calendar/KR")
        show("국내 장 캘린더 /api/v1/market-calendar/KR", cal)
    except urllib.error.HTTPError as e:
        print(f"[X] market-calendar 실패 {e.code}: {e.read().decode(errors='replace')}")

    print("\n[완료] 위 응답들이 스펙과 맞는지 확인해주세요.")


if __name__ == "__main__":
    main()
