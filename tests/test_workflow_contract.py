from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_workflow(path: str) -> dict:
    return yaml.load((REPO_ROOT / path).read_text(), Loader=yaml.BaseLoader)


def test_newsdesk_publish_dispatches_umbrella_import() -> None:
    workflow = load_workflow(".github/workflows/newsdesk-public-publish.yml")
    steps = workflow["jobs"]["publish"]["steps"]

    dispatch_steps = [step for step in steps if step.get("name") == "Dispatch umbrella-site Newsdesk import"]

    assert len(dispatch_steps) == 1
    dispatch_step = dispatch_steps[0]
    assert dispatch_step["env"]["UMBRELLA_REPO"] == "dteichrow/dteichrow.github.io"
    assert "EOE_UMBRELLA_DISPATCH_TOKEN" in dispatch_step["env"]["GH_TOKEN"]
    assert "newsdesk_published" in dispatch_step["run"]
    assert "repos/${UMBRELLA_REPO}/dispatches" in dispatch_step["run"]


def test_newsdesk_schedule_uses_staggered_publish_and_repair_windows() -> None:
    workflow = load_workflow(".github/workflows/newsdesk-public-publish.yml")
    schedule = workflow["on"]["schedule"]
    steps = workflow["jobs"]["publish"]["steps"]

    assert [entry["cron"] for entry in schedule] == ["7,37 * * * *", "22,52 * * * *"]
    assert workflow["concurrency"]["cancel-in-progress"] == "false"

    publish_step = next(step for step in steps if step.get("name") == "Publish Newsdesk")
    watchdog_step = next(step for step in steps if step.get("name") == "Repair stale Newsdesk publish")

    assert "7,37 * * * *" in publish_step["if"]
    assert "22,52 * * * *" in watchdog_step["if"]
    assert watchdog_step["env"]["EPI_DOSSIER_WATCHDOG_STALE_MINUTES"] == "35"
    assert watchdog_step["run"] == ".venv/bin/python src/public_publish_watchdog.py"
