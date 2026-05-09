from src.render_markdown import analyze_story_updates
from src.utils import Item


def make_hanta_items():
    return [
        Item(
            title="Suspected hantavirus outbreak on cruise ship under investigation: risk for Europeans very low",
            source="ECDC News",
            url="https://example.com/ecdc-1",
            category="Outbreaks and emerging infections",
            summary="Officials say the event is under investigation and risk for Europeans is very low.",
            relevance_score=5,
            official=True,
        ),
        Item(
            title="Human-to-human transmission suspected in hantavirus outbreak on cruise ship",
            source="NBC News",
            url="https://example.com/nbc-1",
            category="Outbreaks and emerging infections",
            summary="Coverage highlights possible human-to-human transmission.",
            relevance_score=3,
        ),
        Item(
            title="Suspected hantavirus outbreak on cruise ship leaves 3 dead, 147 quarantined",
            source="Reuters",
            url="https://example.com/reuters-1",
            category="Outbreaks and emerging infections",
            summary="Reports now include deaths and quarantine measures.",
            relevance_score=3,
        ),
    ]


def test_analyze_story_updates_creates_baseline_snapshot():
    updates, snapshots = analyze_story_updates(make_hanta_items(), {})
    assert updates
    assert updates[0].is_new_story is True
    assert "Hantavirus and cruise-ship outbreak" in snapshots


def test_analyze_story_updates_reports_new_flags_against_previous_snapshot():
    previous = {
        "Hantavirus and cruise-ship outbreak": {
            "topic_name": "Hantavirus and cruise-ship outbreak",
            "lead_title": "Earlier Hantavirus item",
            "lead_url": "https://example.com/old",
            "lead_source": "ECDC News",
            "cluster_size": 1,
            "source_names": ["ECDC News"],
            "flags": ["active_investigation", "low_public_risk"],
            "canonical_urls": ["https://example.com/old"],
            "top_titles": ["Earlier Hantavirus item"],
        }
    }
    updates, _ = analyze_story_updates(make_hanta_items(), previous)
    update = next(item for item in updates if item.topic_name == "Hantavirus and cruise-ship outbreak")
    joined = " ".join(update.bullets)
    assert "human-to-human transmission" in joined
    assert "deaths or fatal cases" in joined


def test_analyze_story_updates_keeps_two_item_official_story_cluster():
    items = [
        Item(
            title="Suspected hantavirus outbreak on cruise ship under investigation: risk for Europeans very low",
            source="ECDC News",
            url="https://example.com/ecdc-a",
            category="Outbreaks and emerging infections",
            summary="Three deaths were reported among passengers aboard the ship.",
            official=True,
            relevance_score=5,
        ),
        Item(
            title="ECDC monitoring outbreak associated with cruise ship",
            source="ECDC News",
            url="https://example.com/ecdc-b",
            category="Outbreaks and emerging infections",
            summary="ECDC said suspected hantavirus cases are under investigation.",
            official=True,
            relevance_score=5,
        ),
    ]

    updates, snapshots = analyze_story_updates(items, {})
    assert updates
    assert "Hantavirus and cruise-ship outbreak" in snapshots


def test_analyze_story_updates_calls_out_new_official_source_and_new_links():
    previous = {
        "Hantavirus and cruise-ship outbreak": {
            "topic_name": "Hantavirus and cruise-ship outbreak",
            "lead_title": "Earlier Hantavirus item",
            "lead_url": "https://example.com/ecdc-a",
            "lead_source": "ECDC News",
            "cluster_size": 2,
            "source_names": ["ECDC News", "Reuters"],
            "official_source_names": ["ECDC News"],
            "flags": ["active_investigation"],
            "canonical_urls": ["https://example.com/ecdc-a", "https://example.com/reuters-a"],
            "top_titles": ["Earlier Hantavirus item"],
        }
    }
    items = [
        Item(
            title="Cruise ship hantavirus outbreak: ECDC response activated",
            source="ECDC News",
            url="https://example.com/ecdc-a",
            category="Outbreaks and emerging infections",
            summary="ECDC deployed an expert to the ship.",
            official=True,
            relevance_score=5,
        ),
        Item(
            title="WHO reports eight hantavirus cases linked to the voyage",
            source="WHO Disease Outbreak News",
            url="https://example.com/who-a",
            category="Outbreaks and emerging infections",
            summary="WHO now reports eight cases linked to the voyage.",
            official=True,
            relevance_score=5,
        ),
        Item(
            title="Reuters says ship is heading toward Canary Islands",
            source="Reuters",
            url="https://example.com/reuters-b",
            category="Outbreaks and emerging infections",
            summary="Coverage says the vessel has new docking permission.",
            relevance_score=3,
        ),
    ]

    updates, _ = analyze_story_updates(items, previous)
    update = next(item for item in updates if item.topic_name == "Hantavirus and cruise-ship outbreak")
    joined = " ".join(update.bullets)
    assert "New official source(s) joined this story cluster: WHO Disease Outbreak News." in joined
    assert "newly observed linked item(s)" in joined
