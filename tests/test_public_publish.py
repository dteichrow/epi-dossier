import os
import time

from src import public_publish


def test_prepare_publish_script_pins_repo_root(tmp_path):
    script_path = tmp_path / "publish_public_site.sh"
    script_path.write_text(
        '#!/bin/zsh\nREPO_ROOT="${0:A:h:h}"\nEDGE_REPO_ROOT="$REPO_ROOT/../edge-of-epidemiology-site"\nPYTHON_BIN="$REPO_ROOT/.venv/bin/python"\necho "$REPO_ROOT"\n',
    )
    edge_root = tmp_path / "edge-of-epidemiology-site"

    prepared = public_publish.prepare_publish_script(script_path=script_path, repo_root=tmp_path, edge_repo_root=edge_root)

    assert 'REPO_ROOT="${0:A:h:h}"' not in prepared
    assert 'EDGE_REPO_ROOT="$REPO_ROOT/../edge-of-epidemiology-site"' not in prepared
    assert 'PYTHON_BIN="$REPO_ROOT/.venv/bin/python"' not in prepared
    assert f'REPO_ROOT="{tmp_path}"' in prepared
    assert f'EDGE_REPO_ROOT="{edge_root}"' in prepared
    assert f'PYTHON_BIN="{public_publish.PYTHON_BIN}"' in prepared


def test_prepare_publish_script_requires_expected_repo_root_line(tmp_path):
    script_path = tmp_path / "publish_public_site.sh"
    script_path.write_text("#!/bin/zsh\necho missing\n")

    try:
        public_publish.prepare_publish_script(script_path=script_path, repo_root=tmp_path)
    except RuntimeError as exc:
        assert "missing expected repo-root line" in str(exc)
    else:
        raise AssertionError("prepare_publish_script should reject an unexpected publish script")


def test_prepare_publish_script_requires_expected_edge_root_line(tmp_path):
    script_path = tmp_path / "publish_public_site.sh"
    script_path.write_text('#!/bin/zsh\nREPO_ROOT="${0:A:h:h}"\necho missing edge\n')

    try:
        public_publish.prepare_publish_script(script_path=script_path, repo_root=tmp_path)
    except RuntimeError as exc:
        assert "missing expected edge-root line" in str(exc)
    else:
        raise AssertionError("prepare_publish_script should reject an unexpected edge-root line")


def test_prepare_publish_script_requires_expected_python_bin_line(tmp_path):
    script_path = tmp_path / "publish_public_site.sh"
    script_path.write_text(
        '#!/bin/zsh\nREPO_ROOT="${0:A:h:h}"\nEDGE_REPO_ROOT="$REPO_ROOT/../edge-of-epidemiology-site"\necho missing python\n'
    )

    try:
        public_publish.prepare_publish_script(script_path=script_path, repo_root=tmp_path)
    except RuntimeError as exc:
        assert "missing expected Python-bin line" in str(exc)
    else:
        raise AssertionError("prepare_publish_script should reject an unexpected Python-bin line")


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


def test_check_configuration_reports_prepared_script(tmp_path, monkeypatch, capsys):
    script_path = tmp_path / "publish_public_site.sh"
    script_path.write_text(
        '#!/bin/zsh\nREPO_ROOT="${0:A:h:h}"\nEDGE_REPO_ROOT="$REPO_ROOT/../edge-of-epidemiology-site"\nPYTHON_BIN="$REPO_ROOT/.venv/bin/python"\necho "$REPO_ROOT"\n',
    )
    lock_dir = tmp_path / "lock"
    monkeypatch.setattr(public_publish, "PUBLISH_SCRIPT", script_path)
    monkeypatch.setattr(public_publish, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(public_publish, "EDGE_REPO_ROOT", tmp_path / "edge-of-epidemiology-site")
    monkeypatch.setattr(public_publish, "LOCK_DIR", lock_dir)

    assert public_publish.main(["--check"]) == 0

    output = capsys.readouterr().out
    assert "public_publish_check_ok" in output
    assert f"repo_root={tmp_path}" in output
    assert "lock_state=ready" in output


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
