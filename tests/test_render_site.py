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


def test_render_story_page_adds_outbreak_intelligence_layer():
    story = {
        "display_title": "Ebola virus disease",
        "lead_title": "EBOLA BUNDIBUGYO VIRUS DISEASE OUTBREAK Democratic Republic of the Congo | Uganda Weekly External Situation Report 01",
        "lead_url": "https://example.com/who",
        "lead_source": "WHO Regional Office for Africa",
        "item_count": 3,
        "source_count": 3,
        "official_item_ids": ["official_1"],
        "press_item_ids": ["press_1", "press_2"],
        "publisher_names": ["WHO Regional Office for Africa", "CIDRAP", "Reuters"],
        "freshness_counts": {"live": 3, "refresh_cache": 0, "fallback_cache": 0, "retained": 0},
        "latest_update_summary": "Story volume increased.",
        "latest_update_bullets": ["WHO now foregrounds vaccination or vaccine policy in the story."],
        "related_references": [
            {
                "name": "Ebola virus disease",
                "reference_url": "file:///tmp/ebola.html",
                "pathogen": "Ebola viruses, including Bundibugyo virus in the current DRC/Uganda outbreak",
                "latest_outbreak": {
                    "location": "Ituri Province, DRC, with imported cases reported in Kampala, Uganda",
                    "summary": "About 395 suspected cases and 106 associated deaths have been reported in DRC and Uganda.",
                    "source_name": "Africa CDC",
                    "as_of": "2026-05-18",
                },
                "vaccine_status": "Bundibugyo-specific vaccine and therapeutic availability remains uncertain.",
                "research_caveats": "Suspected cases and deaths can be a better warning signal than confirmed cases alone.",
            }
        ],
        "first_seen_at": "2026-05-18T18:05:45",
        "latest_updated_at": "2026-05-20T21:34:28",
        "timeline": [],
    }
    items_by_id = {
        "official_1": {
            "title": "EBOLA BUNDIBUGYO VIRUS DISEASE OUTBREAK Democratic Republic of the Congo | Uganda Weekly External Situation Report 01",
            "preferred_url": "https://example.com/who",
            "publisher_name": "WHO Regional Office for Africa",
            "published_at": "2026-05-20T06:12+00:00",
            "summary": "WHO received an alert regarding an unknown illness with high mortality in Mongbwalu Health Zone, Ituri Province, including reports of four health workers who died. Uganda subsequently confirmed two imported cases in Kampala. As of 21 June 2026, a cumulative total of 1048 laboratory-confirmed cases, including 267 confirmed deaths, has been reported. WHO determined the outbreak constituted a Public Health Emergency of International Concern.",
            "link_quality": "wrapper_only",
            "source_confidence": "official_agency",
            "official": True,
            "region": "Africa",
            "country": "Democratic Republic of the Congo / Uganda",
            "freshness_state": "live",
        },
        "press_1": {
            "title": "At least 600 Ebola cases suspected as US pledges to fund 50 treatment clinics",
            "preferred_url": "https://example.com/cidrap",
            "publisher_name": "CIDRAP",
            "published_at": "2026-05-20T21:13+00:00",
            "summary": "Limited detail was available from feed metadata alone.",
            "link_quality": "metadata_only",
            "source_confidence": "metadata_only_signal",
            "publisher_tier": "specialist_health",
            "region": "Africa",
            "freshness_state": "live",
            "low_detail": True,
        },
        "press_2": {
            "title": "WHO says 600 suspected cases, 139 deaths in growing Ebola outbreak",
            "preferred_url": "https://example.com/reuters",
            "publisher_name": "Reuters",
            "published_at": "2026-05-20T21:14+00:00",
            "summary": "Vaccine candidates could take months to develop.",
            "link_quality": "resolved_article",
            "source_confidence": "wire",
            "publisher_tier": "wire",
            "region": "Africa",
            "freshness_state": "live",
        },
    }

    content = render_story_page(story, items_by_id, date(2026, 5, 20), datetime(2026, 5, 20, 21, 34))
    assert "Outbreak dashboard" in content
    assert "<strong>1,048</strong>" in content
    assert "<strong>267</strong>" in content
    assert "Official-source confirmed-case count" in content
    assert "Official-source death count" in content
    assert "<strong>About 395</strong>" not in content
    assert "<strong>106</strong>" not in content
    assert "<strong>At least 600</strong>" not in content
    assert "<strong>139</strong>" not in content
    assert "DRC; Uganda" in content
    assert "WHO PHEIC declared" in content
    assert "Ebola viruses, including Bundibugyo virus" in content
    assert "What Matters Now" in content
    assert "Urban Spread" in content
    assert "Conflict-Zone Response" in content
    assert "Suspected Vs Confirmed Counts" in content
    assert "Methodology Note" in content
    assert "Scientific / vaccine / therapeutic context" in content
    assert "Operational response" in content
    assert "Location:</strong> DRC / Ituri / Mongbwalu" in content
    assert "Official report" in content or "Confirmed" in content
    assert 'data-intel-category="scientific-vaccine-therapeutic-context"' in content
    assert 'data-story-filter="intel-category"' in content


