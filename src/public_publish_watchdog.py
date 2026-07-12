from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
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
PUBLIC_MANIFEST_URL = "https://dteichrow.github.io/app_exports/manifest.json"
PUBLIC_LATEST_URL = "https://dteichrow.github.io/app_exports/latest.json"
UPSTREAM_MANIFEST_URL = "https://raw.githubusercontent.com/dteichrow/epi-dossier/main/docs/app_exports/manifest.json"
WATCHDOG_STATE_PATH = REPO_ROOT / "data" / "public_publish_watchdog_state.json"
DEFAULT_STALE_MINUTES = 45
DEFAULT_NEW_ITEM_MIN_PUBLISH_INTERVAL_MINUTES = 30
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_SEARCH_WINDOW_DAYS = 7
DEFAULT_PUBLISH_MODE = "local"
DEFAULT_GITHUB_REPOSITORY = "dteichrow/epi-dossier"
DEFAULT_GITHUB_WORKFLOW = "Newsdesk public publish"
DEFAULT_GITHUB_REF = "main"
DEFAULT_REMOTE_DISPATCH_COOLDOWN_MINUTES = 45
DEFAULT_UMBRELLA_REPOSITORY = "dteichrow/dteichrow.github.io"
DEFAULT_UMBRELLA_WORKFLOW = "deploy-pages.yml"
DEFAULT_UMBRELLA_DISPATCH_COOLDOWN_MINUTES = 30
DEFAULT_ENABLE_UMBRELLA_DISPATCH = True
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


def env_choice(name: str, default: str, allowed: set[str]) -> str:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in allowed:
        return normalized
    log(f"Ignoring invalid {name}={raw!r}; using {default!r}.")
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


def cache_busting_url(url: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}watchdog={time.time_ns()}"


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


def manifest_is_newer(candidate: dict[str, Any], current: dict[str, Any], now: datetime | None = None) -> bool:
    candidate_raw = str(candidate.get("generated_at", ""))
    current_raw = str(current.get("generated_at", ""))
    if not candidate_raw or not current_raw:
        return False
    reference_time = now or datetime.now().astimezone()
    try:
        return parse_generated_at(candidate_raw, now=reference_time) > parse_generated_at(current_raw, now=reference_time)
    except ValueError:
        return False


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


