# Market Radar — 진행 상황 / 인계

> 새 세션에서 이어서 개발할 때 이 파일부터 읽으면 됨. (마지막 갱신: 2026-06-12)

## ✅ 완료 (MVP 코어 — 오늘 마감 브리핑 채팅 출력까지 동작 확인)

- **메타**: `CLAUDE.md`(코딩 규칙·함정), 에이전트 2개(`.claude/agents/` — 🔵market-analyst, 🟢code-reviewer, 둘 다 opus-4-8), `docs/decisions/`
- **데이터 소스 검증**: 토스 Open API 전 엔드포인트 응답 확인 → `docs/toss-api.md`(함정 포함). PoC/탐색 스크립트(`poc_toss.py`, `explore_api.py`)
- **종목 유니버스**: `config/sectors.yaml`(9대분류/55소섹터), `config/stocks.kr.yaml`(126), `config/stocks.us.yaml`(48) — 토스 stocks API로 전수 검증, 종목명 토스 공식명 통일
- **지표·시그널 설계**: `config/indicators.yaml`, `config/signals.yaml` — "돈·추세·상대강도·폭" 4축. MACD/스토캐스틱 제외. 시총가중 집계, leader 시총 자동산정
- **파이프라인 구현** (`scripts/`):
  - `lib/toss.py`(클라이언트), `lib/config.py`, `lib/sessions.py`, `lib/store.py`
  - `collect.py` → `indicators.py` → `signals.py` → `aggregate.py`(섹터+시장) → `report.py` → `notify.py`(console/telegram/slack)
  - `main.py` 오케스트레이션. `python scripts/main.py close` 로 동작 확인됨
- **데이터 저장**: `data/{raw,stocks,sectors,market,indices}`, `reports/` 생성·저장 동작
- **코드리뷰 반영 완료**: 🔴(거래량 0처리/섹터 0division/미국 날짜오염→거래일 저장) + 🟡(신고가 기간가드/eval오타경고/시총가중 헬퍼/임계값 yaml화) + 🟢(throttle/탈락로그) 전부 수정
- **하락장 대칭**: 약세 섹터 RS 표시 + 📉낙폭 주도 종목 섹션 + 약세 시그널(역배열·20일선이탈). 헤드라인 `📈 오른 종목 N/M`로 명확화
- **수급(투자자별)**: ✅ pykrx + KRX 계정으로 동작. 헤드라인 시장 수급(외국인/기관/개인) + 투자자별 담은/판 섹터 섹션. `lib/flow.py`, KR close 전용
- **시그널 TOP3 반영**: 거래대금 폭증(3배 +5 누적), 52주(200일) 신고가 돌파/근접, 200일선 상회 (웹 레퍼런스 평가 근거)
- **GitHub Actions yml 작성됨**: `.github/workflows/market-radar.yml` (아침 cron `30 22 * * 0-4` / 마감 `0 7 * * 1-5`). 깃 푸시 + Secrets 등록만 하면 자동 동작

## ⚙️ 운영 시작에 필요한 것 (사용자)
1. **GitHub 레포**: `git init` → 레포 생성 → 푸시 (현재 git 레포 아님)
2. **Secrets 등록** (레포 Settings → Secrets and variables → Actions): `TOSS_CLIENT_ID`, `TOSS_CLIENT_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `KRX_ID`, `KRX_PW`
3. **텔레그램 봇**: 아래 PROGRESS 끝 "텔레봇 설정" 참고
- **헤드라인 지수**: `config/benchmarks.yaml` + `lib/indices.py`(yfinance) — 코스피(^KS11)·코스닥(^KQ11)·환율(KRW=X), 아침은 S&P(^GSPC)·나스닥(^IXIC). `data/indices/{key}.json`에 날짜별 history 누적. 실패 시 graceful skip
- **브리핑 포맷 확정**: 텔레그램(parse_mode=Markdown). 헤드라인 지수 + 거래대금(💰조/억) 강조 + 섹터(대분류›소분류) + 변별력 시그널 아이콘(🚀신고가·📐정배열·🔥시장강세·⚠️과열). `report.py`

## 🔜 남은 작업 (우선순위 순)

1. **아침(morning/US) 브리핑 테스트** — `python scripts/main.py morning --force` 로 미국 종목 경로 점검 (US 캔들/상대강도)
2. **code-reviewer 에이전트로 전체 코드 리뷰** (새 세션이면 활성화됨) — 버그/규칙 점검 후 수정
3. **텔레그램/슬랙 연결** — `.env`에 키 넣고 `notify.py` 실전송 테스트
4. **GitHub Actions** — `.github/workflows/market-radar.yml`
   - 아침(미국리뷰): cron `30 22 * * 0-4` (UTC) = KST 평일 07:30
   - 마감(한국): cron `0 7 * * 1-5` (UTC) = KST 평일 16:00
   - `permissions: contents: write`, Secrets(`TOSS_*`, 전송키), `git add data reports && commit && push`
5. **주간 리포트** (일요일) — `weekly.py`. 일주일 `data/` 누적 + 뉴스 → LLM 요약. LLM 클라이언트는 `notify`처럼 추상화(키 들어오면 연결). cron 일요일.
6. **leader yaml 필드 정리** — 이제 시총 자동산정이라 `stocks.*.yaml`의 `leader:` 값은 미사용. 혼선 방지 위해 제거하거나 주석 처리.
7. **리포트 품질·섹터 회전(rotation)** — 데이터 며칠 쌓이면 "어제 vs 오늘 강세 섹터" 자금이동. `market-analyst`와 종목/임계값 튜닝.
8. **git init + 레포 생성 + 푸시** (현재 git 레포 아님)

## 실행법
```
python scripts/main.py close            # 한국 마감 브리핑 (KR)
python scripts/main.py morning          # 아침 미국 리뷰 (US)
python scripts/main.py close --force    # 휴장 무시(테스트)
python scripts/main.py close --no-store # data 저장 생략
```
- 세션→시장: `close`=KR, `morning`=US (`lib/sessions.py: SESSION_COUNTRY`)
- 키는 `.env` (TOSS_CLIENT_ID/SECRET). 전송키 없으면 console 출력.

## 새 세션 시작 프롬프트 (복붙용)
> "Market Radar 프로젝트 이어서 개발할게. `docs/PROGRESS.md` 읽고 현황 파악해줘. 다음은 [N번 작업] 하자."

## 알려진 특이사항
- 토스가 주는 2026년 시세가 변동성이 큼(가상 미래데이터 성격). 로직 문제 아님.
- 로컬 파이썬(python.org)은 SSL 인증서 때문에 `certifi` 필요 — 코드에 반영됨.
