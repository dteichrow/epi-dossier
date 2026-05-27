from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src import public_publish_watchdog
from src.utils import stable_id


def test_watchdog_defaults_to_canonical_project_manifest():
    assert public_publish_watchdog.PUBLIC_MANIFEST_URL.endswith("/epi-dossier/app_exports/manifest.json")
    assert public_publish_watchdog.PUBLIC_LATEST_URL.endswith("/epi-dossier/app_exports/latest.json")
    assert public_publish_watchdog.DEFAULT_STALE_MINUTES == 45


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


def test_main_publishes_when_fresh_manifest_has_new_candidate(monkeypatch):
    calls = []
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
    assert calls == ["publish"]


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


def test_manifest_age_minutes_rejects_missing_generated_at():
    try:
        public_publish_watchdog.manifest_age_minutes({})
    except ValueError as exc:
        assert "generated_at" in str(exc)
    else:
        raise AssertionError("missing generated_at should be rejected")
