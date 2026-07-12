from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta

from .app_exports import export_app_data
from .database import SeenItemsDB
from .dedupe import deduplicate_items
from .emailer import send_dossier_email
from .fetchers import enrich_item_text, fetch_all_sources
from .render_markdown import analyze_story_updates, classify_topic, render_markdown
from .render_html import render_html, validate_reader_story_sections
from .scoring import score_item
from .summarize import summarize_item
from .utils import (
    app_exports_dir,
    ensure_directories,
    has_disease_reference_signal,
    has_local_signal,
    infer_region,
    Item,
    legacy_briefing_filename,
    legacy_briefing_html_filename,
    latest_filename,
    latest_html_filename,
    list_briefing_archives,
    load_email_config,
    load_outbreak_reference,
    load_sources,
    load_search_terms,
    parse_datetime,
    safe_filename,
    safe_html_filename,
    sortable_datetime,
    setup_logging,
)

MAX_ITEMS_TO_RENDER = 40
MAX_ITEMS_TO_ENRICH = 18
MAX_HISTORICAL_ITEMS_TO_RENDER = 8
MAX_RESEARCH_ITEMS = 6
MIN_RENDERABLE_RELEVANCE = 2
MAX_PER_SOURCE = 4
MAX_PUBMED_ITEMS = 6
MAX_MAJOR_STUDY_ITEMS = 8
MIN_OFFICIAL_SIGNAL_ITEMS = 6
MAX_OFFICIAL_ITEMS_PER_OUTBREAK_TOPIC = 2
MAX_POSTMERGE_ENRICH = 12
MAX_ACTIVE_STORY_POSTMERGE_ENRICH = 40
REGIONAL_MONITORING_WINDOW_DAYS = 14
STORY_RENDER_FALLBACK_MIN_ITEMS = 8

GENERIC_PRIORITY_TERMS = {
    "cluster",
    "clusters",
    "epidemiology",
    "public health",
    "surveillance",
    "vaccine",
    "virology",
    "wastewater",
}

HISTORICAL_TERMS = (
    "historical",
    "ancient",
    "paleopathology",
    "archaeology",
    "archaeogenetics",
    "paleogenomics",
    "paleomicrobiology",
    "history of medicine",
    "ancient dna",
    "pathogen adna",
    "ancient genome",
    "yersinia pestis",
    "plague",
    "smallpox",
    "variola",
    "leprosy",
    "mycobacterium leprae",
    "mycobacterium tuberculosis",
    "treponemal",
    "syphilis",
    "burial",
    "cemetery",
    "mummified",
    "skeletal",
)

RESEARCH_SOURCE_TYPES = {"pubmed", "medrxiv", "biorxiv"}
RESEARCH_CATEGORIES = {
    "Major epidemiology studies",
    "Virology and pathogen evolution",
    "Historical epidemiology / ancient disease / paleopathology",
}
RESEARCH_SCOPE_TERMS = (
    "infectious",
    "infection",
    "pathogen",
    "pathogens",
    "virolog",
    "viral",
    "bacter",
    "parasit",
    "fung",
    "antimicrobial resistance",
    "antibiotic resistance",
    "carbapenem",
    "nosocomial",
    "outbreak",
    "surveillance",
    "transmission",
    "seroepidemi",
    "vaccine",
    "vaccination",
    "zoonotic",
    "spillover",
    "reservoir",
    "vector",
    "wastewater",
    "h5n1",
    "avian influenza",
    "influenza",
    "covid",
    "sars-cov-2",
    "coronavirus",
    "rsv",
    "hantavirus",
    "measles",
    "mpox",
    "dengue",
    "malaria",
    "cholera",
    "polio",
    "tuberculosis",
    "mycobacterium tuberculosis",
    "salmonella",
    "e. coli",
    "listeria",
    "norovirus",
    "cyclospora",
    "cyclosporiasis",
    "campylobacter",
    "shigella",
    "vibrio",
    "yersinia",
    "botulism",
    "hepatitis",
    "yellow fever",
    "chikungunya",
    "oropouche",
    "rift valley fever",
    "anthrax",
    "ebola",
    "marburg",
    "lassa",
    "nipah",
    "rabies",
    "schistosomiasis",
    "klebsiella pneumoniae",
    "plague",
    "variola",
    "smallpox",
    "leprosy",
    "syphilis",
    "ancient dna",
    "ancient pathogen",
    "archaeogenetics",
    "paleopathology",
    "paleogenomics",
    "paleomicrobiology",
)

LOW_VALUE_TITLE_PATTERNS = (
    "what you need to know",
    "here is what you need to know",
    "here's what you need to know",
    "what are hantavirus symptoms",
    "what are measles symptoms",
    "symptoms?",
    "live updates",
)

MISCLASSIFIED_TRAVEL_NOTICE_PATTERNS = (
    "voluntary recall",
    "possible health risk",
    "recalls ",
    "issues voluntary recall",
)

LOW_DETAIL_MARKERS = (
    "limited detail was available from feed metadata alone.",
    "limited usable detail remained after boilerplate cleanup.",
)

