import json
from datetime import date, datetime
from pathlib import Path

from src import site_build


def test_site_build_writes_story_reference_and_index_files(tmp_path, monkeypatch):
    dated_html = tmp_path / "dated.html"
    legacy_html = tmp_path / "legacy.html"
    latest_html = tmp_path / "latest.html"
    story_path = tmp_path / "stories" / "story.html"
    reference_path = tmp_path / "reference" / "measles.html"
    index_path = tmp_path / "index.html"

    payload = {
        "target_date": date(2026, 5, 7),
        "window_days": 4,
        "generated_at": datetime(2026, 5, 7, 8, 0),
        "markdown_output": "# Sample dossier",
        "html_output": "<!DOCTYPE html><html><body>Measles transmission and vaccination</body></html>",
        "html_validation_issues": [],
        "processed": [],
        "story_updates": [],
        "outbreak_reference": [],
        "archive_entries": [],
        "source_failures": [],
        "promote_latest": True,
        "latest_snapshot": {
            "item_count": 1,
            "story_count": 1,
            "stories": [
                {
                    "story_id": "story_1",
                    "topic_name": "Measles transmission and vaccination",
                    "display_title": "Measles transmission and vaccination",
                    "story_url": story_path.resolve().as_uri(),
                    "item_count": 1,
                    "source_count": 1,
                    "official_item_ids": ["item_1"],
                    "press_item_ids": [],
                    "publisher_names": ["CDC"],
                    "latest_update_summary": "CDC still frames this as a vaccination-gap story.",
                    "latest_update_bullets": ["A new update landed."],
                    "first_seen_at": "2026-05-07T08:00:00",
                    "latest_updated_at": "2026-05-07T08:00:00",
                    "timeline": [],
                    "lead_title": "CDC update",
                    "lead_url": "https://example.com/cdc",
                    "lead_source": "CDC",
                }
            ],
            "reference": [
                {
                    "name": "Measles",
                    "reference_url": reference_path.resolve().as_uri(),
                    "pathogen": "Measles virus",
                    "transmission": "Airborne",
                    "categories": ["Vaccine-preventable"],
                    "field_guide_links": [],
                    "latest_outbreak": {"label": "Resurgence", "location": "United States", "period": "2025", "summary": "A large year.", "source_name": "CDC", "source_url": "https://example.com/measles", "as_of": "2026-04-24"},
                    "notable_outbreaks": [],
                    "surveillance_note": "",
                    "symptoms": [],
                    "outbreak_settings": [],
                }
            ],
            "items": [
                {
                    "item_id": "item_1",
                    "title": "CDC update",
                    "summary": "Official measles update.",
                    "publisher_name": "CDC",
                    "published_at": "2026-05-07T08:00",
                    "preferred_url": "https://example.com/cdc",
                    "link_quality": "direct",
                    "region": "North America",
                }
            ],
        },
        "paths": {
            "dated_html": dated_html,
            "legacy_html": legacy_html,
            "latest_html": latest_html,
        },
    }

    monkeypatch.setattr(site_build, "run_once", lambda *args, **kwargs: payload)
    monkeypatch.setattr(site_build, "story_filename", lambda *args, **kwargs: story_path)
    monkeypatch.setattr(site_build, "reference_filename", lambda *args, **kwargs: reference_path)
    monkeypatch.setattr(site_build, "site_index_filename", lambda: index_path)
    monkeypatch.setattr(site_build, "list_briefing_archives", lambda include_date=None: [])
    monkeypatch.setattr(site_build, "SITE_BUILD_LOG", tmp_path / "site-build.log")

    assert site_build.main(["--date", "2026-05-07"]) == 0
    assert story_path.exists()
    assert reference_path.exists()
    assert index_path.exists()
    assert latest_html.exists()


