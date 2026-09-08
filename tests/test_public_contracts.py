from unittest.mock import Mock
from src.public_contracts import (
    coverage_geography,
    infer_country,
    normalize_snapshot,
    item_date_label,
    collection_date_label,
)
from src.utils import Item, infer_region
from src.parsers import extract_publication_date
from src.fetchers import enrich_item_text


def test_florida_official_geography_is_retained_in_dengue_story():
    item = Item(title="Florida Surgeon General reminds Floridians about dengue", source="Florida Department of Health Press Releases", url="https://www.floridahealth.gov/", category="Outbreaks", official=True)
    result = coverage_geography([item], infer_country, infer_region)
    assert result["country"] == "United States"
    assert result["primary_region"] == "North America"
    item.official = False
    assert infer_country(item) == "United States"


def test_collection_label_is_distinct_from_source_publication():
    assert collection_date_label("2026-09-08T08:10:37") == "Collection updated Sep 8, 2026"
    assert collection_date_label(None) == "Collection date not established"


def test_http_modification_never_becomes_publication(monkeypatch):
    response = Mock(
        text="<html><p>An undated report.</p></html>",
        headers={
            "content-type": "text/html",
            "last-modified": "Tue, 08 Sep 2026 10:30:00 GMT",
        },
    )
    monkeypatch.setattr("src.fetchers.resilient_get", lambda *a, **k: response)
    item = enrich_item_text(
        Item(
            title="Report",
            source="Agency",
            url="https://example.org/report",
            category="Outbreaks",
            source_type="html_page",
        ),
        Mock(),
    )
    assert item.published_at is None
    assert item.metadata["source_last_modified_at"].startswith("2026-09-08")
    assert item.metadata["last_retrieved_at"]


def test_explicit_publication_metadata_is_distinct_from_update():
    value = extract_publication_date(
        '<meta property="article:modified_time" content="2026-09-08"><script type="application/ld+json">{"@type":"NewsArticle","datePublished":"2026-06-06"}</script>'
    )
    assert value.date().isoformat() == "2026-06-06"
    assert (
        extract_publication_date(
            '<meta property="article:modified_time" content="2026-09-08">'
        )
        is None
    )


def test_coverage_is_multi_region_and_not_the_publisher_location():
    items = [
        Item(
            title="Cholera in Uganda",
            summary="",
            source="CDC",
            url="https://cdc.gov/r",
            category="Outbreaks",
            official=True,
        ),
        Item(
            title="Cases in India",
            source="Agency",
            url="https://example.org/r",
            category="Outbreaks",
            official=True,
        ),
    ]
    result = coverage_geography(items, infer_country, infer_region)
    assert result["countries"] == ["India", "Uganda"]
    assert result["regions"] == ["Africa", "South Asia"]
    assert result["primary_region"] == "Multi-region"
    assert infer_region(items[0]) == "Africa"


def test_legacy_rebuild_preserves_unknowns_and_does_not_fake_freshness():
    original = {
        "generated_at": "2026-09-01T00:00:00",
        "items": [
            {
                "item_id": "x",
                "title": "Cholera in Uganda",
                "summary": "Source report",
                "official": True,
                "source": "CDC",
                "source_type": "html_page",
                "published_at": "2026-08-31",
                "source_cached_at": "2026-09-01T00:00:00",
            }
        ],
        "stories": [
            {
                "item_ids": ["x"],
                "lead_title": "Cholera in Uganda",
                "latest_update_summary": "Baseline snapshot created; story tracking is now active.",
            }
        ],
    }
    upgraded = normalize_snapshot(original)
    item = upgraded["items"][0]
    assert item["source_published_at"] is None and item["published_at"] == "Unknown"
    assert item["legacy_reported_date"] == "2026-08-31"
    assert item["first_discovered_at"] is None
    assert item["last_retrieved_at"] == "2026-09-01T00:00:00"
    assert upgraded["generated_at"] == original["generated_at"]
    assert upgraded["stories"][0]["country"] == "Uganda"
    assert upgraded["stories"][0]["primary_region"] == "Africa"
    assert (
        upgraded["stories"][0]["latest_update_summary"]
        == "Monitoring: Cholera in Uganda"
    )
    assert normalize_snapshot(upgraded) == upgraded
    assert original["items"][0]["published_at"] == "2026-08-31"


def test_explicit_unknown_publication_is_not_overridden_by_legacy_date():
    assert (
        item_date_label(
            {
                "source_published_at": None,
                "published_at": "2026-09-08",
                "last_retrieved_at": "2026-09-08T10:00:00",
            }
        )
        == "Publication date not established · Retrieved Sep 8, 2026"
    )
