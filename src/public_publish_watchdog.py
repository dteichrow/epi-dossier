from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_BIN = REPO_ROOT / ".venv/bin/python"
PUBLIC_PUBLISH = REPO_ROOT / "src/public_publish.py"
PUBLIC_MANIFEST_URL = "https://dteichrow.github.io/epi-dossier/app_exports/manifest.json"
PUBLIC_LATEST_URL = "https://dteichrow.github.io/epi-dossier/app_exports/latest.json"
DEFAULT_STALE_MINUTES = 45
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_SEARCH_WINDOW_DAYS = 7
NAIVE_UTC_FUTURE_TOLERANCE = timedelta(minutes=5)


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


def env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    log(f"Ignoring invalid {name}={raw!r}; using {default}.")
    return default


def ensure_repo_on_path() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def fetch_json(url: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "epi-dossier-watchdog/1.0"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_manifest(url: str = PUBLIC_MANIFEST_URL, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    return fetch_json(url, timeout_seconds=timeout_seconds)


def parse_generated_at(value: str, now: datetime | None = None) -> datetime:
    generated = datetime.fromisoformat(value)
    if generated.tzinfo is not None:
        return generated
    current = now or datetime.now().astimezone()
    local_generated = generated.replace(tzinfo=current.tzinfo)
    if local_generated - current > NAIVE_UTC_FUTURE_TOLERANCE:
        return generated.replace(tzinfo=timezone.utc).astimezone(current.tzinfo)
    return local_generated


def manifest_age_minutes(manifest: dict[str, Any], now: datetime | None = None) -> float:
    current = now or datetime.now().astimezone()
    generated_raw = str(manifest.get("generated_at", ""))
    if not generated_raw:
        raise ValueError("manifest missing generated_at")
    generated = parse_generated_at(generated_raw, now=current)
    return (current - generated).total_seconds() / 60


def identity_values(*, canonical_url: str = "", item_id: str = "") -> set[str]:
    ensure_repo_on_path()
    from src.utils import canonicalize_url, stable_id

    identities = {item_id.strip()} if item_id.strip() else set()
    if canonical_url.strip():
        canonical = canonicalize_url(canonical_url)
        identities.add(canonical)
        identities.add(stable_id("item", canonical))
    return {identity for identity in identities if identity}


def live_item_identities(live_snapshot: dict[str, Any]) -> set[str]:
    identities: set[str] = set()
    for item in live_snapshot.get("items", []):
        if not isinstance(item, dict):
            continue
        identities.update(
            identity_values(
                canonical_url=str(item.get("canonical_url") or item.get("preferred_url") or item.get("source_url") or ""),
                item_id=str(item.get("item_id") or ""),
            )
        )
    return identities


def candidate_item_identities(item: Any) -> set[str]:
    return identity_values(canonical_url=str(getattr(item, "canonical_url", "") or getattr(item, "url", "")))


def find_new_candidate_items(candidates: list[Any], live_snapshot: dict[str, Any]) -> list[Any]:
    live_identities = live_item_identities(live_snapshot)
    new_items = []
    for item in candidates:
        identities = candidate_item_identities(item)
        if identities and identities.isdisjoint(live_identities):
            new_items.append(item)
    return new_items


def fetch_live_latest(timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    return fetch_json(PUBLIC_LATEST_URL, timeout_seconds=timeout_seconds)


def run_candidate_search(window_days: int) -> list[Any]:
    ensure_repo_on_path()
    from src.main import parse_target_date, run_once
    from src.utils import ensure_directories, setup_logging

    ensure_directories()
    payload = run_once(
        parse_target_date(None),
        window_days,
        True,
        setup_logging(),
        return_payload=True,
        write_local_artifacts=False,
    )
    return list((payload or {}).get("processed", []))


def summarize_candidate(item: Any) -> str:
    title = str(getattr(item, "title", "Untitled")).strip() or "Untitled"
    source = str(getattr(item, "source", "unknown source")).strip() or "unknown source"
    return f"{title} | {source}"


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
    search_window_days = env_int("EPI_DOSSIER_WATCHDOG_SEARCH_WINDOW_DAYS", DEFAULT_SEARCH_WINDOW_DAYS)
    check_new_items = env_bool("EPI_DOSSIER_WATCHDOG_CHECK_NEW_ITEMS", True)
    manifest_url = os.environ.get("EPI_DOSSIER_WATCHDOG_MANIFEST_URL", PUBLIC_MANIFEST_URL)
    try:
        manifest = fetch_manifest(url=manifest_url, timeout_seconds=timeout_seconds)
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
    if age_minutes >= stale_minutes:
        log("Manifest is stale; invoking publisher.")
        return run_public_publish()

    if check_new_items:
        try:
            live_snapshot = fetch_live_latest(timeout_seconds=timeout_seconds)
            candidates = run_candidate_search(search_window_days)
            new_items = find_new_candidate_items(candidates, live_snapshot)
        except Exception as exc:
            log(f"New-item watchdog check failed: {exc}")
            return 0
        log(
            f"New-item watchdog checked {len(candidates)} current candidate item(s); "
            f"found {len(new_items)} not present in the live feed."
        )
        if new_items:
            for item in new_items[:5]:
                log(f"New candidate: {summarize_candidate(item)}")
            return run_public_publish()

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
