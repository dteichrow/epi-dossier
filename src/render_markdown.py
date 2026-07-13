from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

import polars as pl

from .summarize import (
    build_fact_summary_sentences,
    clean_sentence,
    rank_sentences,
    sentence_just_repeats_title_plus_outlet,
    title_overlap_ratio,
    trim_text,
)
from .utils import DiseaseReference, Item, format_timestamp, matched_disease_reference_names, sortable_datetime


TOPIC_KEYWORDS = {
    "Hantavirus and cruise-ship outbreak": ("hantavirus", "andes virus"),
    "Polio and wastewater surveillance": ("poliovirus", "polio", "wastewater"),
    "Measles transmission and vaccination": ("measles", "vaccin"),
    "Avian influenza and H5N1": ("avian influenza", "h5n1", "bird flu"),
    "COVID-19 and SARS-CoV-2": ("covid", "sars-cov-2"),
    "Dengue and arboviruses": ("dengue", "arbovirus", "mosquito"),
    "Tuberculosis and antimicrobial resistance": ("tuberculosis", "tb", "antimicrobial resistance", "amr"),
    "Occupational and environmental epidemiology": ("occupational", "worker", "exposure", "niosh", "osha", "environmental"),
    "Historical epidemiology and ancient pathogens": (
        "ancient",
        "historical epidemiology",
        "paleopathology",
        "ancient dna pathogen",
        "ancient pathogen",
        "ancient dna",
        "pathogen adna",
        "archaeogenetics",
        "paleogenomics",
        "paleomicrobiology",
        "yersinia pestis",
        "variola",
        "mycobacterium leprae",
        "mycobacterium tuberculosis",
        "treponemal",
        "history of medicine",
        "burial",
        "cemetery",
        "mummified",
        "skeletal",
    ),
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
    "syphilis archaeology",
    "burial",
    "cemetery",
    "mummified",
    "skeletal",
)

STORY_FLAG_RULES = {
    "active_investigation": (
        "under investigation",
        "investigation",
        "monitoring outbreak",
        "monitoring",
    ),
    "low_public_risk": (
        "very low",
        "low risk",
        "risk for europeans very low",
        "low threat",
    ),
    "human_to_human_suspected": (
        "human-to-human",
        "person-to-person",
    ),
    "deaths_reported": (
        " dead ",
        " deaths ",
        " died ",
        "fatal",
        "killed",
    ),
    "quarantine_measures": (
        "quarantined",
        "quarantine",
    ),
    "evacuation_measures": (
        "evacuate",
        "evacuated",
        "evacuation",
    ),
    "response_site_attack": (
        "treatment center burned",
        "treatment centre burned",
        "clinic burned",
        "ward burned",
        "center set on fire",
        "centre set on fire",
        "hospital stormed",
        "clinic stormed",
        "set on fire",
    ),
    "burial_conflict": (
        "safe burial",
        "traditional burial",
        "unsafe burial",
        "burial team",
        "retrieve body",
        "retrieve bodies",
        "body retrieval",
        "body of a suspected",
        "bodies of suspected",
    ),
    "wastewater_signal": (
        "wastewater",
    ),
    "vaccine_signal": (
        "vaccine",
        "vaccination",
        "unvaccinated",
    ),
}

STORY_FLAG_MESSAGES = {
    "active_investigation": "{source} now explicitly uses investigation or monitoring language.",
    "low_public_risk": "{source} currently frames broader public risk as low.",
    "human_to_human_suspected": "{source} now mentions possible human-to-human transmission.",
    "deaths_reported": "{source} now includes deaths or fatal cases in the story frame.",
    "quarantine_measures": "{source} now includes quarantine language.",
    "evacuation_measures": "{source} now includes evacuation reporting.",
    "response_site_attack": "{source} now reports violence or fire at a treatment site.",
    "burial_conflict": "{source} now reports conflict over body retrieval or burial practices.",
    "wastewater_signal": "{source} now brings wastewater surveillance into the story.",
    "vaccine_signal": "{source} now foregrounds vaccination or vaccine policy in the story.",
}

