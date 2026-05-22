from datetime import datetime, timedelta, timezone

from src import public_publish_watchdog


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


def test_manifest_age_minutes_rejects_missing_generated_at():
    try:
        public_publish_watchdog.manifest_age_minutes({})
    except ValueError as exc:
        assert "generated_at" in str(exc)
    else:
        raise AssertionError("missing generated_at should be rejected")