def test_site_build_writes_docs_outputs_without_file_uris(tmp_path, monkeypatch):
    dated_html = tmp_path / "Daily Dossiers" / "2026" / "05" / "2026-05-07.html"
    legacy_html = tmp_path / "briefings" / "2026-05-07_epi_dossier.html"
    latest_html = tmp_path / "Daily Dossiers" / "latest.html"
    latest_md = tmp_path / "Daily Dossiers" / "latest.md"
    story_path = tmp_path / "Daily Dossiers" / "stories" / "story.html"
    reference_path = tmp_path / "Daily Dossiers" / "reference" / "measles.html"
    index_path = tmp_path / "Daily Dossiers" / "index.html"
    deploy_dir = tmp_path / "docs"

    payload = {
        "target_date": date(2026, 5, 7),
        "window_days": 7,
        "generated_at": datetime(2026, 5, 7, 8, 0),
        "processed": [],
        "story_updates": [],
        "outbreak_reference": [],
        "archive_entries": [],
        "source_failures": [],
        "source_health": [],
        "promote_latest": True,
        "markdown_output": "# Sample dossier",
        "html_output": '<a href="file:///Users/devinteichrow/Downloads/Work%20and%20Statistics/Blogs/epi-dossier/Daily%20Dossiers/stories/story_1-measles-transmission-and-vaccination.html">Measles transmission and vaccination</a>',
        "html_validation_issues": [],
        "latest_snapshot": {
            "run_id": "run_1",
            "generated_at": "2026-05-07T08:00:00",
            "item_count": 1,
            "story_count": 1,
            "stories": [
                {
                    "story_id": "story_1",
                    "topic_name": "Measles transmission and vaccination",
                    "display_title": "Measles transmission and vaccination",
                    "story_url": story_path.resolve().as_uri(),
                    "story_web_path": "stories/story_1-measles-transmission-and-vaccination.html",
                    "editions": ["index", "watch"],
                    "item_count": 1,
                    "source_count": 1,
                    "official_item_ids": ["item_1"],
                    "press_item_ids": [],
                    "publisher_names": ["CDC"],
                    "latest_update_summary": "CDC still frames this as a vaccination-gap story.",
                    "latest_update_bullets": ["A new update landed."],
                    "first_seen_at": "2026-05-07T08:00:00",
                    "latest_updated_at": "2026-05-07T08:00:00",
                    "timeline": [],
                    "lead_title": "CDC update",
                    "lead_url": "https://example.com/cdc",
                    "lead_source": "CDC",
                    "status": "active_investigation",
                    "current_status_summary": "Active investigation",
                    "primary_region": "North America",
                    "country": "United States",
                }
            ],
            "reference": [
                {
                    "name": "Measles",
                    "reference_url": reference_path.resolve().as_uri(),
                    "reference_web_path": "reference/measles.html",
                    "editions": ["index", "research"],
                    "pathogen": "Measles virus",
                    "transmission": "Airborne",
                    "categories": ["Vaccine-preventable"],
                    "why_reporters_care": "High transmissibility exposes immunity gaps.",
                    "field_guide_links": [],
                    "latest_outbreak": {"label": "Resurgence", "location": "United States", "period": "2025", "summary": "A large year.", "source_name": "CDC", "source_url": "https://example.com/measles", "as_of": "2026-04-24"},
                    "notable_outbreaks": [],
                    "surveillance_note": "",
                    "symptoms": [],
                    "outbreak_settings": [],
                    "related_stories": [],
                }
            ],
            "items": [
                {
                    "item_id": "item_1",
                    "title": "CDC update",
                    "summary": "Official measles update.",
                    "publisher_name": "CDC",
                    "source": "CDC MMWR",
                    "published_at": "2026-05-07T08:00",
                    "preferred_url": "https://example.com/cdc",
                    "source_url": "https://example.com/cdc",
                    "link_quality": "direct_article",
                    "source_confidence": "official_agency",
                    "freshness_state": "live",
                    "region": "North America",
                    "evidence_type": "official_update",
                    "official": True,
                    "editions": ["index", "watch", "official"],
                }
            ],
            "editor_summary": {"wrapper_only_count": 0},
            "freshness_summary": {"live": 1, "refresh_cache": 0, "fallback_cache": 0, "retained": 0},
            "degraded": False,
            "source_failures": [],
        },
        "paths": {
            "dated_html": dated_html,
            "legacy_html": legacy_html,
            "latest_html": latest_html,
            "latest_markdown": latest_md,
        },
    }

    monkeypatch.setattr(site_build, "run_once", lambda *args, **kwargs: payload)
    monkeypatch.setattr(site_build, "story_filename", lambda *args, **kwargs: story_path)
    monkeypatch.setattr(site_build, "reference_filename", lambda *args, **kwargs: reference_path)
    monkeypatch.setattr(site_build, "site_index_filename", lambda: index_path)
    monkeypatch.setattr(site_build, "list_briefing_archives", lambda include_date=None: [])
    monkeypatch.setattr(site_build, "SITE_BUILD_LOG", tmp_path / "site-build.log")
    monkeypatch.setattr(site_build, "docs_dir", lambda deploy_dir='docs': deploy_dir if isinstance(deploy_dir, Path) else deploy_dir)
    monkeypatch.setattr(site_build, "docs_index_filename", lambda deploy_dir='docs': Path(deploy_dir) / "index.html")
    monkeypatch.setattr(site_build, "docs_desk_filename", lambda slug, deploy_dir='docs': Path(deploy_dir) / f"{slug}.html")
    monkeypatch.setattr(site_build, "docs_archive_index_filename", lambda deploy_dir='docs': Path(deploy_dir) / "archive" / "index.html")
    monkeypatch.setattr(site_build, "docs_story_filename", lambda *args, deploy_dir='docs', **kwargs: Path(deploy_dir) / "stories" / "story_1-measles-transmission-and-vaccination.html")
    monkeypatch.setattr(site_build, "docs_reference_filename", lambda *args, deploy_dir='docs', **kwargs: Path(deploy_dir) / "reference" / "measles.html")
    monkeypatch.setattr(site_build, "docs_archive_filename", lambda target_date, deploy_dir='docs', suffix='.html': Path(deploy_dir) / "2026" / "05" / f"2026-05-07{suffix}")

    assert site_build.main(["--date", "2026-05-07", "--output-mode", "both", "--deploy-dir", str(deploy_dir)]) == 0
    assert (deploy_dir / "index.html").exists()
    assert (deploy_dir / "watch.html").exists()
    assert (deploy_dir / "research.html").exists()
    assert (deploy_dir / "stories" / "story_1-measles-transmission-and-vaccination.html").exists()
    assert (deploy_dir / "reference" / "measles.html").exists()
    assert (deploy_dir / "archive" / "index.html").exists()
    latest_json = json.loads((deploy_dir / "app_exports" / "latest.json").read_text())
    assert latest_json["stories"][0]["story_url"] == "stories/story_1-measles-transmission-and-vaccination.html"
    latest_html_text = (deploy_dir / "latest.html").read_text()
    assert "file:///" not in latest_html_text
    assert "public-live-update-banner" in latest_html_text
    assert "./app_exports/manifest.json" in latest_html_text
    assert "Load latest" in latest_html_text
    assert "Keep reading" in latest_html_text
    assert "__pathogenLoadPublicLatest" in latest_html_text
    assert "__pathogenDismissPublicUpdate" in latest_html_text
    assert "_edition" in latest_html_text
    public_story_text = (deploy_dir / "stories" / "story_1-measles-transmission-and-vaccination.html").read_text()
    assert "../app_exports/manifest.json" in public_story_text
    assert "Load latest" in public_story_text
    assert "Keep reading" in public_story_text
    research_text = (deploy_dir / "research.html").read_text()
    assert "Latest Papers And Preprints" in research_text