DISEASE_TOPIC_ACTIVITY_TERMS = (
    "outbreak",
    "cluster",
    "confirmed",
    "suspected",
    "probable",
    "case",
    "cases",
    "death",
    "deaths",
    "died",
    "fatal",
    "case fatality",
    "transmission",
    "public health emergency",
    "health emergency",
    "contact tracing",
    "contacts",
    "isolation",
    "quarantine",
    "safe burial",
    "traditional burial",
    "unsafe burial",
    "burial team",
    "retrieve body",
    "retrieve bodies",
    "body retrieval",
    "tests positive",
    "test positive",
    "diagnosed",
    "hospitalized",
    "hospitalised",
    "treatment center",
    "treatment centre",
    "treatment facility",
    "hospital stormed",
    "clinic stormed",
    "set on fire",
    "travel health notice",
    "cross-border",
    "imported",
    "health zone",
    "rapid response",
    "unknown illness",
    "mystery illness",
    "under investigation",
    "investigation",
)


@dataclass
class StoryUpdate:
    topic_name: str
    lead_title: str
    lead_url: str
    lead_source: str
    bullets: list[str]
    item_count: int
    source_count: int
    is_new_story: bool = False


def render_markdown(
    items: list[Item],
    target_date: date,
    generated_at: datetime,
    search_window: str,
    outbreak_reference: list[DiseaseReference] | None = None,
    story_updates: list[StoryUpdate] | None = None,
    source_failures: list[dict[str, str]] | None = None,
    source_health: list[dict[str, str]] | None = None,
) -> str:
    sorted_items = sorted(
        items,
        key=lambda item: (item.relevance_score, 1 if item.official else 0, sortable_datetime(item.published_at)),
        reverse=True,
    )
    executive = sorted_items[:8]
    highest_priority = [item for item in sorted_items if item.relevance_score >= 4][:10]
    others = [item for item in sorted_items if item not in highest_priority][:20]
    papers = [item for item in sorted_items if item.source_type in {"pubmed", "medrxiv", "biorxiv"}][:12]
    historical = [item for item in sorted_items if item_is_historical(item)][:10]
    category_summary = summarize_categories(sorted_items)
    topic_groups = build_topic_groups(sorted_items)

    lines: list[str] = []
    lines.append("# Daily Infectious Disease & Epidemiology Dossier")
    lines.append(f"Date: {target_date.isoformat()}")
    lines.append(f"Generated at: {generated_at.isoformat(timespec='minutes')}")
    lines.append(f"Search window: {search_window}")
    lines.append("")
    lines.append("## Executive scan")
    if executive:
        for item in executive:
            lines.append(
                f"- [{item.title}]({item.url}) ({item.display_source}; {format_timestamp(item.published_at)}; {item.category}; relevance {item.relevance_score}/5)"
            )
        if category_summary:
            lines.append(f"- Category mix: {category_summary}")
    else:
        lines.append("- No new high-confidence items cleared the configured filters in this run, but the dossier was still generated for auditability.")
    if source_failures:
        lines.append(f"- Source health: {render_source_failure_summary(source_failures)}")

    lines.append("")
    lines.append("## Ongoing stories and what changed")
    if story_updates:
        for update in story_updates[:5]:
            lines.extend(_render_story_updates(update))
    else:
        lines.append("- No multi-item story clusters produced concrete update bullets in this run.")

    lines.append("")
    lines.append("## Major topics")
    if topic_groups:
        for topic_name, topic_items in topic_groups[:6]:
            lines.extend(_render_topic(topic_name, topic_items))
    else:
        lines.append("No major topic clusters emerged from today’s items.")

    lines.append("")
    lines.append("## Last major outbreaks on file")
    if outbreak_reference:
        for reference in outbreak_reference:
            lines.extend(_render_outbreak_reference(reference))
    else:
        lines.append("- No outbreak reference entries have been curated yet.")

    lines.append("")
    lines.append("## Highest priority items")
    if highest_priority:
        for item in highest_priority:
            lines.extend(_render_full_item(item))
    else:
        lines.append("No new items cleared the highest-priority threshold today.")
        lines.append("")
        lines.append("The pipeline completed, but everything in the search window was either already seen, filtered out, or too low-detail to rank highly.")

    lines.append("")
    lines.append("## Other notable readings")
    if others:
        for item in others:
            lines.append(f"- [{item.title}]({item.url}) | {item.display_source} | {format_timestamp(item.published_at)} | {item.category}")
            lines.append(f"  {item.summary}")
    else:
        lines.append("- No additional new readings passed the filters.")

    lines.append("")
    lines.append("## Papers worth saving")
    if papers:
        for item in papers:
            lines.append(f"- [{item.title}]({item.url})")
            lines.append(f"  Source: {item.display_source}")
            lines.append(f"  DOI: {item.doi or 'Unknown'}")
            lines.append(f"  Journal/preprint server: {item.journal or 'Unknown'}")
            lines.append(f"  Abstract link: {item.abstract_url or item.url}")
            lines.append(f"  Source URL: {item.url}")
    else:
        lines.append("- No papers met the current filter.")

    lines.append("")
    lines.append("## Historical epi / weird epi corner")
    if historical:
        for item in historical:
            lines.append(f"- [{item.title}]({item.url}) | {item.display_source}")
            lines.append(f"  {item.summary}")
    else:
        lines.append("- No dedicated historical or paleopathology items stood out today.")

    lines.append("")
    lines.append("## Possible blog/video angles")
    for idea in generate_angles(sorted_items):
        lines.append(f"- {idea}")

    return "\n".join(lines).strip() + "\n"


