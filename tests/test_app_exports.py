import json
from datetime import date, datetime

from src.app_exports import export_app_data, infer_country, infer_story_primary_country
from src.database import SeenItemsDB
from src.render_markdown import analyze_story_updates
from src.utils import APP_EXPORTS_DIR, DiseaseReference, Item, OutbreakEventReference


def make_items():
    return [
        Item(
            title="Suspected hantavirus outbreak on cruise ship under investigation: risk for Europeans very low",
            source="ECDC News",
            url="https://example.com/ecdc-1",
            category="Outbreaks and emerging infections",
            summary="Officials say the event is under investigation and risk for Europeans is very low.",
            relevance_score=5,
            official=True,
            why_it_matters="Directly relevant.",
            caveats="Summary stays within source text.",
        ),
        Item(
            title="Human-to-human transmission suspected in hantavirus outbreak on cruise ship",
            source="NBC News",
            url="https://example.com/nbc-1",
            category="Outbreaks and emerging infections",
            summary="Coverage highlights possible human-to-human transmission.",
            relevance_score=3,
            why_it_matters="Directly relevant.",
            caveats="Limited detail.",
        ),
        Item(
            title="Suspected hantavirus outbreak on cruise ship leaves 3 dead, 147 quarantined",
            source="Reuters",
            url="https://example.com/reuters-1",
            category="Outbreaks and emerging infections",
            summary="Reports now include deaths and quarantine measures.",
            relevance_score=3,
            why_it_matters="Directly relevant.",
            caveats="Limited detail.",
        ),
    ]


def make_reference():
    return [
        DiseaseReference(
            name="Hantavirus syndrome",
            pathogen="Hantaviruses",
            transmission="Rodent exposure",
            categories=["Zoonotic"],
            aliases=["hantavirus"],
            latest_outbreak=OutbreakEventReference(
                label="Cruise-ship linked cluster",
                period="2026",
                location="Global / Maritime",
                summary="A maritime cluster remains active.",
                source_name="WHO",
                source_url="https://example.com/hanta-reference",
                as_of="2026-05-07",
            ),
        )
    ]


def test_country_inference_does_not_use_publisher_domain_for_outbreak_geography():
    item = Item(
        title="Michigan and Ohio investigate a cyclosporiasis outbreak",
        source="International Business Times UK",
        url="https://www.ibtimes.co.uk/health/cyclosporiasis-outbreak",
        category="Outbreaks and emerging infections",
        summary="Health officials report a growing foodborne outbreak in Michigan and Ohio.",
    )

    assert infer_country(item) == "United States"


def test_story_country_prefers_official_local_evidence_over_publisher_geography():
    official = Item(
        title="Cyclosporiasis provider update",
        source="Michigan Department of Health and Human Services Infectious Disease Updates",
        url="https://www.michigan.gov/mdhhs/example",
        category="Outbreaks and emerging infections",
        summary="Provider update for the current investigation.",
        official=True,
    )
    press = Item(
        title="UK media discuss the Michigan cyclosporiasis outbreak",
        source="International Business Times UK",
        url="https://www.ibtimes.co.uk/health/cyclosporiasis-outbreak",
        category="Outbreaks and emerging infections",
        summary="The United Kingdom article describes the Michigan and Ohio investigation.",
    )

    assert infer_country(press) == "United Kingdom / United States"
    assert infer_story_primary_country([press, official]) == "United States"


def test_export_app_data_stable_ids_and_latest_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.APP_EXPORTS_DIR", tmp_path / "exports")
    db = SeenItemsDB(tmp_path / "test.sqlite")
    items = make_items()
    updates, snapshots = analyze_story_updates(items, {})

    first = export_app_data(
        db=db,
        items=items,
        story_updates=updates,
        story_snapshots=snapshots,
        outbreak_reference=make_reference(),
        target_date=date(2026, 5, 5),
        generated_at=datetime(2026, 5, 5, 6, 30),
        search_window="2 day(s) ending 2026-05-05",
        source_failures=[],
        source_health=[],
    )
    second = export_app_data(
        db=db,
        items=items,
        story_updates=updates,
        story_snapshots=snapshots,
        outbreak_reference=make_reference(),
        target_date=date(2026, 5, 5),
        generated_at=datetime(2026, 5, 5, 6, 31),
        search_window="2 day(s) ending 2026-05-05",
        source_failures=[],
        source_health=[],
    )

    assert first["items"][0]["item_id"] == second["items"][0]["item_id"]
    assert first["stories"][0]["story_id"] == second["stories"][0]["story_id"]

    latest = json.loads((tmp_path / "exports" / "latest.json").read_text())
    archive = json.loads((tmp_path / "exports" / "archive.json").read_text())
    assert latest["items"]
    assert "publisher_name" in latest["items"][0]
    assert "publisher_tier" in latest["items"][0]
    assert "publisher_access" in latest["items"][0]
    assert "link_quality" in latest["items"][0]
    assert "freshness_state" in latest["items"][0]
    assert latest["stories"]
    assert "story_url" in latest["stories"][0]
    assert "related_references" in latest["stories"][0]
    assert "freshness_counts" in latest["stories"][0]
    assert latest["topics"]
    assert "reference" in latest
    assert "related_stories" in latest["reference"][0]
    assert "freshness_summary" in latest
    assert latest["run_id"]
    assert "entries" in archive
    db.close()