def test_site_build_preserves_existing_reader_html_when_reader_guard_blocks(tmp_path, monkeypatch):
    dated_html = tmp_path / "Daily Dossiers" / "2026" / "05" / "2026-05-07.html"
    legacy_html = tmp_path / "briefings" / "2026-05-07_epi_dossier.html"
    latest_html = tmp_path / "Daily Dossiers" / "latest.html"
    latest_html.parent.mkdir(parents=True, exist_ok=True)
    latest_html.write_text("keep local latest", encoding="utf-8")
    story_path = tmp_path / "Daily Dossiers" / "stories" / "story.html"
    reference_path = tmp_path / "Daily Dossiers" / "reference" / "measles.html"
    index_path = tmp_path / "Daily Dossiers" / "index.html"
    deploy_dir = tmp_path / "docs"
    deploy_dir.mkdir(parents=True, exist_ok=True)
    (deploy_dir / "latest.html").write_text("keep public latest", encoding="utf-8")

    payload = {
        "target_date": date(2026, 5, 7),
        "window_days": 7,
        "generated_at": datetime(2026, 5, 7, 8, 0),
        "processed": [],
        "story_updates": [],
        "outbreak_reference": [],
        "archive_entries": [],
        "source_failures": [],
        "source_health": [],
        "promote_latest": True,
        "markdown_output": "# Sample dossier",
        "html_output": '<p class="empty-note">No lead outbreak files are featured in this edition.</p>',
        "html_validation_issues": ["Lead outbreak files rendered as empty despite active story records."],
        "latest_snapshot": {
            "run_id": "run_2",
            "generated_at": "2026-05-07T08:00:00",
            "item_count": 1,
            "story_count": 1,
            "stories": [
                {
                    "story_id": "story_1",
                    "topic_name": "Measles transmission and vaccination",
                    "display_title": "Measles transmission and vaccination",
                    "story_url": story_path.resolve().as_uri(),
                    "story_web_path": "stories/story_1-measles-transmission-and-vaccination.html",
                    "editions": ["index", "watch"],
                    "item_count": 1,
                    "source_count": 1,
                    "official_item_ids": ["item_1"],
                    "press_item_ids": [],
                    "publisher_names": ["CDC"],
                    "latest_update_summary": "CDC still frames this as a vaccination-gap story.",
                    "latest_update_bullets": ["A new update landed."],
                    "first_seen_at": "2026-05-07T08:00:00",
                    "latest_updated_at": "2026-05-07T08:00:00",
                    "timeline": [],
                    "lead_title": "CDC update",
                    "lead_url": "https://example.com/cdc",
                    "lead_source": "CDC",
                    "status": "active_investigation",
                    "current_status_summary": "Active investigation",
                    "primary_region": "North America",
                    "country": "United States",
                }
            ],
            "reference": [
                {
                    "name": "Measles",
                    "reference_url": reference_path.resolve().as_uri(),
                    "reference_web_path": "reference/measles.html",
                    "editions": ["index", "research"],
                    "pathogen": "Measles virus",
                    "transmission": "Airborne",
                    "categories": ["Vaccine-preventable"],
                    "why_reporters_care": "High transmissibility exposes immunity gaps.",
                    "field_guide_links": [],
                    "latest_outbreak": {"label": "Resurgence", "location": "United States", "period": "2025", "summary": "A large year.", "source_name": "CDC", "source_url": "https://example.com/measles", "as_of": "2026-04-24"},
                    "notable_outbreaks": [],
                    "surveillance_note": "",
                    "symptoms": [],
                    "outbreak_settings": [],
                    "related_stories": [],
                }
            ],
            "items": [
                {
                    "item_id": "item_1",
                    "title": "CDC update",
                    "summary": "Official measles update.",
                    "publisher_name": "CDC",
                    "source": "CDC MMWR",
                    "published_at": "2026-05-07T08:00",
                    "preferred_url": "https://example.com/cdc",
                    "source_url": "https://example.com/cdc",
                    "link_quality": "direct_article",
                    "source_confidence": "official_agency",
                    "freshness_state": "live",
                    "region": "North America",
                    "evidence_type": "official_update",
                    "official": True,
                    "editions": ["index", "watch", "official"],
                }
            ],
            "editor_summary": {"wrapper_only_count": 0},
            "freshness_summary": {"live": 1, "refresh_cache": 0, "fallback_cache": 0, "retained": 0},
            "degraded": False,
            "source_failures": [],
        },
        "paths": {
            "dated_html": dated_html,
            "legacy_html": legacy_html,
            "latest_html": latest_html,
        },
    }

    monkeypatch.setattr(site_build, "run_once", lambda *args, **kwargs: payload)
    monkeypatch.setattr(site_build, "story_filename", lambda *args, **kwargs: story_path)
    monkeypatch.setattr(site_build, "reference_filename", lambda *args, **kwargs: reference_path)
    monkeypatch.setattr(site_build, "site_index_filename", lambda: index_path)
    monkeypatch.setattr(site_build, "list_briefing_archives", lambda include_date=None: [])
    monkeypatch.setattr(site_build, "SITE_BUILD_LOG", tmp_path / "site-build.log")
    monkeypatch.setattr(site_build, "docs_dir", lambda deploy_dir='docs': deploy_dir if isinstance(deploy_dir, Path) else deploy_dir)
    monkeypatch.setattr(site_build, "docs_index_filename", lambda deploy_dir='docs': Path(deploy_dir) / "index.html")
    monkeypatch.setattr(site_build, "docs_desk_filename", lambda slug, deploy_dir='docs': Path(deploy_dir) / f"{slug}.html")
    monkeypatch.setattr(site_build, "docs_archive_index_filename", lambda deploy_dir='docs': Path(deploy_dir) / "archive" / "index.html")
    monkeypatch.setattr(site_build, "docs_story_filename", lambda *args, deploy_dir='docs', **kwargs: Path(deploy_dir) / "stories" / "story_1-measles-transmission-and-vaccination.html")
    monkeypatch.setattr(site_build, "docs_reference_filename", lambda *args, deploy_dir='docs', **kwargs: Path(deploy_dir) / "reference" / "measles.html")
    monkeypatch.setattr(site_build, "docs_archive_filename", lambda target_date, deploy_dir='docs', suffix='.html': Path(deploy_dir) / "2026" / "05" / f"2026-05-07{suffix}")

    assert site_build.main(["--date", "2026-05-07", "--output-mode", "both", "--deploy-dir", str(deploy_dir)]) == 0
    assert latest_html.read_text(encoding="utf-8") == "keep local latest"
    assert (deploy_dir / "latest.html").read_text(encoding="utf-8") == "keep public latest"
