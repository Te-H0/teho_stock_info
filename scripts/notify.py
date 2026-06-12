"""전송 추상화. console / telegram / slack 갈아끼우게.
env에 키 있으면 해당 채널, 없으면 console로 출력.
"""

import json
import ssl
import urllib.request

try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL = ssl.create_default_context()


class Notifier:
    def __init__(self, env: dict):
        self.env = env

    def channels(self) -> list[str]:
        ch = ["console"]
        if self.env.get("TELEGRAM_BOT_TOKEN") and self.env.get("TELEGRAM_CHAT_ID"):
            ch.append("telegram")
        if self.env.get("SLACK_WEBHOOK_URL"):
            ch.append("slack")
        return ch

    def send(self, markdown: str) -> None:
        for ch in self.channels():
            getattr(self, f"_send_{ch}")(markdown)

    def _send_console(self, markdown: str) -> None:
        print("\n" + "=" * 60)
        print(markdown)
        print("=" * 60)

    def _send_telegram(self, markdown: str) -> None:
        token = self.env["TELEGRAM_BOT_TOKEN"]
        data = json.dumps({
            "chat_id": self.env["TELEGRAM_CHAT_ID"],
            "text": markdown,
            "parse_mode": "Markdown",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data, headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=15, context=_SSL)
        except Exception as e:
            print(f"[telegram 전송 실패] {e}")

    def _send_slack(self, markdown: str) -> None:
        data = json.dumps({"text": markdown}).encode()
        req = urllib.request.Request(
            self.env["SLACK_WEBHOOK_URL"],
            data=data, headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=15, context=_SSL)
        except Exception as e:
            print(f"[slack 전송 실패] {e}")
