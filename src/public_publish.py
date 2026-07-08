from __future__ import annotations

import argparse
import os
import signal
import shutil
import subprocess
import sys
import time
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    sys.path.insert(0, str(REPO_ROOT))
    from src.outbreak_dashboard_quality import build_report as build_outbreak_dashboard_report
    from src.outbreak_dashboard_quality import run_quality_checks as run_outbreak_dashboard_quality_checks
else:
    from .outbreak_dashboard_quality import build_report as build_outbreak_dashboard_report
    from .outbreak_dashboard_quality import run_quality_checks as run_outbreak_dashboard_quality_checks

EDGE_REPO_ROOT = REPO_ROOT.parent / "edge-of-epidemiology-site"
PUBLISH_SCRIPT = REPO_ROOT / "scripts" / "publish_public_site.sh"
PYTHON_BIN = REPO_ROOT / ".venv/bin/python"
SSH_KEY = Path.home() / ".ssh/id_ed25519_epi_dossier"


def default_temp_root() -> Path:
    private_tmp = Path("/private/tmp")
    if private_tmp.exists():
        return private_tmp
    return Path(tempfile.gettempdir())


TEMP_ROOT = Path(os.environ.get("EPI_DOSSIER_PUBLIC_PUBLISH_TEMP_ROOT", str(default_temp_root())))
LOCK_DIR = Path(os.environ.get("EPI_DOSSIER_PUBLIC_PUBLISH_LOCK_DIR", str(TEMP_ROOT / "epi-dossier-public-publish.lock")))
TEMP_WORKTREE_ROOT = Path(
    os.environ.get("EPI_DOSSIER_PUBLIC_PUBLISH_TEMP_WORKTREE_ROOT", str(TEMP_ROOT / "epi-dossier-public-publish-worktrees"))
)
DEFAULT_TIMEOUT_SECONDS = 45 * 60
DEFAULT_STALE_LOCK_SECONDS = 60 * 60
DEFAULT_REMOTE = "origin"
DEFAULT_BRANCH = "main"
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


def prepare_publish_script(
    script_path: Path | None = None,
    repo_root: Path | None = None,
    edge_repo_root: Path | None = None,
) -> str:
    repo_root = repo_root or REPO_ROOT
    edge_repo_root = edge_repo_root or EDGE_REPO_ROOT
    script_path = script_path or (PUBLISH_SCRIPT if repo_root == REPO_ROOT else repo_root / "scripts" / "publish_public_site.sh")
    script = script_path.read_text()
    if REPO_ROOT_LINE not in script:
        raise RuntimeError(f"Publish script missing expected repo-root line: {REPO_ROOT_LINE}")
    script = script.replace(REPO_ROOT_LINE, f'REPO_ROOT="{repo_root}"', 1)
    return script


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


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    explicit_ssh_command = os.environ.get("EPI_DOSSIER_GIT_SSH_COMMAND")
    if explicit_ssh_command:
        env["GIT_SSH_COMMAND"] = explicit_ssh_command
    elif SSH_KEY.exists():
        env["GIT_SSH_COMMAND"] = f"/usr/bin/ssh -o StrictHostKeyChecking=accept-new -i {SSH_KEY}"
    return env


def zsh_bin() -> str:
    configured = os.environ.get("EPI_DOSSIER_ZSH_BIN")
    if configured:
        return configured
    return shutil.which("zsh") or "/bin/zsh"


def run_git(
    args: list[str],
    repo_root: Path = REPO_ROOT,
    capture_output: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/usr/bin/git", "-C", str(repo_root), *args],
        check=True,
        capture_output=capture_output,
        text=True,
        env=env,
    )


def path_from_porcelain_line(line: str) -> str:
    path = line[3:] if len(line) > 3 else ""
    if " -> " in path:
        path = path.rsplit(" -> ", 1)[-1]
    return path


def blocking_paths_from_porcelain(status: str) -> list[str]:
    blocking: list[str] = []
    for line in status.splitlines():
        if not line:
            continue
        path = path_from_porcelain_line(line)
        if path.startswith("docs/"):
            continue
        blocking.append(path)
    return blocking


def collect_blocking_changes(repo_root: Path = REPO_ROOT) -> list[str]:
    status = run_git(["status", "--porcelain"], repo_root=repo_root).stdout
    return blocking_paths_from_porcelain(status)


def fetch_publish_ref(repo_root: Path = REPO_ROOT, remote_name: str = DEFAULT_REMOTE, branch_name: str = DEFAULT_BRANCH) -> str:
    remote_ref = f"{remote_name}/{branch_name}"
    try:
        run_git(["fetch", remote_name, branch_name], repo_root=repo_root, env=git_env())
        run_git(["rev-parse", "--verify", remote_ref], repo_root=repo_root)
    except subprocess.CalledProcessError as exc:
        log(f"Could not refresh {remote_ref}; falling back to local HEAD: {exc}")
        return "HEAD"
    return remote_ref