def render_source_failure_summary(source_failures: list[dict[str, str]]) -> str:
    if not source_failures:
        return "No source failures were logged."
    labels = [failure.get("source", "Unknown source") for failure in source_failures[:5]]
    summary = ", ".join(labels)
    if len(source_failures) > 5:
        summary += f", plus {len(source_failures) - 5} more"
    return f"{len(source_failures)} source(s) failed during collection: {summary}."


def _render_outbreak_reference(reference: DiseaseReference) -> list[str]:
    lines = [
        f"- **{reference.name}** | {reference.pathogen}",
        f"  Transmission: {reference.transmission}",
        f"  Last major outbreak on file: {reference.latest_outbreak.label} | {reference.latest_outbreak.location} | {reference.latest_outbreak.period}",
        f"  Summary: {reference.latest_outbreak.summary}",
        f"  Source: {reference.latest_outbreak.source_name} ({reference.latest_outbreak.as_of})",
        f"  URL: {reference.latest_outbreak.source_url}",
    ]
    if reference.field_guide_links:
        field_guide = "; ".join(f"[{link.label}]({link.url})" for link in reference.field_guide_links)
        lines.append(f"  Field guide: {field_guide}")
    if reference.notable_outbreaks:
        lines.append(f"  Notable earlier outbreaks: {'; '.join(reference.notable_outbreaks)}")
    if reference.surveillance_note:
        lines.append(f"  Desk note: {reference.surveillance_note}")
    return lines


def summarize_categories(items: list[Item]) -> str:
    if not items:
        return ""
    frame = pl.DataFrame(
        {
            "category": [item.category for item in items],
        }
    )
    counts = (
        frame.group_by("category")
        .len()
        .sort("len", descending=True)
        .head(3)
        .iter_rows()
    )
    return ", ".join(f"{category} ({count})" for category, count in counts)


def _render_full_item(item: Item) -> list[str]:
    return [
        f"### {item.title}",
        f"- Source: {item.display_source}",
        f"- Date: {format_timestamp(item.published_at)}",
        f"- URL: {item.url}",
        f"- Category: {item.category}",
        f"- Summary: {item.summary}",
        f"- Why it matters: {item.why_it_matters}",
        f"- Caveats / uncertainty: {item.caveats}",
        f"- Relevance score: {item.relevance_score}/5",
        "",
    ]


def build_topic_groups(items: list[Item]) -> list[tuple[str, list[Item]]]:
    grouped: dict[str, list[Item]] = {}
    for item in items:
        topic_name = classify_topic(item)
        grouped.setdefault(topic_name, []).append(item)

    groups = [
        (topic, topic_items)
        for topic, topic_items in grouped.items()
        if len(topic_items) >= 2 or topic != "Miscellaneous signals"
    ]
    groups.sort(key=lambda pair: topic_rank(pair[1]), reverse=True)
    return groups


