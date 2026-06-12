"""config/*.yaml 로더 + .env 로더."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = ROOT / "config"


def load_env() -> dict:
    """.env (KEY=VALUE) 파싱. 환경변수가 있으면 그게 우선."""
    import os
    env = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    # OS 환경변수 우선 (GitHub Actions Secrets)
    for key in ("TOSS_CLIENT_ID", "TOSS_CLIENT_SECRET", "TELEGRAM_BOT_TOKEN",
                "TELEGRAM_CHAT_ID", "SLACK_WEBHOOK_URL", "KRX_ID", "KRX_PW"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    return env


def _read(name: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / name).read_text(encoding="utf-8"))


def load_sectors() -> dict:
    return _read("sectors.yaml")


def load_stocks(country: str | None = None) -> list[dict]:
    """country=None이면 KR+US 전부."""
    rows = []
    files = {"KR": "stocks.kr.yaml", "US": "stocks.us.yaml"}
    targets = [files[country]] if country else files.values()
    for f in targets:
        rows += _read(f)["stocks"]
    return [s for s in rows if s.get("enabled", True)]


def load_signals() -> dict:
    return _read("signals.yaml")


def load_indicators() -> dict:
    return _read("indicators.yaml")


def load_benchmarks() -> dict:
    return _read("benchmarks.yaml")


def sector_names(sectors_cfg: dict) -> tuple[dict, dict]:
    """(소분류id -> 소분류명), (소분류id -> (대분류id, 대분류명))."""
    sub_name, sub_parent = {}, {}
    for parent in sectors_cfg["sectors"]:
        for child in parent["children"]:
            sub_name[child["id"]] = child["name"]
            sub_parent[child["id"]] = (parent["id"], parent["name"])
    return sub_name, sub_parent