def test_export_app_data_delta_and_failure_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.APP_EXPORTS_DIR", tmp_path / "exports")
    db = SeenItemsDB(tmp_path / "test.sqlite")
    items = make_items()
    updates, snapshots = analyze_story_updates(items, {})
    first = export_app_data(
        db=db,
        items=items,
        story_updates=updates,
        story_snapshots=snapshots,
        outbreak_reference=make_reference(),
        target_date=date(2026, 5, 5),
        generated_at=datetime(2026, 5, 5, 6, 30),
        search_window="2 day(s) ending 2026-05-05",
        source_failures=[{"source": "CDC Newsroom", "source_type": "rss", "error": "Timeout"}],
        source_health=[{"source": "CDC Newsroom", "mode": "failed", "item_count": 0}],
    )

    modified_items = make_items()
    modified_items[1].summary = "Coverage highlights possible human-to-human transmission and evacuation reporting."
    updates2, snapshots2 = analyze_story_updates(modified_items, snapshots)
    second = export_app_data(
        db=db,
        items=modified_items,
        story_updates=updates2,
        story_snapshots=snapshots2,
        outbreak_reference=make_reference(),
        target_date=date(2026, 5, 5),
        generated_at=datetime(2026, 5, 5, 6, 35),
        search_window="2 day(s) ending 2026-05-05",
        source_failures=[],
        source_health=[{"source": "ECDC News", "mode": "live", "item_count": 3}],
    )

    delta = json.loads((tmp_path / "exports" / "deltas" / f"{second['run_id']}.json").read_text())
    health = json.loads((tmp_path / "exports" / "health.json").read_text())
    manifest = json.loads((tmp_path / "exports" / "manifest.json").read_text())
    first_delta = json.loads((tmp_path / "exports" / "deltas" / f"{first['run_id']}.json").read_text())

    assert first_delta["stories"]
    assert delta["since_run_id"] == first["run_id"]
    assert delta["changed_story_ids"] or delta["changed_item_ids"]
    assert health["degraded"] is False
    assert "source_health" in health
    assert "freshness_summary" in health
    assert manifest["files"]["archive"] == "archive.json"
    assert manifest["files"]["reference"] == "reference.json"
    assert manifest["files"]["story_pages"] == "story_pages.json"
    assert manifest["files"]["delta"] == f"deltas/{second['run_id']}.json"
    db.close()


