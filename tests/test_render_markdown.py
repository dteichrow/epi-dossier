from datetime import date, datetime

from src.render_markdown import StoryUpdate, classify_topic, render_markdown
from src.utils import DiseaseReference, Item, OutbreakEventReference, ReferenceLink


def test_render_markdown_contains_sections():
    items = [
        Item(
            title="Example outbreak",
            source="CDC",
            url="https://example.com",
            category="Outbreaks and emerging infections",
            summary="A source-backed summary.",
            why_it_matters="It matters.",
            caveats="Some uncertainty.",
            relevance_score=5,
        )
        ,
        Item(
            title="Example outbreak follow-up",
            source="WHO",
            url="https://example.com/follow-up",
            category="Outbreaks and emerging infections",
            summary="A second source-backed summary about the same outbreak.",
            why_it_matters="It also matters.",
            caveats="Some uncertainty.",
            relevance_score=4,
        ),
        Item(
            title="Example outbreak leaves 3 dead and 10 quarantined",
            source="Reuters",
            url="https://example.com/third",
            category="Outbreaks and emerging infections",
            summary="A third source-backed summary about the same outbreak with deaths and quarantine.",
            why_it_matters="It escalates.",
            caveats="Some uncertainty.",
            relevance_score=4,
        ),
    ]
    content = render_markdown(items, date(2026, 5, 3), datetime(2026, 5, 3, 6, 30), "2 day(s)")
    assert "# Daily Infectious Disease & Epidemiology Dossier" in content
    assert "## Ongoing stories and what changed" in content
    assert "## Major topics" in content
    assert "## Last major outbreaks on file" in content
    assert "## Highest priority items" in content
    assert "## Papers worth saving" in content
    assert "## Historical epi / weird epi corner" in content


def test_render_markdown_renders_outbreak_reference_entries():
    items: list[Item] = []
    outbreak_reference = [
        DiseaseReference(
            name="Measles",
            pathogen="Measles virus",
            transmission="Airborne",
            categories=["Vaccine-preventable"],
            latest_outbreak=OutbreakEventReference(
                label="United States resurgence",
                period="2025",
                location="United States",
                summary="CDC reported a large national measles resurgence.",
                source_name="CDC Measles Cases and Outbreaks",
                source_url="https://example.com/measles-reference",
                as_of="2026-04-24",
            ),
            field_guide_links=[
                ReferenceLink(label="CDC overview", url="https://www.cdc.gov/measles/about/index.html"),
                ReferenceLink(label="WHO fact sheet", url="https://www.who.int/news-room/fact-sheets/detail/measles"),
            ],
            notable_outbreaks=["2019 Samoa outbreak."],
            surveillance_note="Vaccination gaps remain central.",
        )
    ]
    content = render_markdown(
        items,
        date(2026, 5, 3),
        datetime(2026, 5, 3, 6, 30),
        "2 day(s)",
        outbreak_reference=outbreak_reference,
    )
    assert "**Measles** | Measles virus" in content
    assert "https://example.com/measles-reference" in content
    assert "Field guide: [CDC overview](https://www.cdc.gov/measles/about/index.html); [WHO fact sheet](https://www.who.int/news-room/fact-sheets/detail/measles)" in content
    assert "Notable earlier outbreaks: 2019 Samoa outbreak." in content


def test_render_markdown_story_updates_use_delta_style_bullets():
    items = [
        Item(
            title="Hantavirus outbreak on cruise ship under investigation",
            source="ECDC",
            url="https://example.com",
            category="Outbreaks and emerging infections",
            summary="Officials reported three deaths and quarantine measures aboard the ship.",
            why_it_matters="It matters.",
            caveats="Some uncertainty.",
            relevance_score=5,
        )
    ]
    updates = [
        StoryUpdate(
            topic_name="Hantavirus and cruise-ship outbreak",
            lead_title="Hantavirus outbreak on cruise ship under investigation",
            lead_url="https://example.com",
            lead_source="ECDC",
            bullets=[
                "WHO-linked coverage now mentions possible human-to-human transmission.",
                "Reuters coverage now includes quarantine language.",
            ],
            item_count=4,
            source_count=2,
        )
    ]
    content = render_markdown(items, date(2026, 5, 3), datetime(2026, 5, 3, 6, 30), "2 day(s)", story_updates=updates)
    assert "WHO-linked coverage now mentions possible human-to-human transmission." in content
    assert "Coverage now clearly includes" not in content


