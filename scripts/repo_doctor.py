#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]

COMMON_REQUIRED_PATHS = (
    "README.md",
    "requirements.txt",
    ".github/workflows",
    "tests",
)

REPO_REQUIRED_PATHS = {
    "epi-dossier": (
        "src/public_publish.py",
        "src/site_build.py",
        "src/app_exports.py",
        "scripts/publish_public_site.sh",
        ".github/workflows/newsdesk-public-publish.yml",
    ),
    "edge-site": (
        "content/posts.yml",
        "src/build_site.py",
        "src/substack_sync.py",
        ".github/workflows/deploy-pages.yml",
        ".github/workflows/substack-sync.yml",
    ),
}

LIVE_ROUTES = {
    "epi-dossier": (
        "https://dteichrow.github.io/newsdesk/",
        "https://dteichrow.github.io/newsdesk/app_exports/latest.json",
        "https://dteichrow.github.io/newsdesk/stories/story_56666e9c6c86e976-ebola-virus-disease.html",
    ),
    "edge-site": (
        "https://dteichrow.github.io/",
        "https://dteichrow.github.io/essays/",
        "https://dteichrow.github.io/newsdesk/",
        "https://dteichrow.github.io/app_exports/latest.json",
    ),
}

FORBIDDEN_TRACKED_PATTERNS = (
    re.compile(r"(^|/)__pycache__/"),
    re.compile(r"\.pyc$"),
    re.compile(r"(^|/)\.pytest_cache/"),
    re.compile(r"(^|/)\.venv/"),
    re.compile(r"(^|/)\.env$"),
    re.compile(r"(^|/)\.DS_Store$"),
    re.compile(r"(^|/)logs/.*\.log$"),
    re.compile(r"(^|/)tmp/"),
)


@dataclass
class Check:
    name: str
    status: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def detect_repo_kind(explicit: str) -> str:
    if explicit != "auto":
        return explicit
    if (REPO_ROOT / "src/public_publish.py").exists():
        return "epi-dossier"
    if (REPO_ROOT / "content/posts.yml").exists():
        return "edge-site"
    return "unknown"


def parse_branch_status(line: str) -> dict[str, int]:
    ahead_match = re.search(r"ahead (\d+)", line)
    behind_match = re.search(r"behind (\d+)", line)
    return {
        "ahead": int(ahead_match.group(1)) if ahead_match else 0,
        "behind": int(behind_match.group(1)) if behind_match else 0,
    }


def collect_git_status() -> tuple[dict[str, Any], list[str]]:
    status_result = run_git(["status", "--short", "--branch"])
    if status_result.returncode != 0:
        return {
            "branch": None,
            "ahead": 0,
            "behind": 0,
            "tracked_dirty_count": 0,
            "untracked_count": 0,
            "status_available": False,
        }, [status_result.stderr.strip() or "git status failed"]

    lines = [line for line in status_result.stdout.splitlines() if line.strip()]
    branch_line = lines[0] if lines else "## unknown"
    branch = branch_line.removeprefix("## ").split("...", 1)[0].strip()
    divergence = parse_branch_status(branch_line)
    tracked_dirty = [line for line in lines[1:] if not line.startswith("?? ")]
    untracked = [line for line in lines[1:] if line.startswith("?? ")]
    return {
        "branch": branch,
        "ahead": divergence["ahead"],
        "behind": divergence["behind"],
        "tracked_dirty_count": len(tracked_dirty),
        "untracked_count": len(untracked),
        "status_available": True,
    }, lines


def tracked_files() -> list[str]:
    result = run_git(["ls-files"])
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def check_required_paths(repo_kind: str) -> list[Check]:
    checks: list[Check] = []
    required = list(COMMON_REQUIRED_PATHS)
    required.extend(REPO_REQUIRED_PATHS.get(repo_kind, ()))
    missing = [path for path in required if not (REPO_ROOT / path).exists()]
    if missing:
        checks.append(Check("required_paths", "error", "Missing: " + ", ".join(missing)))
    else:
        checks.append(Check("required_paths", "ok", f"All {len(required)} required paths are present."))
    return checks


