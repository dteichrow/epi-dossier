from unittest.mock import Mock

from src.main import (
    enrich_postmerge_items,
    filter_by_terms,
    item_should_drop,
    merge_tracked_story_followups,
    should_promote_latest,
)
from src.utils import Item


def test_filter_by_terms_does_not_keep_generic_epidemiology_paper():
    items = [
        Item(
            title="Clusters of social and substance use-related risks are associated with the duration of untreated psychosis.",
            source="PubMed Infectious Disease Search",
            url="https://pubmed.ncbi.nlm.nih.gov/42083874/",
            category="Major epidemiology studies",
            summary="Psychological medicine article metadata.",
        )
    ]

    filtered = filter_by_terms(items, ["outbreak", "infectious disease", "hantavirus", "measles"])
    assert filtered == []


def test_filter_by_terms_keeps_official_outbreak_item_from_content():
    items = [
        Item(
            title="Suspected hantavirus outbreak on cruise ship under investigation: risk for Europeans very low",
            source="ECDC News",
            url="https://www.ecdc.europa.eu/en/news-events/suspected-hantavirus-outbreak-cruise-ship-under-investigation-risk-europeans-very-low",
            category="Policy, surveillance, and public health infrastructure",
            summary="A cluster of severe acute respiratory illness, including three deaths, has been reported among passengers.",
            official=True,
        )
    ]

    filtered = filter_by_terms(items, ["outbreak", "infectious disease", "hantavirus", "measles"])
    assert len(filtered) == 1


def test_filter_by_terms_drops_official_generic_health_workforce_item():
    items = [
        Item(
            title="State of the health workforce in Africa 2026: Plan, train and retain",
            source="WHO Regional Office for Africa",
            url="https://www.afro.who.int/publications/state-health-workforce-africa-2026-plan-train-and-retain",
            category="Outbreaks and emerging infections",
            summary="The report describes health worker shortages, unemployment, and migration patterns across Africa.",
            official=True,
        )
    ]

    filtered = filter_by_terms(items, ["outbreak", "infectious disease", "hantavirus", "measles", "surveillance"])
    assert filtered == []


def test_item_should_drop_official_undated_non_disease_signal():
    item = Item(
        title="Local Transmission Confirmed in Ensenada, Mexico",
        source="California Department of Public Health News",
        url="https://www.cdph.ca.gov/Programs/OPA/Pages/NR17-021.aspx",
        category="Policy, surveillance, and public health infrastructure",
        summary="",
        official=True,
    )

    assert item_should_drop(item) is True


def test_should_promote_latest_false_for_zero_item_failed_run_with_existing_latest():
    assert (
        should_promote_latest(
            raw_item_count=0,
            processed_count=0,
            source_failures=[{"source": "CDC Newsroom", "error": "DNS failure"}],
            latest_exists=True,
        )
        is False
    )


def test_should_promote_latest_true_for_zero_item_run_without_source_failures():
    assert (
        should_promote_latest(
            raw_item_count=0,
            processed_count=0,
            source_failures=[],
            latest_exists=True,
        )
        is True
    )


def test_should_promote_latest_true_when_no_prior_latest_exists():
    assert (
        should_promote_latest(
            raw_item_count=0,
            processed_count=0,
            source_failures=[{"source": "CDC Newsroom", "error": "DNS failure"}],
            latest_exists=False,
        )
        is True
    )


def test_merge_tracked_story_followups_adds_secondary_updates_for_active_official_story():
    processed = [
        Item(
            title="Suspected hantavirus outbreak on cruise ship under investigation: risk for Europeans very low",
            source="ECDC News",
            url="https://example.com/ecdc-main",
            category="Outbreaks and emerging infections",
            summary="Three deaths were reported among passengers aboard the ship.",
            official=True,
            relevance_score=5,
        )
    ]
    candidates = processed + [
        Item(
            title="3 passengers evacuated from hantavirus-hit cruise ship as new case is confirmed in Switzerland",
            source="Google News Outbreaks",
            url="https://example.com/followup",
            category="Outbreaks and emerging infections",
            summary="Limited detail was available from feed metadata alone.",
            relevance_score=3,
        )
    ]

    merged = merge_tracked_story_followups(processed, candidates)
    urls = {item.url for item in merged}
    assert "https://example.com/followup" in urls


def test_enrich_postmerge_items_prioritizes_google_wrappers_in_active_story_topics(monkeypatch):
    official = Item(
        title="Cruise ship hantavirus outbreak: ECDC response activated",
        source="ECDC News",
        url="https://example.com/ecdc-main",
        category="Outbreaks and emerging infections",
        summary="Official outbreak notice.",
        official=True,
        relevance_score=5,
    )
    followup = Item(
        title="Sky News says suspected case count rises",
        source="Google News Hantavirus Major Publisher Watch",
        url="https://news.google.com/rss/articles/example-story",
        category="Outbreaks and emerging infections",
        summary="Limited detail was available from feed metadata alone.",
        relevance_score=3,
    )
    unrelated = Item(
        title="Other Google wrapper item",
        source="Google News Major Outbreak Desks",
        url="https://news.google.com/rss/articles/example-other",
        category="Policy, surveillance, and public health infrastructure",
        summary="Limited detail was available from feed metadata alone.",
        relevance_score=2,
    )

    calls: list[str] = []

    def fake_enrich(item, logger):
        calls.append(item.title)
        item.url = "https://news.sky.com/story/hantavirus-update"
        item.summary = "Resolved summary."
        return item

    monkeypatch.setattr("src.main.enrich_item_text", fake_enrich)
    monkeypatch.setattr("src.main.summarize_item", lambda item: item)
    monkeypatch.setattr("src.main.score_item", lambda item: item.relevance_score)

    enriched = enrich_postmerge_items([official, followup, unrelated], logger=Mock())

    assert "Sky News says suspected case count rises" in calls
    assert enriched[1].url == "https://news.sky.com/story/hantavirus-update"
