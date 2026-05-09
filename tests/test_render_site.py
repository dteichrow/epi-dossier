from datetime import date, datetime

from src.render_site import render_reference_page, render_story_page


def test_render_story_page_separates_official_and_press_sections():
    story = {
        "display_title": "Hantavirus and cruise-ship outbreak",
        "lead_title": "Official investigation continues",
        "lead_url": "https://example.com/lead",
        "lead_source": "ECDC",
        "item_count": 3,
        "source_count": 3,
        "official_item_ids": ["official_1"],
        "press_item_ids": ["press_1"],
        "publisher_names": ["Reuters"],
        "freshness_counts": {"live": 1, "refresh_cache": 1, "fallback_cache": 0, "retained": 0},
        "latest_update_summary": "Three deaths remain central to the story.",
        "latest_update_bullets": ["The official source still frames public risk as low."],
        "related_references": [
            {
                "name": "Hantavirus syndrome",
                "reference_url": "file:///tmp/hantavirus.html",
                "pathogen": "Hantaviruses",
            }
        ],
        "first_seen_at": "2026-05-07T06:30:00",
        "latest_updated_at": "2026-05-07T07:30:00",
        "timeline": [{"generated_at": "2026-05-07T07:30:00", "item_count": 3, "source_count": 3, "bullets": ["A new update landed."]}],
    }
    items_by_id = {
        "official_1": {
            "title": "Official investigation continues",
            "preferred_url": "https://example.com/official",
            "publisher_name": "ECDC",
            "published_at": "2026-05-07T06:00",
            "summary": "Officials are still investigating the outbreak.",
            "link_quality": "direct_article",
            "official": True,
            "region": "Global / Maritime",
            "freshness_state": "live",
        },
        "press_1": {
            "title": "Reuters adds evacuation details",
            "preferred_url": "https://example.com/reuters",
            "publisher_name": "Reuters",
            "published_at": "2026-05-07T06:30",
            "summary": "Publisher follow-up adds evacuation details.",
            "link_quality": "resolved_article",
            "publisher_tier": "wire",
            "publisher_access": "open",
            "region": "Global / Maritime",
            "freshness_state": "refresh_cache",
        },
    }

    content = render_story_page(story, items_by_id, date(2026, 5, 7), datetime(2026, 5, 7, 7, 30))
    assert "Unified Desk Navigation" in content
    assert "Latest briefing" in content
    assert "Global watch" in content
    assert "On this page" in content
    assert "Official Sources" in content
    assert "Publisher Coverage" in content
    assert "Related Disease Intelligence" in content
    assert "Timeline" in content
    assert "Newest first" in content
    assert 'data-sort-target="official-sources"' in content
    assert 'data-sort-target="publisher-coverage"' in content
    assert 'data-sort-target="story-timeline"' in content
    assert 'data-sort-ts="' in content
    assert "Direct links:" in content
    assert "Resolved links:" in content
    assert "Wrapper-only:" in content
    assert "Live fetches:" in content
    assert "Refresh cache:" in content
    assert "Official sources:" in content
    assert "Wire:" in content
    assert "Filter This Story File" in content
    assert 'data-story-filter="source-kind"' in content
    assert 'data-story-filter="freshness"' in content
    assert 'data-story-filter="link-quality"' in content
    assert 'data-story-filter="region"' in content
    assert 'data-story-filter="access"' in content
    assert 'data-story-filter="date-window"' in content
    assert "Showing all" in content
    assert "Official" in content
    assert "Wire" in content
    assert "Open access" in content
    assert "Reuters adds evacuation details" in content
    assert "file:///tmp/hantavirus.html" in content
    assert "Feed metadata only. Open the source link for the full piece." not in content


