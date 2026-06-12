# 토스증권 Open API 레퍼런스 (Market Radar 용)

> 원문: https://developers.tossinvest.com/docs · OpenAPI 1.0.3
> 이 문서는 실제 호출로 확인한 응답 + 스펙을 정리한 것. 시세값은 캡처 시점(2026-06-12) 예시.
> 원본 샘플 JSON: `docs/api-samples/*.json` (`scripts/explore_api.py` 로 재생성).

- **Base URL**: `https://openapi.tossinvest.com`
- **인증**: OAuth2 Client Credentials. 토큰을 `Authorization: Bearer {token}` 헤더로.
- 성공 응답은 `{ "result": ... }` envelope, 실패는 `{ "error": {...} }` (토큰 엔드포인트만 OAuth 표준 형식).

## ⚠️ 구현 시 반드시 지킬 함정 (실측으로 확인)

| 함정 | 내용 | 대응 |
|---|---|---|
| **응답 순서 비보장** | `prices`/`stocks` 다건 조회 시 응답 배열 순서가 **요청 순서와 다름** | 결과를 `symbol` 키로 dict 매핑. 인덱스 매칭 금지 |
| **없는 심볼 = 빈 배열** | 잘못된 심볼도 `404`가 아니라 `200` + 해당 항목 **누락** | 요청 심볼이 응답에 있는지로 유효성 판단 |
| **모든 숫자가 문자열** | `"327500"`, US는 소수점 `"296.7327"` | 계산 단계에서 `float`/`Decimal` 변환 |
| **캔들 최신순(내림차순)** | `[06-12, 06-11, 06-10...]` | 지표 계산 전 역순 정렬(오름차순) |
| **거래대금 없음** | 캔들/현재가에 거래대금 필드 없음 | `tradingValue = close * volume` 계산 |
| **타임스탬프 ms 포함** | `2026-06-12T19:09:55.557+09:00` (ms 자릿수 가변) | `datetime.fromisoformat` (3.11+) |
| **Rate Limit 그룹 분리** | 캔들은 `MARKET_DATA_CHART`, 시세는 `MARKET_DATA` 로 한도 별도 | 종목당 캔들 1콜이라 종목 많으면 캔들이 병목 |

## 인증 — `POST /oauth2/token`

`application/x-www-form-urlencoded`, `Authorization` 헤더 없이 호출. (스펙상 Basic도 언급되나 **client_secret_post 방식이 정상 동작 확인**.)

```
grant_type=client_credentials&client_id=...&client_secret=...
```

응답: `{ "access_token": "...", "token_type": "Bearer", "expires_in": 86400 }`
- 만료 24h. refresh token 없음 → 만료 시 동일 엔드포인트 재발급.
- **client당 유효 토큰 1개** — 재발급하면 이전 토큰 즉시 무효화. (GitHub Actions에서 매 실행 새로 발급하면 됨)
- 인증 실패: `401 { "error": "invalid_client", "error_description": "...client_secret" }`

---

# 우리가 쓰는 엔드포인트

## 현재가 — `GET /api/v1/prices?symbols=...`
- 최대 200개 콤마 구분 **한 번에**. (장중 브리핑 핵심)
- 응답: `result[]` of `{ symbol, timestamp(nullable), lastPrice, currency }`
```json
{"result":[{"symbol":"005930","timestamp":"2026-06-12T19:09:55.000+09:00","lastPrice":"327500","currency":"KRW"}]}
```

## 캔들 — `GET /api/v1/candles?symbol=...&interval=1d|1m&count=200`
- **종목당 1콜** (symbol 단건). count 최대 200, 최신순 정렬.
- `before`(ISO8601, exclusive) + 응답의 `nextBefore`로 페이지네이션 → 200봉 초과 확보(52주 신고가 정밀화).
- `adjusted`(기본 true) 수정주가.
- 응답: `result.candles[]` of `{ timestamp, openPrice, highPrice, lowPrice, closePrice, volume, currency }`, `result.nextBefore`(마지막이면 null)
```json
{"result":{"candles":[{"timestamp":"2026-06-12T00:00:00.000+09:00","openPrice":"313000","highPrice":"339000","lowPrice":"313000","closePrice":"327500","volume":"59150441","currency":"KRW"}],"nextBefore":"2026-06-09T00:00:00.000+09:00"}}
```

## 종목 기본정보 — `GET /api/v1/stocks?symbols=...`
- 최대 200개 콤마. 심볼 유효성·종목명·상장상태·발행주식수 확인용. **하루 1회 캐시 권장**(자주 안 바뀜).
- 응답: `result[]` of `StockInfo` — `{ symbol, name, englishName, market(KOSPI|KOSDAQ|NYSE|NASDAQ|AMEX|...), securityType(STOCK|ETF|ETN|REIT|...), status(SCHEDULED|ACTIVE|DELISTED), currency, listDate, delistDate, sharesOutstanding, leverageFactor, koreanMarketDetail }`
- `koreanMarketDetail`: `{ liquidationTrading(정리매매), nxtSupported, krxTradingSuspended, nxtTradingSuspended }` (해외는 null)
- **종목 리서치 후 심볼 검증에 사용**: 요청 심볼이 응답에 없거나 `status != ACTIVE`면 거름.

