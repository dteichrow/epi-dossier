from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .database import SeenItemsDB
from .render_markdown import StoryUpdate, build_topic_groups, build_topic_synopsis, classify_topic
from .utils import (
    EditionConfig,
    EditorialConfig,
    DiseaseReference,
    Item,
    app_exports_dir,
    archive_relpath,
    atomic_write_json,
    format_timestamp,
    has_local_signal,
    infer_region,
    latest_filename,
    latest_html_filename,
    list_briefing_archives,
    load_atlas_visual_manifest,
    load_editions_config,
    load_editorial_config,
    load_pathogen_atlas,
    normalize_whitespace,
    reference_filename,
    reference_relpath,
    slugify,
    stable_id,
    story_filename,
    story_relpath,
)


ACTIVE_STORY_RETENTION_DAYS = 14
ACTIVE_STORY_MIN_ITEMS = 3
HIGH_SIGNAL_PUBLISHER_FAMILIES = {
    "Reuters",
    "Associated Press",
    "BBC",
    "Sky News",
    "New York Times",
    "Guardian",
    "NPR",
    "PBS",
    "CNN",
    "NBC News",
    "CBS News",
    "ABC News",
    "STAT",
    "CIDRAP",
}

ACADEMIC_SOURCE_TYPES = {"pubmed", "medrxiv", "biorxiv"}
RESEARCH_NEWS_CATEGORIES = {"Major epidemiology studies", "Virology and pathogen evolution"}
RESEARCH_REPORTING_TERMS = (
    "study",
    "studies",
    "paper",
    "preprint",
    "analysis",
    "analyses",
    "review",
    "cohort",
    "trial",
    "retrospective",
    "case series",
    "genomic",
    "genome",
    "phylogen",
    "seroepidemi",
    "neutralizing",
    "metagenom",
    "modeling",
    "model",
)

MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
DOI_URL_RE = re.compile(r"(^|//)doi\.org/|/10\.\d{4,9}/", re.IGNORECASE)


def source_failures_degrade(source_failures: list[dict[str, Any]]) -> bool:
    return any(bool(failure.get("required", True)) for failure in source_failures)


def is_doi_url(value: str) -> bool:
    return bool(DOI_URL_RE.search(value or ""))


def public_atlas_citations(record: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    public_citations: list[dict[str, Any]] = []
    withheld_citations: list[dict[str, Any]] = []
    for citation in record.get("citations", []):
        citation_copy = dict(citation)
        if is_doi_url(str(citation_copy.get("url", ""))) and not citation_copy.get("verified"):
            withheld_citations.append(
                {
                    "id": citation_copy.get("id", ""),
                    "short_citation": citation_copy.get("short_citation", ""),
                    "reason": "DOI link withheld pending manual verification",
                }
            )
            continue
        public_citations.append(citation_copy)
    return public_citations, withheld_citations


def export_app_data(
    db: SeenItemsDB,
    items: list[Item],
    story_updates: list[StoryUpdate],
    story_snapshots: dict[str, dict],
    outbreak_reference: list[DiseaseReference],
    target_date: date,
    generated_at: datetime,
    search_window: str,
    source_failures: list[dict[str, Any]],
    source_health: list[dict[str, Any]],
) -> dict[str, Any]:
    run_id = stable_id("run", target_date.isoformat(), generated_at.isoformat(timespec="seconds"))
    exported_at = generated_at.isoformat(timespec="seconds")
    previous_run = db.load_latest_app_run() or {}
    previous_items = db.load_app_feed_items()
    previous_stories = db.load_app_stories()
    previous_topics = db.load_app_topics()
    editorial = load_editorial_config()
    editions = load_editions_config()

    item_records = build_item_records(items, exported_at)
    topic_groups = build_topic_groups(items)
    topic_records = build_topic_records(topic_groups)
    story_records = build_story_records(story_updates, story_snapshots, topic_groups, previous_stories, db, run_id, exported_at, editorial)
    reference_records = build_outbreak_reference_records(outbreak_reference, editorial)
    enrich_story_reference_links(story_records, reference_records)
    atlas_records = build_atlas_records(load_pathogen_atlas(), story_records, reference_records, load_atlas_visual_manifest())
    annotate_story_status_on_items(item_records, story_records)
    annotate_edition_membership(item_records, story_records, reference_records, editions)

    changed_item_ids = persist_items(db, item_records, previous_items, exported_at)
    changed_topic_ids = persist_topics(db, topic_records, previous_topics, exported_at)
    changed_story_ids = persist_stories(db, story_records, previous_stories, exported_at)

    latest_snapshot = {
        "run_id": run_id,
        "target_date": target_date.isoformat(),
        "generated_at": exported_at,
        "search_window": search_window,
        "degraded": source_failures_degrade(source_failures),
        "source_failures": source_failures,
        "source_health": source_health,
        "freshness_summary": build_freshness_summary(item_records),
        "item_count": len(item_records),
        "story_count": len(story_records),
        "topic_count": len(topic_records),
        "high_priority_item_ids": [item["item_id"] for item in item_records if item["relevance_score"] >= 4][:10],
        "items": item_records,
        "stories": story_records,
        "topics": topic_records,
        "reference": reference_records,
        "atlas": atlas_records,
    }
    latest_snapshot["editor_summary"] = build_editor_summary(latest_snapshot)

    delta_snapshot = {
        "run_id": run_id,
        "generated_at": exported_at,
        "since_run_id": previous_run.get("run_id"),
        "changed_item_ids": changed_item_ids,
        "changed_story_ids": changed_story_ids,
        "changed_topic_ids": changed_topic_ids,
        "items": [item for item in item_records if item["item_id"] in set(changed_item_ids)],
        "stories": [story for story in story_records if story["story_id"] in set(changed_story_ids)],
        "topics": [topic for topic in topic_records if topic["topic_id"] in set(changed_topic_ids)],
    }

    run_record = {
        "run_id": run_id,
        "target_date": target_date.isoformat(),
        "generated_at": exported_at,
        "search_window": search_window,
        "item_count": len(item_records),
        "story_count": len(story_records),
        "topic_count": len(topic_records),
        "degraded": source_failures_degrade(source_failures),
        "source_failures": source_failures,
        "source_health": source_health,
        "snapshot_path": str(app_exports_dir() / "latest.json"),
    }
    db.save_app_run(run_record)
    write_export_files(latest_snapshot, delta_snapshot)
    return latest_snapshot


def clean_story_delta_text(text: str) -> str:
    cleaned = MARKDOWN_LINK_RE.sub(r"\1", str(text or ""))
    return normalize_whitespace(cleaned)


def json_safe_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe_value(item) for item in value]
    return value


