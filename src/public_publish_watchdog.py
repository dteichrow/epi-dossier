from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_BIN = REPO_ROOT / ".venv/bin/python"
PUBLIC_PUBLISH = REPO_ROOT / "src/public_publish.py"
PUBLIC_MANIFEST_URL = "https://dteichrow.github.io/app_exports/manifest.json"
DEFAULT_STALE_MINUTES = 90
DEFAULT_TIMEOUT_SECONDS = 15


def log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"[public_publish_watchdog {timestamp}] {message}", flush=True)


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return max(int(raw), 1)
    except ValueError:
        log(f"Ignoring invalid {name}={raw!r}; using {default}.")
        return default


def fetch_manifest(url: str = PUBLIC_MANIFEST_URL, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "epi-dossier-watchdog/1.0"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_generated_at(value: str, now: datetime | None = None) -> datetime:
    generated = datetime.fromisoformat(value)
    if generated.tzinfo is not None:
        return generated
    current = now or datetime.now().astimezone()
    return generated.replace(tzinfo=current.tzinfo)


def manifest_age_minutes(manifest: dict[str, Any], now: datetime | None = None) -> float:
    current = now or datetime.now().astimezone()
    generated_raw = str(manifest.get("generated_at", ""))
    if not generated_raw:
        raise ValueError("manifest missing generated_at")
    generated = parse_generated_at(generated_raw, now=current)
    return (current - generated).total_seconds() / 60


def run_public_publish() -> int:
    log("Running public publisher.")
    return subprocess.call([str(PYTHON_BIN), str(PUBLIC_PUBLISH)], cwd=REPO_ROOT)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check the public Newsdesk manifest and repair stale publishes.")
    parser.add_argument("--check", action="store_true", help="Check manifest freshness without invoking the publisher.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    stale_minutes = env_int("EPI_DOSSIER_WATCHDOG_STALE_MINUTES", DEFAULT_STALE_MINUTES)
    timeout_seconds = env_int("EPI_DOSSIER_WATCHDOG_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    try:
        manifest = fetch_manifest(timeout_seconds=timeout_seconds)
        age_minutes = manifest_age_minutes(manifest)
    except (OSError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        log(f"Manifest check failed: {exc}")
        if args.check:
            return 1
        return run_public_publish()

    generated_at = manifest.get("generated_at", "unknown")
    log(f"Manifest generated_at={generated_at}; age={age_minutes:.1f} minutes; threshold={stale_minutes} minutes.")
    if args.check:
        return 0
    if age_minutes < stale_minutes:
        return 0
    log("Manifest is stale; invoking publisher.")
    return run_public_publish()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