def test_render_story_page_keeps_real_summaries_for_aggregator_only_items():
    story = {
        "display_title": "Hantavirus and cruise-ship outbreak",
        "lead_title": "Official investigation continues",
        "lead_url": "https://example.com/lead",
        "lead_source": "ECDC",
        "item_count": 2,
        "source_count": 2,
        "official_item_ids": ["official_1"],
        "press_item_ids": ["press_1"],
        "publisher_names": ["ECDC News", "BBC"],
        "freshness_counts": {"live": 1, "refresh_cache": 0, "fallback_cache": 1, "retained": 0},
        "latest_update_summary": "Story remains active.",
        "latest_update_bullets": [],
        "related_references": [],
        "first_seen_at": "2026-05-07T06:30:00",
        "latest_updated_at": "2026-05-07T07:30:00",
        "timeline": [],
    }
    items_by_id = {
        "official_1": {
            "title": "Official investigation continues",
            "preferred_url": "https://example.com/official",
            "publisher_name": "ECDC News",
            "published_at": "2026-05-07T06:00",
            "summary": "ECDC deployed an expert and reported suspected person-to-person transmission concerns.",
            "link_quality": "wrapper_only",
            "low_detail": False,
            "official": True,
            "freshness_state": "live",
        },
        "press_1": {
            "title": "BBC follow-up",
            "preferred_url": "https://example.com/bbc",
            "publisher_name": "BBC",
            "published_at": "2026-05-07T06:30",
            "summary": "Limited detail was available from feed metadata alone.",
            "link_quality": "metadata_only",
            "low_detail": True,
            "publisher_tier": "major_newsroom",
            "publisher_access": "subscription",
            "freshness_state": "fallback_cache",
        },
    }

    content = render_story_page(story, items_by_id, date(2026, 5, 7), datetime(2026, 5, 7, 7, 30))
    assert "ECDC deployed an expert and reported suspected person-to-person transmission concerns." in content
    assert "Metadata only" in content
    assert "Wrapper only" in content
    assert "Major newsroom" in content
    assert "Login likely" in content
    assert 'data-source-kind="official"' in content
    assert 'data-freshness="fallback_cache"' in content
    assert 'data-link-quality="metadata_only"' in content
    assert 'data-access="subscription"' in content
    assert 'data-scope="publisher"' in content


def test_render_story_page_collapses_near_duplicate_same_publisher_followups():
    story = {
        "display_title": "Hantavirus and cruise-ship outbreak",
        "lead_title": "Official investigation continues",
        "lead_url": "https://example.com/lead",
        "lead_source": "ECDC",
        "item_count": 5,
        "source_count": 3,
        "official_item_ids": [],
        "press_item_ids": ["press_1", "press_2", "press_3", "press_4", "press_5"],
        "publisher_names": ["BBC", "Reuters", "Guardian"],
        "freshness_counts": {"live": 5, "refresh_cache": 0, "fallback_cache": 0, "retained": 0},
        "latest_update_summary": "Story remains active.",
        "latest_update_bullets": ["New publisher coverage joined this story cluster: Guardian."],
        "related_references": [],
        "first_seen_at": "2026-05-07T06:30:00",
        "latest_updated_at": "2026-05-07T07:30:00",
        "timeline": [],
    }
    items_by_id = {
        "press_1": {
            "title": "Tenerife resident calls docking of hantavirus ship 'reckless'",
            "preferred_url": "https://example.com/bbc-1",
            "publisher_name": "BBC",
            "published_at": "2026-05-07T12:37+00:00",
            "summary": "Limited detail was available from feed metadata alone.",
            "link_quality": "metadata_only",
            "low_detail": True,
            "freshness_state": "live",
        },
        "press_2": {
            "title": "Hantavirus-hit cruise ship on way to Canary Islands after three evacuated",
            "preferred_url": "https://example.com/bbc-2",
            "publisher_name": "BBC",
            "published_at": "2026-05-07T11:37+00:00",
            "summary": "Limited detail was available from feed metadata alone.",
            "link_quality": "metadata_only",
            "low_detail": True,
            "freshness_state": "live",
        },
        "press_3": {
            "title": "Hantavirus-hit cruise ship to head to Spain after permission granted to dock in Canary Islands",
            "preferred_url": "https://example.com/reuters-1",
            "publisher_name": "Reuters",
            "published_at": "2026-05-07T10:37+00:00",
            "summary": "Limited detail was available from feed metadata alone.",
            "link_quality": "metadata_only",
            "low_detail": True,
            "freshness_state": "live",
        },
        "press_4": {
            "title": "Two Britons evacuated from hantavirus-hit ship 'improving' in hospital",
            "preferred_url": "https://example.com/guardian-1",
            "publisher_name": "Guardian",
            "published_at": "2026-05-07T19:19+00:00",
            "summary": "Limited detail was available from feed metadata alone.",
            "link_quality": "metadata_only",
            "low_detail": True,
            "freshness_state": "live",
        },
        "press_5": {
            "title": "BBC follow-up on cruise ship hantavirus evacuations",
            "preferred_url": "https://example.com/bbc-3",
            "publisher_name": "BBC",
            "published_at": "2026-05-07T10:00+00:00",
            "summary": "Limited detail was available from feed metadata alone.",
            "link_quality": "metadata_only",
            "low_detail": True,
            "freshness_state": "live",
        },
    }

    content = render_story_page(story, items_by_id, date(2026, 5, 7), datetime(2026, 5, 7, 7, 30))
    assert "Showing 4 of 5 items after collapsing 1 near-duplicate follow-up." in content


