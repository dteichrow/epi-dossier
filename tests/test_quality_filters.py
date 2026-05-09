from src.main import filter_renderable_items, item_should_drop
from src.scoring import score_item
from src.utils import Item


def test_item_should_drop_google_news_low_detail_explainer():
    item = Item(
        title="What Are Hantavirus Symptoms? Suspected Cruise Ship Outbreak Leaves 3 Dead",
        source="Google News Outbreaks",
        url="https://example.com/hanta-explainer",
        category="Outbreaks and emerging infections",
        summary="Limited detail was available from feed metadata alone.",
        relevance_score=2,
    )

    assert item_should_drop(item) is True


def test_filter_renderable_items_keeps_official_and_fact_rich_story_item():
    official = Item(
        title="Suspected hantavirus outbreak on cruise ship under investigation: risk for Europeans very low",
        source="ECDC News",
        url="https://example.com/ecdc-hanta",
        category="Outbreaks and emerging infections",
        summary="A cluster of severe acute respiratory illness, including three deaths, has been reported among passengers aboard the ship.",
        extracted_text="The ship is currently off the coast of Cabo Verde with 149 people on board.",
        official=True,
        relevance_score=5,
    )
    unofficial = Item(
        title="What Are Hantavirus Symptoms? Suspected Cruise Ship Outbreak Leaves 3 Dead",
        source="Google News Outbreaks",
        url="https://example.com/noisy-hanta",
        category="Outbreaks and emerging infections",
        summary="Limited detail was available from feed metadata alone.",
        relevance_score=2,
    )

    kept = filter_renderable_items([official, unofficial])
    assert kept == [official]


def test_item_should_keep_google_news_story_followup_with_strong_update_title():
    item = Item(
        title="Hantavirus-hit cruise ship evacuates 3 passengers, expected to head next to Spain",
        source="Google News Outbreaks",
        url="https://example.com/hanta-followup",
        category="Outbreaks and emerging infections",
        summary="Limited detail was available from feed metadata alone.",
        relevance_score=3,
    )

    assert item_should_drop(item) is False


def test_score_item_penalizes_low_detail_google_news():
    item = Item(
        title="US on the Brink of Losing Measles-free Status, Study Warns",
        source="Google News Outbreaks",
        url="https://example.com/measles",
        category="Outbreaks and emerging infections",
        summary="Limited detail was available from feed metadata alone.",
    )

    assert score_item(item) == 1


def test_item_should_drop_low_detail_historical_google_news_wrapper():
    item = Item(
        title="Scientists decode ancient diseases from bones, teeth and DNA evidence",
        source="Google News Historical Epi",
        url="https://example.com/ancient-wrapper",
        category="Historical epidemiology / ancient disease / paleopathology",
        summary="Limited detail was available from feed metadata alone.",
        relevance_score=1,
    )

    assert item_should_drop(item) is True
