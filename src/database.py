from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .dedupe import titles_similar
from .utils import Item, SQLITE_PATH, clean_headline


SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    source TEXT,
    first_seen_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_seen_title ON seen_items(title);

CREATE TABLE IF NOT EXISTS story_snapshots (
    topic_name TEXT PRIMARY KEY,
    snapshot_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_runs (
    run_id TEXT PRIMARY KEY,
    target_date TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    search_window TEXT NOT NULL,
    item_count INTEGER NOT NULL,
    story_count INTEGER NOT NULL,
    topic_count INTEGER NOT NULL,
    degraded INTEGER NOT NULL DEFAULT 0,
    source_failures_json TEXT NOT NULL,
    snapshot_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_feed_items (
    item_id TEXT PRIMARY KEY,
    canonical_url TEXT NOT NULL UNIQUE,
    latest_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_stories (
    story_id TEXT PRIMARY KEY,
    topic_name TEXT NOT NULL UNIQUE,
    latest_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_story_updates (
    update_id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    update_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_topics (
    topic_id TEXT PRIMARY KEY,
    topic_name TEXT NOT NULL UNIQUE,
    latest_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class SeenItemsDB:
    def __init__(self, path: Path = SQLITE_PATH) -> None:
        self.path = path
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self._migrate_schema()
        self.connection.commit()

    def _migrate_schema(self) -> None:
        columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(seen_items)").fetchall()
        }
        if "normalized_title" not in columns:
            self.connection.execute(
                "ALTER TABLE seen_items ADD COLUMN normalized_title TEXT NOT NULL DEFAULT ''"
            )
        rows = self.connection.execute(
            "SELECT id, title FROM seen_items WHERE normalized_title = ''"
        ).fetchall()
        for row in rows:
            self.connection.execute(
                "UPDATE seen_items SET normalized_title = ? WHERE id = ?",
                (clean_headline(row["title"]).lower(), row["id"]),
            )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_seen_normalized_title ON seen_items(normalized_title)"
        )

    def has_seen_url(self, canonical_url: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM seen_items WHERE canonical_url = ?",
            (canonical_url,),
        ).fetchone()
        return row is not None

    def has_similar_title(self, title: str) -> bool:
        normalized_title = clean_headline(title).lower()
        rows = self.connection.execute(
            "SELECT title FROM seen_items WHERE normalized_title = ? OR normalized_title LIKE ? OR normalized_title LIKE ?",
            (normalized_title, f"{normalized_title[:40]}%", f"%{normalized_title[-40:]}"),
        ).fetchall()
        if not rows:
            rows = self.connection.execute("SELECT title FROM seen_items").fetchall()
        return any(titles_similar(title, row["title"]) for row in rows)

    def mark_seen(self, item: Item) -> None:
        self.connection.execute(
            """
            INSERT OR IGNORE INTO seen_items(canonical_url, title, normalized_title, source, first_seen_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                item.canonical_url,
                item.title,
                clean_headline(item.title).lower(),
                item.source,
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
        self.connection.commit()

    def load_story_snapshots(self) -> dict[str, dict]:
        rows = self.connection.execute(
            "SELECT topic_name, snapshot_json FROM story_snapshots"
        ).fetchall()
        snapshots: dict[str, dict] = {}
        for row in rows:
            try:
                snapshots[row["topic_name"]] = json.loads(row["snapshot_json"])
            except json.JSONDecodeError:
                continue
        return snapshots

    def save_story_snapshot(self, topic_name: str, snapshot: dict) -> None:
        self.connection.execute(
            """
            INSERT INTO story_snapshots(topic_name, snapshot_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(topic_name) DO UPDATE SET
                snapshot_json = excluded.snapshot_json,
                updated_at = excluded.updated_at
            """,
            (
                topic_name,
                json.dumps(snapshot, sort_keys=True),
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
        self.connection.commit()

    def load_app_feed_items(self) -> dict[str, dict]:
        return self._load_json_map("SELECT item_id, latest_json FROM app_feed_items", "item_id")

    def load_app_stories(self) -> dict[str, dict]:
        return self._load_json_map("SELECT story_id, latest_json FROM app_stories", "story_id")

    def load_app_topics(self) -> dict[str, dict]:
        return self._load_json_map("SELECT topic_id, latest_json FROM app_topics", "topic_id")

    def load_latest_app_run(self) -> dict | None:
        row = self.connection.execute(
            "SELECT snapshot_json FROM app_runs ORDER BY generated_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["snapshot_json"])
        except json.JSONDecodeError:
            return None

    def load_story_updates_for_story(self, story_id: str) -> list[dict]:
        rows = self.connection.execute(
            "SELECT update_json FROM app_story_updates WHERE story_id = ? ORDER BY created_at ASC",
            (story_id,),
        ).fetchall()
        updates: list[dict] = []
        for row in rows:
            try:
                payload = json.loads(row["update_json"])
            except json.JSONDecodeError:
                continue
            if not payload.get("bullets") and not payload.get("is_new_story"):
                continue
            updates.append(payload)
        return updates

    def save_app_run(self, run_record: dict) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO app_runs(
                run_id, target_date, generated_at, search_window, item_count, story_count,
                topic_count, degraded, source_failures_json, snapshot_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_record["run_id"],
                run_record["target_date"],
                run_record["generated_at"],
                run_record["search_window"],
                run_record["item_count"],
                run_record["story_count"],
                run_record["topic_count"],
                1 if run_record["degraded"] else 0,
                json.dumps(run_record["source_failures"], sort_keys=True),
                json.dumps(run_record, sort_keys=True),
            ),
        )
        self.connection.commit()

    def upsert_app_feed_item(self, item_id: str, canonical_url: str, payload: dict, content_hash: str, seen_at: str) -> None:
        existing = self.connection.execute(
            "SELECT first_seen_at FROM app_feed_items WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        first_seen_at = existing["first_seen_at"] if existing else seen_at
        self.connection.execute(
            """
            INSERT OR REPLACE INTO app_feed_items(
                item_id, canonical_url, latest_json, content_hash, first_seen_at, last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                canonical_url,
                json.dumps(payload, sort_keys=True),
                content_hash,
                first_seen_at,
                seen_at,
            ),
        )
        self.connection.commit()

    def upsert_app_story(self, story_id: str, topic_name: str, payload: dict, content_hash: str, updated_at: str) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO app_stories(story_id, topic_name, latest_json, content_hash, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                story_id,
                topic_name,
                json.dumps(payload, sort_keys=True),
                content_hash,
                updated_at,
            ),
        )
        self.connection.commit()

    def append_story_update(self, update_id: str, story_id: str, run_id: str, payload: dict, created_at: str) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO app_story_updates(update_id, story_id, run_id, update_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                update_id,
                story_id,
                run_id,
                json.dumps(payload, sort_keys=True),
                created_at,
            ),
        )
        self.connection.commit()

    def upsert_app_topic(self, topic_id: str, topic_name: str, payload: dict, content_hash: str, updated_at: str) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO app_topics(topic_id, topic_name, latest_json, content_hash, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                topic_id,
                topic_name,
                json.dumps(payload, sort_keys=True),
                content_hash,
                updated_at,
            ),
        )
        self.connection.commit()

    def _load_json_map(self, query: str, key_name: str) -> dict[str, dict]:
        rows = self.connection.execute(query).fetchall()
        payloads: dict[str, dict] = {}
        for row in rows:
            try:
                payloads[row[key_name]] = json.loads(row["latest_json"])
            except json.JSONDecodeError:
                continue
        return payloads

    def close(self) -> None:
        self.connection.close()