def test_render_markdown_topic_note_avoids_lead_signal_template_when_summary_available():
    items = [
        Item(
            title="Hantavirus outbreak under investigation",
            source="ECDC",
            url="https://example.com/1",
            category="Outbreaks and emerging infections",
            summary="Officials reported three deaths aboard a cruise ship off Cabo Verde.",
            why_it_matters="It matters.",
            caveats="Some uncertainty.",
            relevance_score=5,
        ),
        Item(
            title="Human-to-human transmission suspected on cruise ship",
            source="Reuters",
            url="https://example.com/2",
            category="Outbreaks and emerging infections",
            summary="Secondary coverage now mentions possible human-to-human transmission and quarantine measures.",
            why_it_matters="It matters.",
            caveats="Some uncertainty.",
            relevance_score=4,
        ),
        Item(
            title="Cruise ship outbreak leaves passengers quarantined",
            source="AP",
            url="https://example.com/3",
            category="Outbreaks and emerging infections",
            summary="Passengers were quarantined while health authorities continued the investigation.",
            why_it_matters="It matters.",
            caveats="Some uncertainty.",
            relevance_score=4,
        ),
    ]
    content = render_markdown(items, date(2026, 5, 3), datetime(2026, 5, 3, 6, 30), "2 day(s)")
    assert "The lead signal is" not in content


def test_render_markdown_miscellaneous_topic_uses_non_synthesis_note():
    items = [
        Item(
            title="Webinar | Listening to communities through AI for cholera response",
            source="WHO Regional Office for Africa",
            url="https://example.com/cholera-webinar",
            category="Outbreaks and emerging infections",
            summary="Cholera response webinar.",
            why_it_matters="It matters.",
            caveats="Some uncertainty.",
            relevance_score=4,
        ),
        Item(
            title="Comparative analysis of viral biological characteristics and pathogenicity of representative prevalent avian reovirus strains from genotypes I to V.",
            source="PubMed Infectious Disease Search",
            url="https://example.com/reovirus-paper",
            category="Major epidemiology studies",
            summary="Avian reovirus paper.",
            why_it_matters="It matters.",
            caveats="Some uncertainty.",
            relevance_score=4,
        ),
    ]
    content = render_markdown(items, date(2026, 5, 3), datetime(2026, 5, 3, 6, 30), "2 day(s)")
    assert "do not resolve into one coherent topic cluster" in content


def test_render_markdown_surfaces_source_failures_in_executive_scan():
    content = render_markdown(
        [],
        date(2026, 5, 3),
        datetime(2026, 5, 3, 6, 30),
        "2 day(s)",
        source_failures=[
            {"source": "CDC Newsroom", "error": "DNS failure"},
            {"source": "WHO Disease Outbreak News", "error": "Timeout"},
        ],
    )
    assert "Source health: 2 source(s) failed during collection" in content
    assert "CDC Newsroom" in content


def test_live_disease_signal_is_not_routed_to_historical_topic():
    item = Item(
        title="Second U.S. citizen tests positive for Ebola in Congo",
        source="Example News",
        url="https://example.com/ebola",
        category="Historical Pathogen Case Studies",
        summary="Officials are investigating active Ebola transmission and contact tracing.",
    )

    assert classify_topic(item) == "Ebola virus disease"


def test_generic_cruise_ship_norovirus_signal_is_not_hantavirus():
    item = Item(
        title="Norovirus outbreak on cruise ship sickens passengers",
        source="Example News",
        url="https://example.com/norovirus",
        category="Outbreaks and emerging infections",
        summary="Officials reported 104 cases and continued investigation.",
    )

    assert classify_topic(item) == "Norovirus"