def check_workflows() -> list[Check]:
    workflow_root = REPO_ROOT / ".github" / "workflows"
    workflows = sorted(workflow_root.glob("*.yml")) + sorted(workflow_root.glob("*.yaml"))
    checks: list[Check] = []
    if not workflows:
        return [Check("workflow_files", "error", "No workflow files found under .github/workflows.")]

    malformed: list[str] = []
    for workflow in workflows:
        text = workflow.read_text(errors="replace")
        has_name = re.search(r"(?m)^name:\s*\S", text)
        has_on = re.search(r"(?m)^on:\s*", text)
        has_jobs = re.search(r"(?m)^jobs:\s*", text)
        if not (has_name and has_on and has_jobs):
            malformed.append(str(workflow.relative_to(REPO_ROOT)))
    if malformed:
        checks.append(Check("workflow_files", "error", "Missing name/on/jobs in: " + ", ".join(malformed)))
    else:
        checks.append(Check("workflow_files", "ok", f"{len(workflows)} workflow file(s) have basic required keys."))
    return checks


def check_tracked_hygiene() -> list[Check]:
    files = tracked_files()
    offenders = [
        path
        for path in files
        if any(pattern.search(path) for pattern in FORBIDDEN_TRACKED_PATTERNS)
    ]
    if offenders:
        sample = ", ".join(offenders[:12])
        suffix = "" if len(offenders) <= 12 else f" and {len(offenders) - 12} more"
        return [Check("tracked_hygiene", "error", f"Tracked local/cache artifacts: {sample}{suffix}")]
    return [Check("tracked_hygiene", "ok", f"Scanned {len(files)} tracked file(s); no cache/local artifacts found.")]


def check_git_cleanliness(status: dict[str, Any]) -> list[Check]:
    checks: list[Check] = []
    if not status["status_available"]:
        return [Check("git_status", "warn", "git status was unavailable.")]
    if status["behind"]:
        checks.append(Check("remote_divergence", "warn", f"Branch is behind upstream by {status['behind']} commit(s)."))
    elif status["ahead"]:
        checks.append(Check("remote_divergence", "warn", f"Branch is ahead of upstream by {status['ahead']} commit(s)."))
    else:
        checks.append(Check("remote_divergence", "ok", "Branch is not ahead or behind its upstream."))

    dirty = status["tracked_dirty_count"]
    untracked = status["untracked_count"]
    if dirty or untracked:
        checks.append(Check("working_tree", "warn", f"{dirty} tracked dirty path(s), {untracked} untracked path(s)."))
    else:
        checks.append(Check("working_tree", "ok", "Working tree is clean."))
    return checks


def check_live_routes(repo_kind: str) -> list[Check]:
    routes = LIVE_ROUTES.get(repo_kind, ())
    if not routes:
        return [Check("live_routes", "warn", f"No live-route checks configured for repo kind {repo_kind!r}.")]
    checks: list[Check] = []
    for url in routes:
        try:
            with urlopen(url, timeout=20) as response:
                status = getattr(response, "status", None)
                body = response.read(256)
        except URLError as exc:
            checks.append(Check("live_route", "error", f"{url} failed: {exc}"))
            continue
        if status and 200 <= status < 400 and body:
            checks.append(Check("live_route", "ok", f"{url} returned HTTP {status}."))
        else:
            checks.append(Check("live_route", "error", f"{url} returned HTTP {status} with {len(body)} byte(s)."))
    return checks


def build_report(repo_kind: str, include_live: bool) -> dict[str, Any]:
    status, raw_status = collect_git_status()
    checks: list[Check] = []
    checks.extend(check_required_paths(repo_kind))
    checks.extend(check_workflows())
    checks.extend(check_tracked_hygiene())
    checks.extend(check_git_cleanliness(status))
    if include_live:
        checks.extend(check_live_routes(repo_kind))

    errors = sum(1 for check in checks if check.status == "error")
    warnings = sum(1 for check in checks if check.status == "warn")
    return {
        "repo": REPO_ROOT.name,
        "repo_root": str(REPO_ROOT),
        "repo_kind": repo_kind,
        "git": status,
        "raw_status": raw_status[:80],
        "checks": [check.as_dict() for check in checks],
        "summary": {"errors": errors, "warnings": warnings},
    }


def print_human(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print(f"Repo doctor: {report['repo']} ({report['repo_kind']})")
    print(f"Errors: {summary['errors']}  Warnings: {summary['warnings']}")
    for check in report["checks"]:
        marker = {"ok": "OK", "warn": "WARN", "error": "ERROR"}[check["status"]]
        print(f"[{marker}] {check['name']}: {check['detail']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run structural and operational health checks for this repository.")
    parser.add_argument("--repo-kind", choices=("auto", "epi-dossier", "edge-site"), default="auto")
    parser.add_argument("--check-live", action="store_true", help="Also verify public GitHub Pages routes.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    repo_kind = detect_repo_kind(args.repo_kind)
    report = build_report(repo_kind, args.check_live)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_human(report)
    return 1 if report["summary"]["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