def test_render_reference_page_renders_curated_fields_and_links():
    reference = {
        "name": "Measles",
        "pathogen": "Measles virus",
        "transmission": "Airborne and respiratory",
        "reservoir_or_vector": "Humans",
        "incubation": "Usually 7 to 14 days",
        "symptoms": ["Fever", "Cough", "Rash"],
        "severity": "Can cause pneumonia and encephalitis.",
        "diagnostics": "PCR or serology depending on timing.",
        "treatment": "Supportive care.",
        "prevention": "Vaccination is central.",
        "vaccine_status": "Routine vaccination is highly effective.",
        "categories": ["Vaccine-preventable"],
        "outbreak_settings": ["Schools", "Households"],
        "field_guide_links": [{"label": "CDC overview", "url": "https://www.cdc.gov/measles/about/index.html"}],
        "related_stories": [
            {
                "display_title": "Measles school cluster",
                "story_url": "file:///tmp/measles-story.html",
                "latest_update_summary": "School-linked spread is still growing.",
            }
        ],
        "latest_outbreak": {
            "label": "United States resurgence",
            "location": "United States",
            "period": "2025",
            "summary": "A large outbreak year.",
            "source_name": "CDC",
            "source_url": "https://example.com/measles",
            "as_of": "2026-04-24",
        },
        "surveillance_note": "Watch vaccination gaps closely.",
        "why_reporters_care": "Measles exposes immunity gaps fast.",
        "what_reporters_get_wrong": "Raw case counts matter less than vaccination context.",
        "metrics_that_matter": ["Vaccination status of cases.", "School-linked spread."],
        "research_caveats": "Jurisdictional case tallies can lag.",
        "notable_outbreaks": ["2019 Samoa outbreak."],
    }

    content = render_reference_page(reference, date(2026, 5, 7), datetime(2026, 5, 7, 7, 30))
    assert "Unified Desk Navigation" in content
    assert "Latest briefing" in content
    assert "Research + reference" in content
    assert "On this page" in content
    assert "Reservoir / vector" in content
    assert "Symptoms And Clinical Pattern" in content
    assert "Current Story Files" in content
    assert "Why Reporters Care" in content
    assert "Desk Notes And Historical Signals" in content
    assert "Routine vaccination is highly effective." in content
    assert "Measles exposes immunity gaps fast." in content
    assert "Raw case counts matter less than vaccination context." in content
    assert "Jurisdictional case tallies can lag." in content
    assert "CDC overview" in content
    assert "2019 Samoa outbreak." in content
    assert "file:///tmp/measles-story.html" in content
