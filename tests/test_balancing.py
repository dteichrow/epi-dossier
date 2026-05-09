from src.main import build_balanced_shortlist
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
