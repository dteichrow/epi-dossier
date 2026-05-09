from datetime import date, datetime

from src.render_site import render_public_desk_page, render_public_homepage, render_reference_page, render_story_page


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


def test_render_story_page_web_mode_includes_live_update_polling():
    story = {
        "display_title": "Hantavirus and cruise-ship outbreak",
        "lead_title": "Official investigation continues",
        "lead_url": "https://example.com/lead",
        "lead_source": "ECDC",
        "item_count": 1,
        "source_count": 1,
        "official_item_ids": [],
        "press_item_ids": ["press_1"],
        "publisher_names": ["Reuters"],
        "freshness_counts": {"live": 1, "refresh_cache": 0, "fallback_cache": 0, "retained": 0},
        "latest_update_summary": "Story remains active.",
        "latest_update_bullets": [],
        "related_references": [],
        "first_seen_at": "2026-05-07T06:30:00",
        "latest_updated_at": "2026-05-07T07:30:00",
        "timeline": [],
    }
    items_by_id = {
        "press_1": {
            "title": "Reuters follow-up",
            "preferred_url": "https://example.com/reuters",
            "publisher_name": "Reuters",
            "published_at": "2026-05-07T06:30",
            "summary": "Publisher follow-up adds evacuation details.",
            "link_quality": "resolved_article",
            "publisher_tier": "wire",
            "publisher_access": "open",
            "region": "Global / Maritime",
            "freshness_state": "live",
        }
    }

    content = render_story_page(
        story,
        items_by_id,
        date(2026, 5, 7),
        datetime(2026, 5, 7, 7, 30),
        web_mode=True,
        current_run_id="run_1",
    )
    assert 'id="live-update-banner"' in content
    assert "../app_exports/manifest.json" in content
    assert "Load latest" in content
    assert "Keep reading" in content
    assert "window.sessionStorage" in content
    assert "360000" in content
    assert "600000" in content
    assert "__pathogenLoadLatest" in content
    assert "__pathogenDismissLiveUpdate" in content
    assert 'data-live-update-banner="true"' in content
    assert ".live-update-banner[hidden] { display: none !important; }" in content
    assert "_edition" in content
    assert "banner.style.display='none'" in content
    assert "window.sessionStorage.setItem" in content


def test_render_story_page_strips_markdown_links_from_bullets_and_timeline():
    story = {
        "display_title": "Hantavirus and cruise-ship outbreak",
        "lead_title": "Official investigation continues",
        "lead_url": "https://example.com/lead",
        "lead_source": "ECDC",
        "item_count": 1,
        "source_count": 1,
        "official_item_ids": [],
        "press_item_ids": ["press_1"],
        "publisher_names": ["Reuters"],
        "freshness_counts": {"live": 1, "refresh_cache": 0, "fallback_cache": 0, "retained": 0},
        "latest_update_summary": "The lead item has changed to [Official investigation continues](https://example.com/lead) from ECDC.",
        "latest_update_bullets": [
            "The lead item has changed to [Official investigation continues](https://example.com/lead) from ECDC.",
        ],
        "related_references": [],
        "first_seen_at": "2026-05-07T06:30:00",
        "latest_updated_at": "2026-05-07T07:30:00",
        "timeline": [
            {
                "generated_at": "2026-05-07T07:30:00",
                "item_count": 1,
                "source_count": 1,
                "bullets": [
                    "The lead item has changed to [Official investigation continues](https://example.com/lead) from ECDC.",
                ],
            }
        ],
    }
    items_by_id = {
        "press_1": {
            "title": "Reuters follow-up",
            "preferred_url": "https://example.com/reuters",
            "publisher_name": "Reuters",
            "published_at": "2026-05-07T06:30",
            "summary": "Publisher follow-up adds evacuation details.",
            "link_quality": "resolved_article",
            "publisher_tier": "wire",
            "publisher_access": "open",
            "region": "Global / Maritime",
            "freshness_state": "live",
        }
    }

    content = render_story_page(story, items_by_id, date(2026, 5, 7), datetime(2026, 5, 7, 7, 30))
    assert "[Official investigation continues]" not in content
    assert "(https://example.com/lead)" not in content
    assert "The lead item has changed to Official investigation continues from ECDC." in content


