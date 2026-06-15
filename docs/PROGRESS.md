# Market Radar — 진행 상황 / 인계

> 새 세션에서 이어서 개발할 때 이 파일부터 읽으면 됨. (마지막 갱신: 2026-06-15)

## ✅ 완료 (MVP 운영 중 — 맥 도커 상시 가동, 매일 자동 발송)

- **데이터 소스**: 토스 Open API(시세·캔들, IP 화이트리스트), yfinance(지수), pykrx(투자자 수급, KRX 계정)
- **종목 유니버스**: KR 156 / US 58 = 214종목, 9대분류/61소섹터. 토스 stocks API 전수 검증
- **지표/시그널**: 4축(돈·추세·상대강도·폭). 시총가중 집계, leader 시총 자동산정. 시그널: 거래대금(단계형)·이동평균·정/역배열·20일&52주 신고가·RSI과열·약세(이탈). 임계값 웹 레퍼런스 평가 반영
- **브리핑** (텔레그램): 헤드라인 지수 + 시장/투자자별 수급 + 강세·약세 섹터(RS) + 대장주 고정(삼성·하이닉스) + 대표·낙폭 종목. escape·줄압축·이모지 정리 완료. 용어 공지 발송
- **수급**(KR close): 외국인/기관/개인을 **코스피/코스닥 분리** 표시 + **20일대비(z-score 🔥/🧊)·연속일수**(`flow_history.json` 누적, 30거래일 백필) + 담은(🟢)/판(🔴) 섹터 + 대장주 종목별. 헤더에 발송시각(KST) 표기. (`docs/decisions/2026-06-15-…`)
- **운영**: 맥 Docker(`docker-compose.yml` restart:always, `scheduler.py`). 발송 — morning(미국) 화~토 07:30 / close(한국) 월~금 **18:00**(시간외 종료 후 수급 확정값). 네트워크 재시도 2단(toss 종목별 + scheduler 10초×3) + 실패 시 IP 텔레 알림
- **git**: GitHub(Te-H0/teho_stock_info, private) 푸시 완료. Secrets 등록(TOSS/TELEGRAM/KRX). Actions yml은 향후 VPS 이전용 보존

## 🔜 남은 작업

1. **주간 리포트 (일요일)** ⭐ — `weekly.py` + LLM. 일주일 누적 자금이동(외인/기관/개인)·섹터 회전·뉴스 종합 해석. 데이터(`data/`)는 일별로 쌓이는 중. **설계는 `docs/weekly-report-notes.md` 참고**
2. **시그널 임계값 튜닝** — 운영 데이터 쌓이면 백테스트(거래대금 2배·RS 1.5 등 검증). `docs/backlog.md`
3. **RS 벤치마크 개선** — 현재 '우리 유니버스' → 진짜 코스피 지수 대비
4. 기타: 섹터 회전, 과열/VI 주의 섹션, 단위 테스트 (backlog)

## 실행법
```
docker compose up -d                              # 상시 가동
docker compose logs -f                            # 로그
docker compose exec market-radar python scripts/main.py close   # 수동 1회
python scripts/main.py [morning|close] [--force]  # 로컬 직접
```
- 세션→시장: `close`=KR(월~금), `morning`=US(화~토). 키는 `.env`.

## 운영 주의
- **맥북 절전 방지 필수** (자면 그 시간 미발송). 전원 연결 + 잠자기 방지.
- 집 IP 바뀌면 토스 차단 → 실행 실패 시 텔레그램으로 새 IP 알림 옴 → 토스 콘솔 재등록.

## 새 세션 시작 프롬프트
> "Market Radar 이어서 개발하자. docs/PROGRESS.md 읽고 [주간 리포트] 진행해줘."

## 문서 맵
- `docs/toss-api.md` — API 레퍼런스 · `docs/weekly-report-notes.md` — 주간 설계
- `docs/decisions/` — 설계 결정 · `docs/backlog.md` — 백로그
- 에이전트: `.claude/agents/`(market-analyst, code-reviewer) · 규칙: `CLAUDE.md`
