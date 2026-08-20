# Market Radar — 프로젝트 가이드

## 이 프로젝트가 뭔가
주식 **추천** 서비스가 아니다. 매일 시장을 볼 때 "오늘 분위기 좋은지 / 어디에 돈이 몰리는지 / 어떤 섹터·테마가 강해지는지 / 대장주가 같이 움직이는지"를 한눈에 보게 하는 **시장 레이더**다.
핵심은 개별 종목 실시간 가격이 아니라 **섹터/테마 단위의 자금 흐름과 시장 상태를 기록하고 브리핑**하는 것.

핵심 자산은 코드보다 `config/sectors.yaml`, `config/stocks.*.yaml`, `config/signals.yaml` — 이 셋이 "시장을 보는 관점"이다.

## 기술 스택
- Python 3.11
- 데이터 저장소: **DB 없음**. GitHub Repo를 데이터 저장소로 사용 (JSON 파일 + git commit)
- 실행: 맥 도커 상시 가동(`scheduler.py`), 하루 2회 (KST 07:30 아침=미국 마감 리뷰 / KST 18:00 마감=한국 정리·수급 확정)
  - 토스 API가 IP 화이트리스트라 GitHub Actions로는 불가(403). 워크플로는 수동 실행용으로만 남겨둠
- 외부: Toss Invest Open API(시세·캔들·환율·캘린더), Telegram Bot API(전송)
- 의존성: `requests`, `PyYAML`. 지표 계산은 `pandas`/`numpy` 사용 가능

## 데이터 계층 — 절대 섞지 말 것
| 폴더 | 의미 |
|---|---|
| `data/raw/` | API 원본 (가공 전) |
| `data/stocks/` | 종목별 계산 결과 + history |
| `data/sectors/` | 섹터별 집계 |
| `data/market/` | 전체 시장 요약 |
| `reports/` | 사람이 읽는 Markdown 브리핑 |

raw에 계산값을 넣거나, stocks에 원본만 넣는 식으로 섞지 않는다.

## 반드시 지키는 규칙 (안티패턴 금지)
1. **시그널은 ID로 저장.** `"signals": ["trading_value_surge"]` (O) / `["거래대금 급증"]` (X). 사람이 읽는 이름·설명은 `signals.yaml`에서만.
2. **종목·섹터·시그널·지표 기준은 코드에 하드코딩하지 않는다.** 전부 `config/*.yaml`에서 로드. 매직넘버 금지 — 임계값은 yaml에.
3. **API 키 하드코딩 절대 금지.** 환경변수로만 (`TOSS_CLIENT_ID`, `TOSS_CLIENT_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`). 로컬은 `.env`(gitignore), CI는 GitHub Secrets.
4. **멱등성.** 같은 날·같은 session을 재실행해도 history가 중복 append되지 않게 — 기존 (date, session) 엔트리가 있으면 갱신.
5. **휴장일/장애 처리.** 캘린더 API로 장 안 열리는 날은 수집·발송 생략. API 실패 시 조용히 죽지 말고 로그 남기고 가능한 부분만 진행.
6. **세션 개념.** session은 `morning` | `close` 둘뿐. 실행 시각으로 판단.
7. **숫자 타입.** raw JSON은 API가 준 문자열 그대로 둬도 되지만, 계산 단계에서는 숫자로 변환해서 다룬다. 저장 시 가격/거래량은 숫자로.
8. **Toss API 함정** (상세: `docs/toss-api.md`):
   - `prices`/`stocks` 다건 응답은 **순서 비보장** → 항상 `symbol`로 매핑(인덱스 매칭 금지).
   - 없는 심볼은 404가 아니라 **200 + 빈 배열로 누락** → 요청 심볼이 응답에 있는지로 검증.
   - 캔들은 **최신순** → 지표 계산 전 역순 정렬. 토큰은 client당 1개(재발급 시 이전 무효화).
   - 세션 판별은 요일+KST 시간 계산 우선, 캘린더 API는 휴장 보정용 (메모리 `market-hours-strategy`).

## 코드 스타일
- 표준 라이브러리 + 명시적 의존성. 한 함수 한 책임.
- 타입힌트 사용. 파일/함수는 `scripts/` 역할 분리(collect / calculate_indicators / evaluate_signals / build_sector_summary / generate_report / send_telegram / main)를 따른다.
- 시간대는 항상 KST 기준으로 다루되 저장 timestamp는 ISO8601 + offset(`+09:00`).
- 한국어 주석/리포트 OK. 단 코드 식별자(변수·함수·시그널 ID)는 영어.

## 코드 구조 / 실행
- 진행상황·남은 작업은 **`docs/PROGRESS.md`** 참조 (새 세션 시작점).
- 모듈: `scripts/lib/{toss,config,sessions,store}.py` 공통 + `collect → indicators → signals → aggregate → report → notify` 파이프라인, `main.py` 오케스트레이션. `scripts/`가 import 루트(`python scripts/main.py`).
- 실행: `python scripts/main.py [morning|close] [--force] [--no-store]`. 세션→시장: `close`=KR, `morning`=US.
- 지표는 4축(돈·추세·상대강도·폭). 섹터는 **시총가중** 집계, leader는 **시총 자동산정**(`indicators.yaml`). 그래서 `stocks.*.yaml`의 `leader:` 값은 현재 미사용.

## 작업할 때
- 섹터/종목/지표/시그널을 추가·변경·삭제하면 **이유를 `docs/decisions/`에 한 줄이라도 기록**한다. (이 관점 파일들이 곧 자산이라 변경 이력이 중요)
- 시장·지표·테마 관련 판단이 필요하면 `market-analyst` 에이전트와 논의한다.
- 구현 완료 후 품질 점검은 `code-reviewer` 에이전트로.
