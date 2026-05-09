from datetime import date
from pathlib import Path

from src.database import SeenItemsDB
from src.utils import Item, legacy_briefing_filename


def test_database_insert_and_seen_url(tmp_path: Path):
    db = SeenItemsDB(tmp_path / "test.sqlite")
    item = Item(title="Example", source="CDC", url="https://example.com/a", category="c")
    db.mark_seen(item)
    assert db.has_seen_url(item.canonical_url) is True
    db.close()


def test_database_detects_similar_titles(tmp_path: Path):
    db = SeenItemsDB(tmp_path / "test.sqlite")
    item = Item(title="Measles outbreak in Texas expands", source="CDC", url="https://example.com/a", category="c")
    db.mark_seen(item)
    assert db.has_similar_title("Measles outbreak in Texas expands.") is True
    db.close()


def test_legacy_briefing_filename_shape():
    target = legacy_briefing_filename(date(2026, 5, 3))
    assert target.name == "2026-05-03_epi_dossier.md"
    assert target.parent.name == "briefings"


def test_story_snapshot_round_trip(tmp_path: Path):
    db = SeenItemsDB(tmp_path / "test.sqlite")
    snapshot = {"topic_name": "Hantavirus and cruise-ship outbreak", "flags": ["deaths_reported"]}
    db.save_story_snapshot("Hantavirus and cruise-ship outbreak", snapshot)
    loaded = db.load_story_snapshots()
    assert loaded["Hantavirus and cruise-ship outbreak"]["flags"] == ["deaths_reported"]
    db.close()


def test_load_story_updates_for_story_skips_noop_entries(tmp_path: Path):
    db = SeenItemsDB(tmp_path / "test.sqlite")
    db.append_story_update(
        "update_1",
        "story_1",
        "run_1",
        {"update_id": "update_1", "story_id": "story_1", "bullets": ["Deaths now reported."], "is_new_story": False},
        "2026-05-05T06:30:00",
    )
    db.append_story_update(
        "update_2",
        "story_1",
        "run_2",
        {"update_id": "update_2", "story_id": "story_1", "bullets": [], "is_new_story": False},
        "2026-05-05T06:31:00",
    )

    updates = db.load_story_updates_for_story("story_1")
    assert len(updates) == 1
    assert updates[0]["update_id"] == "update_1"
    db.close()
