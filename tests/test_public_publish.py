import os
import time
from types import SimpleNamespace

from src import public_publish
from src.outbreak_dashboard_quality import DashboardQualityIssue


def test_prepare_publish_script_pins_repo_root(tmp_path):
    script_path = tmp_path / "publish_public_site.sh"
    script_path.write_text(
        '#!/bin/zsh\nREPO_ROOT="${0:A:h:h}"\necho "$REPO_ROOT"\n',
    )
    edge_root = tmp_path / "edge-of-epidemiology-site"

    prepared = public_publish.prepare_publish_script(script_path=script_path, repo_root=tmp_path, edge_repo_root=edge_root)

    assert 'REPO_ROOT="${0:A:h:h}"' not in prepared
    assert f'REPO_ROOT="{tmp_path}"' in prepared


def test_prepare_publish_script_requires_expected_repo_root_line(tmp_path):
    script_path = tmp_path / "publish_public_site.sh"
    script_path.write_text("#!/bin/zsh\necho missing\n")

    try:
        public_publish.prepare_publish_script(script_path=script_path, repo_root=tmp_path)
    except RuntimeError as exc:
        assert "missing expected repo-root line" in str(exc)
    else:
        raise AssertionError("prepare_publish_script should reject an unexpected publish script")


def test_lock_state_leaves_fresh_lock_alone(tmp_path):
    lock_dir = tmp_path / "lock"
    lock_dir.mkdir()

    state = public_publish.lock_state(lock_dir=lock_dir, stale_seconds=3600, now=time.time())

    assert state == public_publish.LOCK_ALREADY_RUNNING
    assert lock_dir.exists()


def test_lock_state_removes_empty_stale_lock(tmp_path):
    lock_dir = tmp_path / "lock"
    lock_dir.mkdir()
    old_time = time.time() - 7200
    os.utime(lock_dir, (old_time, old_time))

    state = public_publish.lock_state(lock_dir=lock_dir, stale_seconds=3600, now=time.time())

    assert state == public_publish.LOCK_CLEARED
    assert not lock_dir.exists()


def test_run_publish_cleans_empty_lock_after_failed_publish(monkeypatch, tmp_path):
    lock_dir = tmp_path / "lock"
    lock_dir.mkdir()
    monkeypatch.setattr(public_publish, "LOCK_DIR", lock_dir)
    monkeypatch.setattr(public_publish, "lock_state", lambda **_: public_publish.LOCK_READY)
    monkeypatch.setattr(public_publish, "collect_blocking_changes", lambda: [])
    monkeypatch.setattr(public_publish, "fetch_publish_ref", lambda: "origin/main")
    monkeypatch.setattr(public_publish, "local_head_differs_from_ref", lambda _: False)
    monkeypatch.setattr(public_publish, "prepare_publish_script", lambda **_: "exit 1")
    monkeypatch.setattr(public_publish.subprocess, "Popen", lambda *args, **kwargs: SimpleNamespace(wait=lambda timeout: 1))

    assert public_publish.run_publish(timeout_seconds=1, stale_lock_seconds=60) == 1
    assert not lock_dir.exists()


def test_check_configuration_reports_prepared_script(tmp_path, monkeypatch, capsys):
    script_path = tmp_path / "publish_public_site.sh"
    script_path.write_text(
        '#!/bin/zsh\nREPO_ROOT="${0:A:h:h}"\necho "$REPO_ROOT"\n',
    )
    lock_dir = tmp_path / "lock"
    monkeypatch.setattr(public_publish, "PUBLISH_SCRIPT", script_path)
    monkeypatch.setattr(public_publish, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(public_publish, "EDGE_REPO_ROOT", tmp_path / "edge-of-epidemiology-site")
    monkeypatch.setattr(public_publish, "LOCK_DIR", lock_dir)
    monkeypatch.setattr(public_publish, "run_outbreak_dashboard_quality_checks", lambda: [])

    assert public_publish.main(["--check"]) == 0

    output = capsys.readouterr().out
    assert "public_publish_check_ok" in output
    assert f"repo_root={tmp_path}" in output
    assert "lock_state=ready" in output


def test_check_configuration_allows_expected_dashboard_rebuild(tmp_path, monkeypatch, capsys):
    script_path = tmp_path / "publish_public_site.sh"
    script_path.write_text('#!/bin/zsh\nREPO_ROOT="${0:A:h:h}"\necho "$REPO_ROOT"\n')
    monkeypatch.setattr(public_publish, "PUBLISH_SCRIPT", script_path)
    monkeypatch.setattr(public_publish, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(public_publish, "EDGE_REPO_ROOT", tmp_path / "edge-of-epidemiology-site")
    monkeypatch.setattr(public_publish, "LOCK_DIR", tmp_path / "lock")
    monkeypatch.setattr(
        public_publish,
        "run_outbreak_dashboard_quality_checks",
        lambda: [
            DashboardQualityIssue(
                "error",
                "story_test",
                "cases",
                "Generated story page dashboard does not match the current snapshot policy.",
            )
        ],
    )

    assert public_publish.main(["--check"]) == 0
    assert "public_publish_check_rebuild_required story_test cases" in capsys.readouterr().out


def test_blocking_paths_from_porcelain_ignores_generated_docs():
    status = "\n".join(
        [
            " M docs/index.html",
            " M src/parsers.py",
            "?? tests/test_summarize.py",
            "R  docs/old.html -> docs/new.html",
        ]
    )

    assert public_publish.blocking_paths_from_porcelain(status) == [
        "src/parsers.py",
        "tests/test_summarize.py",
    ]


def test_git_env_uses_explicit_publish_ssh_command(monkeypatch, tmp_path):
    monkeypatch.setenv("EPI_DOSSIER_GIT_SSH_COMMAND", "ssh -i /tmp/publish-key")
    monkeypatch.setattr(public_publish, "SSH_KEY", tmp_path / "missing-key")

    env = public_publish.git_env()

    assert env["GIT_SSH_COMMAND"] == "ssh -i /tmp/publish-key"


def test_git_env_omits_ssh_command_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("EPI_DOSSIER_GIT_SSH_COMMAND", raising=False)
    monkeypatch.delenv("GIT_SSH_COMMAND", raising=False)
    monkeypatch.setattr(public_publish, "SSH_KEY", tmp_path / "missing-key")

    env = public_publish.git_env()

    assert "GIT_SSH_COMMAND" not in env


def test_zsh_bin_prefers_configured_binary(monkeypatch):
    monkeypatch.setenv("EPI_DOSSIER_ZSH_BIN", "/custom/zsh")

    assert public_publish.zsh_bin() == "/custom/zsh"


def test_publish_script_mirrors_newsdesk_when_full_umbrella_publish_is_skipped():
    script = public_publish.PUBLISH_SCRIPT.read_text()

    assert "publish_umbrella_newsdesk_mirror()" in script
    assert "Skipping full umbrella-site refresh by configuration; publishing Newsdesk mirror only." in script
    assert "docs/newsdesk" in script
    assert "NEWS_DESK_ROOT_EXPORTS=(archive.json atlas.json health.json latest.json manifest.json)" in script