def build_item_records(items: list[Item], exported_at: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda entry: (entry.relevance_score, format_timestamp(entry.published_at)), reverse=True):
        topic_name = classify_topic(item)
        topic_id = stable_id("topic", topic_name)
        story_id = stable_id("story", topic_name) if topic_name != "Miscellaneous signals" else None
        item_id = stable_id("item", item.canonical_url)
        item_evidence_type = infer_item_evidence_type(item)
        item_is_public_official = is_public_official_item(item)
        records.append(
            {
                "item_id": item_id,
                "title": item.title,
                "summary": item.summary,
                "why_it_matters": item.why_it_matters,
                "caveats": item.caveats,
                "source": item.source,
                "publisher": item.publisher,
                "publisher_name": item.publisher_name,
                "publisher_tier": item.publisher_tier,
                "publisher_access": item.publisher_access,
                "display_source": item.display_source,
                "source_type": item.source_type,
                "source_url": item.url,
                "preferred_url": item.preferred_url,
                "raw_url": item.raw_url,
                "resolved_url": item.resolved_url,
                "canonical_url": item.canonical_url,
                "aggregator_source": item.aggregator_source,
                "link_quality": item.link_quality,
                "preferred_url_kind": item.preferred_url_kind,
                "source_confidence": infer_item_source_confidence(item),
                "evidence_type": item_evidence_type,
                "freshness_state": str(item.metadata.get("source_freshness", "live")),
                "source_cached_at": item.metadata.get("source_cached_at"),
                "source_cache_age_hours": item.metadata.get("source_cache_age_hours"),
                "published_at": format_timestamp(item.published_at),
                "category": item.category,
                "region": infer_region(item),
                "country": infer_country(item),
                "local_signal": has_local_signal(item),
                "topic_name": topic_name,
                "topic_id": topic_id,
                "story_id": story_id,
                "story_status": "",
                "relevance_score": item.relevance_score,
                "official": item_is_public_official,
                "doi": item.doi,
                "journal": item.journal,
                "abstract_url": item.abstract_url,
                "updated_at": exported_at,
                "low_detail": item.summary.lower().startswith("limited detail") or item.summary.lower().startswith("limited usable detail"),
                "content_class": classify_item_content_class(item),
                "editions": [],
            }
        )
    return records


def build_freshness_summary(item_records: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"live": 0, "refresh_cache": 0, "fallback_cache": 0, "retained": 0, "unknown": 0}
    for item in item_records:
        state = str(item.get("freshness_state") or "unknown")
        if state not in summary:
            summary[state] = 0
        summary[state] += 1
    return summary


def summarize_story_freshness(items: list[Item]) -> dict[str, int]:
    summary = {"live": 0, "refresh_cache": 0, "fallback_cache": 0, "retained": 0, "unknown": 0}
    for item in items:
        state = str(item.metadata.get("source_freshness", "unknown"))
        if state not in summary:
            summary[state] = 0
        summary[state] += 1
    return summary


def summarize_story_source_kinds(items: list[Item]) -> dict[str, int]:
    summary = {"official": 0, "wire": 0, "major_newsroom": 0, "specialist_health": 0, "general_outlet": 0, "aggregator_only": 0, "metadata_only_signal": 0}
    for item in items:
        confidence = item.source_confidence
        if confidence == "official_agency":
            summary["official"] += 1
        elif confidence in summary:
            summary[confidence] += 1
        elif confidence == "aggregator_only":
            summary["aggregator_only"] += 1
    return summary


def summarize_story_source_confidence(items: list[Item]) -> dict[str, int]:
    summary = {
        "official_agency": 0,
        "wire": 0,
        "major_newsroom": 0,
        "specialist_health": 0,
        "general_outlet": 0,
        "aggregator_only": 0,
        "metadata_only_signal": 0,
    }
    for item in items:
        confidence = item.source_confidence
        if confidence not in summary:
            summary[confidence] = 0
        summary[confidence] += 1
    return summary


def build_outbreak_reference_records(entries: list[DiseaseReference], editorial: EditorialConfig | None = None) -> list[dict[str, Any]]:
    spotlight = set((editorial or EditorialConfig()).spotlight_reference_names)
    records = [
        {
            "name": entry.name,
            "reference_url": reference_filename(entry.name).resolve().as_uri(),
            "reference_web_path": reference_relpath(entry.name).as_posix(),
            "pathogen": entry.pathogen,
            "transmission": entry.transmission,
            "categories": entry.categories,
            "aliases": entry.aliases,
            "latest_outbreak": {
                "label": entry.latest_outbreak.label,
                "period": entry.latest_outbreak.period,
                "location": entry.latest_outbreak.location,
                "summary": entry.latest_outbreak.summary,
                "source_name": entry.latest_outbreak.source_name,
                "source_url": entry.latest_outbreak.source_url,
                "as_of": entry.latest_outbreak.as_of,
            },
            "field_guide_links": [{"label": link.label, "url": link.url} for link in entry.field_guide_links],
            "reservoir_or_vector": entry.reservoir_or_vector,
            "incubation": entry.incubation,
            "symptoms": entry.symptoms,
            "severity": entry.severity,
            "diagnostics": entry.diagnostics,
            "treatment": entry.treatment,
            "prevention": entry.prevention,
            "outbreak_settings": entry.outbreak_settings,
            "vaccine_status": entry.vaccine_status,
            "research_caveats": entry.research_caveats,
            "why_reporters_care": entry.why_reporters_care,
            "what_reporters_get_wrong": entry.what_reporters_get_wrong,
            "metrics_that_matter": entry.metrics_that_matter,
            "notable_outbreaks": entry.notable_outbreaks,
            "surveillance_note": entry.surveillance_note,
            "spotlight": entry.name in spotlight,
            "evidence_type": "reference",
        }
        for entry in entries
    ]
    records.sort(key=lambda record: (not record.get("spotlight"), record["name"]))
    return records