def test_render_story_dashboard_does_not_promote_media_only_counts():
    story = {
        "display_title": "Ebola virus disease",
        "lead_title": "Ebola outbreak updates",
        "lead_url": "https://example.com/lead",
        "lead_source": "WHO",
        "item_count": 2,
        "source_count": 2,
        "official_item_ids": [],
        "press_item_ids": ["older", "newer"],
        "publisher_names": ["Emirates 24|7", "Infectious Disease Special Edition"],
        "freshness_counts": {"live": 2},
        "latest_update_summary": "Publisher counts changed.",
        "latest_update_bullets": [],
        "related_references": [],
        "first_seen_at": "2026-05-20T09:43:00",
        "latest_updated_at": "2026-05-22T18:16:00",
        "timeline": [],
    }
    items_by_id = {
        "older": {
            "title": "Ebola outbreak: 600 suspected cases, 139 deaths, numbers expected to rise, says WHO chief",
            "preferred_url": "https://example.com/older",
            "publisher_name": "Emirates 24|7",
            "published_at": "2026-05-20T09:43+00:00",
            "summary": "Limited detail was available from feed metadata alone.",
            "link_quality": "metadata_only",
            "source_confidence": "metadata_only_signal",
            "freshness_state": "live",
            "low_detail": True,
        },
        "newer": {
            "title": "Bundibugyo Ebola Outbreak Nears 750 Suspected Cases, 177 Deaths",
            "preferred_url": "https://example.com/newer",
            "publisher_name": "Infectious Disease Special Edition",
            "published_at": "2026-05-22T18:16+00:00",
            "summary": "Limited detail was available from feed metadata alone.",
            "link_quality": "metadata_only",
            "source_confidence": "metadata_only_signal",
            "freshness_state": "live",
            "low_detail": True,
        },
    }

    content = render_story_page(story, items_by_id, date(2026, 5, 22), datetime(2026, 5, 22, 18, 30))

    assert "<strong>Not yet confirmed</strong>" in content
    assert "does not have an official or report-grade total" in content
    assert "<strong>750</strong>" not in content
    assert "<strong>177</strong>" not in content
    assert "600</strong>" not in content
    assert "139</strong>" not in content


def test_render_story_dashboard_blocks_precise_media_counts_too():
    story = {
        "display_title": "Ebola virus disease",
        "lead_title": "Ebola outbreak updates",
        "lead_url": "https://example.com/lead",
        "lead_source": "Health and Me",
        "item_count": 3,
        "source_count": 3,
        "official_item_ids": [],
        "press_item_ids": ["latest_threshold", "specialist_threshold", "precise_same_day"],
        "publisher_names": ["Health and Me", "CIDRAP", "Chosunbiz"],
        "freshness_counts": {"live": 3},
        "latest_update_summary": "Publisher counts changed.",
        "latest_update_bullets": [],
        "related_references": [],
        "first_seen_at": "2026-06-26T20:37:00",
        "latest_updated_at": "2026-06-27T16:02:00",
        "timeline": [],
    }
    items_by_id = {
        "latest_threshold": {
            "title": "Congo Ebola Outbreak Tops 1,200 Cases; US CDC On Highest Alert",
            "preferred_url": "https://example.com/latest-threshold",
            "publisher_name": "Health and Me",
            "published_at": "2026-06-27T16:02+00:00",
            "summary": "Limited detail was available from feed metadata alone.",
            "link_quality": "metadata_only",
            "source_confidence": "metadata_only_signal",
            "publisher_tier": "general",
            "freshness_state": "live",
            "low_detail": True,
        },
        "specialist_threshold": {
            "title": "As Ebola deaths top 300, African officials meet to boost regional readiness",
            "preferred_url": "https://example.com/specialist-threshold",
            "publisher_name": "CIDRAP",
            "published_at": "2026-06-26T20:37+00:00",
            "summary": "Limited detail was available from feed metadata alone.",
            "link_quality": "metadata_only",
            "source_confidence": "metadata_only_signal",
            "publisher_tier": "specialist_health",
            "freshness_state": "live",
            "low_detail": True,
        },
        "precise_same_day": {
            "title": "Ebola surges in Congo and Uganda, cases hit 1,203 with 321 deaths",
            "preferred_url": "https://example.com/precise",
            "publisher_name": "Chosunbiz",
            "published_at": "2026-06-27T08:20+00:00",
            "summary": "Limited detail was available from feed metadata alone.",
            "link_quality": "metadata_only",
            "source_confidence": "metadata_only_signal",
            "publisher_tier": "general",
            "freshness_state": "live",
            "low_detail": True,
        },
    }

    content = render_story_page(story, items_by_id, date(2026, 6, 27), datetime(2026, 6, 27, 16, 30))

    assert "<strong>Not yet confirmed</strong>" in content
    assert "<strong>1,203</strong>" not in content
    assert "<strong>321</strong>" not in content
    assert "<strong>Over 1,200</strong>" not in content
    assert "<strong>Over 300</strong>" not in content