def candidate_items_signature(items: list[Any]) -> str:
    identities: set[str] = set()
    for item in items:
        identities.update(candidate_item_identities(item))
    payload = json.dumps(sorted(identities), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def candidate_items_identity_set(items: list[Any]) -> set[str]:
    identities: set[str] = set()
    for item in items:
        identities.update(candidate_item_identities(item))
    return identities


def load_watchdog_state(state_path: Path | None = None) -> dict[str, Any]:
    state_path = state_path or WATCHDOG_STATE_PATH
    try:
        raw = state_path.read_text()
    except FileNotFoundError:
        return {}
    try:
        state = json.loads(raw)
    except json.JSONDecodeError:
        log(f"Ignoring invalid watchdog state file: {state_path}")
        return {}
    return state if isinstance(state, dict) else {}


def write_watchdog_state(state: dict[str, Any], state_path: Path | None = None) -> None:
    state_path = state_path or WATCHDOG_STATE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def attempted_candidate_identities(state_path: Path | None = None) -> set[str]:
    state = load_watchdog_state(state_path)
    values = state.get("attempted_new_item_identities", [])
    if not isinstance(values, list):
        return set()
    return {str(value) for value in values if str(value).strip()}


def filter_unattempted_candidate_items(items: list[Any], state_path: Path | None = None) -> list[Any]:
    attempted = attempted_candidate_identities(state_path)
    unattempted = []
    for item in items:
        identities = candidate_item_identities(item)
        if identities and identities.isdisjoint(attempted):
            unattempted.append(item)
    return unattempted


def record_candidate_publish_attempt(
    *,
    items: list[Any],
    manifest: dict[str, Any],
    state_path: Path | None = None,
) -> None:
    state = load_watchdog_state(state_path)
    identities = candidate_items_identity_set(items)
    attempted = attempted_candidate_identities(state_path)
    attempted.update(identities)
    state.update(
        {
            "attempted_new_item_identities": sorted(attempted),
            "last_new_item_signature": candidate_items_signature(items),
            "last_new_item_count": len(items),
            "last_manifest_generated_at": manifest.get("generated_at", ""),
            "last_manifest_run_id": manifest.get("latest_run_id", ""),
            "last_attempted_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
    )
    write_watchdog_state(state, state_path)


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


def run_github_actions_publish(
    *,
    repository: str = DEFAULT_GITHUB_REPOSITORY,
    workflow: str = DEFAULT_GITHUB_WORKFLOW,
    ref: str = DEFAULT_GITHUB_REF,
    gh_binary: str | None = None,
) -> int:
    executable = gh_binary or os.environ.get("EPI_DOSSIER_WATCHDOG_GH_BIN") or shutil.which("gh")
    if not executable:
        log("GitHub Actions publish was requested, but the gh CLI is not available.")
        return 127
    log(f"Requesting GitHub Actions publish for {repository} at {ref}.")
    return subprocess.call(
        [executable, "workflow", "run", workflow, "--repo", repository, "--ref", ref],
        cwd=REPO_ROOT,
    )


def github_dispatch_is_due(
    cooldown_minutes: int,
    *,
    state_key: str,
    state_path: Path | None = None,
    now: datetime | None = None,
) -> bool:
    state = load_watchdog_state(state_path)
    last_raw = state.get(state_key)
    if not isinstance(last_raw, str) or not last_raw:
        return True
    try:
        last_dispatch = datetime.fromisoformat(last_raw)
    except ValueError:
        return True
    current = now or datetime.now().astimezone()
    if last_dispatch.tzinfo is None:
        last_dispatch = last_dispatch.replace(tzinfo=current.tzinfo)
    return current - last_dispatch >= timedelta(minutes=cooldown_minutes)


def record_github_dispatch(
    *,
    state_key: str,
    state_path: Path | None = None,
    state_updates: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> None:
    state = load_watchdog_state(state_path)
    current = now or datetime.now().astimezone()
    state[state_key] = current.isoformat(timespec="seconds")
    if state_updates:
        state.update(state_updates)
    write_watchdog_state(state, state_path)


def request_github_actions_dispatch(
    *,
    repository: str,
    workflow: str,
    ref: str,
    remote_dispatch_cooldown_minutes: int,
    state_key: str,
    state_path: Path | None = None,
    bypass_cooldown: bool = False,
    state_updates: dict[str, Any] | None = None,
) -> int:
    if not bypass_cooldown and not github_dispatch_is_due(
        remote_dispatch_cooldown_minutes,
        state_key=state_key,
        state_path=state_path,
    ):
        log("GitHub Actions recovery dispatch is within its cooldown; skipping duplicate request.")
        return 0
    result = run_github_actions_publish(
        repository=repository,
        workflow=workflow,
        ref=ref,
    )
    if result == 0:
        record_github_dispatch(state_key=state_key, state_path=state_path, state_updates=state_updates)
    return result


def request_publish(
    *,
    publish_mode: str,
    remote_dispatch_cooldown_minutes: int,
    state_path: Path | None = None,
) -> int:
    if publish_mode != "github_actions":
        return run_public_publish()
    return request_github_actions_dispatch(
        repository=os.environ.get("EPI_DOSSIER_WATCHDOG_GITHUB_REPOSITORY", DEFAULT_GITHUB_REPOSITORY),
        workflow=os.environ.get("EPI_DOSSIER_WATCHDOG_GITHUB_WORKFLOW", DEFAULT_GITHUB_WORKFLOW),
        ref=os.environ.get("EPI_DOSSIER_WATCHDOG_GITHUB_REF", DEFAULT_GITHUB_REF),
        remote_dispatch_cooldown_minutes=remote_dispatch_cooldown_minutes,
        state_key="last_github_actions_dispatch_at",
        state_path=state_path,
    )


def request_umbrella_publish(
    *,
    dispatch_cooldown_minutes: int,
    state_path: Path | None = None,
    upstream_generated_at: str = "",
) -> int:
    state = load_watchdog_state(state_path)
    artifact_key = "last_umbrella_artifact_generated_at"
    artifact_is_new = bool(upstream_generated_at and state.get(artifact_key) != upstream_generated_at)
    return request_github_actions_dispatch(
        repository=os.environ.get("EPI_DOSSIER_WATCHDOG_UMBRELLA_REPOSITORY", DEFAULT_UMBRELLA_REPOSITORY),
        workflow=os.environ.get("EPI_DOSSIER_WATCHDOG_UMBRELLA_WORKFLOW", DEFAULT_UMBRELLA_WORKFLOW),
        ref=os.environ.get("EPI_DOSSIER_WATCHDOG_UMBRELLA_REF", DEFAULT_GITHUB_REF),
        remote_dispatch_cooldown_minutes=dispatch_cooldown_minutes,
        state_key="last_umbrella_dispatch_at",
        state_path=state_path,
        bypass_cooldown=artifact_is_new,
        state_updates={artifact_key: upstream_generated_at} if upstream_generated_at else None,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check the public Newsdesk manifest and repair stale publishes.")
    parser.add_argument("--check", action="store_true", help="Check manifest freshness without invoking the publisher.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    stale_minutes = env_int("EPI_DOSSIER_WATCHDOG_STALE_MINUTES", DEFAULT_STALE_MINUTES)
    new_item_min_publish_interval_minutes = env_int(
        "EPI_DOSSIER_WATCHDOG_NEW_ITEM_MIN_PUBLISH_INTERVAL_MINUTES",
        DEFAULT_NEW_ITEM_MIN_PUBLISH_INTERVAL_MINUTES,
    )
    timeout_seconds = env_int("EPI_DOSSIER_WATCHDOG_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    search_window_days = env_int("EPI_DOSSIER_WATCHDOG_SEARCH_WINDOW_DAYS", DEFAULT_SEARCH_WINDOW_DAYS)
    check_new_items = env_bool("EPI_DOSSIER_WATCHDOG_CHECK_NEW_ITEMS", True)
    publish_mode = env_choice("EPI_DOSSIER_WATCHDOG_PUBLISH_MODE", DEFAULT_PUBLISH_MODE, {"local", "github_actions"})
    remote_dispatch_cooldown_minutes = env_int(
        "EPI_DOSSIER_WATCHDOG_REMOTE_DISPATCH_COOLDOWN_MINUTES",
        DEFAULT_REMOTE_DISPATCH_COOLDOWN_MINUTES,
    )
    umbrella_dispatch_cooldown_minutes = env_int(
        "EPI_DOSSIER_WATCHDOG_UMBRELLA_DISPATCH_COOLDOWN_MINUTES",
        DEFAULT_UMBRELLA_DISPATCH_COOLDOWN_MINUTES,
    )
    enable_umbrella_dispatch = env_bool(
        "EPI_DOSSIER_WATCHDOG_ENABLE_UMBRELLA_DISPATCH",
        DEFAULT_ENABLE_UMBRELLA_DISPATCH,
    )
    manifest_url = os.environ.get("EPI_DOSSIER_WATCHDOG_MANIFEST_URL", PUBLIC_MANIFEST_URL)
    upstream_manifest_url = os.environ.get("EPI_DOSSIER_WATCHDOG_UPSTREAM_MANIFEST_URL", UPSTREAM_MANIFEST_URL)
    try:
        manifest = fetch_manifest(url=manifest_url, timeout_seconds=timeout_seconds)
        age_minutes = manifest_age_minutes(manifest)
    except (OSError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        log(f"Manifest check failed: {exc}")
        if args.check:
            return 1
        return request_publish(
            publish_mode=publish_mode,
            remote_dispatch_cooldown_minutes=remote_dispatch_cooldown_minutes,
        )

    generated_at = manifest.get("generated_at", "unknown")
    log(f"Manifest generated_at={generated_at}; age={age_minutes:.1f} minutes; threshold={stale_minutes} minutes.")
    if enable_umbrella_dispatch:
        try:
            upstream_manifest = fetch_manifest(url=cache_busting_url(upstream_manifest_url), timeout_seconds=timeout_seconds)
        except (OSError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            log(f"Upstream manifest check failed: {exc}")
        else:
            if manifest_is_newer(upstream_manifest, manifest):
                log("Upstream Newsdesk artifact is newer than the live export; requesting umbrella import.")
                if args.check:
                    return 0
                return request_umbrella_publish(
                    dispatch_cooldown_minutes=umbrella_dispatch_cooldown_minutes,
                    upstream_generated_at=str(upstream_manifest.get("generated_at", "")),
                )
    if args.check:
        return 0
    if age_minutes >= stale_minutes:
        log("Manifest is stale; invoking publisher.")
        return request_publish(
            publish_mode=publish_mode,
            remote_dispatch_cooldown_minutes=remote_dispatch_cooldown_minutes,
        )

    if check_new_items:
        if age_minutes < new_item_min_publish_interval_minutes:
            log(
                "Manifest is fresh enough to skip new-item publish check; "
                f"age={age_minutes:.1f} minutes; "
                f"minimum={new_item_min_publish_interval_minutes} minutes."
            )
            return 0
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
            unattempted_items = filter_unattempted_candidate_items(new_items)
            if not unattempted_items:
                log(
                    "New-item watchdog is only seeing candidates it already published for; "
                    "skipping repeat publish until at least one new candidate identity appears."
                )
                return 0
            for item in unattempted_items[:5]:
                log(f"New candidate: {summarize_candidate(item)}")
            result = request_publish(
                publish_mode=publish_mode,
                remote_dispatch_cooldown_minutes=remote_dispatch_cooldown_minutes,
            )
            if result == 0:
                record_candidate_publish_attempt(items=new_items, manifest=manifest)
            return result

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