def enrich_story_reference_links(story_records: list[dict[str, Any]], reference_records: list[dict[str, Any]]) -> None:
    if not story_records or not reference_records:
        return

    for story in story_records:
        story_text = " ".join(
            [
                story.get("display_title", ""),
                story.get("lead_title", ""),
                story.get("latest_update_summary", ""),
                " ".join(story.get("latest_update_bullets", [])),
            ]
        )
        matches = [reference for reference in reference_records if story_matches_reference(story_text, reference)]
        story["related_reference_names"] = [reference["name"] for reference in matches]
        story["related_reference_urls"] = [reference["reference_url"] for reference in matches]
        story["related_references"] = [
            {
                "name": reference["name"],
                "reference_url": reference["reference_url"],
                "reference_web_path": reference.get("reference_web_path", ""),
                "pathogen": reference.get("pathogen", ""),
                "transmission": reference.get("transmission", ""),
                "latest_outbreak": reference.get("latest_outbreak", {}),
                "outbreak_settings": reference.get("outbreak_settings", []),
                "vaccine_status": reference.get("vaccine_status", ""),
                "treatment": reference.get("treatment", ""),
                "surveillance_note": reference.get("surveillance_note", ""),
                "research_caveats": reference.get("research_caveats", ""),
                "metrics_that_matter": reference.get("metrics_that_matter", []),
            }
            for reference in matches
        ]

    for reference in reference_records:
        related_stories = [
            {
                "story_id": story["story_id"],
                "display_title": story["display_title"],
                "story_url": story["story_url"],
                "story_web_path": story.get("story_web_path", ""),
                "latest_update_summary": story.get("latest_update_summary", ""),
            }
            for story in story_records
            if reference["name"] in story.get("related_reference_names", [])
        ]
        reference["related_story_ids"] = [story["story_id"] for story in related_stories]
        reference["related_story_urls"] = [story["story_url"] for story in related_stories]
        reference["related_stories"] = related_stories