def test_render_story_dashboard_does_not_promote_metadata_only_pheic_headline():
    story = {
        "display_title": "Ebola virus disease",
        "lead_title": "Ebola outbreak updates",
        "lead_url": "https://example.com/lead",
        "lead_source": "Africa CDC",
        "item_count": 2,
        "source_count": 2,
        "official_item_ids": [],
        "press_item_ids": ["media_pheic"],
        "publisher_names": ["Africa CDC", "Example News"],
        "freshness_counts": {"live": 2},
        "latest_update_summary": "Story remains active.",
        "latest_update_bullets": [],
        "related_references": [
            {
                "name": "Ebola virus disease",
                "reference_url": "file:///tmp/ebola.html",
                "pathogen": "Bundibugyo virus",
                "latest_outbreak": {
                    "location": "DRC / Uganda",
                    "summary": "Africa CDC declared the outbreak a Public Health Emergency of Continental Security.",
                    "source_name": "Africa CDC PHECS declaration",
                    "as_of": "2026-05-18",
                },
            }
        ],
        "first_seen_at": "2026-05-18T07:00:00",
        "latest_updated_at": "2026-06-27T16:02:00",
        "timeline": [],
    }
    items_by_id = {
        "media_pheic": {
            "title": "WHO declares Ebola outbreak a public health emergency of international concern",
            "preferred_url": "https://example.com/media-pheic",
            "publisher_name": "Example News",
            "published_at": "2026-05-17T07:00+00:00",
            "summary": "Limited detail was available from feed metadata alone.",
            "link_quality": "metadata_only",
            "source_confidence": "metadata_only_signal",
            "freshness_state": "live",
            "low_detail": True,
        },
    }

    content = render_story_page(story, items_by_id, date(2026, 6, 27), datetime(2026, 6, 27, 16, 30))

    assert "Africa CDC continental emergency" in content
    assert "WHO PHEIC declared" not in content


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
    assert '<a class="site-nav-link" href="/">Edge home</a>' in content
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


def test_render_public_notebook_page_builds_reporting_layers():
    stories = [
        {
            "story_id": "story_hanta",
            "display_title": "Hantavirus and cruise-ship outbreak",
            "story_web_path": "stories/story_hanta.html",
            "status": "expanding_coverage",
            "current_status_summary": "Expanding coverage",
            "claim_types": [
                "suspected_case",
                "confirmed_case",
                "policy_or_travel",
                "new_geography",
            ],
            "latest_update_summary": "6 newly observed linked item(s) were added since the last saved snapshot.",
            "why_it_matters": "This story has both official follow-up and broad publisher corroboration.",
            "item_count": 12,
            "source_count": 8,
            "official_item_ids": ["official_1"],
            "press_item_ids": ["press_1", "press_2"],
            "source_kind_counts": {"metadata_only_signal": 5},
            "primary_region": "Global / Maritime",
            "country": "Spain",
            "related_references": [
                {
                    "name": "Hantavirus syndrome",
                    "reference_web_path": "reference/hantavirus-syndrome.html",
                }
            ],
        }
    ]
    references = [
        {
            "name": "Hantavirus syndrome",
            "reference_web_path": "reference/hantavirus-syndrome.html",
            "pathogen": "Hantaviruses",
            "why_reporters_care": "A rare but severe cluster can force rapid questions about exposure and spread.",
            "what_reporters_get_wrong": "Coverage often blurs classic rodent exposure with the much rarer Andes-style person-to-person concern.",
            "metrics_that_matter": [
                "Confirmed versus suspected cases.",
                "Whether exposure points to rodents or close-contact transmission.",
            ],
            "surveillance_note": "Useful for rare severe respiratory clusters with rodent ecology or unusual travel-linked spread.",
        }
    ]
    archive_entries = [{"date": "2026-05-09", "month_name": "May", "year": 2026, "html_web_path": "2026/05/2026-05-09.html"}]

    content = render_public_desk_page(
        "Reporter's Notebook",
        "A working layer for reporters: what to ask next, which numbers matter, and which framing traps to avoid before writing.",
        "notebook",
        stories,
        [],
        references,
        archive_entries,
        current_run_id="run_1",
        current_generated_at="2026-05-09T06:30:00",
    )

    assert "Call Sheet" in content
    assert "Questions To Chase" in content
    assert "Numbers To Watch" in content
    assert "Framing Traps" in content
    assert "Disease Sheets" in content
    assert "Next move:" in content
    assert "Confirmed versus suspected cases." in content
    assert "Do not blur suspected and confirmed cases in the headline or lead." in content
    assert "Which of today's links are still thin metadata signals" in content
    assert "stories/story_hanta.html" in content
    assert "reference/hantavirus-syndrome.html" in content
    assert "Tracked Files" not in content
    assert "Latest Signals" not in content