def local_head_differs_from_ref(ref: str, repo_root: Path = REPO_ROOT) -> bool:
    if ref == "HEAD":
        return False
    try:
        head = run_git(["rev-parse", "HEAD"], repo_root=repo_root).stdout.strip()
        target = run_git(["rev-parse", ref], repo_root=repo_root).stdout.strip()
    except subprocess.CalledProcessError:
        return False
    return head != target


def add_temp_worktree(repo_root: Path = REPO_ROOT, ref: str = "HEAD") -> Path:
    TEMP_WORKTREE_ROOT.mkdir(parents=True, exist_ok=True)
    worktree = Path(tempfile.mkdtemp(prefix="run-", dir=TEMP_WORKTREE_ROOT))
    worktree.rmdir()
    run_git(["worktree", "add", "--detach", str(worktree), ref], repo_root=repo_root)
    return worktree


def remove_temp_worktree(worktree: Path, repo_root: Path = REPO_ROOT) -> None:
    try:
        run_git(["worktree", "remove", "--force", str(worktree)], repo_root=repo_root)
    except subprocess.CalledProcessError as exc:
        log(f"Could not remove temporary git worktree cleanly: {exc}")
    shutil.rmtree(worktree, ignore_errors=True)


def fast_forward_local_checkout(repo_root: Path = REPO_ROOT) -> None:
    try:
        run_git(["restore", "--worktree", "--staged", "--", "docs"], repo_root=repo_root)
        run_git(["fetch", "origin", "main"], repo_root=repo_root, env=git_env())
        run_git(["merge", "--ff-only", "origin/main"], repo_root=repo_root)
    except subprocess.CalledProcessError as exc:
        log(f"Could not fast-forward local checkout after temp publish: {exc}")
        return
    log("Fast-forwarded local checkout to origin/main after temp publish.")


def run_publish(timeout_seconds: int, stale_lock_seconds: int) -> int:
    state = lock_state(lock_dir=LOCK_DIR, stale_seconds=stale_lock_seconds)
    if state == LOCK_ALREADY_RUNNING:
        return 0

    blocking = collect_blocking_changes()
    publish_ref = fetch_publish_ref()
    publish_root = REPO_ROOT
    temp_worktree: Path | None = None
    if blocking or local_head_differs_from_ref(publish_ref):
        log(f"Publishing from clean temporary worktree at {publish_ref}.")
        for path in blocking:
            log(f"Blocking local path preserved outside publish: {path}")
        temp_worktree = add_temp_worktree(ref=publish_ref)
        publish_root = temp_worktree

    script = prepare_publish_script(repo_root=publish_root)
    env = os.environ.copy()
    env.setdefault("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    env.setdefault("EPI_DOSSIER_SKIP_UMBRELLA_PUBLISH", "1")
    env["EPI_DOSSIER_LOCAL_REPO_ROOT"] = str(REPO_ROOT)
    env["EPI_DOSSIER_EDGE_REPO_ROOT"] = str(EDGE_REPO_ROOT)
    env["EPI_DOSSIER_PYTHON_BIN"] = str(PYTHON_BIN)
    log(f"Starting guarded public publish from {publish_root}")
    process = subprocess.Popen(
        [zsh_bin(), "-lc", script],
        cwd=publish_root,
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
        if temp_worktree is not None:
            remove_temp_worktree(temp_worktree)
        return 124

    log(f"Publish finished with exit code {return_code}.")
    if temp_worktree is not None:
        remove_temp_worktree(temp_worktree)
        if return_code == 0:
            fast_forward_local_checkout()
    return return_code


def check_configuration(stale_lock_seconds: int) -> int:
    script = prepare_publish_script()
    state = lock_state(lock_dir=LOCK_DIR, stale_seconds=stale_lock_seconds)
    dashboard_report = build_outbreak_dashboard_report(run_outbreak_dashboard_quality_checks())
    print(f"public_publish_check_ok repo_root={REPO_ROOT}", flush=True)
    print(f"public_publish_check_ok script_bytes={len(script.encode())}", flush=True)
    print(f"public_publish_check_ok lock_state={state}", flush=True)
    print(
        "public_publish_check_ok outbreak_dashboard_errors="
        f"{dashboard_report['summary']['errors']} outbreak_dashboard_warnings={dashboard_report['summary']['warnings']}",
        flush=True,
    )
    for issue in dashboard_report["issues"]:
        if issue["severity"] == "warn":
            print(f"public_publish_check_warn {issue['story_id']} {issue['metric']}: {issue['message']}", flush=True)
        elif issue["severity"] == "error":
            print(f"public_publish_check_error {issue['story_id']} {issue['metric']}: {issue['message']}", flush=True)
    return 1 if dashboard_report["summary"]["errors"] else 0


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