def build_atlas_records(
    atlas_entries: tuple[dict[str, Any], ...],
    story_records: list[dict[str, Any]],
    reference_records: list[dict[str, Any]],
    visual_assets: tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    if not atlas_entries:
        return []

    story_by_id = {story["story_id"]: story for story in story_records}
    reference_by_slug = {slugify(reference["name"]): reference for reference in reference_records}
    asset_by_id = {str(asset.get("asset_id")): dict(asset) for asset in visual_assets}
    atlas_records: list[dict[str, Any]] = []

    def decorate_record(
        raw_record: dict[str, Any],
        *,
        atlas_slug: str,
        attach_reference: bool,
    ) -> dict[str, Any]:
        record = json_safe_value(dict(raw_record))
        reference = reference_by_slug.get(record.get("linked_reference_slug", ""))
        linked_stories = [
            {
                "story_id": story["story_id"],
                "display_title": story["display_title"],
                "story_url": story["story_url"],
                "story_web_path": story.get("story_web_path", ""),
                "latest_update_summary": story.get("latest_update_summary", ""),
                "current_status_summary": story.get("current_status_summary", ""),
            }
            for story_id in record.get("linked_story_ids", [])
            for story in [story_by_id.get(story_id)]
            if story
        ]
        if not linked_stories and reference:
            linked_stories = list(reference.get("related_stories", []))
        blog_posts = json_safe_value(record.get("linked_blog_posts", []))
        writing_state = (
            "direct"
            if any(post.get("relation") == "deep_dive" for post in blog_posts)
            else "adjacent"
            if blog_posts
            else "not_yet_written"
        )
        record["writing_state"] = writing_state
        variant_suffix = ""
        if record.get("slug") and record.get("slug") != atlas_slug:
            variant_suffix = f"&variant={record['slug']}"
        record["atlas_url"] = f"atlas.html?pathogen={atlas_slug}{variant_suffix}"
        record["reference_name"] = reference.get("name", "") if reference else ""
        record["reference_url"] = reference.get("reference_url", "") if reference else ""
        record["reference_web_path"] = reference.get("reference_web_path", "") if reference else ""
        record["related_stories"] = linked_stories
        record["story_count"] = len(linked_stories)
        public_citations, withheld_citations = public_atlas_citations(record)
        record["citations"] = public_citations
        record["citation_count"] = len(public_citations)
        if withheld_citations:
            record["withheld_citations"] = withheld_citations
            record["citation_verification_note"] = "Some DOI citations are withheld from public exports until manually verified."
        record["route_count"] = len(record.get("spread_routes", []))
        record["visual_asset"] = asset_by_id.get(str(record.get("visual_asset_id", "")), {})
        if attach_reference and reference is not None:
            reference["atlas_entry_slug"] = atlas_slug
            reference["atlas_url"] = f"atlas.html?pathogen={atlas_slug}"
            reference["atlas_status"] = record.get("status", "mixed")
            reference["atlas_summary"] = raw_record.get("summary", "")
        return record

    for entry in atlas_entries:
        record = decorate_record(entry, atlas_slug=entry["slug"], attach_reference=True)
        variants = [
            decorate_record(variant, atlas_slug=entry["slug"], attach_reference=False)
            for variant in entry.get("variants", [])
        ]
        record["variants"] = variants
        record["variant_count"] = len(variants)
        atlas_records.append(record)

    return atlas_records


def story_matches_reference(story_text: str, reference: dict[str, Any]) -> bool:
    haystack = normalize_text_for_match(story_text)
    return any(match_term_in_text(term, haystack) for term in reference_match_terms(reference))


def reference_match_terms(reference: dict[str, Any]) -> list[str]:
    raw_terms = [
        reference.get("name", ""),
        reference.get("pathogen", ""),
        *reference.get("aliases", []),
    ]
    terms: list[str] = []
    for value in raw_terms:
        normalized = normalize_text_for_match(value)
        if not normalized:
            continue
        terms.append(normalized)
        head = normalized.split(",")[0].strip()
        if head and head not in terms:
            terms.append(head)
        for chunk in re.findall(r"\(([^)]+)\)", value):
            alias = normalize_text_for_match(chunk)
            if alias and alias not in terms:
                terms.append(alias)
    return sorted({term for term in terms if len(term) >= 3}, key=len, reverse=True)


def match_term_in_text(term: str, haystack: str) -> bool:
    return re.search(r"\b" + re.escape(term) + r"\b", haystack) is not None


def normalize_text_for_match(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", (text or "").lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def build_topic_records(topic_groups: list[tuple[str, list[Item]]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for topic_name, topic_items in topic_groups:
        topic_id = stable_id("topic", topic_name)
        records.append(
            {
                "topic_id": topic_id,
                "topic_name": topic_name,
                "display_title": topic_name,
                "summary": build_topic_synopsis(topic_name, topic_items),
                "item_count": len(topic_items),
                "source_count": len({item.display_source for item in topic_items}),
                "story_id": stable_id("story", topic_name) if topic_name != "Miscellaneous signals" else None,
                "item_ids": [stable_id("item", item.canonical_url) for item in topic_items[:10]],
            }
        )
    return records


def build_story_records(
    story_updates: list[StoryUpdate],
    story_snapshots: dict[str, dict],
    topic_groups: list[tuple[str, list[Item]]],
    previous_stories: dict[str, dict],
    db: SeenItemsDB,
    run_id: str,
    exported_at: str,
    editorial: EditorialConfig,
) -> list[dict[str, Any]]:
    groups_by_name = {topic_name: topic_items for topic_name, topic_items in topic_groups}
    records: list[dict[str, Any]] = []
    updates_by_topic = {update.topic_name: update for update in story_updates}
    for topic_name, snapshot in story_snapshots.items():
        canonical_topic_name = editorial.story_aliases.get(topic_name, topic_name)
        story_id = stable_id("story", canonical_topic_name)
        update = updates_by_topic.get(topic_name)
        latest_update_bullets = [clean_story_delta_text(bullet) for bullet in update.bullets] if update else []
        latest_update_summary = latest_update_bullets[0] if latest_update_bullets else "No new story delta in this run."
        previous_story = previous_stories.get(story_id, {})
        previous_story_summary = clean_story_delta_text(previous_story.get("latest_update_summary", latest_update_summary))
        previous_story_bullets = [clean_story_delta_text(bullet) for bullet in previous_story.get("latest_update_bullets", [])]
        if update:
            timeline_entry = {
                "update_id": stable_id("story_update", story_id, run_id),
                "story_id": story_id,
                "run_id": run_id,
                "generated_at": exported_at,
                "topic_name": canonical_topic_name,
                "bullets": latest_update_bullets,
                "is_new_story": bool(update.is_new_story),
                "item_count": snapshot["cluster_size"],
                "source_count": len(snapshot["source_names"]),
            }
            db.append_story_update(timeline_entry["update_id"], story_id, run_id, timeline_entry, exported_at)
        existing_timeline = db.load_story_updates_for_story(story_id)
        story_items = groups_by_name.get(topic_name, [])
        claim_types = detect_story_claim_types(story_items, latest_update_bullets)
        story_status = determine_story_status(story_items, update, previous_story)
        records.append(
            {
                "story_id": story_id,
                "topic_name": canonical_topic_name,
                "display_title": canonical_topic_name,
                "story_url": story_filename(story_id, canonical_topic_name).resolve().as_uri(),
                "story_web_path": story_relpath(story_id, canonical_topic_name).as_posix(),
                "status": story_status,
                "lead_title": snapshot["lead_title"],
                "lead_url": snapshot["lead_url"],
                "lead_source": snapshot["lead_source"],
                "latest_timestamp": snapshot["latest_timestamp"],
                "latest_update_summary": latest_update_summary if update else previous_story_summary,
                "latest_update_bullets": latest_update_bullets if update else previous_story_bullets,
                "new_since_last_refresh": bool(update and update.bullets),
                "source_count": len(snapshot["source_names"]),
                "item_count": snapshot["cluster_size"],
                "source_names": snapshot["source_names"],
                "publisher_names": sorted({item.publisher_name for item in story_items}),
                "flags": snapshot["flags"],
                "topic_id": stable_id("topic", canonical_topic_name),
                "item_ids": [stable_id("item", item.canonical_url) for item in story_items[:15]],
                "official_item_ids": [stable_id("item", item.canonical_url) for item in story_items if item.official],
                "press_item_ids": [stable_id("item", item.canonical_url) for item in story_items if not item.official],
                "freshness_counts": summarize_story_freshness(story_items),
                "source_kind_counts": summarize_story_source_kinds(story_items),
                "source_confidence_counts": summarize_story_source_confidence(story_items),
                "claim_types": claim_types,
                "what_happened": snapshot["lead_title"],
                "why_it_matters": infer_story_why_it_matters(story_items),
                "current_status_summary": humanize_story_status(story_status),
                "primary_region": infer_story_primary_region(story_items),
                "country": infer_story_primary_country(story_items),
                "evidence_type": infer_story_evidence_type(story_items),
                "publisher_family_count": count_high_signal_publishers(story_items),
                "first_seen_at": existing_timeline[0]["generated_at"] if existing_timeline else exported_at,
                "latest_updated_at": exported_at if update else previous_story.get("latest_updated_at", exported_at),
                "timeline": existing_timeline,
                "updated_at": exported_at if update else previous_story.get("updated_at", exported_at),
                "content_class": "tracked_outbreak_file",
                "editions": [],
            }
        )
    records = merge_retained_previous_stories(records, previous_stories, exported_at, editorial)
    suppressed_ids = set(editorial.suppressed_story_ids)
    records = [record for record in records if record["story_id"] not in suppressed_ids]
    pinned_titles = set(editorial.pinned_story_topics)
    records.sort(
        key=lambda record: (
            record.get("display_title") not in pinned_titles,
            not record["new_since_last_refresh"],
            story_status_rank(record.get("status", "active")),
            -record["item_count"],
            record["latest_timestamp"],
        )
    )
    return records


def merge_retained_previous_stories(
    current_records: list[dict[str, Any]],
    previous_stories: dict[str, dict],
    exported_at: str,
    editorial: EditorialConfig,
) -> list[dict[str, Any]]:
    merged = list(current_records)
    current_ids = {record["story_id"] for record in current_records}
    now = datetime.fromisoformat(exported_at)
    for story_id, previous in previous_stories.items():
        if story_id in current_ids:
            continue
        if not previous_story_should_be_retained(previous, now, editorial):
            continue
        retained = dict(previous)
        topic_name = retained.get("topic_name") or retained.get("display_title") or "Tracked story"
        retained["topic_name"] = topic_name
        retained["display_title"] = retained.get("display_title", topic_name)
        retained["story_id"] = retained.get("story_id", story_id)
        retained["story_url"] = retained.get("story_url", story_filename(retained["story_id"], topic_name).resolve().as_uri())
        retained["story_web_path"] = retained.get("story_web_path", story_relpath(retained["story_id"], topic_name).as_posix())
        retained["topic_id"] = retained.get("topic_id", stable_id("topic", topic_name))
        retained["item_ids"] = list(retained.get("item_ids", []))
        retained["official_item_ids"] = list(retained.get("official_item_ids", []))
        retained["press_item_ids"] = list(retained.get("press_item_ids", []))
        retained["publisher_names"] = list(retained.get("publisher_names", []))
        retained["source_names"] = list(retained.get("source_names", []))
        retained["related_reference_names"] = list(retained.get("related_reference_names", []))
        retained["related_reference_urls"] = list(retained.get("related_reference_urls", []))
        retained["related_references"] = list(retained.get("related_references", []))
        retained["timeline"] = list(retained.get("timeline", []))
        retained["status"] = "quiet_retained"
        retained["new_since_last_refresh"] = False
        retained["updated_at"] = previous.get("updated_at", exported_at)
        retained["latest_updated_at"] = previous.get("latest_updated_at", retained["updated_at"])
        bullets = list(previous.get("latest_update_bullets", []))
        if not bullets:
            bullets = ["No new story delta was captured in this run, but this outbreak file remains actively tracked."]
        retained["latest_update_bullets"] = bullets
        retained["latest_update_summary"] = previous.get(
            "latest_update_summary",
            "No new story delta was captured in this run, but this outbreak file remains actively tracked.",
        )
        retained["editions"] = list(retained.get("editions", []))
        merged.append(retained)
    return merged


def previous_story_should_be_retained(previous: dict[str, Any], now: datetime, editorial: EditorialConfig) -> bool:
    if previous.get("status") not in {None, "", "active", "retained", "quiet_retained", "expanding_coverage", "active_investigation", "official_follow_up_only", "archival_watch"}:
        return False
    if int(previous.get("item_count", 0) or 0) < ACTIVE_STORY_MIN_ITEMS:
        return False
    updated_at = previous.get("latest_updated_at") or previous.get("updated_at")
    if not updated_at:
        return False
    try:
        updated_dt = datetime.fromisoformat(updated_at)
    except ValueError:
        return False
    retention_days = ACTIVE_STORY_RETENTION_DAYS
    story_name = previous.get("display_title") or previous.get("topic_name")
    if story_name and story_name in editorial.forced_story_retention_days:
        retention_days = int(editorial.forced_story_retention_days[story_name])
    return updated_dt >= (now - timedelta(days=retention_days))


def story_status_rank(status: str) -> int:
    return {
        "expanding_coverage": 0,
        "active_investigation": 1,
        "official_follow_up_only": 2,
        "quiet_retained": 3,
        "archival_watch": 4,
    }.get(status, 5)


def humanize_story_status(status: str) -> str:
    return {
        "expanding_coverage": "Expanding coverage",
        "active_investigation": "Active investigation",
        "official_follow_up_only": "Official follow-up only",
        "quiet_retained": "Quiet but retained",
        "archival_watch": "Archival watch",
    }.get(status, status.replace("_", " ").title())


def determine_story_status(items: list[Item], update: StoryUpdate | None, previous_story: dict[str, Any]) -> str:
    if not items:
        return previous_story.get("status", "quiet_retained")
    has_press = any(not item.official for item in items)
    has_official = any(item.official for item in items)
    if update and len({item.publisher_name for item in items if not item.official}) >= 3:
        return "expanding_coverage"
    if has_official and not has_press:
        return "official_follow_up_only"
    if update:
        return "active_investigation"
    return previous_story.get("status", "quiet_retained")


def detect_story_claim_types(items: list[Item], bullets: list[str]) -> list[str]:
    text = " ".join([item.title for item in items] + [item.summary for item in items] + bullets).lower()
    rules = {
        "new_official_source": ("official", "agency", "cdc", "who", "ecdc"),
        "suspected_case": ("suspected case", "suspected cases", "possible case", "probable case", "under investigation"),
        "confirmed_case": ("confirmed case", "confirmed cases", "confirmed infection", "laboratory confirmed", "tested positive", "confirmed"),
        "severity_or_death": ("death", "deaths", "fatal", "case fatality", "critical", "hospitalized", "hospitalised", "died"),
        "transmission_change": ("person-to-person", "human-to-human", "transmission"),
        "policy_or_travel": ("evacuation", "quarantine", "travel", "restriction", "advisory", "screening", "border", "entry restriction"),
        "new_geography": ("imported case", "cross-border", "new health zone", "new province", "new country", "reported in", "identified in"),
        "healthcare_transmission": ("health worker", "healthcare worker", "health-care worker", "nosocomial", "hospital-associated", "infection prevention"),
        "laboratory_or_genomic": ("laboratory", "pcr", "sequencing", "genomic", "sample", "samples tested"),
        "medical_countermeasure_gap": ("no vaccine", "no licensed vaccine", "no approved", "no specific therapeutics", "supportive care"),
    }
    return [label for label, needles in rules.items() if any(needle in text for needle in needles)]


def infer_story_why_it_matters(items: list[Item]) -> str:
    if not items:
        return "This file remains useful because the outbreak is still being tracked."
    official_count = sum(1 for item in items if item.official)
    publisher_count = len({item.publisher_name for item in items if not item.official})
    if official_count and publisher_count:
        return f"This story has both official follow-up and broad publisher corroboration across {publisher_count} newsroom source(s)."
    if official_count:
        return "This file matters because official outbreak tracking remains active even if publisher coverage is thin."
    return "This file matters because newsroom follow-up suggests the story is still moving even without a fresh official update."


def infer_story_primary_region(items: list[Item]) -> str:
    if not items:
        return ""
    counts: dict[str, int] = {}
    for item in items:
        region = infer_region(item)
        counts[region] = counts.get(region, 0) + 1
    return max(counts.items(), key=lambda pair: pair[1])[0]


def infer_country(item: Item) -> str:
    text = " ".join([item.title.lower(), item.summary.lower(), item.url.lower()])
    country_map = {
        "Democratic Republic of the Congo": ("democratic republic of the congo", "drc", "dr congo", "congo", "ituri", "north kivu", "bunia", "kinshasa"),
        "Uganda": ("uganda", "kampala"),
        "South Sudan": ("south sudan",),
        "Rwanda": ("rwanda",),
        "Sierra Leone": ("sierra leone",),
        "Liberia": ("liberia",),
        "Guinea": ("guinea",),
        "Nigeria": ("nigeria",),
        "Kenya": ("kenya",),
        "Tanzania": ("tanzania",),
        "Ethiopia": ("ethiopia",),
        "Ghana": ("ghana",),
        "United Kingdom": ("united kingdom", "uk", "britain", "british"),
        "Spain": ("spain", "canary islands", "tenerife"),
        "Cape Verde": ("cape verde",),
        "United States": ("united states", "u.s.", "usa", "california", "new york", "texas"),
        "Canada": ("canada",),
        "India": ("india",),
        "Brazil": ("brazil",),
    }
    matches: list[str] = []
    for country, terms in country_map.items():
        if any(term in text for term in terms):
            matches.append(country)
    if len(matches) > 1:
        return " / ".join(matches[:2])
    if matches:
        return matches[0]
    return ""


def infer_story_primary_country(items: list[Item]) -> str:
    counts: dict[str, int] = {}
    for item in items:
        country = infer_country(item)
        if country:
            counts[country] = counts.get(country, 0) + 1
    return max(counts.items(), key=lambda pair: pair[1])[0] if counts else ""


def infer_story_evidence_type(items: list[Item]) -> str:
    evidence_types = {infer_item_evidence_type(item) for item in items}
    if "official_update" in evidence_types and "news_report" in evidence_types:
        return "mixed_reporting"
    if "journal_article" in evidence_types or "preprint" in evidence_types:
        return "research_linked"
    return next(iter(evidence_types), "news_report")


def infer_item_evidence_type(item: Item) -> str:
    if item.source_type == "pubmed":
        return "journal_article"
    if item.source_type in {"medrxiv", "biorxiv"}:
        return "preprint"
    if item.category in RESEARCH_NEWS_CATEGORIES and item_is_research_linked_reporting(item):
        return "research_linked"
    return item.evidence_type


def infer_item_source_confidence(item: Item) -> str:
    if item.source_type in ACADEMIC_SOURCE_TYPES:
        return "specialist_health"
    return item.source_confidence


def is_public_official_item(item: Item) -> bool:
    return bool(item.official and item.source_type not in ACADEMIC_SOURCE_TYPES)


def item_is_research_linked_reporting(item: Item) -> bool:
    if item.source_type in ACADEMIC_SOURCE_TYPES:
        return False
    text = normalize_text_for_match(
        " ".join(
            [
                item.title,
                item.summary,
                item.category,
                item.source,
                item.publisher_name,
                item.journal or "",
            ]
        )
    )
    return any(term in text for term in RESEARCH_REPORTING_TERMS)


def classify_item_content_class(item: Item) -> str:
    summary = item.summary.lower()
    title = item.title.lower()
    text = " ".join([title, summary, item.category.lower(), item.source.lower(), (item.publisher_name or "").lower()])
    if item.link_quality == "metadata_only":
        return "metadata_only_signal"
    if infer_item_evidence_type(item) in {"journal_article", "preprint", "research_linked"} or item.category in RESEARCH_NEWS_CATEGORIES:
        return "research_context"
    if any(term in text for term in ("workforce", "health system", "healthcare system", "burden", "what to know", "fact check", "explainer")):
        return "background_system_policy"
    if item.official:
        return "official_update"
    return "live_outbreak_development"


def count_high_signal_publishers(items: list[Item]) -> int:
    return len({item.publisher_name for item in items if item.publisher_name in HIGH_SIGNAL_PUBLISHER_FAMILIES})


def annotate_story_status_on_items(item_records: list[dict[str, Any]], story_records: list[dict[str, Any]]) -> None:
    status_by_story = {story["story_id"]: story.get("status", "") for story in story_records}
    for item in item_records:
        story_id = item.get("story_id")
        if story_id:
            item["story_status"] = status_by_story.get(story_id, "")


def annotate_edition_membership(
    item_records: list[dict[str, Any]],
    story_records: list[dict[str, Any]],
    reference_records: list[dict[str, Any]],
    editions: list[EditionConfig],
) -> None:
    if not editions:
        return
    for item in item_records:
        item["editions"] = [edition.key for edition in editions if record_matches_edition(item, edition)]
    for story in story_records:
        story["editions"] = [edition.key for edition in editions if record_matches_edition(story, edition, story_record=True)]
    for reference in reference_records:
        reference["editions"] = [
            edition.key
            for edition in editions
            if edition.key in {"research", "index"} or any(
                category.lower() in {"reference", "research"}
                for category in reference.get("categories", [])
            )
        ]


def record_matches_edition(record: dict[str, Any], edition: EditionConfig, *, story_record: bool = False) -> bool:
    if edition.official_only and not record.get("official") and not story_record:
        return False
    if edition.story_statuses:
        record_status = record.get("status" if story_record else "story_status", "")
        if record_status and record_status not in edition.story_statuses:
            return False
    if edition.regions and record.get("primary_region" if story_record else "region") not in edition.regions:
        return False
    if edition.countries and record.get("country", "") not in edition.countries:
        return False
    if edition.evidence_types and record.get("evidence_type", "") not in edition.evidence_types:
        return False
    if edition.source_confidence:
        if story_record:
            counts = record.get("source_confidence_counts", {})
            if not any(counts.get(confidence, 0) for confidence in edition.source_confidence):
                return False
        elif record.get("source_confidence", "") not in edition.source_confidence:
            return False
    if edition.publisher_families:
        if story_record:
            publisher_names = set(record.get("publisher_names", []))
            if not publisher_names.intersection(edition.publisher_families):
                return False
        elif record.get("publisher_name", "") not in edition.publisher_families:
            return False
    if edition.sources:
        if story_record:
            source_names = set(record.get("source_names", []))
            if not source_names.intersection(edition.sources):
                return False
        elif record.get("source", "") not in edition.sources:
            return False
    if edition.categories:
        record_categories = record.get("categories", []) if story_record else [record.get("category", "")]
        if not set(record_categories).intersection(edition.categories):
            return False
    haystack = normalize_text_for_match(
        " ".join(
            [
                record.get("display_title", "") if story_record else record.get("title", ""),
                record.get("latest_update_summary", "") if story_record else record.get("summary", ""),
                record.get("what_happened", "") if story_record else record.get("why_it_matters", ""),
                record.get("country", ""),
                record.get("primary_region", "") if story_record else record.get("region", ""),
                " ".join(record.get("source_names", [])) if story_record else record.get("source", ""),
                " ".join(record.get("publisher_names", [])) if story_record else record.get("publisher_name", ""),
                record.get("category", ""),
                record.get("evidence_type", ""),
                record.get("source_confidence", ""),
                " ".join(record.get("claim_types", [])) if story_record else "",
                record.get("content_class", ""),
            ]
        )
    )
    if edition.include_terms and not any(match_term_in_text(normalize_text_for_match(term), haystack) for term in edition.include_terms):
        return False
    if edition.exclude_terms and any(match_term_in_text(normalize_text_for_match(term), haystack) for term in edition.exclude_terms):
        return False
    return True


def persist_items(db: SeenItemsDB, records: list[dict[str, Any]], previous_items: dict[str, dict], exported_at: str) -> list[str]:
    changed: list[str] = []
    for record in records:
        item_id = record["item_id"]
        previous = previous_items.get(item_id)
        previous_updated_at = previous.get("updated_at") if previous else exported_at
        fingerprint = content_hash(record, ignore_keys={"updated_at"})
        previous_hash = content_hash(previous, ignore_keys={"updated_at"}) if previous else None
        if previous_hash == fingerprint:
            record["updated_at"] = previous_updated_at
        else:
            changed.append(item_id)
        db.upsert_app_feed_item(item_id, record["canonical_url"], record, fingerprint, exported_at)
    return changed


def persist_topics(db: SeenItemsDB, records: list[dict[str, Any]], previous_topics: dict[str, dict], exported_at: str) -> list[str]:
    changed: list[str] = []
    for record in records:
        topic_id = record["topic_id"]
        previous = previous_topics.get(topic_id)
        previous_updated_at = previous.get("updated_at") if previous else exported_at
        fingerprint = content_hash(record, ignore_keys={"updated_at"})
        previous_hash = content_hash(previous, ignore_keys={"updated_at"}) if previous else None
        if previous_hash == fingerprint:
            record["updated_at"] = previous_updated_at
        else:
            record["updated_at"] = exported_at
            changed.append(topic_id)
        db.upsert_app_topic(topic_id, record["topic_name"], record, fingerprint, record["updated_at"])
    return changed


def persist_stories(db: SeenItemsDB, records: list[dict[str, Any]], previous_stories: dict[str, dict], exported_at: str) -> list[str]:
    changed: list[str] = []
    for record in records:
        story_id = record["story_id"]
        previous = previous_stories.get(story_id)
        previous_updated_at = previous.get("updated_at") if previous else exported_at
        fingerprint = content_hash(record, ignore_keys={"updated_at", "timeline"})
        previous_hash = content_hash(previous, ignore_keys={"updated_at", "timeline"}) if previous else None
        if previous_hash == fingerprint:
            record["updated_at"] = previous_updated_at
        else:
            record["updated_at"] = exported_at
            changed.append(story_id)
        db.upsert_app_story(story_id, record["topic_name"], record, fingerprint, record["updated_at"])
    return changed


def content_hash(payload: dict[str, Any] | None, ignore_keys: set[str] | None = None) -> str:
    ignore_keys = ignore_keys or set()
    normalized = {
        key: value
        for key, value in (payload or {}).items()
        if key not in ignore_keys
    }
    return hashlib.sha1(json.dumps(normalized, sort_keys=True).encode("utf-8")).hexdigest()


def write_export_files(latest_snapshot: dict[str, Any], delta_snapshot: dict[str, Any]) -> None:
    export_dir = app_exports_dir()
    archive_payload = build_archive_payload(latest_snapshot["generated_at"])
    atomic_write_json(export_dir / "latest.json", latest_snapshot)
    atomic_write_json(export_dir / "items.json", {"items": latest_snapshot["items"], "generated_at": latest_snapshot["generated_at"], "run_id": latest_snapshot["run_id"]})
    atomic_write_json(export_dir / "stories.json", {"stories": latest_snapshot["stories"], "generated_at": latest_snapshot["generated_at"], "run_id": latest_snapshot["run_id"]})
    atomic_write_json(export_dir / "story_pages.json", {"stories": latest_snapshot["stories"], "generated_at": latest_snapshot["generated_at"], "run_id": latest_snapshot["run_id"]})
    atomic_write_json(export_dir / "topics.json", {"topics": latest_snapshot["topics"], "generated_at": latest_snapshot["generated_at"], "run_id": latest_snapshot["run_id"]})
    atomic_write_json(export_dir / "reference.json", {"reference": latest_snapshot["reference"], "generated_at": latest_snapshot["generated_at"], "run_id": latest_snapshot["run_id"]})
    atomic_write_json(export_dir / "atlas.json", {"atlas": latest_snapshot.get("atlas", []), "generated_at": latest_snapshot["generated_at"], "run_id": latest_snapshot["run_id"]})
    atomic_write_json(export_dir / "archive.json", archive_payload)
    atomic_write_json(
        export_dir / "health.json",
        {
            "run_id": latest_snapshot["run_id"],
            "generated_at": latest_snapshot["generated_at"],
            "degraded": latest_snapshot["degraded"],
            "source_failures": latest_snapshot["source_failures"],
            "source_health": latest_snapshot.get("source_health", []),
            "freshness_summary": latest_snapshot.get("freshness_summary", {}),
            "item_count": latest_snapshot["item_count"],
            "story_count": latest_snapshot["story_count"],
            "topic_count": latest_snapshot["topic_count"],
            "editor_summary": latest_snapshot.get("editor_summary", {}),
        },
    )
    atomic_write_json(
        export_dir / "manifest.json",
        {
            "latest_run_id": latest_snapshot["run_id"],
            "generated_at": latest_snapshot["generated_at"],
            "files": {
                "latest": "latest.json",
                "items": "items.json",
                "stories": "stories.json",
                "story_pages": "story_pages.json",
                "topics": "topics.json",
                "reference": "reference.json",
                "atlas": "atlas.json",
                "archive": "archive.json",
                "health": "health.json",
                "delta": f"deltas/{latest_snapshot['run_id']}.json",
            },
        },
    )
    atomic_write_json(export_dir / "deltas" / f"{latest_snapshot['run_id']}.json", delta_snapshot)


def build_editor_summary(latest_snapshot: dict[str, Any]) -> dict[str, Any]:
    items = latest_snapshot.get("items", [])
    stories = latest_snapshot.get("stories", [])
    major_publishers = sorted(
        {
            item.get("publisher_name", "")
            for item in items
            if item.get("publisher_name") in HIGH_SIGNAL_PUBLISHER_FAMILIES
        }
    )
    return {
        "sources_live": latest_snapshot.get("freshness_summary", {}).get("live", 0),
        "sources_cached": latest_snapshot.get("freshness_summary", {}).get("refresh_cache", 0) + latest_snapshot.get("freshness_summary", {}).get("fallback_cache", 0),
        "sources_failed": len(latest_snapshot.get("source_failures", [])),
        "major_publisher_families_seen": major_publishers,
        "wrapper_only_count": sum(1 for item in items if item.get("link_quality") == "wrapper_only"),
        "metadata_only_count": sum(1 for item in items if item.get("link_quality") == "metadata_only"),
        "story_count_change": len([story for story in stories if story.get("new_since_last_refresh")]),
    }


def build_archive_payload(generated_at: str) -> dict[str, Any]:
    entries = list_briefing_archives()
    return {
        "generated_at": generated_at,
        "latest": {
            "html_url": latest_html_filename().resolve().as_uri(),
            "markdown_url": latest_filename().resolve().as_uri(),
            "html_web_path": "index.html",
            "markdown_web_path": "latest.md",
        },
        "entries": [
            {
                "date": entry.target_date.isoformat(),
                "year": entry.target_date.year,
                "month": f"{entry.target_date:%m}",
                "month_name": entry.target_date.strftime("%B"),
                "day": f"{entry.target_date:%d}",
                "html_url": entry.html_path.resolve().as_uri(),
                "markdown_url": entry.markdown_path.resolve().as_uri(),
                "html_web_path": archive_relpath(entry.target_date, suffix=".html").as_posix(),
                "markdown_web_path": archive_relpath(entry.target_date, suffix=".md").as_posix(),
            }
            for entry in entries
        ],
    }
