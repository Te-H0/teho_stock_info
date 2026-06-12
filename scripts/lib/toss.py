"""토스증권 Open API 클라이언트. 상세 스펙: docs/toss-api.md"""

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL = ssl.create_default_context()

BASE_URL = "https://openapi.tossinvest.com"


class TossError(RuntimeError):
    pass


class TossClient:
    def __init__(self, client_id: str, client_secret: str):
        self._id = client_id
        self._secret = client_secret
        self._token: str | None = None

    # --- 내부 ---
    def _ensure_token(self) -> str:
        if self._token is None:
            body = urllib.parse.urlencode({
                "grant_type": "client_credentials",
                "client_id": self._id,
                "client_secret": self._secret,
            }).encode()
            req = urllib.request.Request(
                f"{BASE_URL}/oauth2/token", data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=15, context=_SSL) as r:
                    self._token = json.loads(r.read())["access_token"]
            except urllib.error.HTTPError as e:
                raise TossError(f"토큰 발급 실패 {e.code}: {e.read().decode(errors='replace')}")
        return self._token

    def _get(self, path: str, params: dict | None = None, retries: int = 3) -> dict:
        token = self._ensure_token()
        url = f"{BASE_URL}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=20, context=_SSL) as r:
                    return json.loads(r.read())["result"]
            except urllib.error.HTTPError as e:
                # 429: rate limit → Retry-After 만큼 대기 후 재시도
                if e.code == 429 and attempt < retries - 1:
                    wait = int(e.headers.get("Retry-After", "1") or "1")
                    time.sleep(max(1, wait))
                    continue
                raise TossError(f"{path} 실패 {e.code}: {e.read().decode(errors='replace')}")
            except (urllib.error.URLError, TimeoutError) as e:
                # 일시적 네트워크(와이파이 끊김 등) → 잠깐 쉬고 재시도
                if attempt < retries - 1:
                    time.sleep(3)
                    continue
                raise TossError(f"{path} 네트워크 실패: {e}")
        raise TossError(f"{path} 재시도 초과")

    # --- 공개 API ---
    def prices(self, symbols: list[str]) -> dict:
        """symbol -> {timestamp, lastPrice, currency}. 순서 비보장 → dict로 매핑."""
        out = {}
        for i in range(0, len(symbols), 200):
            for item in self._get("/api/v1/prices", {"symbols": ",".join(symbols[i:i + 200])}):
                out[item["symbol"]] = item
        return out

    def stocks(self, symbols: list[str]) -> dict:
        """symbol -> StockInfo (발행주식수 등). 순서 비보장 → dict로 매핑."""
        out = {}
        for i in range(0, len(symbols), 200):
            for item in self._get("/api/v1/stocks", {"symbols": ",".join(symbols[i:i + 200])}):
                out[item["symbol"]] = item
        return out

    def candles(self, symbol: str, interval: str = "1d", count: int = 200) -> list:
        """OHLCV. 토스는 최신순 → **오름차순(과거→현재)으로 정렬해 반환**."""
        res = self._get("/api/v1/candles", {"symbol": symbol, "interval": interval, "count": count})
        candles = res.get("candles", [])
        return list(reversed(candles))

    def exchange_rate(self, base: str = "USD", quote: str = "KRW") -> dict:
        return self._get("/api/v1/exchange-rate", {"baseCurrency": base, "quoteCurrency": quote})

    def market_calendar(self, country: str) -> dict:
        return self._get(f"/api/v1/market-calendar/{country}")