def classify_topic(item: Item) -> str:
    text = " ".join(
        [
            item.title.lower(),
            item.summary.lower(),
            item.category.lower(),
            item.source.lower(),
        ]
    )
    activity_text = " ".join(
        [
            item.title.lower(),
            item.summary.lower(),
            item.extracted_text.lower(),
        ]
    )
    reference_matches = matched_disease_reference_names(text)
    has_reference_outbreak_activity = reference_matches and any(term in activity_text for term in DISEASE_TOPIC_ACTIVITY_TERMS)
    for topic_name, keywords in TOPIC_KEYWORDS.items():
        if topic_name == "Historical epidemiology and ancient pathogens" and has_reference_outbreak_activity:
            continue
        if any(keyword_matches(text, keyword) for keyword in keywords):
            return topic_name
    if has_reference_outbreak_activity:
        return reference_matches[0]
    return "Miscellaneous signals"


def topic_rank(items: list[Item]) -> tuple[int, int, datetime]:
    best_time = max((sortable_datetime(item.published_at) for item in items), default=sortable_datetime(None))
    return (max(item.relevance_score for item in items), len(items), best_time)


def _render_topic(topic_name: str, items: list[Item]) -> list[str]:
    top_items = sorted(
        items,
        key=lambda item: (item.relevance_score, 1 if item.official else 0, sortable_datetime(item.published_at)),
        reverse=True,
    )
    headline = top_items[0]
    official_count = sum(1 for item in items if item.official)
    source_count = len({item.display_source for item in items})
    if topic_name == "Miscellaneous signals":
        synopsis = "Several lower-volume signals passed the filters, but they do not resolve into one coherent topic cluster. Use the linked evidence notes directly rather than reading this as a single story."
    else:
        synopsis = build_topic_synopsis(topic_name, top_items)
    evidence = build_topic_evidence(top_items[:5])
    implications = build_topic_implications(topic_name, top_items)
    caveats = build_topic_caveats(top_items)

    return [
        f"### {topic_name}",
        f"- Topic size: {len(items)} item(s) across {source_count} source(s); {official_count} official/primary-source item(s).",
        f"- Lead item: [{headline.title}]({headline.url}) ({headline.display_source}, {format_timestamp(headline.published_at)})",
        f"- Detailed note: {synopsis}",
        f"- Evidence notes: {evidence}",
        f"- Why this topic matters now: {implications}",
        f"- Caveats / uncertainty: {caveats}",
        "",
    ]


def _render_story_updates(update: StoryUpdate) -> list[str]:
    lines = [f"### {update.topic_name}"]
    lines.append(f"- Lead item: [{update.lead_title}]({update.lead_url}) ({update.lead_source})")
    if update.is_new_story:
        lines.append(f"- Newly tracked story cluster: {update.item_count} item(s) across {update.source_count} source(s).")
    for bullet in update.bullets:
        lines.append(f"- {bullet}")
    lines.append("")
    return lines


def analyze_story_updates(items: list[Item], previous_snapshots: dict[str, dict] | None = None) -> tuple[list[StoryUpdate], dict[str, dict]]:
    previous_snapshots = previous_snapshots or {}
    updates: list[StoryUpdate] = []
    snapshots: dict[str, dict] = {}
    for topic_name, topic_items in build_topic_groups(items):
        if topic_name == "Miscellaneous signals":
            continue
        official_count = sum(1 for item in topic_items if item.official)
        if len(topic_items) < 2:
            continue
        if len(topic_items) < 3 and official_count < 2:
            continue
        if max(item.relevance_score for item in topic_items) < 3:
            continue
        snapshot = build_story_snapshot(topic_name, topic_items)
        snapshots[topic_name] = snapshot
        previous = previous_snapshots.get(topic_name)
        update = build_story_update(topic_name, topic_items, snapshot, previous)
        if update:
            updates.append(update)
    updates.sort(key=lambda update: (0 if update.is_new_story else 1, len(update.bullets), update.item_count), reverse=True)
    return updates, snapshots