def test_render_public_homepage_includes_live_update_banner():
    latest_snapshot = {
        "run_id": "run_1",
        "generated_at": "2026-05-07T08:00:00",
        "story_count": 1,
        "item_count": 1,
        "stories": [
            {
                "display_title": "Measles transmission and vaccination",
                "story_web_path": "stories/story_1.html",
                "latest_update_summary": "Measles coverage is still expanding.",
                "item_count": 3,
                "source_count": 2,
                "current_status_summary": "Expanding coverage",
                "primary_region": "North America",
                "country": "United States",
            }
        ],
        "items": [
            {
                "title": "CDC update",
                "summary": "Official measles update.",
                "publisher_name": "CDC",
                "published_at": "2026-05-07T08:00",
                "preferred_url": "https://example.com/cdc",
                "link_quality": "direct_article",
                "source_confidence": "official_agency",
                "freshness_state": "live",
                "region": "North America",
                "content_class": "official_update",
                "official": True,
                "editions": ["watch", "research"],
            }
        ],
    }
    archive_entries = [{"date": "2026-05-07", "month_name": "May", "year": 2026, "html_web_path": "2026/05/2026-05-07.html"}]
    reference_records = [{"name": "Measles", "reference_web_path": "reference/measles.html", "pathogen": "Measles virus", "why_reporters_care": "High transmissibility exposes immunity gaps.", "spotlight": True}]

    content = render_public_homepage(latest_snapshot, archive_entries, reference_records)
    assert 'id="live-update-banner"' in content
    assert "./app_exports/manifest.json" in content
    assert "Load latest" in content
    assert "Keep reading" in content
    assert "An updated edition is available. Load the latest run when you are ready." in content
    assert "__pathogenLoadLatest" in content
    assert "__pathogenDismissLiveUpdate" in content
    assert ".live-update-banner[hidden] { display: none !important; }" in content
    assert "banner.style.display='none'" in content


def test_render_public_research_page_uses_research_specific_sections():
    items = [
        {
            "title": "Genomic analyses identify nosocomial transmission of ST23 carbapenem-resistant hypervirulent Klebsiella pneumoniae.",
            "summary": "A hospital-transmission paper with antimicrobial resistance implications.",
            "why_it_matters": "It shows how resistance and transmission can move together inside a facility.",
            "caveats": "Single-setting findings should not be overgeneralized.",
            "journal": "Clinical Infectious Diseases",
            "publisher_name": "PubMed",
            "published_at": "2026-05-09T06:15:00",
            "preferred_url": "https://pubmed.ncbi.nlm.nih.gov/42000001/",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/42000001/",
            "abstract_url": "https://pubmed.ncbi.nlm.nih.gov/42000001/",
            "doi": "10.1000/example",
            "link_quality": "direct_article",
            "source_confidence": "specialist_health",
            "freshness_state": "live",
            "region": "Africa",
            "content_class": "research_context",
            "evidence_type": "journal_article",
            "category": "Major epidemiology studies",
            "official": False,
        },
        {
            "title": "Neutralizing epitope mapping for deltacoronavirus receptor-binding domain.",
            "summary": "A virology-focused brief with cross-species implications.",
            "journal": "Virology",
            "publisher_name": "PubMed",
            "published_at": "2026-05-09T05:15:00",
            "preferred_url": "https://pubmed.ncbi.nlm.nih.gov/42000003/",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/42000003/",
            "link_quality": "direct_article",
            "source_confidence": "specialist_health",
            "freshness_state": "live",
            "region": "Global / Maritime",
            "content_class": "research_context",
            "evidence_type": "journal_article",
            "category": "Virology and pathogen evolution",
            "official": False,
        },
    ]
    references = [
        {
            "name": "Schistosomiasis",
            "reference_web_path": "reference/schistosomiasis.html",
            "pathogen": "Schistosoma species",
            "why_reporters_care": "It connects ecology, water systems, and chronic infection.",
            "related_stories": [
                {
                    "story_id": "story_1",
                    "display_title": "Schistosomiasis resurgence and water exposure",
                    "story_web_path": "stories/story_1.html",
                    "latest_update_summary": "Fresh local exposure reporting is expanding.",
                }
            ],
        }
    ]
    archive_entries = [{"date": "2026-05-09", "month_name": "May", "year": 2026, "html_web_path": "2026/05/2026-05-09.html"}]

    content = render_public_desk_page(
        "Research Brief",
        "Papers, preprints, and research-linked reporting that adds context beyond the daily outbreak stream.",
        "research",
        [],
        items,
        references,
        archive_entries,
        current_run_id="run_1",
        current_generated_at="2026-05-09T06:30:00",
    )

    assert "Latest Papers And Preprints" in content
    assert "Virology + Pathogen Evolution" in content
    assert "Research-Linked Active Files" in content
    assert "Disease Sheets" in content
    assert "Research-linked reporting" not in content or "Journal article" in content
    assert "Tracked Files" not in content
    assert "Latest Signals" not in content
    assert "Schistosomiasis resurgence and water exposure" in content
    assert "Why it matters:" in content
    assert "0 item(s)" not in content
    assert "./app_exports/manifest.json" in content


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
