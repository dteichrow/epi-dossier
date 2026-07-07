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