def test_export_app_data_keeps_optional_source_failure_visible_without_degrading(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.APP_EXPORTS_DIR", tmp_path / "exports")
    db = SeenItemsDB(tmp_path / "test.sqlite")
    items = make_items()
    updates, snapshots = analyze_story_updates(items, {})

    snapshot = export_app_data(
        db=db,
        items=items,
        story_updates=updates,
        story_snapshots=snapshots,
        outbreak_reference=make_reference(),
        target_date=date(2026, 5, 5),
        generated_at=datetime(2026, 5, 5, 6, 30),
        search_window="2 day(s) ending 2026-05-05",
        source_failures=[{"source": "Nigeria Centre for Disease Control", "source_type": "html_list", "required": False, "error": "403"}],
        source_health=[{"source": "Nigeria Centre for Disease Control", "mode": "failed", "required": False, "item_count": 0}],
    )

    health = json.loads((tmp_path / "exports" / "health.json").read_text())

    assert snapshot["degraded"] is False
    assert snapshot["source_failures"][0]["source"] == "Nigeria Centre for Disease Control"
    assert health["degraded"] is False
    assert health["source_health"][0]["mode"] == "failed"
    db.close()


def test_export_app_data_marks_pubmed_as_research_not_official(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.APP_EXPORTS_DIR", tmp_path / "exports")
    db = SeenItemsDB(tmp_path / "test.sqlite")
    items = [
        Item(
            title="Genomic analyses identify nosocomial transmission of ST23 carbapenem-resistant hypervirulent Klebsiella pneumoniae.",
            source="PubMed Infectious Disease Search",
            url="https://pubmed.ncbi.nlm.nih.gov/42000001/",
            category="Major epidemiology studies",
            source_type="pubmed",
            official=True,
            journal="Clinical Infectious Diseases",
            summary="Hospital transmission and resistance are central to the paper.",
        )
    ]
    updates, snapshots = analyze_story_updates(items, {})

    snapshot = export_app_data(
        db=db,
        items=items,
        story_updates=updates,
        story_snapshots=snapshots,
        outbreak_reference=make_reference(),
        target_date=date(2026, 5, 9),
        generated_at=datetime(2026, 5, 9, 7, 0),
        search_window="7 day(s) ending 2026-05-09",
        source_failures=[],
        source_health=[],
    )

    exported_item = snapshot["items"][0]
    assert exported_item["evidence_type"] == "journal_article"
    assert exported_item["content_class"] == "research_context"
    assert exported_item["official"] is False
    assert exported_item["source_confidence"] == "specialist_health"
    assert "research" in exported_item["editions"]
    db.close()


def test_export_app_data_does_not_mark_plain_virology_news_as_research(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.APP_EXPORTS_DIR", tmp_path / "exports")
    db = SeenItemsDB(tmp_path / "test.sqlite")
    items = [
        Item(
            title="Fox Tests Positive for Avian Influenza in Tioga County",
            source="Google News Major Outbreak Desks",
            url="https://news.google.com/example",
            category="Virology and pathogen evolution",
            source_type="rss",
            official=False,
            summary="Limited detail was available from feed metadata alone.",
        )
    ]
    updates, snapshots = analyze_story_updates(items, {})

    snapshot = export_app_data(
        db=db,
        items=items,
        story_updates=updates,
        story_snapshots=snapshots,
        outbreak_reference=make_reference(),
        target_date=date(2026, 5, 9),
        generated_at=datetime(2026, 5, 9, 7, 5),
        search_window="7 day(s) ending 2026-05-09",
        source_failures=[],
        source_health=[],
    )

    exported_item = snapshot["items"][0]
    assert exported_item["evidence_type"] == "news_report"
    assert "research" not in exported_item["editions"]
    db.close()


def test_export_app_data_does_not_append_story_timeline_for_noop_refresh(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.APP_EXPORTS_DIR", tmp_path / "exports")
    db = SeenItemsDB(tmp_path / "test.sqlite")
    items = make_items()
    updates, snapshots = analyze_story_updates(items, {})
    first = export_app_data(
        db=db,
        items=items,
        story_updates=updates,
        story_snapshots=snapshots,
        outbreak_reference=make_reference(),
        target_date=date(2026, 5, 5),
        generated_at=datetime(2026, 5, 5, 6, 30),
        search_window="2 day(s) ending 2026-05-05",
        source_failures=[],
        source_health=[],
    )

    noop_updates, noop_snapshots = analyze_story_updates(items, snapshots)
    second = export_app_data(
        db=db,
        items=items,
        story_updates=noop_updates,
        story_snapshots=noop_snapshots,
        outbreak_reference=make_reference(),
        target_date=date(2026, 5, 5),
        generated_at=datetime(2026, 5, 5, 6, 35),
        search_window="2 day(s) ending 2026-05-05",
        source_failures=[],
        source_health=[],
    )

    assert not noop_updates
    assert len(first["stories"][0]["timeline"]) == 1
    assert len(second["stories"][0]["timeline"]) == 1
    assert second["stories"][0]["latest_update_summary"] == first["stories"][0]["latest_update_summary"]
    db.close()


def test_export_app_data_retains_recent_active_story_when_current_snapshot_omits_it(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.APP_EXPORTS_DIR", tmp_path / "exports")
    db = SeenItemsDB(tmp_path / "test.sqlite")
    items = make_items()
    updates, snapshots = analyze_story_updates(items, {})
    first = export_app_data(
        db=db,
        items=items,
        story_updates=updates,
        story_snapshots=snapshots,
        outbreak_reference=make_reference(),
        target_date=date(2026, 5, 7),
        generated_at=datetime(2026, 5, 7, 18, 1, 53),
        search_window="4 day(s) ending 2026-05-07",
        source_failures=[],
        source_health=[],
    )

    second = export_app_data(
        db=db,
        items=[],
        story_updates=[],
        story_snapshots={},
        outbreak_reference=make_reference(),
        target_date=date(2026, 5, 8),
        generated_at=datetime(2026, 5, 8, 6, 13, 5),
        search_window="4 day(s) ending 2026-05-08",
        source_failures=[],
        source_health=[],
    )

    retained = next(story for story in second["stories"] if story["story_id"] == first["stories"][0]["story_id"])
    assert retained["display_title"] == "Hantavirus and cruise-ship outbreak"
    assert retained["new_since_last_refresh"] is False
    assert retained["latest_update_summary"] == first["stories"][0]["latest_update_summary"]
    db.close()