def build_story_snapshot(topic_name: str, items: list[Item]) -> dict:
    top_items = sorted(
        items,
        key=lambda item: (item.relevance_score, 1 if item.official else 0, sortable_datetime(item.published_at)),
        reverse=True,
    )
    combined_text = f" {' '.join(f'{item.title} {item.summary} {item.extracted_text}' for item in top_items[:8]).lower()} "
    flags = [
        flag
        for flag, terms in STORY_FLAG_RULES.items()
        if any(term in combined_text for term in terms)
    ]
    return {
        "topic_name": topic_name,
        "lead_title": top_items[0].title,
        "lead_url": top_items[0].url,
        "lead_source": top_items[0].display_source,
        "cluster_size": len(items),
        "source_names": sorted({item.display_source for item in items}),
        "official_source_names": sorted({item.display_source for item in items if item.official}),
        "official_source_count": sum(1 for item in items if item.official),
        "flags": sorted(flags),
        "flag_sources": build_flag_sources(top_items),
        "canonical_urls": [item.canonical_url for item in top_items[:10]],
        "top_titles": [item.title for item in top_items[:5]],
        "latest_timestamp": format_timestamp(top_items[0].published_at),
    }


def build_story_update(topic_name: str, items: list[Item], snapshot: dict, previous: dict | None) -> StoryUpdate | None:
    bullets: list[str] = []
    previous_flags = set((previous or {}).get("flags", []))
    current_flags = set(snapshot["flags"])
    new_flags = [flag for flag in snapshot["flags"] if flag not in previous_flags]

    if previous is None:
        bullets.extend(build_baseline_story_bullets(snapshot))
        return StoryUpdate(
            topic_name=topic_name,
            lead_title=snapshot["lead_title"],
            lead_url=snapshot["lead_url"],
            lead_source=snapshot["lead_source"],
            bullets=bullets[:4],
            item_count=snapshot["cluster_size"],
            source_count=len(snapshot["source_names"]),
            is_new_story=True,
        )

    for flag in new_flags:
        message = format_story_flag_message(flag, snapshot)
        if message:
            bullets.append(message)

    previous_sources = set(previous.get("source_names", []))
    new_sources = [source for source in snapshot["source_names"] if source not in previous_sources]
    if new_sources:
        official_new_sources = [source for source in new_sources if source in snapshot.get("official_source_names", [])]
        if official_new_sources:
            bullets.append(f"New official source(s) joined this story cluster: {', '.join(official_new_sources[:3])}.")
        else:
            bullets.append(f"New publisher/source coverage joined this story cluster: {', '.join(new_sources[:3])}.")

    if snapshot["lead_url"] != previous.get("lead_url"):
        bullets.append(f"The lead item has changed to [{snapshot['lead_title']}]({snapshot['lead_url']}) from {snapshot['lead_source']}.")

    previous_size = int(previous.get("cluster_size", 0))
    if snapshot["cluster_size"] > previous_size:
        bullets.append(f"Story volume increased from {previous_size} to {snapshot['cluster_size']} clustered item(s) in the current window.")

    previous_urls = set(previous.get("canonical_urls", []))
    new_urls = [url for url in snapshot["canonical_urls"] if url not in previous_urls]
    if new_urls:
        bullets.append(f"{len(new_urls)} newly observed linked item(s) were added since the last saved snapshot.")

    if not bullets:
        return None

    return StoryUpdate(
        topic_name=topic_name,
        lead_title=snapshot["lead_title"],
        lead_url=snapshot["lead_url"],
        lead_source=snapshot["lead_source"],
        bullets=deduplicate_caveats(bullets)[:4],
        item_count=snapshot["cluster_size"],
        source_count=len(snapshot["source_names"]),
    )


def build_baseline_story_bullets(snapshot: dict) -> list[str]:
    bullets = [
        f"Baseline snapshot created with {snapshot['cluster_size']} clustered item(s) across {len(snapshot['source_names'])} source(s).",
    ]
    for flag in snapshot["flags"][:3]:
        message = format_story_flag_message(flag, snapshot)
        if message:
            bullets.append(message)
    if len(bullets) == 1:
        bullets.append("Story tracking is now active for this cluster; future runs will report only new developments against this baseline.")
    return bullets


