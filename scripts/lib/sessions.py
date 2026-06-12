"""세션/휴장 판별. 메모리 market-hours-strategy: 요일+KST 시간 계산 우선, 캘린더는 보정용."""

from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# 세션별 대상 시장:
#  - morning (한국 개장 전 아침): 밤사이 끝난 미국 시장을 리뷰 → US
#  - close   (한국 장 마감): 오늘 한국 시장 정리 → KR
SESSION_COUNTRY = {"morning": "US", "close": "KR"}


def now_kst() -> datetime:
    return datetime.now(KST)


def detect_session(now: datetime | None = None) -> str:
    """KST 시각으로 morning/close 판단. 정오 이전이면 아침(미국 리뷰), 이후면 마감(한국)."""
    now = now or now_kst()
    return "morning" if now.hour < 12 else "close"


def is_weekend(now: datetime | None = None) -> bool:
    now = now or now_kst()
    return now.weekday() >= 5  # 5=토, 6=일


def today_str(now: datetime | None = None) -> str:
    return (now or now_kst()).strftime("%Y-%m-%d")


def is_market_open(country: str, toss=None, now: datetime | None = None) -> bool:
    """1차로 주말 거름. toss 주어지면 공휴일까지 캘린더로 보정."""
    now = now or now_kst()
    if is_weekend(now):
        return False
    if toss is None:
        return True
    try:
        cal = toss.market_calendar(country)
        today = cal["today"]
        if country == "KR":
            return today.get("integrated") is not None
        return any(today.get(s) for s in ("dayMarket", "preMarket", "regularMarket", "afterMarket"))
    except Exception:
        return True  # 캘린더 실패 시 주말만 아니면 진행
