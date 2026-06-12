# 2026-06-12 — 종목 유니버스 1차 구축 (KR 126 / US 48)

## 한 일
- `market-analyst`(general-purpose 대행)로 KR/US 섹터별 대표 대장주 리서치 → 토스 `stocks` API로 전 종목 심볼·상장상태·종목명 검증 → `config/stocks.kr.yaml`, `stocks.us.yaml` 생성.
- 종목명은 **토스 공식명으로 통일**(신뢰소스). 55개 소섹터 전부 2개 이상 커버 확인.

## 제거/변경 (검증으로 발견)
- `048260 오스템임플란트` — DELISTED, 제거. (medical_device는 클래시스·루닛 유지)
- `042670 HD현대인프라코어` — DELISTED(HD현대사이트솔루션 통합), 제거. (machinery는 두산밥캣·현대엘리베이터 유지)
- `377030` — 맥스트인 줄 알았으나 실제 **비트맥스**(사명변경+가상자산 전환), XR 부적합으로 제거.
- `069540` — 라이트론인 줄 알았으나 실제 **빛과전자**, 광통신 소자라 태그 유효 → 이름만 정정 유지.

## 후속 과제 (TODO)
- **XR 소섹터 보강**: 비트맥스 제거로 KR XR이 LG전자·선익시스템 2개로 빈약. 라온텍 등 보강 검토.
- **leader 과다**: KR 126중 94개가 leader. "sector_leaders_strong" 시그널 민감도 위해 진짜 대장만 남기게 솎아내기.
- 재현: `scripts/_research_*.json` + `verify_symbols.py` / `build_stocks_yaml.py`. 정본은 이제 `config/stocks.*.yaml`.