def build_flag_sources(items: list[Item]) -> dict[str, dict[str, str]]:
    flag_sources: dict[str, dict[str, str]] = {}
    for item in items:
        text = f" {item.title} {item.summary} {item.extracted_text} ".lower()
        for flag, terms in STORY_FLAG_RULES.items():
            if flag in flag_sources:
                continue
            if any(term in text for term in terms):
                flag_sources[flag] = {"source": item.display_source, "title": item.title, "url": item.url}
    return flag_sources


def format_story_flag_message(flag: str, snapshot: dict) -> str:
    template = STORY_FLAG_MESSAGES.get(flag)
    if not template:
        return ""
    source_info = snapshot.get("flag_sources", {}).get(flag, {})
    source = source_info.get("source", snapshot.get("lead_source", "Current coverage"))
    return template.format(source=source)


def build_topic_synopsis(topic_name: str, items: list[Item]) -> str:
    candidate_sentences: list[str] = []
    seen: set[str] = set()
    for item in items[:6]:
        for sentence in build_fact_summary_sentences(item, max_sentences=2):
            cleaned = clean_sentence(sentence)
            normalized = cleaned.lower()
            if not cleaned or normalized in seen:
                continue
            if normalized.startswith("limited detail was available") or normalized.startswith("limited usable detail remained"):
                continue
            seen.add(normalized)
            candidate_sentences.append(cleaned)

    ranked = rank_sentences(candidate_sentences, title=items[0].title)
    selected: list[str] = []
    for sentence in ranked:
        if sentence_should_skip_topic_sentence(sentence, items[0].title, selected):
            continue
        selected.append(sentence)
        if len(selected) == 3:
            break
    if selected:
        return trim_text(" ".join(selected), 420)

    if summary_usable(items[0].summary, items[0].title):
        return trim_text(items[0].summary, 280)
    return f"Cluster remains active across {len(items)} related item(s), but usable factual summary text was limited after cleanup."


def build_topic_evidence(items: list[Item]) -> str:
    notes = []
    for item in items:
        notes.append(f"[{item.title}]({item.url}) ({item.display_source})")
    return "; ".join(notes)


def build_topic_implications(topic_name: str, items: list[Item]) -> str:
    text = " ".join(f"{item.title} {item.summary} {item.category}" for item in items).lower()
    statements: list[str] = []
    if any(term in text for term in ("outbreak", "cluster", "surveillance", "wastewater")):
        statements.append("It affects how to interpret current surveillance or outbreak detection signals.")
    if any(term in text for term in ("travel", "health notice", "who", "cdc")):
        statements.append("It may influence public-health messaging, travel guidance, or risk framing.")
    if any(term in text for term in ("preprint", "study", "cohort", "model", "analysis")):
        statements.append("It may shape how new evidence is framed before broader consensus forms.")
    if "historical" in topic_name.lower() or "ancient" in topic_name.lower():
        statements.append("It also has value for historical epidemiology and blog-idea generation.")
    return " ".join(statements[:2]) or "It is one of the clearer recurring signals in today’s source set."


def build_topic_caveats(items: list[Item]) -> str:
    caveats: list[str] = []
    if not any(item.official for item in items):
        caveats.append("This cluster leans on secondary coverage rather than official primary-source reporting.")
    if len({item.display_source for item in items}) == 1:
        caveats.append("Source diversity is limited so corroboration is thin.")
    if any(item.source_type in {"medrxiv", "biorxiv"} for item in items):
        caveats.append("Some items are preprints and may change after review.")
    if any(len(item.summary) < 90 and not item.extracted_text for item in items):
        caveats.append("Several entries still rely on short feed metadata rather than full-text extraction.")
    if not caveats:
        return "These notes are limited to source text collected in this run."
    return " ".join(deduplicate_caveats(caveats[:2]))


def keyword_matches(text: str, keyword: str) -> bool:
    pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
    return re.search(pattern, text) is not None


