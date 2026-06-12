"""도커 컨테이너 안에서 항상 떠서, 매일 정해진 시각에 브리핑을 실행하는 스케줄러.

- 07:30 KST: morning (미국 마감 리뷰)
- 16:00 KST: close   (한국 마감 정리)
컨테이너 TZ=Asia/Seoul. 실행 실패(특히 토스 IP 차단) 시 현재 공인 IP를 텔레그램으로 알림.
"""

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

import schedule
from lib.config import load_env
from notify import Notifier


def public_ip() -> str:
    try:
        return urllib.request.urlopen("https://api.ipify.org", timeout=10).read().decode()
    except Exception:
        return "확인불가"


def run(session: str, max_tries: int = 3, gap: int = 10) -> None:
    """전체 실행 재시도. 와이파이 일시 끊김 등 대비 10초 간격 최대 3회."""
    for attempt in range(1, max_tries + 1):
        print(f"[{time.strftime('%Y-%m-%d %H:%M')}] run {session} (시도 {attempt}/{max_tries})", flush=True)
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "main.py"), session],
                           capture_output=True, text=True)
        print(r.stdout[-2000:], flush=True)
        if r.stderr:
            print("STDERR:", r.stderr[-1500:], flush=True)
        if r.returncode == 0:
            return
        if attempt < max_tries:
            print(f"실패 → {gap}초 후 재시도", flush=True)
            time.sleep(gap)
    # 모두 실패 → IP 알림 (네트워크 회복 안 됨 또는 토스 IP 차단)
    ip = public_ip()
    msg = (f"⚠️ *Market Radar* {session} 실행 실패 ({max_tries}회 재시도 후)\n"
           f"현재 공인 IP: `{ip}`\n"
           f"토스 'IP not allowed' 라면 콘솔 허용 IP에 위 IP를 등록/갱신, "
           f"아니면 네트워크/맥 상태를 확인하세요.")
    try:
        Notifier(load_env()).send(msg)
    except Exception as e:
        print("알림 전송 실패:", e, flush=True)


schedule.every().day.at("07:30").do(run, "morning")
schedule.every().day.at("16:00").do(run, "close")

print(f"스케줄러 시작 — 매일 07:30 morning(US) / 16:00 close(KR) · KST · IP={public_ip()}", flush=True)
while True:
    schedule.run_pending()
    time.sleep(30)
