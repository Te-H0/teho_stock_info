# Market Radar 📈

섹터/테마 단위 **자금 흐름**을 매일 텔레그램으로 브리핑하는 "시장 레이더".
종목 추천이 아니라 *"오늘 어디에 돈이 몰리는지"*를 본다.

## 무엇을 하나
- 🌅 **화~토 07:30** — 미국 마감 리뷰 (전날 미국장)
- 🌆 **월~금 16:00** — 한국 마감 정리 (+투자자 수급)
- 📅 일요일 — 주간 리포트 (예정)

각 브리핑: 헤드라인 지수 → 강세/약세 섹터(시장 대비 RS) → 투자자별 수급(외인/기관/개인 담은·판 섹터) → 대장주 고정(삼성·하이닉스) → 대표/낙폭 종목.

## 스택
- **데이터**: 토스 Open API(시세·캔들) · yfinance(코스피/나스닥 등 지수) · pykrx(투자자 수급)
- **전송**: 텔레그램 · **저장**: 로컬 JSON(+GitHub)
- **실행**: Docker (맥 상시 가동, `scheduler.py`)

## 실행
```bash
cp .env.example .env        # 키 입력 (토스/텔레그램/KRX)
docker compose up -d        # 상시 가동 → 07:30/16:00 자동 발송
# 수동 1회:
python scripts/main.py close     # 한국 마감
python scripts/main.py morning   # 미국 리뷰
```

## 핵심 자산 = config (이 셋이 "시장을 보는 관점")
- `config/sectors.yaml` — 섹터 트리 (9대분류 / 61소섹터)
- `config/stocks.{kr,us}.yaml` — 종목 214 (KR 156 / US 58, 토스 검증)
- `config/signals.yaml` — 시그널 정의 (ID·조건·점수)
- `config/indicators.yaml` — 지표 파라미터·임계값

## 코드 구조
`scripts/lib/{toss,config,sessions,store,indices,flow}` (공통) +
`collect → indicators → signals → aggregate → report → notify` 파이프라인 +
`main.py`(오케스트레이션) · `scheduler.py`(도커 스케줄러). `scripts/`가 import 루트.

## 운영
- 토스가 **IP 화이트리스트**라 GitHub Actions(동적 IP) 불가 → **맥 도커**로 운영(맥 IP 등록됨). 맥 **절전 방지** 필수.
- 키는 `.env`(gitignore) / GitHub Actions용은 Secrets. IP 바뀌면 실행 실패 시 텔레그램으로 새 IP 알림.

## 문서
- `docs/PROGRESS.md` — 현황·남은 작업·세션 시작 프롬프트
- `docs/toss-api.md` — 토스 API 레퍼런스(함정 포함)
- `docs/decisions/` — 설계 결정 이력
- `docs/weekly-report-notes.md` — 주간 리포트 설계 노트
- `docs/backlog.md` — 백로그
