from datetime import datetime

from src.main import build_balanced_shortlist, filter_by_date, uses_regional_monitoring_window
from src.utils import Item


def make_pubmed_item(index: int) -> Item:
    return Item(
        title=f"Study {index} on SARS-CoV-2 neutralization",
        source="PubMed Infectious Disease Search",
        url=f"https://pubmed.ncbi.nlm.nih.gov/{42080000 + index}/",
        category="Major epidemiology studies",
        summary="Neutralization titers increased 4-fold after booster dosing in the study cohort.",
        source_type="pubmed",
        official=True,
        relevance_score=5,
    )


def test_build_balanced_shortlist_reserves_official_outbreak_signals():
    items = [
        Item(
            title="Suspected hantavirus outbreak on cruise ship under investigation: risk for Europeans very low",
            source="ECDC News",
            url="https://example.com/hanta-1",
            category="Policy, surveillance, and public health infrastructure",
            summary="Three deaths were reported and risk for Europeans was described as very low.",
            source_type="rss",
            official=True,
            relevance_score=5,
        ),
        Item(
            title="ECDC monitoring outbreak associated with cruise ship",
            source="ECDC News",
            url="https://example.com/hanta-2",
            category="Policy, surveillance, and public health infrastructure",
            summary="ECDC is monitoring suspected hantavirus cases tied to the ship.",
            source_type="rss",
            official=True,
            relevance_score=5,
        ),
        Item(
            title="FDA outbreak investigation 1369: E. coli O157:H7 linked to Raw Cheddar Cheese",
            source="FDA Foodborne Outbreaks",
            url="https://example.com/fda-1369",
            category="Outbreaks and emerging infections",
            summary="FDA lists reference 1369 with E. coli O157:H7 linked to raw cheddar cheese and 12 cases.",
            source_type="html_list",
            official=True,
            relevance_score=5,
        ),
    ] + [make_pubmed_item(index) for index in range(10)]

    shortlist = build_balanced_shortlist(items)
    urls = {item.url for item in shortlist}
    assert "https://example.com/hanta-1" in urls
    assert "https://example.com/hanta-2" in urls
    assert "https://example.com/fda-1369" in urls


def test_build_balanced_shortlist_caps_pubmed_volume():
    items = [make_pubmed_item(index) for index in range(12)]
    shortlist = build_balanced_shortlist(items)
    pubmed_items = [item for item in shortlist if item.source_type == "pubmed"]
    assert len(pubmed_items) <= 6


def test_build_balanced_shortlist_reserves_story_followups_for_active_outbreak():
    items = [
        Item(
            title="Suspected hantavirus outbreak on cruise ship under investigation: risk for Europeans very low",
            source="ECDC News",
            url="https://example.com/hanta-official",
            category="Outbreaks and emerging infections",
            summary="Three deaths were reported and one passenger was critically ill.",
            source_type="rss",
            official=True,
            relevance_score=5,
        ),
        Item(
            title="Hantavirus-hit cruise ship evacuates 3 passengers, expected to head next to Spain",
            source="Google News Outbreaks",
            url="https://example.com/hanta-followup-1",
            category="Outbreaks and emerging infections",
            summary="Limited detail was available from feed metadata alone.",
            relevance_score=3,
        ),
        Item(
            title="3 passengers evacuated from hantavirus-hit cruise ship as new case is confirmed in Switzerland",
            source="Google News Outbreaks",
            url="https://example.com/hanta-followup-2",
            category="Outbreaks and emerging infections",
            summary="Limited detail was available from feed metadata alone.",
            relevance_score=3,
        ),
    ] + [make_pubmed_item(index) for index in range(12)]

    shortlist = build_balanced_shortlist(items)
    urls = {item.url for item in shortlist}
    assert "https://example.com/hanta-followup-1" in urls
    assert "https://example.com/hanta-followup-2" in urls


def test_build_balanced_shortlist_retains_official_new_outbreak_topic_during_busy_cycle():
    crowded_items = [
        Item(
            title=f"Official outbreak update {index}",
            source=f"Health authority {index}",
            url=f"https://example.com/official-{index}",
            category="Outbreaks and emerging infections",
            summary="Officials report an outbreak investigation and surveillance update.",
            source_type="html_list",
            official=True,
            relevance_score=5,
            published_at=datetime(2026, 7, 12),
        )
        for index in range(45)
    ]
    cyclosporiasis_items = [
        Item(
            title=title,
            source="Michigan Department of Health and Human Services Infectious Disease Updates",
            url=url,
            category="Outbreaks and emerging infections",
            summary="Official foodborne outbreak investigation with rapidly rising case counts.",
            source_type="html_list",
            official=True,
            relevance_score=5,
            published_at=datetime(2026, 7, day),
        )
        for title, url, day in (
            ("Outbreak of cyclosporiasis occurring in Michigan", "https://example.com/cyclo-1", 1),
            ("MDHHS update on growing cyclosporiasis outbreak", "https://example.com/cyclo-2", 4),
        )
    ]

    shortlist = build_balanced_shortlist(crowded_items + cyclosporiasis_items)
    urls = {item.url for item in shortlist}

    assert "https://example.com/cyclo-1" in urls
    assert "https://example.com/cyclo-2" in urls


def test_outbreak_signal_sources_use_fourteen_day_monitoring_window():
    item = Item(
        title="Outbreak of cyclosporiasis occurring in Michigan",
        source="Michigan Department of Health and Human Services Infectious Disease Updates",
        url="https://example.com/cyclo",
        category="Outbreaks and emerging infections",
        summary="Official outbreak update.",
        source_type="html_list",
        official=True,
        published_at=datetime(2026, 7, 1),
        metadata={"source_outbreak_signal": True},
    )

    assert uses_regional_monitoring_window(item) is True
    assert filter_by_date([item], target_date=datetime(2026, 7, 12).date(), window_days=7) == [item]
