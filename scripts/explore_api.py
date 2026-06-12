"""
Toss Open API 응답/에러 형태를 실제로 캡처해서 문서화하기 위한 탐색 스크립트.

- 안전한 read-only 엔드포인트(시세/종목/시장정보)만 실제 호출한다.
- 계좌/자산/주문 그룹은 호출하지 않는다 (주문은 실제 매매, 계좌는 개인정보).
- 결과는 콘솔 + docs/api-samples/ 에 JSON 으로 저장한다.

실행: python scripts/explore_api.py   (.env 의 TOSS_CLIENT_ID/SECRET 사용)
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
OUT_DIR = ROOT / "docs" / "api-samples"


def load_env(path: Path) -> dict:
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def get_token(client_id: str, client_secret: str) -> str:
    body = urllib.parse.urlencode(
        {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret}
    ).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/oauth2/token", data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=15, context=SSL_CONTEXT) as resp:
        return json.loads(resp.read())["access_token"]


def call(token: str, name: str, path: str, params: dict | None = None) -> None:
    """엔드포인트 1개 호출 → 콘솔 출력 + 파일 저장. 성공/실패 모두 캡처."""
    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    print(f"\n{'='*70}\n### {name}\nGET {path}" + (f"?{urllib.parse.urlencode(params)}" if params else ""))
    try:
        with urllib.request.urlopen(req, timeout=15, context=SSL_CONTEXT) as resp:
            status, payload = resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        status, payload = e.code, json.loads(e.read())
    print(f"HTTP {status}")
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text[:2000])
    (OUT_DIR / f"{name}.json").write_text(
        json.dumps({"endpoint": path, "params": params, "status": status, "response": payload},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    env = load_env(ENV_PATH)
    cid, csec = env.get("TOSS_CLIENT_ID", ""), env.get("TOSS_CLIENT_SECRET", "")
    if not cid or cid.startswith("여기에") or not csec:
        print("[!] .env 에 키를 먼저 채워주세요.")
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    token = get_token(cid, csec)
    print(f"[OK] 토큰 발급 (len={len(token)})")

    # --- 안전한 read-only 엔드포인트 (Market Data / Stock Info / Market Info) ---
    call(token, "prices", "/api/v1/prices", {"symbols": "005930,000660,AAPL"})
    call(token, "orderbook", "/api/v1/orderbook", {"symbol": "005930"})
    call(token, "trades", "/api/v1/trades", {"symbol": "005930", "count": 3})
    call(token, "price-limits_kr", "/api/v1/price-limits", {"symbol": "005930"})
    call(token, "price-limits_us", "/api/v1/price-limits", {"symbol": "AAPL"})
    call(token, "candles_1d", "/api/v1/candles", {"symbol": "005930", "interval": "1d", "count": 3})
    call(token, "candles_1m", "/api/v1/candles", {"symbol": "005930", "interval": "1m", "count": 3})
    call(token, "stocks", "/api/v1/stocks", {"symbols": "005930,AAPL,069500"})
    call(token, "stock-warnings", "/api/v1/stocks/005930/warnings")
    call(token, "exchange-rate", "/api/v1/exchange-rate", {"baseCurrency": "USD", "quoteCurrency": "KRW"})
    call(token, "market-calendar_kr", "/api/v1/market-calendar/KR")
    call(token, "market-calendar_us", "/api/v1/market-calendar/US")

    # --- 에러 응답 샘플 (존재하지 않는 심볼) ---
    call(token, "error_not-found", "/api/v1/prices", {"symbols": "ZZZZZZ"})

    print(f"\n[완료] 샘플 저장 위치: {OUT_DIR}")


if __name__ == "__main__":
    main()
