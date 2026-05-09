from datetime import date, datetime
from pathlib import Path

from src.render_html import render_html, render_region_watch, validate_reader_story_sections
from src.render_markdown import StoryUpdate
from src.utils import ArchiveEntry, DiseaseReference, Item, OutbreakEventReference, ReferenceLink


def test_render_html_contains_core_sections_and_links():
    items = [
        Item(
            title="Suspected hantavirus outbreak on cruise ship under investigation",
            source="ECDC News",
            url="https://example.com/hanta",
            category="Outbreaks and emerging infections",
            summary="Three deaths were reported among passengers aboard the ship.",
            why_it_matters="It matters for surveillance framing.",
            caveats="Investigation is ongoing.",
            relevance_score=5,
            official=True,
        ),
        Item(
            title="Reuters reports new hantavirus evacuation details from cruise voyage",
            source="Google News Outbreaks",
            url="https://example.com/hanta-reuters",
            category="Outbreaks and emerging infections",
            publisher="Reuters",
            summary="Follow-up coverage adds evacuation details and confirms the story remains active.",
            why_it_matters="It broadens corroboration beyond the official notice.",
            caveats="Secondary coverage.",
            relevance_score=4,
            official=False,
        ),
        Item(
            title="AP reports additional cruise-ship hantavirus follow-up coverage",
            source="Google News Outbreaks",
            url="https://example.com/hanta-ap",
            category="Outbreaks and emerging infections",
            publisher="Associated Press",
            summary="Another outlet confirms the outbreak is still drawing active follow-up reporting.",
            why_it_matters="It shows the cluster has multiple underlying publishers.",
            caveats="Secondary coverage.",
            relevance_score=4,
            official=False,
        ),
        Item(
            title="New York Times follow-up focuses on the Canary Islands docking dispute",
            source="Google News Major Outbreak Desks",
            url="https://www.nytimes.com/2026/05/05/world/europe/example.html",
            category="Outbreaks and emerging infections",
            publisher="New York Times",
            summary="A deeper follow-up centers on local resistance to docking and the political response.",
            why_it_matters="It shows the reader can keep first-class publishers even when login is required.",
            caveats="Subscription access may be required.",
            relevance_score=4,
            official=False,
        ),
        Item(
            title="A copper uptake ABC transport system is essential for Mycobacterium tuberculosis virulence.",
            source="PubMed Infectious Disease Search",
            url="https://example.com/tb-paper",
            category="Major epidemiology studies",
            publisher="Reuters",
            summary="Deletion of the transporter lowered bacterial burdens in a murine model.",
            why_it_matters="Useful for pathogen biology context.",
            caveats="Animal-model evidence.",
            relevance_score=4,
            official=True,
            doi="10.1080/22221751.2026.2668753",
            journal="Emerging microbes & infections",
        ),
    ]
    updates = [
        StoryUpdate(
            topic_name="Hantavirus and cruise-ship outbreak",
            lead_title="Suspected hantavirus outbreak on cruise ship under investigation",
            lead_url="https://example.com/hanta",
            lead_source="ECDC News",
            bullets=["Three deaths remain central to the official outbreak framing."],
            item_count=3,
            source_count=3,
            is_new_story=True,
        )
    ]
    archive_entries = [
        ArchiveEntry(
            target_date=date(2026, 5, 5),
            html_path=Path("/tmp/2026-05-05.html"),
            markdown_path=Path("/tmp/2026-05-05.md"),
        ),
        ArchiveEntry(
            target_date=date(2026, 5, 4),
            html_path=Path("/tmp/2026-05-04.html"),
            markdown_path=Path("/tmp/2026-05-04.md"),
        ),
    ]
    outbreak_reference = [
        DiseaseReference(
            name="Hantavirus syndrome",
            pathogen="Hantaviruses",
            transmission="Rodent exposure; limited person-to-person transmission for Andes virus",
            categories=["Zoonotic", "Emerging"],
            latest_outbreak=OutbreakEventReference(
                label="Cruise-ship linked cluster",
                period="April-May 2026",
                location="Multi-country / maritime",
                summary="WHO reported seven cases and three deaths linked to cruise-ship travel.",
                source_name="WHO Disease Outbreak News",
                source_url="https://example.com/hanta-reference",
                as_of="2026-05-04",
            ),
                field_guide_links=[
                    ReferenceLink(label="WHO fact sheet", url="https://www.who.int/fact-sheet-hanta"),
                    ReferenceLink(label="CDC overview", url="https://www.cdc.gov/hantavirus/about/index.html"),
                ],
                notable_outbreaks=["Andes virus clusters in South America remain the classic transmission reference point."],
                surveillance_note="Useful for unusual respiratory clusters with rodent ecology.",
                why_reporters_care="Rare severe respiratory clusters make this highly newsworthy.",
                research_caveats="Early transmission claims can be unstable in tiny clusters.",
            )
        ]

    content = render_html(
        items,
        date(2026, 5, 5),
        datetime(2026, 5, 5, 6, 30),
        "2 day(s) ending 2026-05-05",
        outbreak_reference=outbreak_reference,
        story_updates=updates,
        archive_entries=archive_entries,
        source_health=[
            {"source": "CDC Newsroom", "mode": "live"},
            {"source": "PubMed Historical Epidemiology", "mode": "refresh_cache"},
            {"source": "USDA APHIS Avian Influenza", "mode": "failed", "error": "timeout"},
        ],
        story_records=[
            {
                "topic_name": "Hantavirus and cruise-ship outbreak",
                "display_title": "Hantavirus and cruise-ship outbreak",
                "story_url": "file:///tmp/story.html",
                "item_count": 3,
                "source_count": 3,
                "official_item_ids": ["item_1"],
                "publisher_names": ["Reuters", "Associated Press", "New York Times"],
                "latest_update_summary": "Three deaths remain central to the official outbreak framing.",
                "related_references": [
                    {
                        "name": "Hantavirus syndrome",
                        "reference_url": "file:///tmp/reference.html",
                        "pathogen": "Hantaviruses",
                    }
                ],
            }
        ],
        reference_records=[
            {
                "name": "Hantavirus syndrome",
                "reference_url": "file:///tmp/reference.html",
                "pathogen": "Hantaviruses",
                "transmission": "Rodent exposure",
                "categories": ["Zoonotic", "Emerging"],
                "why_reporters_care": "Rare severe respiratory clusters make this highly newsworthy.",
                "surveillance_note": "Watch for unusual travel-linked exposures.",
                "research_caveats": "Small denominators make certainty hard early.",
                "related_stories": [
                    {
                        "display_title": "Hantavirus and cruise-ship outbreak",
                        "story_url": "file:///tmp/story.html",
                        "latest_update_summary": "Three deaths remain central to the official outbreak framing.",
                    }
                ],
            }
        ],
    )
    assert "<!DOCTYPE html>" in content
    assert "The Pathogen Dispatch" in content
    assert "The Pathogen Dispatch by The Edge of Epidemiology" in content
    assert "Unified desk navigation" in content
    assert "Latest briefing" in content
    assert "Site index" in content
    assert "Reader sections" in content
    assert "Lead Outbreak Files" in content
    assert "What Changed Today" in content
    assert "Global Watch" in content
    assert "Research + Reference" in content
    assert "Archive + Backfile" in content
    assert 'data-view="briefing"' in content
    assert 'data-view="tracking"' in content
    assert "Front-Page Scan" in content
    assert "What Changed In Active Files" in content
    assert "Major Story Files" in content
    assert "Regional Watch" in content
    assert "Operational Desk Health" in content
    assert "Refresh cache sources" in content
    assert "Failed sources" in content
    assert "USDA APHIS Avian Influenza" in content
    assert "Disease Intelligence Desk" in content
    assert "Last Major Outbreaks On File" in content
    assert "Papers Worth Saving" in content
    assert "Dossier Archive" in content
    assert "Search the reader" in content
    assert "Advanced search" in content
    assert 'data-structured-filter="region"' in content
    assert 'data-structured-filter="sourceKind"' in content
    assert 'data-structured-filter="pathogen"' in content
    assert 'data-structured-filter="setting"' in content
    assert 'data-structured-filter="linkQuality"' in content
    assert 'data-structured-filter="access"' in content
    assert 'data-structured-filter="evidenceType"' in content
    assert 'data-structured-filter="storyStatus"' in content
    assert 'data-structured-filter="dateWindow"' in content
    assert 'data-structured-filter="officialOnly"' in content
    assert "Last Updated" in content
    assert "May 5, 2026 at 6:30:00 AM" in content
    assert "Open latest briefing" in content
    assert "Newest first" in content
    assert 'data-sort-target="highest-priority-supporting"' in content
    assert 'data-sort-target="other-readings-grid"' in content
    assert 'data-sort-target="major-story-files-grid"' in content
    assert 'data-sort-target="regional-watch-grid"' in content
    assert 'data-default-sort="newest"' in content
    assert "https://example.com/hanta" in content
    assert "10.1080/22221751.2026.2668753" in content
    assert "Open cluster items" in content
    assert "Cruise-ship linked cluster" in content
    assert "https://example.com/hanta-reference" in content
    assert "file:///tmp/story.html" in content
    assert "file:///tmp/reference.html" in content
    assert "WHO fact sheet" in content
    assert "https://www.who.int/fact-sheet-hanta" in content
    assert "Why reporters care:" in content
    assert "Rare severe respiratory clusters make this highly newsworthy." in content
    assert "Research caveat:" in content
    assert "CDC overview" in content
    assert "Official" in content
    assert "Wire" in content
    assert "Major newsroom" in content
    assert "Login likely" in content
    assert "Open access" in content
    assert "Reuters" in content
    assert "Associated Press" in content
    assert "New York Times" in content
    assert "3 source(s)" in content
    assert "2026" in content
    assert "Global / Maritime" in content
    assert 'data-region="global_maritime"' in content
    assert 'data-source-kind="' in content
    assert 'data-pathogen="hantavirus"' in content
    assert 'data-link-quality="' in content
    assert 'data-evidence-type="' in content
    assert "Publisher coverage • PubMed Infectious Disease Search" not in content
    assert 'data-source-kind="research"' in content


