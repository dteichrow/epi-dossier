from __future__ import annotations

from pathlib import Path

from src.outbreak_dashboard_quality import validate_overrides, validate_snapshot


def story_html(latest_updated: str, cases_label: str, cases_value: str, deaths_value: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
  <body>
    <section id="outbreak-dashboard">
      <div class="dashboard-item"><span class="dashboard-label">{cases_label}</span><strong>{cases_value}</strong></div>
      <div class="dashboard-item"><span class="dashboard-label">Deaths</span><strong>{deaths_value}</strong></div>
      <div class="dashboard-item"><span class="dashboard-label">Last updated</span><strong>{latest_updated}</strong></div>
    </section>
    <section id="what-matters-now"></section>
    <section id="methodology-note"></section>
  </body>
</html>
"""


def base_story() -> dict:
    return {
        "story_id": "story_test_ebola",
        "display_title": "Ebola virus disease",
        "topic_name": "Ebola virus disease",
        "content_class": "tracked_outbreak_file",
        "status": "expanding_coverage",
        "editions": ["outbreaks", "watch"],
        "story_web_path": "stories/story_test_ebola.html",
        "latest_updated_at": "2026-07-08T10:00:00",
        "official_item_ids": ["official_old"],
        "press_item_ids": ["authority_new"],
        "related_references": [],
    }


def test_dashboard_quality_rejects_stale_rendered_story_page(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    story_path = docs_root / "stories" / "story_test_ebola.html"
    story_path.parent.mkdir(parents=True)
    story_path.write_text(story_html("2026-07-08T10:00:00", "Confirmed cases", "1,048", "267"), encoding="utf-8")

    story = base_story()
    snapshot = {
        "degraded": False,
        "stories": [story],
        "items": [
            {
                "item_id": "official_old",
                "title": "WHO situation report",
                "summary": "A cumulative total of 1048 laboratory-confirmed cases, including 267 confirmed deaths, has been reported.",
                "publisher_name": "WHO Regional Office for Africa",
                "published_at": "2026-06-26T16:55+00:00",
                "official": True,
                "source_confidence": "official_agency",
                "link_quality": "direct_article",
            },
            {
                "item_id": "authority_new",
                "title": "Congo Says Confirmed Ebola Cases Rise to 1,561, Including 506 Deaths",
                "summary": "Congo's Ministry of Health said cases and deaths increased in its latest update.",
                "publisher_name": "U.S. News & World Report",
                "published_at": "2026-07-06T05:14+00:00",
                "source_confidence": "metadata_only_signal",
                "link_quality": "metadata_only",
            },
        ],
    }

    issues = validate_snapshot(snapshot, docs_root=docs_root, overrides={})

    errors = [issue for issue in issues if issue.severity == "error"]
    assert any(issue.metric == "cases" and "does not match" in issue.message for issue in errors)
    assert any(issue.metric == "deaths" and "does not match" in issue.message for issue in errors)


def test_dashboard_quality_override_passes_when_rendered_dashboard_matches(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    story_path = docs_root / "stories" / "story_test_ebola.html"
    story_path.parent.mkdir(parents=True)
    story_path.write_text(story_html("2026-07-08T10:00:00", "Reported cases", "1,708", "580"), encoding="utf-8")

    story = base_story()
    story["press_item_ids"] = []
    snapshot = {
        "degraded": False,
        "stories": [story],
        "items": [
            {
                "item_id": "official_old",
                "title": "WHO situation report",
                "summary": "A cumulative total of 1048 laboratory-confirmed cases, including 267 confirmed deaths, has been reported.",
                "publisher_name": "WHO Regional Office for Africa",
                "published_at": "2026-06-26T16:55+00:00",
                "official": True,
                "source_confidence": "official_agency",
                "link_quality": "direct_article",
            }
        ],
    }
    overrides = {
        "story_test_ebola": {
            "source_name": "Associated Press",
            "source_url": "https://apnews.com/article/159288cd2a4be74e6cd61255e0f12044",
            "source_status": "Government data reported by AP",
            "as_of": "2026-07-08",
            "cases": {"label": "Reported cases", "value": "1,708", "note": "Latest government data reported by AP on 2026-07-08."},
            "deaths": {"value": "580", "note": "Latest government data reported by AP on 2026-07-08."},
        }
    }

    issues = validate_snapshot(snapshot, docs_root=docs_root, overrides=overrides)

    assert [issue for issue in issues if issue.severity == "error"] == []


def test_dashboard_quality_flags_rendered_override_stale_after_newer_authority_count(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    story_path = docs_root / "stories" / "story_test_ebola.html"
    story_path.parent.mkdir(parents=True)
    story_path.write_text(story_html("2026-07-08T10:00:00", "Reported cases", "1,561", "506"), encoding="utf-8")

    story = base_story()
    snapshot = {
        "degraded": False,
        "stories": [story],
        "items": [
            {
                "item_id": "official_old",
                "title": "WHO situation report",
                "summary": "A cumulative total of 1048 laboratory-confirmed cases, including 267 confirmed deaths, has been reported.",
                "publisher_name": "WHO Regional Office for Africa",
                "published_at": "2026-06-26T16:55+00:00",
                "official": True,
                "source_confidence": "official_agency",
                "link_quality": "direct_article",
            },
            {
                "item_id": "authority_new",
                "title": "Some health workers in Congo's Ebola outbreak go on strike over pay issues as deaths near 600",
                "summary": "The latest government data shows 1,708 recorded cases, including 580 deaths.",
                "publisher_name": "Associated Press",
                "published_at": "2026-07-08T07:39+00:00",
                "source_confidence": "wire",
                "publisher_tier": "wire",
                "link_quality": "resolved_article",
            },
        ],
    }
    overrides = {
        "story_test_ebola": {
            "source_name": "Associated Press",
            "source_url": "https://apnews.com/article/1831766b125395f48ff626fbf664fb36",
            "source_status": "Government data reported by AP",
            "as_of": "2026-07-06",
            "cases": {"label": "Reported cases", "value": "1,561", "note": "Latest government data reported by AP on 2026-07-06."},
            "deaths": {"value": "506", "note": "Latest government data reported by AP on 2026-07-06."},
        }
    }

    issues = validate_snapshot(snapshot, docs_root=docs_root, overrides=overrides)

    errors = [issue for issue in issues if issue.severity == "error"]
    assert any(issue.metric == "cases" and "does not match" in issue.message for issue in errors)
    assert any(issue.metric == "deaths" and "does not match" in issue.message for issue in errors)


def test_dashboard_override_requires_traceable_source() -> None:
    issues = validate_overrides(
        {
            "story_test_ebola": {
                "source_name": "Associated Press",
                "as_of": "2026-07-08",
                "cases": {"value": "1,708", "note": "Reported by AP."},
            }
        },
        {"story_test_ebola"},
    )

    errors = [issue.message for issue in issues if issue.severity == "error"]
    assert "Dashboard override is missing source_url." in errors
    assert "Dashboard override is missing source_status." in errors


def test_dashboard_quality_rejects_dashboard_on_non_outbreak_topic(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    story_path = docs_root / "stories" / "story_topic.html"
    story_path.parent.mkdir(parents=True)
    story_path.write_text('<section id="outbreak-dashboard"></section><p>Tracked outbreak file</p>', encoding="utf-8")
    snapshot = {
        "degraded": False,
        "stories": [
            {
                "story_id": "story_topic",
                "display_title": "Occupational and environmental epidemiology",
                "story_web_path": "stories/story_topic.html",
                "outbreak_dashboard_enabled": False,
            }
        ],
        "items": [],
    }

    issues = validate_snapshot(snapshot, docs_root=docs_root, overrides={})

    errors = [issue.message for issue in issues if issue.severity == "error"]
    assert "Non-outbreak topic page still renders an outbreak dashboard." in errors
    assert "Non-outbreak topic page still presents itself as a tracked outbreak file." in errors
