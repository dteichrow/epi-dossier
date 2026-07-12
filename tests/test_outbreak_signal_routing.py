from src.app_exports import record_matches_edition
from src.main import item_looks_like_story_followup, item_matches_briefing_scope
from src.render_markdown import classify_topic
from src.scoring import score_item
from src.utils import Item, load_editions_config, load_outbreak_reference


def test_reference_aliases_drive_topic_classification_for_configured_diseases():
    item = Item(
        title="Health officials confirm Marburg outbreak after hospital cluster",
        source="Google News Active Outbreak Alerts",
        url="https://example.com/marburg",
        category="Outbreaks and emerging infections",
        summary="Officials reported confirmed cases, deaths, and contact tracing after a Marburg virus disease cluster.",
        source_type="rss",
    )

    assert classify_topic(item) == "Marburg virus disease"


def test_bundibugyo_alias_routes_current_ebola_story_from_reference_config():
    item = Item(
        title="WHO declares Bundibugyo virus disease outbreak a public health emergency",
        source="WHO Disease Outbreak News",
        url="https://example.com/bundibugyo",
        category="Outbreaks and emerging infections",
        summary="The alert describes suspected cases, confirmed cases, deaths, contact tracing, and cross-border response.",
        source_type="html_list",
        official=True,
    )

    assert classify_topic(item) == "Ebola virus disease"


def test_generic_viral_hemorrhagic_fever_phrase_does_not_force_ebola_topic():
    item = Item(
        title="Officials investigate viral hemorrhagic fever cluster after deaths",
        source="Google News Active Outbreak Alerts",
        url="https://example.com/vhf",
        category="Outbreaks and emerging infections",
        summary="The report describes suspected cases, contact tracing, and laboratory testing but does not identify the virus species.",
        source_type="rss",
    )

    assert classify_topic(item) == "Miscellaneous signals"


def test_google_news_followup_detection_uses_generic_outbreak_signals():
    item = Item(
        title="Health workers race to contain fast-spreading outbreak after suspected cases and deaths",
        source="Google News Active Outbreak Alerts",
        url="https://news.google.com/rss/articles/example",
        category="Outbreaks and emerging infections",
        summary="Officials reported confirmed Marburg cases, contact tracing, isolation, and rapid response deployments.",
        source_type="rss",
    )

    assert item_looks_like_story_followup(item) is True
    assert item_matches_briefing_scope(item) is True
    assert score_item(item) >= 4


def test_cyclosporiasis_official_alert_routes_to_the_outbreak_terminal():
    item = Item(
        title="Outbreak of cyclosporiasis occurring in Michigan",
        source="Michigan Department of Health and Human Services Infectious Disease Updates",
        url="https://www.michigan.gov/mdhhs/keep-mi-healthy/infectious-diseases/cyclosporiasis-outbreak",
        category="Outbreaks and emerging infections",
        summary="Officials are investigating a large and growing foodborne outbreak with more than 170 cases across southeast Michigan counties.",
        source_type="html_list",
        official=True,
    )
    outbreak_terminal = next(edition for edition in load_editions_config() if edition.key == "outbreaks")
    record = {
        "official": True,
        "story_status": "active_investigation",
        "evidence_type": "official_update",
        "title": item.title,
        "summary": item.summary,
        "why_it_matters": "Official foodborne outbreak alert with rapidly rising case counts.",
        "category": item.category,
        "source": item.source,
        "publisher_name": item.source,
        "region": "North America",
        "source_confidence": "official_agency",
    }

    assert "Cyclosporiasis" in {reference.name for reference in load_outbreak_reference()}
    assert item_matches_briefing_scope(item) is True
    assert classify_topic(item) == "Cyclosporiasis"
    assert score_item(item) == 5
    assert record_matches_edition(record, outbreak_terminal) is True


def test_google_news_followup_requires_content_level_outbreak_activity():
    item = Item(
        title="Researchers publish Ebola survivor immunology study",
        source="Google News Active Outbreak Alerts",
        url="https://news.google.com/rss/articles/example",
        category="Outbreaks and emerging infections",
        summary="The article covers long-term immune markers and follow-up samples from recovered patients.",
        source_type="rss",
    )

    assert item_looks_like_story_followup(item) is False


def test_ebola_treatment_site_and_burial_conflict_counts_as_story_followup():
    item = Item(
        title="Young men storm hospital to retrieve body of suspected Ebola victim",
        source="Google News Ebola Burial and Treatment Response",
        url="https://news.google.com/rss/articles/example",
        category="Outbreaks and emerging infections",
        summary="Local reporting says a treatment centre was burned after residents demanded a traditional burial.",
        source_type="rss",
    )

    assert classify_topic(item) == "Ebola virus disease"
    assert item_looks_like_story_followup(item) is True
    assert item_matches_briefing_scope(item) is True
    assert score_item(item) >= 4


def test_outbreak_terminal_and_official_alerts_are_configured_for_broad_monitoring():
    editions = {edition.key: edition for edition in load_editions_config()}

    assert "outbreaks" in editions
    assert editions["outbreaks"].max_items >= 30
    assert "public health emergency" in editions["outbreaks"].include_terms
    assert "Africa CDC" in editions["official"].sources
    assert "CDC Newsroom" in editions["official"].sources
    assert "CDC Current Outbreak List" in editions["official"].sources


def test_ebola_reference_sheet_tracks_current_bundibugyo_outbreak_data():
    references = {reference.name: reference for reference in load_outbreak_reference()}
    ebola = references["Ebola virus disease"]

    assert "bundibugyo" in {alias.lower() for alias in ebola.aliases}
    assert ebola.latest_outbreak.as_of == "2026-05-18"
    assert "Public Health Emergency of Continental Security" in ebola.latest_outbreak.summary
