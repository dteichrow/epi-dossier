from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from src import public_publish_watchdog
from src.utils import stable_id


def test_watchdog_defaults_to_canonical_public_manifest():
    assert public_publish_watchdog.PUBLIC_MANIFEST_URL.endswith("/app_exports/manifest.json")
    assert public_publish_watchdog.PUBLIC_LATEST_URL.endswith("/app_exports/latest.json")
    assert public_publish_watchdog.UPSTREAM_MANIFEST_URL.endswith("/docs/app_exports/manifest.json")
    assert public_publish_watchdog.DEFAULT_STALE_MINUTES == 35
    assert public_publish_watchdog.DEFAULT_NEW_ITEM_MIN_PUBLISH_INTERVAL_MINUTES == 30


def test_watchdog_launch_agent_checks_the_live_export_and_dispatches_remotely():
    agent = Path(__file__).resolve().parents[1] / "automation" / "com.codex.epi-dossier.public-publish-watchdog.plist"
    content = agent.read_text()

    assert "https://dteichrow.github.io/app_exports/manifest.json" in content
    assert "EPI_DOSSIER_WATCHDOG_PUBLISH_MODE" in content
    assert "github_actions" in content
    assert "/opt/homebrew/bin/gh" in content
    assert "EPI_DOSSIER_WATCHDOG_UPSTREAM_MANIFEST_URL" in content
    assert "EPI_DOSSIER_WATCHDOG_UMBRELLA_WORKFLOW" in content
    assert "<key>EPI_DOSSIER_WATCHDOG_STALE_MINUTES</key>\n      <string>35</string>" in content


def test_manifest_age_minutes_handles_local_naive_generated_at():
    now = datetime(2026, 5, 22, 7, 34, tzinfo=timezone(timedelta(hours=-7)))
    manifest = {"generated_at": "2026-05-22T05:17:29"}

    age = public_publish_watchdog.manifest_age_minutes(manifest, now=now)

    assert 136 < age < 137


def test_manifest_age_minutes_handles_offset_generated_at():
    now = datetime(2026, 5, 22, 7, 34, tzinfo=timezone(timedelta(hours=-7)))
    manifest = {"generated_at": "2026-05-22T14:17:29+00:00"}

    age = public_publish_watchdog.manifest_age_minutes(manifest, now=now)

    assert 16 < age < 17


def test_manifest_age_minutes_handles_legacy_utc_naive_generated_at():
    now = datetime(2026, 5, 23, 9, 51, tzinfo=timezone(timedelta(hours=-7)))
    manifest = {"generated_at": "2026-05-23T15:35:45"}

    age = public_publish_watchdog.manifest_age_minutes(manifest, now=now)

    assert 75 < age < 76


def test_manifest_is_newer_uses_the_generated_timestamp():
    now = datetime(2026, 5, 22, 7, 34, tzinfo=timezone(timedelta(hours=-7)))

    assert public_publish_watchdog.manifest_is_newer(
        {"generated_at": "2026-05-22T14:20:00+00:00"},
        {"generated_at": "2026-05-22T14:17:29+00:00"},
        now=now,
    )


def test_cache_busting_url_preserves_existing_query_parameters(monkeypatch):
    monkeypatch.setattr(public_publish_watchdog.time, "time_ns", lambda: 123)

    assert public_publish_watchdog.cache_busting_url("https://example.com/manifest.json") == "https://example.com/manifest.json?watchdog=123"
    assert public_publish_watchdog.cache_busting_url("https://example.com/manifest.json?cache=1") == "https://example.com/manifest.json?cache=1&watchdog=123"


def test_find_new_candidate_items_detects_item_absent_from_live_feed():
    live_snapshot = {
        "items": [
            {
                "item_id": stable_id("item", "https://example.com/already-live"),
                "canonical_url": "https://example.com/already-live",
            }
        ]
    }
    candidates = [
        SimpleNamespace(canonical_url="https://example.com/already-live", title="Already live", source="Example"),
        SimpleNamespace(canonical_url="https://example.com/new-report", title="New report", source="Example"),
    ]

    new_items = public_publish_watchdog.find_new_candidate_items(candidates, live_snapshot)

    assert [item.title for item in new_items] == ["New report"]


def test_find_new_candidate_items_matches_live_item_id_when_url_is_missing():
    canonical_url = "https://example.com/report?utm_source=newsletter"
    live_snapshot = {"items": [{"item_id": stable_id("item", "https://example.com/report")}]}
    candidates = [SimpleNamespace(canonical_url=canonical_url, title="Report", source="Example")]

    new_items = public_publish_watchdog.find_new_candidate_items(candidates, live_snapshot)

    assert new_items == []


