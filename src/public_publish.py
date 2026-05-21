from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLISH_SCRIPT = REPO_ROOT / "scripts" / "publish_public_site.sh"
LOCK_DIR = Path("/private/tmp/epi-dossier-public-publish.lock")
DEFAULT_TIMEOUT_SECONDS = 45 * 60
DEFAULT_STALE_LOCK_SECONDS = 60 * 60
LOCK_ALREADY_RUNNING = "already_running"
LOCK_CLEARED = "cleared_stale"
LOCK_READY = "ready"
REPO_ROOT_LINE = 'REPO_ROOT="${0:A:h:h}"'


def log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"[public_publish {timestamp}] {message}", flush=True)


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        log(f"Ignoring invalid {name}={raw!r}; using {default}.")
        return default
    return max(value, 1)


def prepare_publish_script(script_path: Path = PUBLISH_SCRIPT, repo_root: Path = REPO_ROOT) -> str:
    script = script_path.read_text()
    if REPO_ROOT_LINE not in script:
        raise RuntimeError(f"Publish script missing expected repo-root line: {REPO_ROOT_LINE}")
    return script.replace(REPO_ROOT_LINE, f'REPO_ROOT="{repo_root}"', 1)


def lock_state(lock_dir: Path = LOCK_DIR, stale_seconds: int = DEFAULT_STALE_LOCK_SECONDS, now: float | None = None) -> str:
    if not lock_dir.exists():
        return LOCK_READY

    current_time = time.time() if now is None else now
    age_seconds = current_time - lock_dir.stat().st_mtime
    if age_seconds < stale_seconds:
        log(f"Publish lock exists and is {age_seconds:.0f}s old; assuming another run is active.")
        return LOCK_ALREADY_RUNNING

    try:
        lock_dir.rmdir()
    except OSError as exc:
        log(f"Publish lock is stale but could not be removed: {exc}")
        return LOCK_ALREADY_RUNNING

    log(f"Removed stale publish lock after {age_seconds:.0f}s: {lock_dir}")
    return LOCK_CLEARED


def cleanup_empty_lock(lock_dir: Path = LOCK_DIR) -> None:
    try:
        lock_dir.rmdir()
    except FileNotFoundError:
        return
    except OSError:
        return


def terminate_process_group(process: subprocess.Popen[str], grace_seconds: int = 15) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return

    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return
        time.sleep(0.2)

    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def run_publish(timeout_seconds: int, stale_lock_seconds: int) -> int:
    state = lock_state(stale_seconds=stale_lock_seconds)
    if state == LOCK_ALREADY_RUNNING:
        return 0

    script = prepare_publish_script()
    env = os.environ.copy()
    env.setdefault("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    log(f"Starting guarded public publish from {REPO_ROOT}")
    process = subprocess.Popen(
        ["/bin/zsh", "-lc", script],
        cwd=REPO_ROOT,
        env=env,
        start_new_session=True,
        text=True,
    )
    try:
        return_code = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        log(f"Publish exceeded {timeout_seconds}s; terminating process group.")
        terminate_process_group(process)
        cleanup_empty_lock()
        return 124

    log(f"Publish finished with exit code {return_code}.")
    return return_code


def check_configuration(stale_lock_seconds: int) -> int:
    script = prepare_publish_script()
    state = lock_state(stale_seconds=stale_lock_seconds)
    print(f"public_publish_check_ok repo_root={REPO_ROOT}", flush=True)
    print(f"public_publish_check_ok script_bytes={len(script.encode())}", flush=True)
    print(f"public_publish_check_ok lock_state={state}", flush=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the guarded public Newsdesk publish from launchd.")
    parser.add_argument("--check", action="store_true", help="Validate paths, script preparation, and lock state without publishing.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    timeout_seconds = env_int("EPI_DOSSIER_PUBLIC_PUBLISH_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    stale_lock_seconds = env_int("EPI_DOSSIER_PUBLIC_PUBLISH_STALE_LOCK_SECONDS", DEFAULT_STALE_LOCK_SECONDS)
    if args.check:
        return check_configuration(stale_lock_seconds)
    return run_publish(timeout_seconds=timeout_seconds, stale_lock_seconds=stale_lock_seconds)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