## 환율 — `GET /api/v1/exchange-rate?baseCurrency=USD&quoteCurrency=KRW`
- 1분 갱신, 참고용. 응답: `{ baseCurrency, quoteCurrency, rate, midRate, basisPoint, rateChangeType(UP|EQUAL|DOWN), validFrom, validUntil }`

## 장 캘린더 — `GET /api/v1/market-calendar/KR` · `/US`
- **휴장 안전장치 전용** (세션 판별은 요일+KST 시간 계산이 우선 — `market-hours` 메모리 참조).
- 전일/당일/익일 3영업일. 모든 시간 KST.
- **KR**: `today.integrated` 가 null이면 휴장. `integrated = { preMarket, regularMarket, afterMarket }` 각 nullable.
  - 정규장 09:00–15:30, 프리 08:00–09:00, 애프터 15:30–20:00 (KST)
- **US**: 4세션 `dayMarket / preMarket / regularMarket / afterMarket` 각 nullable, 모두 null이면 휴장.
  - 실측: dayMarket 09:00–17:00, preMarket 17:00–22:30, regularMarket 22:30–05:00(+1), afterMarket 05:00–08:50 (KST, 서머타임 기준)

## 매수 유의사항 — `GET /api/v1/stocks/{symbol}/warnings`
- (선택) risk 시그널 보강용. 응답: `result[]` of `{ warningType, exchange, startDate, endDate }`, 없으면 `[]`.
- `warningType`: `LIQUIDATION_TRADING|OVERHEATED|INVESTMENT_WARNING|INVESTMENT_RISK|VI_STATIC|VI_DYNAMIC|VI_STATIC_AND_DYNAMIC|STOCK_WARRANTS`

---

# 기타 read-only (현재 미사용, 참고)

| 엔드포인트 | 용도 | 응답 핵심 |
|---|---|---|
| `GET /api/v1/orderbook?symbol=` | 10호가 | `{ timestamp, currency, asks[], bids[] }` (각 `{price, volume}`) |
| `GET /api/v1/trades?symbol=&count=` | 최근 체결 (최대 50) | `result[]` `{ price, volume, timestamp, currency }` |
| `GET /api/v1/price-limits?symbol=` | 상/하한가 | `{ timestamp, upperLimitPrice, lowerLimitPrice, currency }` (US는 limit null) |

---

# 계좌·주문 그룹 (⛔ 미사용 — 실제 호출 안 함)

Market Radar는 시세만 쓰므로 **호출하지 않는다.** 주문은 실제 매매가 체결되고, 계좌/자산은 개인정보(계좌번호·잔고)가 노출되므로 안전상 제외. 아래는 스펙 참고용 요약.

- `GET /api/v1/accounts` — 계좌 목록. `accountSeq`는 이후 계좌 API의 `X-Tossinvest-Account` 헤더값.
- `GET /api/v1/holdings` — 보유 주식 (계좌 헤더 필요)
- `POST /api/v1/orders` — **주문 생성 (실매매, 절대 호출 금지)**
- `GET /api/v1/orders`, `/orders/{id}` — 주문 목록/상세
- `POST /api/v1/orders/{id}/modify` · `/cancel` — 정정/취소
- `GET /api/v1/buying-power`, `/sellable-quantity`, `/commissions` — 주문 전 정보

> 계좌 컨텍스트 API는 모두 `X-Tossinvest-Account: {accountSeq}` 헤더 필요.

---

# 공통 에러

실패 응답: `{ "error": { "requestId", "code", "message", "data?" } }` (4xx/5xx).
- 클라이언트는 **unknown code 허용**하도록 구현 (toss가 코드 추가 가능).
- `X-Request-Id` 헤더 = `error.requestId` (CS 문의용).

| code | 상황 |
|---|---|
| `invalid-request` | 파라미터 오류 (`data.field`, `constraint`, `allowedValues` 등 힌트 포함) |
| `stock-not-found` | 단건 symbol 엔드포인트에서 종목 없음 (404). ※ `prices`/`stocks` 다건은 빈배열로 누락 |
| `invalid-token` / `expired-token` | 토큰 무효/만료 (401, `WWW-Authenticate` 헤더) |
| `rate-limit-exceeded` | 429. `X-RateLimit-*`, `Retry-After` 헤더 확인 후 재시도 |
| `internal-error` / `maintenance` | 500. `data.retryAfterSeconds` 있으면 그만큼 대기 |

## Rate Limit 헤더 (429 시)
`X-RateLimit-Limit`(초당 허용), `X-RateLimit-Remaining`(남은 토큰, 429면 0), `X-RateLimit-Reset`(재충전 초), `Retry-After`(권장 재시도 초).
그룹: `AUTH` / `MARKET_DATA` / `MARKET_DATA_CHART`(캔들) / `STOCK` / `MARKET_INFO`. → **캔들은 별도 한도**라 종목 수 많을 때 throttle 필요.