def test_render_reference_page_renders_curated_fields_and_links():
    reference = {
        "name": "Measles",
        "atlas_entry_slug": "measles",
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
    assert "../atlas.html?pathogen=measles" in content


def test_render_public_atlas_page_builds_map_selector_and_evidence_layers():
    atlas_entries = [
        {
            "slug": "yellow-fever",
            "name": "Yellow fever",
            "subtitle": "Atlantic mosquito ecology, slavery, empire, and port-city mortality",
            "status": "consensus",
            "pathogen_type": "Virus",
            "summary": "Yellow fever is one of the clearest examples of maritime disease geography.",
            "why_it_matters": "It shows vectors, shipping, and imperial history in one file.",
            "atlas_scope": "Historical-to-modern transatlantic spread",
            "origin_claim": {
                "label": "West and Central African transmission zone",
                "coordinates": [-1.5, 6.2],
                "date_or_era": "Pre-colonial circulation",
                "confidence": "strong",
                "narrative": "African endemic ecology predates Atlantic spread.",
            },
            "spread_routes": [
                {
                    "route_id": "yellow-west-africa-caribbean",
                    "from_label": "West African coast",
                    "to_label": "Caribbean ports",
                    "from_coordinates": [-1.5, 6.2],
                    "to_coordinates": [-72.3, 18.9],
                    "date_or_era": "Seventeenth century Atlantic shipping",
                    "route_type": "maritime",
                    "confidence": "strong",
                    "narrative": "Ships moved infected people and mosquito ecology into the Caribbean.",
                    "citation_ids": ["yellow-handbook"],
                }
            ],
            "modern_echoes": ["Vaccination policy and proof-of-entry rules still matter."],
            "framing_traps": ["Do not write this as a purely human-travel story."],
            "linked_reference_slug": "yellow-fever",
            "reference_web_path": "reference/yellow-fever.html",
            "reference_url": "file:///tmp/yellow-fever.html",
            "linked_blog_posts": [
                {
                    "title": "The First American Epidemic",
                    "url": "https://theedgeofepidemiology.substack.com/p/the-first-american-epidemic-how-yellow",
                    "published_at": "2026-04-04",
                    "relation": "deep_dive",
                }
            ],
            "related_stories": [
                {
                    "story_id": "story_1",
                    "display_title": "Yellow fever and Atlantic circulation",
                    "story_web_path": "stories/story_1.html",
                    "story_url": "file:///tmp/story_1.html",
                    "latest_update_summary": "Historical framing remains stable.",
                }
            ],
            "citations": [
                {
                    "id": "yellow-handbook",
                    "short_citation": "Routledge handbook chapter.",
                    "url": "https://doi.org/10.4324/9781003531425",
                    "claim_supported": "Atlantic spread framing.",
                }
            ],
            "visual_asset_id": "atlas-yellow-fever-hero",
            "visual_asset": {"asset_id": "atlas-yellow-fever-hero", "status": "pending"},
            "writing_state": "direct",
            "route_count": 1,
            "citation_count": 1,
        }
    ]
    archive_entries = [{"date": "2026-05-09", "month_name": "May", "year": 2026, "html_web_path": "2026/05/2026-05-09.html"}]

    content = render_public_desk_page(
        "Pathogen Atlas",
        "A curated origin-and-spread atlas that links geography, evidence, and prior writing.",
        "atlas",
        [],
        [],
        [],
        archive_entries,
        atlas_entries=atlas_entries,
        current_run_id="run_1",
        current_generated_at="2026-05-09T06:30:00",
    )

    assert "Global Atlas Map" in content
    assert "Evidence Panel" in content
    assert "Pathogen Selector" in content
    assert "Written at The Edge of Epidemiology" in content
    assert "leaflet" in content.lower()
    assert "atlas-data" in content
    assert "West and Central African transmission zone" in content
    assert "The First American Epidemic" in content
    assert "./reference/yellow-fever.html" in content
    assert "Routledge handbook chapter." in content
