# 2026-06-12 — 운영 방식: 로컬 도커 (토스 IP 화이트리스트 대응)

## 문제
토스 Open API가 **IP 화이트리스트**(허용 IP만 토큰 발급). GitHub Actions는 IP가 동적(수천 CIDR)이라 등록 불가 → `403 IP address not allowed`.

## 결정: 사용자 맥북에서 도커 상시 가동
- 맥 공인 IP는 이미 토스 허용됨 → 추가 등록 불필요.
- `docker-compose.yml`(restart:always) + `scheduler.py`가 컨테이너 안에서 매일 07:30 morning / 16:00 close 실행 (TZ=Asia/Seoul).
- `data`/`reports`는 volume으로 호스트 맥에 영속 저장.
- GitHub Actions yml은 **향후 VPS 이전용으로 보존**(VPS 고정 IP 등록하면 그대로 재사용).

## 운영 주의
- **맥북이 07:30/16:00에 깨어있어야** 함 (절전 시 미실행). 전원연결 + 잠자기 방지 권장.
- 발송 요일:
  - **close(한국)**: 월~금 16:00 (한국 영업일, 공휴일 캘린더 스킵)
  - **morning(미국)**: 화~토 07:30 (미국 월~금장이 끝난 *다음* 한국 아침). 월·일 아침엔 미국 안 보냄.
  - **일요일**: 주간 리포트 자리 (미구현, backlog).
- 집 IP가 바뀌면 토스 차단 → `scheduler.py`가 실패 시 현재 IP를 텔레그램으로 알림 → 토스 콘솔 재등록.

## 재시도 로직 (와이파이 일시 끊김 대비)
- `lib/toss.py`: 종목별 호출에서 네트워크 예외(URLError/Timeout) 3초 간격 재시도.
- `scheduler.py`: 전체 실행 실패 시 10초 간격 최대 3회 재시도 후 IP 알림.

## 컨테이너 관리 명령
- 로그: `docker compose logs -f`
- 재시작: `docker compose restart`
- 수동 1회 실행: `docker compose exec market-radar python scripts/main.py close`
- 중지: `docker compose down`