BRIEFING_SCOPE_TERMS = (
    "outbreak",
    "emerging infection",
    "infectious disease",
    "epidemiology",
    "surveillance",
    "virology",
    "occupational exposure",
    "occupational health",
    "environmental exposure",
    "wastewater",
    "antimicrobial resistance",
    "travel health",
    "health notice",
    "foodborne",
    "recall",
    "zoonotic",
    "spillover",
    "avian influenza",
    "h5n1",
    "influenza",
    "covid",
    "sars-cov-2",
    "rsv",
    "hantavirus",
    "measles",
    "mpox",
    "dengue",
    "malaria",
    "cholera",
    "polio",
    "tuberculosis",
    "norovirus",
    "salmonella",
    "e. coli",
    "listeria",
    "hepatitis a",
    "cyclospora",
    "cyclosporiasis",
    "campylobacter",
    "shigella",
    "vibrio",
    "yersinia",
    "botulism",
    "yellow fever",
    "chikungunya",
    "oropouche",
    "rift valley fever",
    "anthrax",
    "ebola",
    "marburg",
    "lassa",
    "nipah",
    "meningococcal",
    "pertussis",
    "legionnaires",
    "rabies",
    "historical epidemiology",
    "ancient dna",
    "ancient pathogen",
    "paleopathology",
    "paleogenomics",
    "paleomicrobiology",
    "archaeogenetics",
    "history of medicine",
)

STORY_FOLLOW_UP_TERMS = (
    "human-to-human",
    "person-to-person",
    "evacuat",
    "confirmed",
    "new case",
    "tests positive",
    "test positive",
    "switzerland",
    "canary islands",
    "dock",
    "docking",
    "anded strain",
    "andes strain",
    "remains anchored",
    "passengers evacuated",
    "medical teams",
)

OUTBREAK_ACTIVITY_TERMS = (
    "outbreak",
    "cluster",
    "confirmed",
    "confirmed case",
    "suspected",
    "suspected case",
    "probable case",
    "new case",
    "cases",
    "death",
    "deaths",
    "died",
    "fatal",
    "case fatality",
    "transmission",
    "community transmission",
    "healthcare transmission",
    "tests positive",
    "test positive",
    "evacuat",
    "medical teams",
    "infection prevention",
    "contact tracing",
    "contacts",
    "isolation",
    "quarantine",
    "safe burial",
    "safe burials",
    "traditional burial",
    "unsafe burial",
    "burial team",
    "retrieve body",
    "retrieve bodies",
    "body retrieval",
    "body of a suspected",
    "bodies of suspected",
    "treatment center",
    "treatment centre",
    "treatment facility",
    "clinic burned",
    "ward burned",
    "hospital stormed",
    "clinic stormed",
    "center burned",
    "centre burned",
    "set on fire",
    "stormed",
    "health emergency",
    "public health emergency",
    "emergency response",
    "travel health notice",
    "border screening",
    "entry screening",
    "surveillance",
    "rapid response",
    "health zone",
    "province",
    "district",
    "unknown illness",
    "mystery illness",
)

