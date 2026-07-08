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
    assert (latest_html.parent / "notebook.html").exists()
    assert (latest_html.parent / "atlas.html").exists()


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
            "atlas": [
                {
                    "slug": "measles",
                    "name": "Measles",
                    "subtitle": "Colonial spread and immunity gaps",
                    "status": "mixed",
                    "pathogen_type": "Virus",
                    "summary": "A test atlas entry.",
                    "why_it_matters": "A test atlas entry matters.",
                    "atlas_scope": "Test scope",
                    "origin_claim": {
                        "label": "Eurasian origin zone",
                        "coordinates": [35.5, 32.0],
                        "date_or_era": "Antiquity",
                        "confidence": "moderate",
                        "narrative": "A test origin narrative.",
                    },
                    "spread_routes": [
                        {
                            "route_id": "measles-test-route",
                            "from_label": "Origin",
                            "to_label": "Americas",
                            "from_coordinates": [35.5, 32.0],
                            "to_coordinates": [-76.0, 18.5],
                            "date_or_era": "Colonial era",
                            "route_type": "maritime",
                            "confidence": "strong",
                            "narrative": "A test route.",
                            "citation_ids": ["measles-test-citation"],
                        }
                    ],
                    "modern_echoes": ["Immunity gaps still matter."],
                    "framing_traps": ["Do not overstate certainty."],
                    "linked_reference_slug": "measles",
                    "linked_story_ids": ["story_1"],
                    "linked_blog_posts": [],
                    "citations": [
                        {
                            "id": "measles-test-citation",
                            "short_citation": "Test citation.",
                            "url": "https://example.com/paper",
                            "claim_supported": "Route history.",
                            "note": "Testing.",
                        }
                    ],
                    "visual_asset_id": "atlas-measles-hero",
                    "atlas_url": "atlas.html?pathogen=measles",
                    "reference_name": "Measles",
                    "reference_url": reference_path.resolve().as_uri(),
                    "reference_web_path": "reference/measles.html",
                    "related_stories": [
                        {
                            "story_id": "story_1",
                            "display_title": "Measles transmission and vaccination",
                            "story_url": story_path.resolve().as_uri(),
                            "story_web_path": "stories/story_1-measles-transmission-and-vaccination.html",
                            "latest_update_summary": "CDC still frames this as a vaccination-gap story.",
                        }
                    ],
                    "story_count": 1,
                    "citation_count": 1,
                    "route_count": 1,
                    "visual_asset": {
                        "asset_id": "atlas-measles-hero",
                        "pathogen_slug": "measles",
                        "surface": "hero",
                        "prompt": "Test prompt.",
                        "negative_prompt": "Test negative prompt.",
                        "output_path": "graphics/atlas/generated/measles-hero.png",
                        "alt_text": "Test atlas art.",
                        "source_mode": "gpt-image-2",
                        "status": "pending",
                        "editorial_note": "Testing.",
                    },
                    "writing_state": "not_yet_written",
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

    stale_story = deploy_dir / "stories" / "story_old-hantavirus-and-cruise-ship-outbreak.html"
    stale_story.parent.mkdir(parents=True, exist_ok=True)
    stale_story.write_text("archived story stays public", encoding="utf-8")

    assert site_build.main(["--date", "2026-05-07", "--output-mode", "both", "--deploy-dir", str(deploy_dir)]) == 0
    assert (deploy_dir / "index.html").exists()
    assert (deploy_dir / "notebook.html").exists()
    assert (deploy_dir / "atlas.html").exists()
    assert (deploy_dir / "watch.html").exists()
    assert (deploy_dir / "research.html").exists()
    assert (deploy_dir / "stories" / "story_1-measles-transmission-and-vaccination.html").exists()
    assert stale_story.read_text(encoding="utf-8") == "archived story stays public"
    assert (deploy_dir / "reference" / "measles.html").exists()
    assert (deploy_dir / "archive" / "index.html").exists()
    latest_json = json.loads((deploy_dir / "app_exports" / "latest.json").read_text())
    atlas_json = json.loads((deploy_dir / "app_exports" / "atlas.json").read_text())
    assert latest_json["stories"][0]["story_url"] == "stories/story_1-measles-transmission-and-vaccination.html"
    assert "atlas" in atlas_json
    latest_html_text = (deploy_dir / "latest.html").read_text()
    atlas_html_text = (deploy_dir / "atlas.html").read_text()
    assert "file:///" not in latest_html_text
    assert "file:///" not in atlas_html_text
    assert "/atlases/pathogen/" in atlas_html_text
    assert "window.location.search" in atlas_html_text
    assert "window.location.hash" in atlas_html_text
    assert "public-live-update-banner" in latest_html_text
    assert "./app_exports/manifest.json" in latest_html_text
    assert "Load latest" in latest_html_text
    assert "Keep reading" in latest_html_text
    assert "__pathogenLoadPublicLatest" in latest_html_text
    assert "__pathogenDismissPublicUpdate" in latest_html_text
    assert "_edition" in latest_html_text
    assert "banner.style.display='none'" in latest_html_text
    public_story_text = (deploy_dir / "stories" / "story_1-measles-transmission-and-vaccination.html").read_text()
    assert "../app_exports/manifest.json" in public_story_text
    assert "Load latest" in public_story_text
    assert "Keep reading" in public_story_text
    research_text = (deploy_dir / "research.html").read_text()
    assert "Latest Papers And Preprints" in research_text
    notebook_text = (deploy_dir / "notebook.html").read_text()
    assert "Call Sheet" in notebook_text
    assert "Questions To Chase" in notebook_text


def test_public_exports_include_retained_story_evidence_items(tmp_path):
    deploy_dir = tmp_path / "docs"
    snapshot = {
        "run_id": "run_1",
        "generated_at": "2026-07-08T08:00:00",
        "items": [{"item_id": "item_live", "title": "Live item"}],
        "stories": [
            {
                "story_id": "story_1",
                "topic_name": "Ebola virus disease",
                "story_web_path": "stories/story_1-ebola-virus-disease.html",
                "official_item_ids": ["item_retained"],
                "press_item_ids": ["item_live"],
                "item_ids": ["item_retained", "item_live"],
            }
        ],
    }
    retained = {
        "item_retained": {
            "item_id": "item_retained",
            "title": "Retained WHO situation report",
            "summary": "A retained item used by the story page renderer.",
            "preferred_url": "https://example.com/who",
        },
        "item_live": {"item_id": "item_live", "title": "Live item"},
    }

    site_build.write_public_exports(snapshot, [], str(deploy_dir), story_items_by_id=retained)

    latest_json = json.loads((deploy_dir / "app_exports" / "latest.json").read_text())
    assert latest_json.get("item_count") == snapshot.get("item_count")
    assert latest_json["story_item_count"] == 1
    assert latest_json["story_items"][0]["item_id"] == "item_retained"
    assert latest_json["story_items"][0]["title"] == "Retained WHO situation report"


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