def item_is_historical(item: Item) -> bool:
    joined = " ".join(
        [
            item.category.lower(),
            item.title.lower(),
            item.summary.lower(),
            item.display_source.lower(),
        ]
    )
    return any(term in joined for term in HISTORICAL_TERMS)


def summary_usable(summary: str, title: str) -> bool:
    cleaned = normalize_summary_text(summary)
    if len(cleaned) < 90:
        return False
    if cleaned.lower() == title.lower():
        return False
    if title_overlap_ratio(cleaned, title) >= 0.72:
        return False
    if looks_like_headline_bundle(cleaned):
        return False
    if is_navigation_heavy(cleaned):
        return False
    if sentence_just_repeats_title_plus_outlet(cleaned, title):
        return False
    return True


def sentence_should_skip_topic_sentence(sentence: str, lead_title: str, selected: list[str]) -> bool:
    if title_overlap_ratio(sentence, lead_title) >= 0.72:
        return True
    sentence_tokens = {token for token in re.findall(r"[a-z0-9]+", sentence.lower()) if len(token) > 3}
    if not sentence_tokens:
        return True
    for prior in selected:
        prior_tokens = {token for token in re.findall(r"[a-z0-9]+", prior.lower()) if len(token) > 3}
        if prior_tokens and len(sentence_tokens & prior_tokens) / min(len(sentence_tokens), len(prior_tokens)) >= 0.65:
            return True
    return False


def normalize_summary_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def is_navigation_heavy(text: str) -> bool:
    lowered = text.lower()
    blocked_phrases = (
        "official website of the united states government",
        "opens in a new window",
        "publications and data",
        "infectious disease topics",
    )
    return any(phrase in lowered for phrase in blocked_phrases)


def deduplicate_caveats(caveats: list[str]) -> list[str]:
    seen: set[str] = set()
    kept: list[str] = []
    for caveat in caveats:
        normalized = caveat.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        kept.append(caveat)
    return kept


def title_overlap_ratio(summary: str, title: str) -> float:
    summary_tokens = {token for token in re.findall(r"[a-z0-9]+", summary.lower()) if len(token) > 3}
    title_tokens = {token for token in re.findall(r"[a-z0-9]+", title.lower()) if len(token) > 3}
    if not summary_tokens or not title_tokens:
        return 0.0
    return len(summary_tokens & title_tokens) / len(title_tokens)


def looks_like_headline_bundle(text: str) -> bool:
    if text.count(".") >= 2 or text.count("?") >= 1:
        return False
    title_case_words = sum(1 for word in text.split() if word[:1].isupper())
    if title_case_words >= max(6, len(text.split()) // 3):
        return True
    source_suffixes = (
        "Yahoo",
        "Reuters",
        "AOL.com",
        "ABC News",
        "NBC News",
        "Sky News",
        "Al Jazeera",
        "MedPage Today",
        "Global Polio Eradication",
    )
    return any(text.endswith(suffix) for suffix in source_suffixes)


def trim_length(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    shortened = text[: max_length - 3].rsplit(" ", 1)[0]
    return shortened + "..."


def generate_angles(items: list[Item]) -> list[str]:
    ideas: list[str] = []
    joined = " ".join(f"{item.title} {item.summary} {item.category}" for item in items[:20]).lower()
    if "measles" in joined or "vaccin" in joined:
        ideas.append("Vaccination coverage versus outbreak control: what the day’s measles or vaccine items actually show.")
    if "h5n1" in joined or "avian influenza" in joined:
        ideas.append("Bird flu signal versus noise: separating livestock surveillance updates from true human-risk changes.")
    if "occupational" in joined or "worker" in joined or "niosh" in joined:
        ideas.append("Occupational epidemiology angle: when workplace exposure reports become early-warning public-health signals.")
    if "ancient" in joined or "historical" in joined or "paleopathology" in joined:
        ideas.append("Historical epi angle: how ancient-pathogen papers can sharpen modern outbreak interpretation.")
    ideas.append("Speculative: build a recurring segment on what official surveillance channels emphasized today versus what headlines emphasized.")
    return ideas[:5]