def test_main_publishes_when_fresh_manifest_has_new_candidate(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(public_publish_watchdog, "WATCHDOG_STATE_PATH", tmp_path / "watchdog-state.json")
    monkeypatch.setattr(public_publish_watchdog, "fetch_manifest", lambda url, timeout_seconds: {"generated_at": "fresh"})
    monkeypatch.setattr(public_publish_watchdog, "manifest_age_minutes", lambda manifest: 34)
    monkeypatch.setattr(public_publish_watchdog, "fetch_live_latest", lambda timeout_seconds: {"items": []})
    monkeypatch.setattr(
        public_publish_watchdog,
        "run_candidate_search",
        lambda window_days: [SimpleNamespace(canonical_url="https://example.com/new", title="New", source="Example")],
    )
    monkeypatch.setattr(public_publish_watchdog, "run_public_publish", lambda: calls.append("publish") or 0)

    assert public_publish_watchdog.main([]) == 0
    assert calls == ["publish"]


def test_main_skips_new_candidate_publish_when_manifest_is_too_recent(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(public_publish_watchdog, "WATCHDOG_STATE_PATH", tmp_path / "watchdog-state.json")
    monkeypatch.setattr(public_publish_watchdog, "fetch_manifest", lambda url, timeout_seconds: {"generated_at": "fresh"})
    monkeypatch.setattr(public_publish_watchdog, "manifest_age_minutes", lambda manifest: 10)
    monkeypatch.setattr(public_publish_watchdog, "fetch_live_latest", lambda timeout_seconds: {"items": []})
    monkeypatch.setattr(
        public_publish_watchdog,
        "run_candidate_search",
        lambda window_days: [SimpleNamespace(canonical_url="https://example.com/new", title="New", source="Example")],
    )
    monkeypatch.setattr(public_publish_watchdog, "run_public_publish", lambda: calls.append("publish") or 0)

    assert public_publish_watchdog.main([]) == 0
    assert calls == []


def test_main_does_not_republish_same_new_candidate_identity(monkeypatch, tmp_path):
    calls = []
    state_path = tmp_path / "watchdog-state.json"
    monkeypatch.setattr(public_publish_watchdog, "WATCHDOG_STATE_PATH", state_path)
    monkeypatch.setattr(public_publish_watchdog, "fetch_manifest", lambda url, timeout_seconds: {"generated_at": "fresh"})
    monkeypatch.setattr(public_publish_watchdog, "manifest_age_minutes", lambda manifest: 34)
    monkeypatch.setattr(public_publish_watchdog, "fetch_live_latest", lambda timeout_seconds: {"items": []})
    monkeypatch.setattr(
        public_publish_watchdog,
        "run_candidate_search",
        lambda window_days: [SimpleNamespace(canonical_url="https://example.com/new", title="New", source="Example")],
    )
    monkeypatch.setattr(public_publish_watchdog, "run_public_publish", lambda: calls.append("publish") or 0)

    assert public_publish_watchdog.main([]) == 0
    assert public_publish_watchdog.main([]) == 0
    assert calls == ["publish"]


def test_main_publishes_when_new_candidate_identity_appears(monkeypatch, tmp_path):
    calls = []
    state_path = tmp_path / "watchdog-state.json"
    monkeypatch.setattr(public_publish_watchdog, "WATCHDOG_STATE_PATH", state_path)
    monkeypatch.setattr(public_publish_watchdog, "fetch_manifest", lambda url, timeout_seconds: {"generated_at": "fresh"})
    monkeypatch.setattr(public_publish_watchdog, "manifest_age_minutes", lambda manifest: 34)
    monkeypatch.setattr(public_publish_watchdog, "fetch_live_latest", lambda timeout_seconds: {"items": []})
    candidate_batches = [
        [SimpleNamespace(canonical_url="https://example.com/new", title="New", source="Example")],
        [
            SimpleNamespace(canonical_url="https://example.com/new", title="New", source="Example"),
            SimpleNamespace(canonical_url="https://example.com/newer", title="Newer", source="Example"),
        ],
    ]
    monkeypatch.setattr(public_publish_watchdog, "run_candidate_search", lambda window_days: candidate_batches.pop(0))
    monkeypatch.setattr(public_publish_watchdog, "run_public_publish", lambda: calls.append("publish") or 0)

    assert public_publish_watchdog.main([]) == 0
    assert public_publish_watchdog.main([]) == 0
    assert calls == ["publish", "publish"]


def test_main_does_not_publish_when_fresh_manifest_has_no_new_candidates(monkeypatch):
    calls = []
    canonical = "https://example.com/live"
    monkeypatch.setattr(public_publish_watchdog, "fetch_manifest", lambda url, timeout_seconds: {"generated_at": "fresh"})
    monkeypatch.setattr(public_publish_watchdog, "manifest_age_minutes", lambda manifest: 10)
    monkeypatch.setattr(public_publish_watchdog, "fetch_live_latest", lambda timeout_seconds: {"items": [{"canonical_url": canonical}]})
    monkeypatch.setattr(
        public_publish_watchdog,
        "run_candidate_search",
        lambda window_days: [SimpleNamespace(canonical_url=canonical, title="Live", source="Example")],
    )
    monkeypatch.setattr(public_publish_watchdog, "run_public_publish", lambda: calls.append("publish") or 0)

    assert public_publish_watchdog.main([]) == 0
    assert calls == []


def test_github_actions_recovery_dispatch_is_rate_limited(monkeypatch, tmp_path):
    calls = []
    state_path = tmp_path / "watchdog-state.json"
    monkeypatch.setattr(public_publish_watchdog, "run_github_actions_publish", lambda **kwargs: calls.append(kwargs) or 0)

    assert public_publish_watchdog.request_publish(
        publish_mode="github_actions",
        remote_dispatch_cooldown_minutes=45,
        state_path=state_path,
    ) == 0
    assert public_publish_watchdog.request_publish(
        publish_mode="github_actions",
        remote_dispatch_cooldown_minutes=45,
        state_path=state_path,
    ) == 0

    assert len(calls) == 1
    assert public_publish_watchdog.load_watchdog_state(state_path)["last_github_actions_dispatch_at"]


def test_umbrella_recovery_dispatch_has_an_independent_cooldown(monkeypatch, tmp_path):
    calls = []
    state_path = tmp_path / "watchdog-state.json"
    monkeypatch.setattr(public_publish_watchdog, "run_github_actions_publish", lambda **kwargs: calls.append(kwargs) or 0)

    assert public_publish_watchdog.request_umbrella_publish(
        dispatch_cooldown_minutes=30,
        state_path=state_path,
        upstream_generated_at="2026-05-05T06:30:00",
    ) == 0
    assert public_publish_watchdog.request_umbrella_publish(
        dispatch_cooldown_minutes=30,
        state_path=state_path,
        upstream_generated_at="2026-05-05T06:30:00",
    ) == 0
    assert public_publish_watchdog.request_umbrella_publish(
        dispatch_cooldown_minutes=30,
        state_path=state_path,
        upstream_generated_at="2026-05-05T06:35:00",
    ) == 0

    assert len(calls) == 2
    assert calls[0]["repository"] == "dteichrow/dteichrow.github.io"
    assert calls[0]["workflow"] == "deploy-pages.yml"
    assert public_publish_watchdog.load_watchdog_state(state_path)["last_umbrella_dispatch_at"]
    assert public_publish_watchdog.load_watchdog_state(state_path)["last_umbrella_artifact_generated_at"] == "2026-05-05T06:35:00"


def test_watchdog_can_skip_umbrella_dispatch_when_runner_has_no_cross_repo_credential(monkeypatch, tmp_path):
    live_manifest = {"generated_at": "2026-05-05T06:00:00"}
    calls = []

    def unexpected_umbrella_dispatch(**kwargs):
        raise AssertionError(f"umbrella dispatch should be disabled, got {kwargs}")

    monkeypatch.setenv("EPI_DOSSIER_WATCHDOG_ENABLE_UMBRELLA_DISPATCH", "false")
    monkeypatch.setenv("EPI_DOSSIER_WATCHDOG_CHECK_NEW_ITEMS", "false")
    monkeypatch.setenv("EPI_DOSSIER_WATCHDOG_MANIFEST_URL", "https://example.test/live")
    monkeypatch.setenv("EPI_DOSSIER_WATCHDOG_UPSTREAM_MANIFEST_URL", "https://example.test/upstream")
    monkeypatch.setattr(public_publish_watchdog, "fetch_manifest", lambda **kwargs: calls.append(kwargs["url"]) or live_manifest)
    monkeypatch.setattr(public_publish_watchdog, "request_umbrella_publish", unexpected_umbrella_dispatch)
    monkeypatch.setattr(public_publish_watchdog, "manifest_age_minutes", lambda manifest: 1)
    monkeypatch.setattr(public_publish_watchdog, "WATCHDOG_STATE_PATH", tmp_path / "watchdog-state.json")

    assert public_publish_watchdog.main([]) == 0
    assert calls == ["https://example.test/live"]


def test_manifest_age_minutes_rejects_missing_generated_at():
    try:
        public_publish_watchdog.manifest_age_minutes({})
    except ValueError as exc:
        assert "generated_at" in str(exc)
    else:
        raise AssertionError("missing generated_at should be rejected")