GENERIC_STORYWORTHY_OUTBREAK_TERMS = (
    "disease outbreak",
    "infectious disease outbreak",
    "unknown illness",
    "mystery illness",
    "public health emergency",
    "health emergency",
    "viral hemorrhagic fever",
    "viral haemorrhagic fever",
    "travel health notice",
    "rapid response team",
    "contact tracing",
    "case fatality",
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a daily infectious disease dossier.")
    parser.add_argument("--dry-run", action="store_true", help="Print candidates without writing a dossier.")
    parser.add_argument("--days", type=int, default=7, help="Search window in days ending at the target date.")
    parser.add_argument("--date", type=str, help="Target date in YYYY-MM-DD format.")
    parser.add_argument("--backfill", type=int, help="Generate dossiers for the previous N days.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    ensure_directories()
    logger = setup_logging()

    if args.backfill:
        target_end = parse_target_date(args.date)
        for offset in reversed(range(args.backfill)):
            run_date = target_end - timedelta(days=offset)
            run_once(run_date, args.days, args.dry_run, logger)
        return 0

    target_date = parse_target_date(args.date)
    run_once(target_date, args.days, args.dry_run, logger)
    return 0


def parse_target_date(raw: str | None) -> date:
    if not raw:
        return datetime.now().date()
    parsed = parse_datetime(raw)
    if not parsed:
        raise ValueError(f"Invalid date: {raw}")
    return parsed.date()


def load_previous_latest_snapshot() -> dict:
    latest_snapshot_path = app_exports_dir() / "latest.json"
    if not latest_snapshot_path.exists():
        return {}
    try:
        return json.loads(latest_snapshot_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def select_story_records_for_render(
    latest_snapshot: dict,
    previous_snapshot: dict,
    processed_count: int,
) -> tuple[list[dict], bool]:
    current_story_records = latest_snapshot.get("stories", [])
    if current_story_records:
        return current_story_records, False

    previous_story_records = previous_snapshot.get("stories", []) if previous_snapshot else []
    if previous_story_records and processed_count >= STORY_RENDER_FALLBACK_MIN_ITEMS:
        return previous_story_records, True
    return current_story_records, False


def select_reference_records_for_render(latest_snapshot: dict, previous_snapshot: dict) -> list[dict]:
    return latest_snapshot.get("reference", []) or previous_snapshot.get("reference", []) or []


def run_once(
    target_date: date,
    window_days: int,
    dry_run: bool,
    logger,
    return_payload: bool = False,
    *,
    write_local_artifacts: bool = True,
) -> dict | None:
    db = SeenItemsDB()
    try:
        email_config = load_email_config()
        sources = load_sources()
        search_terms = load_search_terms()
        outbreak_reference = load_outbreak_reference()
        previous_published_snapshot = load_previous_latest_snapshot()
        start_date = target_date - timedelta(days=max(window_days - 1, 0))
        raw_items, source_failures, source_health = fetch_all_sources(sources, logger, start_date=start_date, end_date=target_date)
        filtered = filter_by_date(raw_items, target_date, window_days)
        filtered = filter_by_terms(filtered, search_terms)
        deduped = deduplicate_items(filtered)
        unseen = [item for item in deduped if not is_seen(item, db)]
        previous_story_snapshots = db.load_story_snapshots()
        output_path = safe_filename(target_date)
        html_path = safe_html_filename(target_date)
        legacy_output_path = legacy_briefing_filename(target_date)
        legacy_html_output_path = legacy_briefing_html_filename(target_date)
        archive_entries = list_briefing_archives(include_date=target_date)

        if dry_run:
            processed = process_items(deduped, logger)
            story_updates, _ = analyze_story_updates(processed, previous_story_snapshots)
            if processed:
                for item in processed[:30]:
                    print(f"[{item.relevance_score}/5] {item.title} | {item.source} | {item.url}")
                if story_updates:
                    print("")
                    print("Story updates:")
                    for update in story_updates[:5]:
                        print(f"- {update.topic_name}: {update.bullets[0]}")
            else:
                print("No candidate items passed the current filters for this run.")
            logger.info("Dry run completed with %s items", len(processed))
            return {
                "target_date": target_date,
                "window_days": window_days,
                "processed": processed,
                "story_updates": story_updates,
                "archive_entries": archive_entries,
                "outbreak_reference": outbreak_reference,
                "source_failures": source_failures,
                "source_health": source_health,
                "dry_run": True,
            } if return_payload else None

        processed = process_items(deduped, logger)
        story_updates, current_story_snapshots = analyze_story_updates(processed, previous_story_snapshots)
        generated_at = datetime.now()
        markdown = render_markdown(
            processed,
            target_date=target_date,
            generated_at=generated_at,
            search_window=f"{window_days} day(s) ending {target_date.isoformat()}",
            outbreak_reference=outbreak_reference,
            story_updates=story_updates,
            source_failures=source_failures,
            source_health=source_health,
        )
        latest_snapshot = export_app_data(
            db=db,
            items=processed,
            story_updates=story_updates,
            story_snapshots=current_story_snapshots,
            outbreak_reference=outbreak_reference,
            target_date=target_date,
            generated_at=generated_at,
            search_window=f"{window_days} day(s) ending {target_date.isoformat()}",
            source_failures=source_failures,
            source_health=source_health,
        )
        render_story_records, used_story_render_fallback = select_story_records_for_render(
            latest_snapshot,
            previous_published_snapshot,
            len(processed),
        )
        render_reference_records = select_reference_records_for_render(latest_snapshot, previous_published_snapshot)
        if used_story_render_fallback:
            logger.warning(
                "Using the prior published story records for reader HTML because the current snapshot produced zero active stories across %s rendered items.",
                len(processed),
            )
        html_output = render_html(
            processed,
            target_date=target_date,
            generated_at=generated_at,
            search_window=f"{window_days} day(s) ending {target_date.isoformat()}",
            outbreak_reference=outbreak_reference,
            story_updates=story_updates,
            archive_entries=archive_entries,
            source_failures=source_failures,
            source_health=source_health,
            story_records=render_story_records,
            reference_records=render_reference_records,
        )
        html_validation_issues = validate_reader_story_sections(html_output, render_story_records)
        html_writable = not html_validation_issues
        if html_validation_issues:
            logger.error("Skipping HTML artifact writes because reader validation failed: %s", "; ".join(html_validation_issues))
        latest_path = latest_filename()
        latest_html_path = latest_html_filename()
        promote_latest = should_promote_latest(
            raw_item_count=len(raw_items),
            processed_count=len(processed),
            source_failures=source_failures,
            latest_exists=latest_path.exists() and latest_html_path.exists(),
        )
        if write_local_artifacts:
            output_path.write_text(markdown, encoding="utf-8")
            legacy_output_path.write_text(markdown, encoding="utf-8")
            if html_writable:
                html_path.write_text(html_output, encoding="utf-8")
                legacy_html_output_path.write_text(html_output, encoding="utf-8")
            if promote_latest:
                latest_path.write_text(markdown, encoding="utf-8")
                if html_writable:
                    latest_html_path.write_text(html_output, encoding="utf-8")
            else:
                logger.warning(
                    "Skipping latest dossier promotion because the run fetched zero raw items and logged source failures; preserving the previous latest briefing."
                )
        for item in unseen:
            db.mark_seen(item)
        for topic_name, snapshot in current_story_snapshots.items():
            db.save_story_snapshot(topic_name, snapshot)
        if write_local_artifacts and promote_latest:
            send_dossier_email(
                config=email_config,
                dossier_path=latest_path,
                target_date=target_date.isoformat(),
                generated_at=generated_at.isoformat(timespec="minutes"),
                logger=logger,
            )
        elif write_local_artifacts:
            logger.warning("Skipping dossier email because latest briefing promotion was skipped.")
        if write_local_artifacts:
            written_paths = [output_path, legacy_output_path]
            if html_writable:
                written_paths.extend([html_path, legacy_html_output_path])
            if promote_latest:
                written_paths.append(latest_path)
                if html_writable:
                    written_paths.append(latest_html_path)
            logger.info(
                "Wrote dossier artifacts to %s with %s rendered items (%s new, %s fetched, %s date-filtered, %s deduped)%s",
                ", ".join(str(path) for path in written_paths),
                len(processed),
                len(unseen),
                len(raw_items),
                len(filtered),
                len(deduped),
                "" if promote_latest else "; latest briefing was preserved from the prior successful run",
            )
        else:
            logger.info(
                "Completed dossier run without writing local artifacts: %s rendered items (%s new, %s fetched, %s date-filtered, %s deduped)%s",
                len(processed),
                len(unseen),
                len(raw_items),
                len(filtered),
                len(deduped),
                "" if promote_latest else "; latest promotion was withheld by degraded-run guard",
            )
        if return_payload:
            return {
                "target_date": target_date,
                "window_days": window_days,
                "generated_at": generated_at,
                "markdown_output": markdown,
                "html_output": html_output,
                "processed": processed,
                "story_updates": story_updates,
                "story_snapshots": current_story_snapshots,
                "outbreak_reference": outbreak_reference,
                "archive_entries": archive_entries,
                "source_failures": source_failures,
                "source_health": source_health,
                "latest_snapshot": latest_snapshot,
                "render_story_records": render_story_records,
                "render_reference_records": render_reference_records,
                "html_validation_issues": html_validation_issues,
                "story_render_fallback_used": used_story_render_fallback,
                "promote_latest": promote_latest,
                "write_local_artifacts": write_local_artifacts,
                "paths": {
                    "dated_markdown": output_path,
                    "dated_html": html_path,
                    "legacy_markdown": legacy_output_path,
                    "legacy_html": legacy_html_output_path,
                    "latest_markdown": latest_path,
                    "latest_html": latest_html_path,
                },
            }
        return None
    finally:
        db.close()


def should_promote_latest(
    raw_item_count: int,
    processed_count: int,
    source_failures: list[dict[str, str]],
    latest_exists: bool,
) -> bool:
    if raw_item_count == 0 and processed_count == 0 and source_failures and latest_exists:
        return False
    return True


def process_items(items, logger):
    if not items:
        return []

    prelim = [summarize_item(item) for item in items]
    for item in prelim:
        item.relevance_score = score_item(item)

    prelim.sort(key=lambda item: (item.relevance_score, sortable_datetime(item.published_at)), reverse=True)
    shortlisted = build_balanced_shortlist(prelim)
    shortlist_urls = {item.canonical_url for item in shortlisted[:MAX_ITEMS_TO_ENRICH]}

    processed: list[Item] = []
    for item in shortlisted:
        current = item
        if item.canonical_url in shortlist_urls:
            current = summarize_item(enrich_item_text(item, logger))
            current.relevance_score = score_item(current)
        processed.append(current)

    processed = filter_renderable_items(processed)
    processed = merge_tracked_story_followups(processed, prelim)
    processed = enrich_postmerge_items(processed, logger)
    processed.sort(key=lambda item: (item.relevance_score, sortable_datetime(item.published_at)), reverse=True)
    return processed


def build_balanced_shortlist(items: list[Item]) -> list[Item]:
    selected: list[Item] = []
    used_urls: set[str] = set()
    per_source_counts: dict[str, int] = {}
    major_study_count = 0
    pubmed_count = 0
    research_item_count = 0

    def can_add(item: Item) -> bool:
        nonlocal major_study_count, pubmed_count, research_item_count
        if item.canonical_url in used_urls:
            return False
        if per_source_counts.get(item.source, 0) >= source_cap(item):
            return False
        if item.source_type == "pubmed" and pubmed_count >= MAX_PUBMED_ITEMS:
            return False
        if item.category == "Major epidemiology studies" and major_study_count >= MAX_MAJOR_STUDY_ITEMS:
            return False
        if item_is_research_item(item) and not item_is_historical(item) and research_item_count >= MAX_RESEARCH_ITEMS:
            return False
        return True

    def add(item: Item) -> bool:
        nonlocal major_study_count, pubmed_count, research_item_count
        if not can_add(item):
            return False
        selected.append(item)
        used_urls.add(item.canonical_url)
        per_source_counts[item.source] = per_source_counts.get(item.source, 0) + 1
        if item.source_type == "pubmed":
            pubmed_count += 1
        if item.category == "Major epidemiology studies":
            major_study_count += 1
        if item_is_research_item(item) and not item_is_historical(item):
            research_item_count += 1
        return True

    # Establish each known official outbreak topic before general balancing can
    # spend the render budget on a busy news cycle.
    active_official_outbreak_items = build_active_official_outbreak_items(items)
    for item in active_official_outbreak_items:
        if len(selected) >= MAX_ITEMS_TO_RENDER:
            break
        add(item)

    official_priority = [item for item in items if is_official_signal_item(item)]
    for item in official_priority:
        if len(selected) >= MIN_OFFICIAL_SIGNAL_ITEMS:
            break
        add(item)

    active_official_topics: list[str] = []
    seen_topics: set[str] = set()
    for item in official_priority:
        topic_name = classify_topic(item)
        if topic_name == "Miscellaneous signals" or topic_name in seen_topics:
            continue
        seen_topics.add(topic_name)
        active_official_topics.append(topic_name)

    regional_priority_items = build_regional_priority_items(items)
    for item in regional_priority_items:
        if len(selected) >= MAX_ITEMS_TO_RENDER:
            break
        add(item)

    for topic_name in active_official_topics:
        topic_followups = [
            item
            for item in items
            if classify_topic(item) == topic_name and item_looks_like_story_followup(item)
        ]
        for item in topic_followups:
            if len(selected) >= MAX_ITEMS_TO_RENDER:
                break
            if add(item):
                continue

    research_items = [
        item
        for item in items
        if item_is_research_item(item) and not item_is_historical(item)
    ]
    research_items = sorted(
        research_items,
        key=lambda item: (
            1 if item.source_type in RESEARCH_SOURCE_TYPES else 0,
            item.relevance_score,
            sortable_datetime(item.published_at),
        ),
        reverse=True,
    )
    for item in research_items:
        if len(selected) >= MAX_ITEMS_TO_RENDER:
            break
        add(item)

    ongoing_story_items = [item for item in items if is_storyworthy_signal(item)]
    for item in ongoing_story_items:
        if len(selected) >= MAX_ITEMS_TO_RENDER:
            break
        add(item)

    major_studies = [item for item in items if item.category == "Major epidemiology studies"]
    for item in major_studies:
        if len(selected) >= MAX_ITEMS_TO_RENDER:
            break
        add(item)

    historical_items = [item for item in items if item_is_historical(item)]
    historical_added = 0
    for item in historical_items:
        if len(selected) >= MAX_ITEMS_TO_RENDER or historical_added >= MAX_HISTORICAL_ITEMS_TO_RENDER:
            break
        if add(item):
            historical_added += 1

    for item in items:
        if len(selected) >= MAX_ITEMS_TO_RENDER:
            break
        add(item)

    return dedupe_shortlist_by_url(selected)


def build_active_official_outbreak_items(items: list[Item]) -> list[Item]:
    """Keep a small official foothold for every named active outbreak topic."""
    candidates_by_topic: dict[str, list[Item]] = {}
    for item in items:
        if not item.official or item.relevance_score < 4 or not is_official_signal_item(item):
            continue
        topic_name = classify_topic(item)
        if topic_name == "Miscellaneous signals":
            continue
        candidates_by_topic.setdefault(topic_name, []).append(item)

    topic_groups = [
        sorted(
            topic_items,
            key=lambda item: (item.relevance_score, sortable_datetime(item.published_at)),
            reverse=True,
        )
        for topic_items in candidates_by_topic.values()
    ]
    topic_groups.sort(
        key=lambda topic_items: (topic_items[0].relevance_score, sortable_datetime(topic_items[0].published_at)),
        reverse=True,
    )

    # One lead from every topic comes before a second item from any topic.
    prioritized: list[Item] = []
    for position in range(MAX_OFFICIAL_ITEMS_PER_OUTBREAK_TOPIC):
        prioritized.extend(topic_items[position] for topic_items in topic_groups if len(topic_items) > position)
    return prioritized


def build_regional_priority_items(items: list[Item]) -> list[Item]:
    buckets: dict[str, list[Item]] = {}
    for item in items:
        region = infer_region(item)
        if region in {"Global / Maritime", "Cross-region / unassigned", "North America", "Europe"}:
            continue
        if item_is_pseudo_regional_maritime_story(item):
            continue
        if not (item.official or item_has_concrete_signal(item) or regionally_undercovered_signal(item)):
            continue
        buckets.setdefault(region, []).append(item)

    region_targets = {
        "Africa": 4,
        "South Asia": 3,
        "Southeast Asia": 2,
        "East Asia": 2,
        "Middle East": 2,
        "Latin America and Caribbean": 2,
        "Oceania": 1,
    }

    prioritized: list[Item] = []
    for region in ("Africa", "South Asia", "Southeast Asia", "East Asia", "Middle East", "Latin America and Caribbean", "Oceania"):
        region_items = buckets.get(region, [])
        if not region_items:
            continue
        region_items = sorted(
            region_items,
            key=lambda item: (
                1 if has_local_signal(item) else 0,
                1 if item.official else 0,
                item.relevance_score,
                sortable_datetime(item.published_at),
            ),
            reverse=True,
        )
        target = region_targets.get(region, 2)
        chosen: list[Item] = []
        seen_sources: set[str] = set()
        for item in region_items:
            if item.source not in seen_sources:
                chosen.append(item)
                seen_sources.add(item.source)
            if len(chosen) >= target:
                break
        if len(chosen) < target:
            for item in region_items:
                if item in chosen:
                    continue
                chosen.append(item)
                if len(chosen) >= target:
                    break
        prioritized.extend(chosen)
    return prioritized


def source_cap(item: Item) -> int:
    if item_looks_like_story_followup(item):
        return max(MAX_PER_SOURCE, 12)
    if item.source_type == "pubmed":
        return min(MAX_PER_SOURCE, 3)
    if item.official and item.category != "Major epidemiology studies":
        return MAX_PER_SOURCE + 1
    return MAX_PER_SOURCE


def is_official_signal_item(item: Item) -> bool:
    if not item.official:
        return False
    if item.category == "Major epidemiology studies":
        return False
    text = " ".join([item.title.lower(), item.summary.lower(), item.category.lower()])
    content_text = " ".join([item.title.lower(), item.summary.lower(), item.extracted_text.lower(), item.url.lower()])
    if any(
        term in text
        for term in (
            "outbreak",
            "investigation",
            "surveillance",
            "hantavirus",
            "measles",
            "cholera",
            "dengue",
            "lassa",
            "avian influenza",
            "h5n1",
            "wastewater",
            "travel health",
            "public health",
        )
    ):
        return True
    return has_disease_reference_signal(content_text) and any(term in content_text for term in OUTBREAK_ACTIVITY_TERMS)


def is_storyworthy_signal(item: Item) -> bool:
    if item.relevance_score < 3:
        return False
    text = " ".join([item.title.lower(), item.summary.lower(), item.category.lower()])
    return any(
        term in text
        for term in (
            "outbreak",
            "cluster",
            "under investigation",
            "monitoring",
            "quarantine",
            "deaths",
            "transmission",
            "surveillance",
            "hantavirus",
            "measles",
            "polio",
            "wastewater",
            "avian influenza",
            "h5n1",
            "cholera",
            "dengue",
            "mpox",
            "marburg",
            "ebola",
            "anthrax",
            "lassa",
            "nipah",
            "chikungunya",
            "yellow fever",
            "zika",
            "malaria",
            "meningococcal",
            "diphtheria",
            "pertussis",
            "legionnaires",
            "rabies",
            "hepatitis a",
            "norovirus",
            "cyclospora",
            "cyclosporiasis",
            "campylobacter",
            "shigella",
            "vibrio",
            "yersinia",
            "botulism",
            "oropouche",
            "rift valley fever",
            "mers",
        )
    )


def filter_renderable_items(items: list[Item]) -> list[Item]:
    kept: list[Item] = []
    for item in items:
        if item_should_drop(item):
            continue
        kept.append(item)
    return kept


def item_should_drop(item: Item) -> bool:
    low_detail = any(marker in item.summary.lower() for marker in LOW_DETAIL_MARKERS)
    source = item.source.lower()
    if item_from_misclassified_travel_notice_feed(item):
        return True
    if (
        "google news" in source
        and item.publisher_tier in {"wire", "major_newsroom", "specialist_health"}
        and item_has_concrete_signal(item)
    ):
        return False
    if item_is_historical(item):
        if not item.official and low_detail:
            return True
        return False
    if item_is_research_item(item):
        if not item_matches_research_scope(item):
            return True
        if low_detail:
            return True
        return False
    if not item_matches_briefing_scope(item):
        return True
    if item.official:
        if not item.published_at and not item_has_disease_specific_signal(item):
            return True
        return False
    if item.relevance_score < MIN_RENDERABLE_RELEVANCE and not regionally_undercovered_signal(item):
        return True

    title = item.title.lower()
    summary = item.summary.lower()
    if "google news" in source and low_detail and not item_looks_like_story_followup(item) and not regionally_undercovered_signal(item):
        return True
    if any(pattern in title for pattern in LOW_VALUE_TITLE_PATTERNS):
        return True
    if title.startswith("what are ") and " symptoms" in title:
        return True
    if "google news" in source and not item_has_concrete_signal(item) and not regionally_undercovered_signal(item):
        return True
    if low_detail and not item_has_concrete_signal(item) and not regionally_undercovered_signal(item):
        return True
    return False


def item_looks_like_story_followup(item: Item) -> bool:
    if item.official:
        return False
    if "google news" not in item.source.lower():
        return False
    title = item.title.lower()
    content_text = " ".join([item.title.lower(), item.summary.lower(), item.extracted_text.lower(), item.url.lower()])
    if any(pattern in title for pattern in LOW_VALUE_TITLE_PATTERNS):
        return False
    if not any(term in content_text for term in OUTBREAK_ACTIVITY_TERMS):
        return False
    if has_disease_reference_signal(content_text):
        return True
    return any(term in content_text for term in GENERIC_STORYWORTHY_OUTBREAK_TERMS)


def item_is_pseudo_regional_maritime_story(item: Item) -> bool:
    text = " ".join([item.title.lower(), item.summary.lower(), item.category.lower()])
    return (
        "hantavirus" in text
        and any(
            term in text
            for term in (
                "cruise ship",
                "canary islands",
                "cape verde",
                "atlantic",
                "docking",
                "aboard",
                "mv hondius",
                "passengers evacuated",
                "british patient",
                "clinically improving",
                "spain-bound cruise",
            )
        )
    )


def merge_tracked_story_followups(processed: list[Item], candidates: list[Item]) -> list[Item]:
    active_topics = {
        classify_topic(item)
        for item in processed
        if item.official and classify_topic(item) != "Miscellaneous signals"
    }
    if not active_topics:
        return processed

    merged = list(processed)
    seen_urls = {item.canonical_url for item in processed}
    followups = sorted(
        [
            item
            for item in candidates
            if item.canonical_url not in seen_urls
            and classify_topic(item) in active_topics
            and (item.official or item_looks_like_story_followup(item))
        ],
        key=lambda item: sortable_datetime(item.published_at),
        reverse=True,
    )

    for item in followups:
        current = summarize_item(item)
        current.relevance_score = score_item(current)
        if item_should_drop(current) and not item_looks_like_story_followup(current):
            continue
        merged.append(current)
        seen_urls.add(current.canonical_url)

    return merged


def enrich_postmerge_items(items: list[Item], logger) -> list[Item]:
    remaining = MAX_POSTMERGE_ENRICH
    active_story_remaining = MAX_ACTIVE_STORY_POSTMERGE_ENRICH
    active_topics = {
        classify_topic(item)
        for item in items
        if item.official and classify_topic(item) != "Miscellaneous signals"
    }
    enriched: list[Item] = []
    for item in items:
        current = item
        low_detail = any(marker in item.summary.lower() for marker in LOW_DETAIL_MARKERS)
        is_google_wrapper = "google news" in item.source.lower() and ("news.google.com" in item.url.lower() or low_detail)
        topic_name = classify_topic(item)
        if is_google_wrapper and topic_name in active_topics and active_story_remaining > 0:
            current = summarize_item(enrich_item_text(item, logger))
            current.relevance_score = score_item(current)
            active_story_remaining -= 1
        elif remaining > 0 and is_google_wrapper:
            current = summarize_item(enrich_item_text(item, logger))
            current.relevance_score = score_item(current)
            remaining -= 1
        enriched.append(current)
    return enriched


def item_has_concrete_signal(item: Item) -> bool:
    text = " ".join([item.title.lower(), item.summary.lower(), item.extracted_text.lower()])
    if any(term in text for term in ("cdc", "ecdc", "who", "fda", "aphis", "department of health")):
        return True
    if any(term in text for term in ("death", "deaths", "died", "fatal", "quarantine", "quarantined", "evacuated", "investigation", "monitoring", "surveillance", "wastewater", "transmission", "confirmed", "suspected", "cases", "outbreak", "cluster", "health alert", "warning", "emergency")):
        return True
    if any(
        term in text
        for term in (
            "cholera",
            "dengue",
            "mpox",
            "marburg",
            "ebola",
            "anthrax",
            "lassa",
            "nipah",
            "chikungunya",
            "yellow fever",
            "zika",
            "malaria",
            "meningococcal",
            "diphtheria",
            "pertussis",
            "legionnaires",
            "rabies",
            "hepatitis a",
            "norovirus",
            "cyclospora",
            "cyclosporiasis",
            "campylobacter",
            "shigella",
            "vibrio",
            "yersinia",
            "botulism",
            "oropouche",
            "rift valley fever",
            "mers",
            "avian influenza",
            "h5n1",
            "measles",
            "polio",
            "tuberculosis",
            "hantavirus",
        )
    ):
        return True
    return bool(re.search(r"\b\d+\b", text))


def item_is_research_item(item: Item) -> bool:
    return (item.source_type or "") in RESEARCH_SOURCE_TYPES or item.category in RESEARCH_CATEGORIES


def item_matches_research_scope(item: Item) -> bool:
    if item_is_historical(item):
        return True
    text = " ".join(
        [
            item.title.lower(),
            item.summary.lower(),
            item.url.lower(),
            item.extracted_text.lower(),
            item.category.lower(),
            (item.journal or "").lower(),
        ]
    )
    return any(term in text for term in RESEARCH_SCOPE_TERMS)


def item_matches_briefing_scope(item: Item) -> bool:
    text = " ".join(
        [
            item.title.lower(),
            item.summary.lower(),
            item.url.lower(),
            item.extracted_text.lower(),
        ]
    )
    return any(term in text for term in BRIEFING_SCOPE_TERMS) or has_disease_reference_signal(text)


def item_has_disease_specific_signal(item: Item) -> bool:
    text = " ".join(
        [
            item.title.lower(),
            item.summary.lower(),
            item.url.lower(),
            item.extracted_text.lower(),
        ]
    )
    disease_terms = tuple(
        term
        for term in BRIEFING_SCOPE_TERMS
        if term
        not in {
            "epidemiology",
            "surveillance",
            "virology",
            "occupational exposure",
            "occupational health",
            "environmental exposure",
            "travel health",
            "health notice",
            "foodborne",
            "recall",
            "zoonotic",
            "spillover",
            "historical epidemiology",
            "history of medicine",
        }
    )
    return any(term in text for term in disease_terms) or has_disease_reference_signal(text)


def item_from_misclassified_travel_notice_feed(item: Item) -> bool:
    if item.source != "CDC Travel Health Notices":
        return False
    text = " ".join(
        [
            item.title.lower(),
            item.summary.lower(),
            item.url.lower(),
            item.extracted_text.lower(),
        ]
    )
    return any(pattern in text for pattern in MISCLASSIFIED_TRAVEL_NOTICE_PATTERNS)


def regionally_undercovered_signal(item: Item) -> bool:
    region = infer_region(item)
    if region not in {"Africa", "South Asia", "Southeast Asia", "East Asia", "Middle East", "Latin America and Caribbean"}:
        return False
    text = " ".join([item.title.lower(), item.summary.lower(), item.category.lower(), item.source.lower()])
    return any(
        term in text
        for term in (
            "outbreak",
            "cluster",
            "cholera",
            "dengue",
            "mpox",
            "marburg",
            "ebola",
            "anthrax",
            "lassa",
            "nipah",
            "chikungunya",
            "yellow fever",
            "zika",
            "malaria",
            "meningococcal",
            "diphtheria",
            "pertussis",
            "legionnaires",
            "rabies",
            "hepatitis a",
            "norovirus",
            "cyclospora",
            "cyclosporiasis",
            "campylobacter",
            "shigella",
            "vibrio",
            "yersinia",
            "botulism",
            "oropouche",
            "rift valley fever",
            "mers",
            "avian influenza",
            "h5n1",
            "measles",
            "polio",
            "tuberculosis",
        )
    )


def item_is_historical(item: Item) -> bool:
    joined = " ".join(
        [
            item.category.lower(),
            item.title.lower(),
            item.summary.lower(),
            item.source.lower(),
        ]
    )
    if (
        item.category != "Historical epidemiology / ancient disease / paleopathology"
        and has_disease_reference_signal(joined)
        and any(term in joined for term in OUTBREAK_ACTIVITY_TERMS)
    ):
        return False
    return any(term in joined for term in HISTORICAL_TERMS)


def dedupe_shortlist_by_url(items: list[Item]) -> list[Item]:
    unique: list[Item] = []
    seen_urls: set[str] = set()
    for item in items:
        if item.canonical_url in seen_urls:
            continue
        seen_urls.add(item.canonical_url)
        unique.append(item)
    return unique


def filter_by_date(items, target_date: date, window_days: int):
    start_date = target_date - timedelta(days=max(window_days - 1, 0))
    regional_start_date = target_date - timedelta(days=max(REGIONAL_MONITORING_WINDOW_DAYS - 1, 0))
    filtered = []
    for item in items:
        if not item.published_at:
            filtered.append(item)
            continue
        published_date = item.published_at.date()
        effective_start_date = regional_start_date if uses_regional_monitoring_window(item) else start_date
        if effective_start_date <= published_date <= target_date:
            filtered.append(item)
    return filtered


def uses_regional_monitoring_window(item: Item) -> bool:
    if item.metadata.get("source_outbreak_signal"):
        return True
    return item.source in {
        "Google News Africa Outbreaks",
        "Google News West Africa Outbreaks",
        "Google News East Africa Outbreaks",
        "Google News Central Africa Outbreaks",
        "Google News Southern Africa Outbreaks",
        "Google News South Asia Outbreaks",
        "Google News India Outbreaks",
        "Google News Southeast Asia Outbreaks",
        "Google News Latin America Outbreaks",
        "WHO Regional Office for Africa",
        "Africa CDC",
        "Nigeria Centre for Disease Control",
    }


def is_seen(item, db: SeenItemsDB) -> bool:
    if db.has_seen_url(item.canonical_url):
        return True
    return db.has_similar_title(item.title)


def filter_by_terms(items, search_terms: list[str]):
    if not search_terms:
        return items

    kept = []
    lowered_terms = [term.lower() for term in search_terms]
    specific_terms = [term for term in lowered_terms if term not in GENERIC_PRIORITY_TERMS]
    for item in items:
        haystack = item_content_haystack(item)
        if any(term in haystack for term in specific_terms):
            kept.append(item)
            continue
        if item_is_research_item(item) and item_matches_research_scope(item):
            kept.append(item)
            continue
        if item.official and any(
            term in haystack
            for term in (
                "outbreak",
                "surveillance",
                "travel health",
                "health notice",
                "epidemiological",
                "public health",
                "avian influenza",
                "hantavirus",
                "measles",
                "cholera",
                "dengue",
                "foodborne",
                "influenza",
                "mpox",
                "polio",
                "tuberculosis",
                "wastewater",
                "zoonotic",
            )
        ):
            if item_matches_briefing_scope(item):
                kept.append(item)
            continue
        if (
            item.official
            and item.source_type not in {"pubmed", "medrxiv", "biorxiv"}
            and any(term in haystack for term in lowered_terms)
            and item_matches_briefing_scope(item)
        ):
            kept.append(item)
    return kept


def item_content_haystack(item: Item) -> str:
    return " ".join(
        [
            item.title.lower(),
            item.summary.lower(),
            item.url.lower(),
            item.extracted_text.lower(),
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