def test_validate_reader_story_sections_flags_empty_story_surfaces():
    issues = validate_reader_story_sections(
        '<p class="empty-note">No lead outbreak files are featured in this edition.</p>'
        '<p class="empty-note">No major story files are featured in this edition.</p>',
        [
            {
                "topic_name": "Hantavirus and cruise-ship outbreak",
                "display_title": "Hantavirus and cruise-ship outbreak",
            }
        ],
    )
    assert issues
    assert any("Lead outbreak files" in issue for issue in issues)
    assert any("Major story files" in issue for issue in issues)


def test_render_html_surfaces_source_failures_in_empty_runs():
    content = render_html(
        [],
        date(2026, 5, 5),
        datetime(2026, 5, 5, 6, 30),
        "2 day(s) ending 2026-05-05",
        source_failures=[{"source": "CDC Newsroom", "error": "DNS failure"}],
        source_health=[{"source": "CDC Newsroom", "mode": "failed", "error": "DNS failure"}],
    )
    assert "1 source(s) failed during collection: CDC Newsroom." in content
    assert "Search and structured filters control the visible cards on this page and the archive list." in content
    assert "Failed sources" in content


def test_render_html_excludes_background_system_reports_from_front_page_and_regional_watch():
    workforce = Item(
        title="State of the health workforce in Africa 2026: Plan, train and retain",
        source="WHO Regional Office for Africa",
        url="https://example.com/workforce",
        category="Outbreaks and emerging infections",
        summary="The 2026 report on the state of the health workforce in Africa builds on earlier regional analyses and investment priorities.",
        relevance_score=5,
        official=True,
    )
    mpox = Item(
        title="Health: WHO reports declining mpox cases in DR Congo",
        source="Google News Central Africa Outbreaks",
        url="https://example.com/mpox",
        category="Outbreaks and emerging infections",
        publisher="NewVision.co.ug",
        summary='The Democratic Republic of the Congo, the epicenter of the ongoing mpox epidemic, has seen a downward trend in weekly reported new cases.',
        relevance_score=4,
        official=False,
    )
    malaria_context = Item(
        title="Lancet study finds significant child death reduction from malaria vaccine in Africa",
        source="Google News Southern Africa Outbreaks",
        url="https://example.com/malaria-study",
        category="Outbreaks and emerging infections",
        publisher="The Eastleigh Voice",
        summary="A Lancet study found child death reduction linked to malaria vaccine rollout across several African countries.",
        relevance_score=5,
        official=False,
    )
    items = [
        workforce,
        mpox,
        malaria_context,
    ]

    region_watch = render_region_watch(items)
    assert "Health: WHO reports declining mpox cases in DR Congo" in region_watch
    assert "State of the health workforce in Africa 2026: Plan, train and retain" not in region_watch
    assert "Lancet study finds significant child death reduction from malaria vaccine in Africa" not in region_watch

    content = render_html(
        [
            Item(
                title="Suspected hantavirus outbreak on cruise ship under investigation",
                source="ECDC News",
                url="https://example.com/hanta",
                category="Outbreaks and emerging infections",
                summary="Three deaths were reported among passengers aboard the ship.",
                relevance_score=5,
                official=True,
            ),
            workforce,
            mpox,
            malaria_context,
        ],
        date(2026, 5, 8),
        datetime(2026, 5, 8, 16, 0),
        "7 day(s) ending 2026-05-08",
    )

    assert "Health: WHO reports declining mpox cases in DR Congo" in content
    front_page_section = content.split('<section class="panel utility-panel" id="executive-scan">', 1)[1].split("</section>", 1)[0]
    assert "State of the health workforce in Africa 2026: Plan, train and retain" not in front_page_section
    assert "Lancet study finds significant child death reduction from malaria vaccine in Africa" not in front_page_section
