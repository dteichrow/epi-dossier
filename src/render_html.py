from __future__ import annotations

import html
from collections import defaultdict
from datetime import date, datetime
import re

from .render_markdown import StoryUpdate, build_topic_groups, build_topic_synopsis, render_source_failure_summary
from .utils import ArchiveEntry, DiseaseReference, Item, format_timestamp, has_local_signal, infer_region, latest_html_filename, normalize_whitespace, sortable_datetime


def validate_reader_story_sections(html_text: str, story_records: list[dict] | None = None) -> list[str]:
    story_records = story_records or []
    if not story_records:
        return []

    issues: list[str] = []
    if "No lead outbreak files are featured in this edition." in html_text:
        issues.append("Lead outbreak files rendered as empty despite active story records.")
    if "No major story files are featured in this edition." in html_text:
        issues.append("Major story files rendered as empty despite active story records.")

    expected_titles = [
        (story.get("display_title") or story.get("topic_name") or "").strip()
        for story in story_records[:3]
    ]
    if expected_titles and not any(title and title in html_text for title in expected_titles):
        issues.append("Rendered reader HTML omitted the expected lead story titles.")
    return issues


ACADEMIC_SOURCE_TYPES = {"pubmed", "medrxiv", "biorxiv"}


def item_is_research_item(item: Item) -> bool:
    source_type = (item.source_type or "").lower()
    source_candidates = {
        normalize_whitespace(item.source).lower(),
        normalize_whitespace(item.display_source).lower(),
    }
    research_sources = {
        "pubmed infectious disease search",
        "medrxiv",
        "biorxiv",
    }
    return source_type in ACADEMIC_SOURCE_TYPES or any(candidate in research_sources for candidate in source_candidates)


def render_html(
    items: list[Item],
    target_date: date,
    generated_at: datetime,
    search_window: str,
    outbreak_reference: list[DiseaseReference] | None = None,
    story_updates: list[StoryUpdate] | None = None,
    archive_entries: list[ArchiveEntry] | None = None,
    source_failures: list[dict[str, str]] | None = None,
    source_health: list[dict] | None = None,
    story_records: list[dict] | None = None,
    reference_records: list[dict] | None = None,
) -> str:
    sorted_items = sorted(
        items,
        key=lambda item: (item.relevance_score, 1 if item.official else 0, sortable_datetime(item.published_at)),
        reverse=True,
    )
    front_page_items = [
        item
        for item in sorted_items
        if not item_is_research_item(item)
        if not item_is_background_system_report(item) and not item_is_background_context_piece(item)
    ]
    executive = front_page_items[:8]
    highest_priority = [item for item in front_page_items if item.relevance_score >= 4][:10]
    others = [item for item in front_page_items if item not in highest_priority][:20]
    papers = [item for item in sorted_items if item_is_research_item(item) and not item_is_historical(item)][:12]
    historical = [item for item in sorted_items if item_is_historical(item)][:10]
    topic_groups = build_topic_groups(sorted_items)

    story_records = story_records or []
    reference_records = reference_records or []
    filter_options = build_filter_options(sorted_items, story_records, reference_records, generated_at)
    stories_by_topic = {record.get("topic_name"): record for record in story_records}
    story_blocks = "".join(render_story_update(update, stories_by_topic.get(update.topic_name)) for update in (story_updates or [])[:5])
    if not story_blocks:
        story_blocks = '<p class="empty-note">No major file registered a new structured shift in this update.</p>'

    region_blocks = render_region_watch(sorted_items)
    major_story_blocks = "".join(render_major_story_card(story) for story in story_records[:6]) or '<p class="empty-note">No major story files are featured in this edition.</p>'
    reference_desk_blocks = "".join(render_reference_desk_card(reference) for reference in reference_records[:8]) or '<p class="empty-note">No disease intelligence sheets are featured in this edition.</p>'
    references_by_name = {record.get("name"): record for record in reference_records}
    outbreak_reference_blocks = render_outbreak_reference(outbreak_reference or [], references_by_name)

    topic_blocks = "".join(render_topic_block(topic_name, topic_items, stories_by_topic.get(topic_name)) for topic_name, topic_items in topic_groups[:6])
    if not topic_blocks:
        topic_blocks = '<p class="empty-note">No additional topic clusters are leading this edition.</p>'

    highest_priority_blocks = "".join(render_priority_card(item) for item in highest_priority)
    if not highest_priority_blocks:
        highest_priority_blocks = '<p class="empty-note">No new items cleared the highest-priority threshold today.</p>'

    other_blocks = "".join(render_compact_item(item) for item in others)
    if not other_blocks:
        other_blocks = '<p class="empty-note">No additional new readings passed the filters.</p>'

    paper_blocks = "".join(render_paper_card(item) for item in papers)
    if not paper_blocks:
        paper_blocks = '<p class="empty-note">No papers met the current filter.</p>'

    historical_blocks = "".join(render_historical_item(item) for item in historical)
    if not historical_blocks:
        historical_blocks = '<p class="empty-note">No historical or paleopathology item is leading this edition.</p>'

    executive_blocks = "".join(render_executive_item(item) for item in executive)
    if not executive_blocks:
        executive_blocks = '<li class="searchable-row" data-search="no new items auditability">No new high-confidence item is leading this edition.</li>'
    if source_failures:
        executive_blocks += (
            f'<li class="searchable-row" data-search="source failures degraded run">'
            f'{html.escape(render_source_failure_summary(source_failures))}'
            f"</li>"
        )

    freshness_label = generated_at.strftime("%b %d, %Y at %I:%M:%S %p").replace(" 0", " ")
    source_health_note = render_source_health_note(source_health or [])
    desk_health_panel = render_desk_health_panel(source_health or [])
    archive_block = render_archive_sidebar(archive_entries or [], target_date)
    view_switcher = render_view_switcher()
    lead_story_rail = "".join(render_lead_story_rail_card(story, index) for index, story in enumerate(story_records[:4]))
    if not lead_story_rail:
        lead_story_rail = '<p class="empty-note">No lead outbreak files are featured in this edition.</p>'
    lead_priority_item = highest_priority[0] if highest_priority else None
    supporting_priority_items = highest_priority[1:5] if len(highest_priority) > 1 else []
    lead_priority_block = render_feature_priority_card(lead_priority_item) if lead_priority_item else '<p class="empty-note">No new lead item cleared the highest-priority threshold today.</p>'
    supporting_priority_blocks = "".join(render_secondary_priority_card(item) for item in supporting_priority_items)
    if not supporting_priority_blocks:
        supporting_priority_blocks = '<p class="empty-note">No secondary priority items are featured in this edition.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>The Pathogen Dispatch by The Edge of Epidemiology</title>
    <style>
      :root {{
        --bg: #e8e1d3;
        --bg-deep: #d8cebc;
        --surface: #f8f4ea;
        --surface-alt: #f2ebde;
        --surface-ink: #173046;
        --surface-dark: #132331;
        --paper: #fffdf8;
        --ink: #1b2836;
        --ink-soft: #42515e;
        --muted: #66727d;
        --line: #d6cab7;
        --line-strong: #bba98f;
        --accent: #8d3f2f;
        --accent-soft: rgba(141, 63, 47, 0.10);
        --signal: #1f5b89;
        --signal-soft: rgba(31, 91, 137, 0.12);
        --gold: #b58a31;
        --gold-soft: rgba(181, 138, 49, 0.14);
        --shadow: 0 24px 56px rgba(49, 36, 22, 0.10);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background:
          radial-gradient(circle at top left, rgba(181, 138, 49, 0.10), transparent 28%),
          radial-gradient(circle at bottom right, rgba(31, 91, 137, 0.12), transparent 24%),
          linear-gradient(180deg, #f2ede3 0%, var(--bg) 40%, var(--bg-deep) 100%);
        color: var(--ink);
        font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
        line-height: 1.58;
        overflow-x: hidden;
      }}
      a {{ color: var(--signal); text-decoration: none; }}
      a:hover {{ text-decoration: underline; }}
      [hidden] {{ display: none !important; }}
      .page {{
        width: 100%;
        max-width: 1180px;
        margin: 0 auto;
        padding: 24px 16px 56px;
        overflow-x: clip;
      }}
      .page > *,
      .hero > *,
      .panel > *,
      .lead-story-card > *,
      .site-nav-shell > * {{
        min-width: 0;
      }}
      h1, h2, h3, p, li, .subtitle, .desk-note, .site-nav-note, .view-caption, .empty-note, .footer-note, .meta-inline {{
        overflow-wrap: anywhere;
        word-break: break-word;
      }}
      .site-nav-shell {{
        background: linear-gradient(180deg, rgba(255,253,248,0.98), rgba(248,243,233,0.98));
        border: 1px solid rgba(187, 169, 143, 0.82);
        border-radius: 24px;
        box-shadow: var(--shadow);
        padding: 16px 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 18px;
        margin-bottom: 18px;
      }}
      .site-nav-brand {{
        min-width: 0;
      }}
      .site-nav-note {{
        margin: 0;
        color: var(--ink-soft);
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
        font-size: 0.95rem;
      }}
      .site-nav-links {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }}
      .site-nav-link {{
        border-radius: 999px;
        padding: 9px 14px;
        border: 1px solid rgba(187, 169, 143, 0.76);
        background: rgba(255, 252, 245, 0.94);
        color: var(--ink);
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
        font-size: 0.92rem;
        text-decoration: none;
      }}
      .site-nav-link:hover {{
        background: var(--accent-soft);
        text-decoration: none;
      }}
      .site-nav-link.active {{
        background: rgba(31, 91, 137, 0.12);
        border-color: rgba(31, 91, 137, 0.28);
        color: var(--signal);
      }}
      .hero {{
        background:
          linear-gradient(180deg, rgba(255,255,255,0.60), rgba(255,255,255,0)),
          linear-gradient(135deg, rgba(248, 244, 234, 0.98), rgba(242, 235, 222, 0.98));
        border: 1px solid rgba(187, 169, 143, 0.75);
        border-radius: 30px;
        box-shadow: var(--shadow);
        padding: 26px 28px 24px;
        position: relative;
        overflow: hidden;
      }}
      .hero::before {{
        content: "";
        position: absolute;
        inset: 0;
        background-image:
          linear-gradient(rgba(23, 48, 70, 0.04) 1px, transparent 1px),
          linear-gradient(90deg, rgba(23, 48, 70, 0.04) 1px, transparent 1px);
        background-size: 28px 28px;
        opacity: 0.35;
        pointer-events: none;
      }}
      .hero > * {{
        position: relative;
        z-index: 1;
      }}
      .desk-bar {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 22px;
        margin-bottom: 20px;
      }}
      .desk-kicker,
      .kicker,
      .eyebrow {{
        margin: 0 0 10px;
        font-family: "Avenir Next Condensed", "Franklin Gothic Medium", sans-serif;
        text-transform: uppercase;
        letter-spacing: 0.16em;
        font-size: 0.74rem;
        color: var(--accent);
      }}
      .desk-note,
      .subtitle,
      .view-intro p,
      .search-status,
      .view-caption,
      .footer-note,
      .empty-note {{
        color: var(--ink-soft);
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
      }}
      .desk-note {{
        margin: 0;
        font-size: 1rem;
        max-width: 660px;
        line-height: 1.5;
      }}
      .desk-tools {{
        min-width: 250px;
        display: flex;
        justify-content: flex-end;
      }}
      .brand-row {{
        display: grid;
        grid-template-columns: 112px minmax(0, 1fr);
        gap: 22px;
        align-items: center;
        margin-bottom: 18px;
      }}
      .brand-lockup {{
        width: 112px;
        height: 112px;
        border-radius: 26px;
        background: linear-gradient(180deg, rgba(255,255,255,0.85), rgba(240, 231, 215, 0.88));
        border: 1px solid rgba(187, 169, 143, 0.85);
        display: grid;
        place-items: center;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.8);
      }}
      .brand-lockup svg {{
        width: 84px;
        height: 84px;
      }}
      .brand-deck {{
        max-width: 980px;
      }}
      h1, h2, h3 {{
        margin: 0;
        font-weight: 700;
      }}
      h1 {{
        font-size: clamp(2.25rem, 4.6vw, 4.4rem);
        line-height: 0.98;
        letter-spacing: -0.03em;
        color: var(--surface-ink);
        max-width: 980px;
      }}
      .subtitle {{
        margin-top: 8px;
        font-size: 1.08rem;
      }}
      .hero-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 16px;
        min-width: 0;
      }}
      .freshness-pill {{
        display: inline-flex;
        align-items: center;
        gap: 12px;
        background: rgba(255, 252, 244, 0.92);
        border: 1px solid rgba(187, 169, 143, 0.9);
        border-radius: 18px;
        padding: 12px 14px;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
      }}
      .freshness-dot {{
        width: 12px;
        height: 12px;
        border-radius: 999px;
        background: var(--accent);
        box-shadow: 0 0 0 7px rgba(141, 63, 47, 0.10);
      }}
      .freshness-label {{
        font-family: "Avenir Next Condensed", "Franklin Gothic Medium", sans-serif;
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: var(--signal);
      }}
      .freshness-time {{
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
        font-weight: 700;
        font-size: 1rem;
        color: var(--surface-ink);
      }}
      .meta-pill,
      .badge {{
        background: rgba(255, 252, 245, 0.94);
        border: 1px solid rgba(187, 169, 143, 0.72);
        border-radius: 999px;
        padding: 6px 11px;
        font-size: 0.78rem;
        color: var(--ink-soft);
      }}
      .meta-pill {{
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
      }}
      .search-shell {{
        margin-top: 18px;
        display: grid;
        gap: 10px;
      }}
      .desk-controls {{
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: 12px;
      }}
      .search-field {{
        display: grid;
        gap: 8px;
        max-width: 860px;
      }}
      .advanced-search {{
        background: rgba(255, 252, 247, 0.72);
        border: 1px solid rgba(187, 169, 143, 0.76);
        border-radius: 22px;
        padding: 12px 14px 14px;
      }}
      .advanced-search summary {{
        list-style: none;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 10px;
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
        font-weight: 600;
        color: var(--surface-ink);
      }}
      .advanced-search summary::-webkit-details-marker {{
        display: none;
      }}
      .advanced-search summary::before {{
        content: "+";
        display: inline-grid;
        place-items: center;
        width: 24px;
        height: 24px;
        border-radius: 999px;
        background: rgba(31, 91, 137, 0.12);
        color: var(--signal);
        font-weight: 700;
      }}
      .advanced-search[open] summary::before {{
        content: "−";
      }}
      .advanced-search-note {{
        margin: 6px 0 0;
        color: var(--ink-soft);
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
        font-size: 0.92rem;
      }}
      .advanced-search-body {{
        display: grid;
        gap: 12px;
        margin-top: 12px;
      }}
      .search-label {{
        font-family: "Avenir Next Condensed", "Franklin Gothic Medium", sans-serif;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.14em;
        color: var(--signal);
      }}
      .search-input {{
        width: 100%;
        border: 1px solid rgba(187, 169, 143, 0.86);
        border-radius: 18px;
        padding: 15px 16px;
        font-size: 1rem;
        color: var(--ink);
        background: rgba(255, 252, 247, 0.97);
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
      }}
      .search-input::placeholder {{
        color: var(--muted);
      }}
      .chip-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }}
      .structured-filters {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 10px;
      }}
      .filter-group {{
        display: grid;
        gap: 6px;
      }}
      .filter-label {{
        font-family: "Avenir Next Condensed", "Franklin Gothic Medium", sans-serif;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: var(--muted);
      }}
      .filter-chip,
      .sort-select,
      .view-button,
      .filter-select {{
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
        font-size: 0.86rem;
      }}
      .filter-chip {{
        border-radius: 999px;
        padding: 10px 13px;
        border: 1px solid rgba(187, 169, 143, 0.88);
        background: rgba(255, 252, 247, 0.96);
        color: var(--surface-ink);
        cursor: pointer;
        white-space: nowrap;
      }}
      .filter-chip:hover,
      .sort-select:hover,
      .view-button:hover,
      .filter-select:hover {{
        background: var(--accent-soft);
        text-decoration: none;
      }}
      .filter-select {{
        border: 1px solid rgba(187, 169, 143, 0.88);
        background: rgba(255, 252, 247, 0.96);
        border-radius: 14px;
        padding: 10px 12px;
        color: var(--ink);
      }}
      .search-status {{
        font-size: 0.9rem;
      }}
      .sort-bar {{
        display: flex;
        justify-content: flex-end;
        margin: 6px 0 14px;
      }}
      .sort-control {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
        color: var(--muted);
        font-size: 0.86rem;
      }}
      .sort-select {{
        border: 1px solid rgba(187, 169, 143, 0.88);
        background: rgba(255, 252, 247, 0.96);
        border-radius: 999px;
        padding: 8px 12px;
        color: var(--ink);
      }}
      .view-shell {{
        position: sticky;
        top: 12px;
        z-index: 20;
        margin-top: 16px;
        background: rgba(255, 252, 247, 0.96);
        border: 1px solid rgba(187, 169, 143, 0.88);
        border-radius: 22px;
        box-shadow: 0 18px 36px rgba(28, 20, 12, 0.10);
        padding: 12px 14px;
      }}
      .view-switcher {{
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }}
      .view-button {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border-radius: 999px;
        padding: 9px 14px;
        background: rgba(255, 255, 255, 0.76);
        border: 1px solid rgba(187, 169, 143, 0.76);
        color: var(--ink-soft);
        font-weight: 700;
        white-space: nowrap;
        cursor: pointer;
      }}
      .view-button.active {{
        background: rgba(31, 91, 137, 0.12);
        color: var(--signal);
        border-color: rgba(31, 91, 137, 0.28);
      }}
      .view-caption {{
        margin: 10px 2px 0;
        color: var(--muted);
        font-size: 0.84rem;
      }}
      .lead-rail {{
        margin-top: 18px;
        display: grid;
        gap: 16px;
      }}
      .lead-rail-grid {{
        display: grid;
        gap: 14px;
      }}
      .lead-rail-copy {{
        padding: 2px 4px 0;
      }}
      .lead-rail-copy h2 {{
        margin-bottom: 8px;
        font-size: clamp(1.9rem, 3.2vw, 2.8rem);
        line-height: 1.02;
        color: var(--surface-ink);
      }}
      .lead-rail-copy p {{
        margin: 0;
        font-size: 0.98rem;
        color: var(--ink-soft);
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
        max-width: 52rem;
      }}
      .lead-rail-cards {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(min(240px, 100%), 1fr));
        gap: 16px;
      }}
      .lead-story-card {{
        background:
          linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0)),
          linear-gradient(160deg, #152536, #1c3550 62%, #234465 100%);
        color: #f7f3eb;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 24px;
        padding: 18px 18px 16px;
        box-shadow: 0 20px 42px rgba(28, 20, 12, 0.18);
        min-height: 100%;
        display: flex;
        flex-direction: column;
      }}
      .lead-story-card.feature {{
        padding: 24px 24px 20px;
      }}
      .lead-story-card .eyebrow,
      .lead-story-card p,
      .lead-story-card a,
      .lead-story-card .meta-inline {{
        color: inherit;
      }}
      .lead-story-card .eyebrow {{
        color: rgba(247, 243, 235, 0.72);
      }}
      .lead-story-card h3 {{
        font-size: 1.34rem;
        line-height: 1.08;
      }}
      .lead-story-card.feature h3 {{
        font-size: 2rem;
      }}
      .lead-story-card .badge {{
        background: rgba(255,255,255,0.08);
        color: rgba(248, 243, 235, 0.88);
        border-color: rgba(255,255,255,0.12);
      }}
      .lead-story-card .reference-links {{
        margin-top: auto;
        padding-top: 14px;
      }}
      .lead-story-card .reference-link {{
        background: rgba(255,253,248,0.98);
        color: var(--surface-ink);
        border-color: rgba(187, 169, 143, 0.72);
      }}
      .lead-story-card .reference-link::before {{
        color: var(--accent);
      }}
      .reader-views {{
        margin-top: 24px;
        display: grid;
        gap: 26px;
      }}
      .reader-view {{
        display: grid;
        gap: 18px;
      }}
      .view-intro {{
        padding: 0 4px;
      }}
      .view-intro h2 {{
        margin-bottom: 6px;
        font-size: 1.85rem;
        color: var(--surface-ink);
      }}
      .panel-grid,
      .briefing-grid,
      .layout {{
        display: grid;
        gap: 22px;
      }}
      .panel-grid {{
        grid-template-columns: minmax(0, 1.3fr) minmax(300px, 0.85fr);
      }}
      .briefing-grid {{
        grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.9fr);
      }}
      .layout {{
        grid-template-columns: minmax(0, 1.8fr) minmax(320px, 0.92fr);
        margin-top: 10px;
      }}
      .panel-stack,
      .briefing-stack,
      .stack,
      .secondary-priority-grid {{
        display: grid;
        gap: 18px;
      }}
      .panel {{
        background: linear-gradient(180deg, rgba(255,253,248,0.98), rgba(248,243,233,0.98));
        border: 1px solid rgba(187, 169, 143, 0.85);
        border-radius: 28px;
        box-shadow: var(--shadow);
        padding: 24px;
      }}
      .feature-panel {{
        background:
          linear-gradient(180deg, rgba(255,255,255,0.42), rgba(255,255,255,0)),
          linear-gradient(180deg, rgba(248,243,233,1), rgba(242,235,222,1));
      }}
      .utility-panel {{
        background: linear-gradient(180deg, rgba(248,243,233,0.98), rgba(240,232,220,0.96));
      }}
      .panel h2 {{
        font-size: 1.45rem;
        margin-bottom: 14px;
        color: var(--surface-ink);
      }}
      .lead-briefing-grid {{
        display: grid;
        grid-template-columns: minmax(0, 1.22fr) minmax(280px, 0.78fr);
        gap: 16px;
      }}
      .executive-list {{
        margin: 0;
        padding-left: 22px;
        display: grid;
        gap: 12px;
      }}
      .executive-list li {{
        padding-left: 2px;
      }}
      .story-grid,
      .topic-grid,
      .priority-grid,
      .compact-grid,
      .paper-grid,
      .historical-grid,
      .region-grid,
      .reference-grid {{
        display: grid;
        gap: 16px;
      }}
      .story-grid,
      .reference-grid {{
        grid-template-columns: repeat(auto-fit, minmax(min(240px, 100%), 1fr));
      }}
      .story-card,
      .topic-card,
      .priority-card,
      .compact-card,
      .paper-card,
      .historical-card,
      .region-card,
      .reference-card {{
        background: var(--paper);
        border: 1px solid rgba(187, 169, 143, 0.68);
        border-radius: 22px;
        padding: 18px 18px 16px;
        box-shadow: 0 12px 26px rgba(49, 36, 22, 0.06);
      }}
      .story-card {{
        border-top: 5px solid var(--signal);
      }}
      .topic-card {{
        border-top: 5px solid var(--accent);
      }}
      .priority-card {{
        border-top: 5px solid var(--signal);
      }}
      .feature-priority {{
        border-top: 0;
        background:
          linear-gradient(180deg, rgba(31, 91, 137, 0.08), rgba(255,255,255,0)),
          linear-gradient(180deg, rgba(255,253,248,1), rgba(243,236,225,1));
        border-radius: 24px;
        padding: 22px;
      }}
      .feature-priority h3 {{
        font-size: 1.64rem;
        line-height: 1.06;
      }}
      .secondary-priority {{
        padding: 15px 16px 14px;
      }}
      .secondary-priority h3 {{
        font-size: 1.02rem;
      }}
      .region-card {{
        background:
          linear-gradient(180deg, rgba(31, 91, 137, 0.06), rgba(255,255,255,0)),
          var(--paper);
      }}
      .reference-card {{
        background:
          linear-gradient(180deg, rgba(181, 138, 49, 0.10), rgba(255,255,255,0)),
          var(--paper);
      }}
      .cluster-toggle {{
        margin-top: 14px;
        border-top: 1px solid rgba(187, 169, 143, 0.55);
        padding-top: 12px;
      }}
      .cluster-toggle summary,
      .archive-summary {{
        cursor: pointer;
        list-style: none;
        display: inline-flex;
        align-items: center;
        gap: 10px;
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
        font-weight: 700;
        color: var(--surface-ink);
      }}
      .cluster-toggle summary::-webkit-details-marker {{
        display: none;
      }}
      .cluster-toggle summary::before {{
        content: "▸";
        font-size: 0.92rem;
        transition: transform 0.16s ease;
      }}
      .cluster-toggle[open] summary::before {{
        transform: rotate(90deg);
      }}
      .cluster-list,
      .region-list,
      .archive-links {{
        margin: 12px 0 0;
        padding: 0;
        list-style: none;
        display: grid;
        gap: 10px;
      }}
      .cluster-list li,
      .region-list li {{
        border-top: 1px solid rgba(187, 169, 143, 0.44);
        padding-top: 10px;
      }}
      .cluster-item-title {{
        display: block;
        font-weight: 700;
        margin-bottom: 4px;
      }}
      .story-card h3,
      .topic-card h3,
      .priority-card h3,
      .paper-card h3,
      .reference-card h3 {{
        font-size: 1.08rem;
        margin-bottom: 8px;
        color: var(--surface-ink);
      }}
      .item-meta,
      .meta-inline,
      .reference-links {{
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
      }}
      .item-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 10px 0 0;
      }}
      .badge.accent {{
        background: var(--accent-soft);
        color: var(--accent);
        border-color: rgba(141, 63, 47, 0.24);
      }}
      .badge.signal {{
        background: var(--signal-soft);
        color: var(--signal);
        border-color: rgba(31, 91, 137, 0.20);
      }}
      .badge.local {{
        background: var(--gold-soft);
        color: #7d5b0c;
        border-color: rgba(181, 138, 49, 0.26);
      }}
      .bullet-list {{
        margin: 10px 0 0;
        padding-left: 18px;
      }}
      .bullet-list li + li,
      .reference-notes li + li {{
        margin-top: 6px;
      }}
      .reference-notes {{
        margin: 12px 0 0;
        padding-left: 18px;
      }}
      .reference-links {{
        margin: 14px 0 0;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }}
      .reference-link {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border-radius: 999px;
        padding: 7px 12px;
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
        font-size: 0.8rem;
        border: 1px solid rgba(187, 169, 143, 0.72);
        background: rgba(255,253,248,0.96);
        color: var(--surface-ink);
      }}
      .reference-link::before {{
        content: "Field guide";
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 0.64rem;
        color: var(--accent);
      }}
      .compact-card p,
      .paper-card p,
      .historical-card p,
      .priority-card p,
      .topic-card p,
      .story-card p {{
        margin: 8px 0 0;
      }}
      .compact-card,
      .paper-card,
      .historical-card {{
        padding: 14px 14px 13px;
      }}
      .side-section + .side-section {{
        margin-top: 18px;
      }}
      .archive-block {{
        display: grid;
        gap: 12px;
      }}
      .archive-toplink {{
        display: inline-flex;
        align-items: center;
        gap: 10px;
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
        font-weight: 700;
        color: var(--surface-ink);
      }}
      .archive-year,
      .archive-month {{
        border-top: 1px solid rgba(187, 169, 143, 0.5);
        padding-top: 10px;
      }}
      .archive-link {{
        display: flex;
        justify-content: space-between;
        gap: 10px;
        align-items: baseline;
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
      }}
      .archive-link time {{
        color: var(--surface-ink);
        font-weight: 600;
      }}
      .archive-current {{
        font-size: 0.74rem;
        color: var(--accent);
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}
      .footer-note {{
        margin-top: 26px;
        font-size: 0.92rem;
        text-align: center;
      }}
      @media (max-width: 1240px) {{
        .briefing-grid,
        .lead-briefing-grid,
        .panel-grid,
        .layout {{
          grid-template-columns: 1fr;
        }}
      }}
      @media (max-width: 1100px) {{
        .briefing-grid,
        .lead-briefing-grid,
        .story-grid,
        .reference-grid,
        .panel-grid,
        .layout {{
          grid-template-columns: 1fr;
        }}
        .desk-bar {{
          align-items: stretch;
        }}
      }}
      @media (max-width: 760px) {{
        .page {{
          padding: 16px 14px 44px;
        }}
        .hero,
        .panel,
        .lead-story-card {{
          padding: 18px;
          border-radius: 22px;
        }}
        .brand-row {{
          grid-template-columns: 1fr;
        }}
        .brand-lockup {{
          width: 88px;
          height: 88px;
        }}
        h1 {{
          font-size: clamp(2rem, 12vw, 3.2rem);
        }}
        .desk-bar,
        .desk-tools {{
          display: grid;
          justify-items: start;
        }}
        .lead-rail-cards,
        .structured-filters {{
          grid-template-columns: 1fr;
        }}
        .chip-row,
        .view-switcher {{
          flex-wrap: nowrap;
          overflow-x: auto;
          padding-bottom: 2px;
          -webkit-overflow-scrolling: touch;
        }}
        .filter-chip,
        .view-button {{
          flex: 0 0 auto;
        }}
        .hero-meta {{
          gap: 8px;
        }}
        .meta-pill,
        .badge {{
          font-size: 0.74rem;
          padding: 6px 10px;
        }}
        .site-nav-shell {{
          padding: 16px;
          border-radius: 20px;
          flex-direction: column;
          align-items: flex-start;
        }}
        .view-shell {{
          position: static;
        }}
      }}
    </style>
  </head>
  <body>
    <main class="page">
      {render_global_site_nav()}
      <section class="hero">
        <div class="desk-bar">
          <div>
            <p class="desk-kicker">Morning infectious disease desk</p>
            <p class="desk-note">A source-first outbreak and epidemiology front page built for daily scan speed, not generic dashboard browsing.</p>
          </div>
          <div class="desk-tools">
            <div class="freshness-pill" aria-label="Last updated">
              <span class="freshness-dot"></span>
              <div>
                <div class="freshness-label">Last Updated</div>
                <div class="freshness-time">{escape(freshness_label)}</div>
              </div>
            </div>
          </div>
        </div>
        <div class="brand-row">
          <div class="brand-lockup">{render_logo_mark()}</div>
          <div class="brand-text brand-deck">
            <p class="kicker">The Edge of Epidemiology • Infectious disease intelligence desk</p>
            <h1>The Pathogen Dispatch</h1>
            <p class="subtitle">by The Edge of Epidemiology</p>
          </div>
        </div>
        <div class="hero-meta">
          <span class="meta-pill">Date: {escape(target_date.isoformat())}</span>
          <span class="meta-pill">Generated: {escape(generated_at.isoformat(timespec="minutes"))}</span>
          <span class="meta-pill">Search window: {escape(search_window)}</span>
          <span class="meta-pill">Items rendered: {len(sorted_items)}</span>
          {source_health_note}
        </div>
        <div class="search-shell">
          <div class="desk-controls">
            <div class="search-field">
              <label class="search-label" for="reader-search">Search the reader</label>
              <input id="reader-search" class="search-input" type="search" placeholder="Search pathogens, places, dates, outlets, or phrases" />
            </div>
            <details class="advanced-search">
              <summary>Advanced search</summary>
              <p class="advanced-search-note">Open structured filters and quick outbreak shortcuts only when you need them.</p>
              <div class="advanced-search-body">
                <div class="structured-filters" aria-label="Structured filters">
                  {render_structured_filter_controls(filter_options)}
                </div>
                <div class="chip-row" aria-label="Quick filters">
                  <button class="filter-chip" type="button" data-chip-query="official">Official only</button>
                  <button class="filter-chip" type="button" data-chip-query="publisher">Publisher coverage</button>
                  <button class="filter-chip" type="button" data-chip-query="vector-borne">Vector-borne</button>
                  <button class="filter-chip" type="button" data-chip-query="respiratory">Respiratory</button>
                  <button class="filter-chip" type="button" data-chip-query="hemorrhagic">Hemorrhagic</button>
                  <button class="filter-chip" type="button" data-chip-query="vaccine-preventable">Vaccine-preventable</button>
                  <button class="filter-chip" type="button" data-chip-query="occupational environmental">Occupational / environmental</button>
                </div>
              </div>
            </details>
          </div>
          <div id="reader-search-status" class="search-status">Search filters the visible cards on this page and the archive list.</div>
        </div>
      </section>

      <section class="lead-rail" id="lead-outbreak-files">
        <div class="lead-rail-grid">
          <div class="lead-rail-copy">
            <h2>Lead Outbreak Files</h2>
            <p>The top active files reporters should scan first before dropping into the wider desk.</p>
          </div>
          <div class="lead-rail-cards">
            {lead_story_rail}
          </div>
        </div>
      </section>

      <nav class="view-shell" aria-label="Reader sections">
        <div class="view-switcher">{view_switcher}</div>
      </nav>

      <section class="reader-views">
        <section class="reader-view" id="view-briefing" data-view="briefing">
          <div class="view-intro">
            <h2>What Changed Today</h2>
            <p>The front page for the day: one short scan, one lead strip, and the secondary readings worth opening next.</p>
          </div>
          <div class="briefing-grid">
            <div class="briefing-stack">
              <section class="panel utility-panel" id="executive-scan">
                <h2>Front-Page Scan</h2>
                <ol class="executive-list">{executive_blocks}</ol>
              </section>
              <section class="panel feature-panel" id="highest-priority">
                <h2>Lead News Strip</h2>
                <div class="lead-briefing-grid">
                  <div>{lead_priority_block}</div>
                  <div>
                    {render_sort_bar("highest-priority-supporting")}
                    <div id="highest-priority-supporting" class="secondary-priority-grid sortable-grid" data-default-sort="newest">{supporting_priority_blocks}</div>
                  </div>
                </div>
              </section>
            </div>
            <aside class="panel-stack">
              <section class="panel utility-panel side-section" id="other-readings">
                <h2>Secondary Coverage</h2>
                {render_sort_bar("other-readings-grid")}
                <div id="other-readings-grid" class="compact-grid sortable-grid" data-default-sort="newest">{other_blocks}</div>
              </section>
            </aside>
          </div>
        </section>

        <section class="reader-view" id="view-tracking" data-view="tracking" hidden>
          <div class="view-intro">
            <h2>Global Watch</h2>
            <p>Major outbreaks, regional developments, and the cross-border signals worth following now.</p>
          </div>
          <div class="layout">
            <div class="stack">
              <section class="panel feature-panel" id="major-story-files">
                <h2>Major Story Files</h2>
                {render_sort_bar("major-story-files-grid")}
                <div id="major-story-files-grid" class="story-grid sortable-grid" data-default-sort="newest">{major_story_blocks}</div>
              </section>
              <section class="panel" id="story-updates">
                <h2>What Changed In Active Files</h2>
                <div class="story-grid">{story_blocks}</div>
              </section>
              <section class="panel" id="regional-watch">
                <h2>Regional Watch</h2>
                {render_sort_bar("regional-watch-grid", source_label="Region A-Z")}
                <div id="regional-watch-grid" class="region-grid sortable-grid" data-default-sort="newest">{region_blocks}</div>
              </section>
            </div>
            <aside class="stack">
              <section class="panel side-section" id="major-topics">
                <h2>Outbreak Clusters</h2>
                <div class="topic-grid">{topic_blocks}</div>
              </section>
            </aside>
          </div>
        </section>

        <section class="reader-view" id="view-reference" data-view="reference" hidden>
          <div class="view-intro">
            <h2>Research + Reference</h2>
            <p>The evergreen layer: disease intelligence sheets, outbreak backstory, literature worth saving, and the historical corner.</p>
          </div>
          <div class="layout">
            <div class="stack">
              <section class="panel utility-panel" id="reference-desk-rail">
                <h2>Disease Intelligence Desk</h2>
                <div class="reference-grid">{reference_desk_blocks}</div>
              </section>
              <section class="panel" id="outbreak-reference">
                <h2>Last Major Outbreaks On File</h2>
                <div class="reference-grid">{outbreak_reference_blocks}</div>
              </section>
            </div>
            <aside class="stack">
              <section class="panel utility-panel side-section" id="papers-worth-saving">
                <h2>Papers Worth Saving</h2>
                <div class="paper-grid">{paper_blocks}</div>
              </section>
              <section class="panel utility-panel side-section" id="historical-corner">
                <h2>Historical Epi / Weird Corner</h2>
                <div class="historical-grid">{historical_blocks}</div>
              </section>
            </aside>
          </div>
        </section>

        <section class="reader-view" id="view-archive" data-view="archive" hidden>
          <div class="view-intro">
            <h2>Archive + Backfile</h2>
            <p>The browseable backfile for prior briefings, story continuity, and operational source-health context.</p>
          </div>
          <div class="panel-grid">
            <section class="panel" id="dossier-archive">
              <h2>Dossier Archive</h2>
              {archive_block}
            </section>
            <section class="panel utility-panel">
              <h2>Operational Desk Health</h2>
              {desk_health_panel}
            </section>
            <section class="panel utility-panel">
              <h2>Archive Desk Notes</h2>
              <div class="compact-grid">
                <article class="compact-card" data-search="archive latest current dated html markdown browse chronology">
                  <div class="eyebrow">Why use the backfile</div>
                  <p>Use the archive when you care about when a story entered the dossier, how the frame changed, or what the desk looked like on a specific date.</p>
                </article>
                <article class="compact-card" data-search="search filter archive reader outlet pathogen date region">
                  <div class="eyebrow">Search behavior</div>
                  <p>Search still spans archive links and live cards together, so you can move between today’s desk and the backfile without changing tools.</p>
                </article>
              </div>
            </section>
          </div>
        </section>
      </section>

      <p class="footer-note">The Edge of Epidemiology infectious disease desk.</p>
    </main>
    <script>
      const searchInput = document.getElementById("reader-search");
      const searchStatus = document.getElementById("reader-search-status");
      const searchableNodes = Array.from(document.querySelectorAll("[data-search]"));
      const archiveNodes = Array.from(document.querySelectorAll("[data-archive-search]"));
      const viewButtons = Array.from(document.querySelectorAll("[data-view-target]"));
      const filterChips = Array.from(document.querySelectorAll("[data-chip-query]"));
      const structuredFilters = Array.from(document.querySelectorAll("[data-structured-filter]"));
      const readerViews = Array.from(document.querySelectorAll(".reader-view"));
      const readerSorters = Array.from(document.querySelectorAll("[data-sort-target]"));

      function setActiveView(viewName) {{
        viewButtons.forEach((button) => {{
          const active = button.dataset.viewTarget === viewName;
          button.classList.toggle("active", active);
          button.setAttribute("aria-pressed", active ? "true" : "false");
        }});
        readerViews.forEach((view) => {{
          view.hidden = view.dataset.view !== viewName;
        }});
      }}

      function applyReaderSearch() {{
        const query = (searchInput.value || "").trim().toLowerCase();
        const filterState = Object.fromEntries(structuredFilters.map((node) => [node.dataset.structuredFilter, (node.value || "").trim().toLowerCase()]));
        let visibleCards = 0;
        let visibleArchive = 0;

        if (query) {{
          readerViews.forEach((view) => {{
            view.hidden = false;
          }});
          viewButtons.forEach((button) => {{
            button.classList.remove("active");
            button.setAttribute("aria-pressed", "false");
          }});
        }} else {{
          const activeButton = document.querySelector(".view-button.active");
          setActiveView((activeButton && activeButton.dataset.viewTarget) || "briefing");
        }}

        searchableNodes.forEach((node) => {{
          const haystack = (node.dataset.search || "").toLowerCase();
          const show = (!query || haystack.includes(query)) && matchesStructuredFilters(node, filterState);
          node.hidden = !show;
          if (show) {{
            visibleCards += 1;
          }}
        }});

        archiveNodes.forEach((node) => {{
          const haystack = (node.dataset.archiveSearch || "").toLowerCase();
          const show = (!query || haystack.includes(query)) && matchesStructuredFilters(node, filterState);
          node.hidden = !show;
          if (show) {{
            visibleArchive += 1;
          }}
        }});

        if (!query) {{
          searchStatus.textContent = "Search and structured filters control the visible cards on this page and the archive list.";
          return;
        }}
        searchStatus.textContent = `${{visibleCards}} on-page match(es), ${{visibleArchive}} archive link(s).`;
      }}

      function matchesStructuredFilters(node, filters) {{
        const region = filters.region || "";
        const sourceKind = filters.sourceKind || "";
        const pathogen = filters.pathogen || "";
        const setting = filters.setting || "";
        const linkQuality = filters.linkQuality || "";
        const access = filters.access || "";
        const evidenceType = filters.evidenceType || "";
        const storyStatus = filters.storyStatus || "";
        const dateWindow = filters.dateWindow || "";
        const officialOnly = filters.officialOnly || "";

        if (region && (node.dataset.region || "") !== region) return false;
        if (sourceKind && !(node.dataset.sourceKind || "").split(" ").includes(sourceKind)) return false;
        if (pathogen && !(node.dataset.pathogen || "").split(" ").includes(pathogen)) return false;
        if (setting && !(node.dataset.setting || "").split(" ").includes(setting)) return false;
        if (linkQuality && (node.dataset.linkQuality || "") !== linkQuality) return false;
        if (access && (node.dataset.access || "") !== access) return false;
        if (evidenceType && (node.dataset.evidenceType || "") !== evidenceType) return false;
        if (storyStatus && (node.dataset.storyStatus || "") !== storyStatus) return false;
        if (officialOnly === "official" && node.dataset.official !== "true") return false;
        if (dateWindow) {{
          const ageDays = Number(node.dataset.ageDays || "9999");
          const threshold = Number(dateWindow);
          if (!Number.isNaN(threshold) && ageDays > threshold) return false;
        }}
        return true;
      }}

      function sortSortableGrid(targetId, mode) {{
        const container = document.getElementById(targetId);
        if (!container) return;
        const cards = Array.from(container.querySelectorAll(".sortable-card"));
        const normalizedMode = mode || container.dataset.defaultSort || "newest";
        cards.sort((left, right) => {{
          if (normalizedMode === "oldest") {{
            return Number(left.dataset.sortTs || 0) - Number(right.dataset.sortTs || 0);
          }}
          if (normalizedMode === "source") {{
            const sourceCompare = (left.dataset.sortSource || "").localeCompare(right.dataset.sortSource || "");
            if (sourceCompare !== 0) return sourceCompare;
            return (left.dataset.sortTitle || "").localeCompare(right.dataset.sortTitle || "");
          }}
          return Number(right.dataset.sortTs || 0) - Number(left.dataset.sortTs || 0);
        }});
        cards.forEach((card) => container.appendChild(card));
      }}

      viewButtons.forEach((button) => {{
        button.addEventListener("click", () => {{
          searchInput.value = "";
          const nextView = button.dataset.viewTarget || "briefing";
          setActiveView(nextView);
          window.location.hash = `view-${{nextView}}`;
          applyReaderSearch();
          window.scrollTo({{ top: 0, behavior: "smooth" }});
        }});
      }});

      const initialHash = window.location.hash.replace("#", "");
      if (initialHash.startsWith("view-")) {{
        const initialView = initialHash.replace("view-", "");
        setActiveView(initialView);
      }} else {{
        setActiveView("briefing");
      }}
      searchInput.addEventListener("input", applyReaderSearch);
      filterChips.forEach((chip) => {{
        chip.addEventListener("click", () => {{
          searchInput.value = chip.dataset.chipQuery || "";
          applyReaderSearch();
        }});
      }});
      structuredFilters.forEach((control) => {{
        control.addEventListener("change", applyReaderSearch);
      }});
      readerSorters.forEach((select) => {{
        const targetId = select.dataset.sortTarget;
        sortSortableGrid(targetId, select.value);
        select.addEventListener("change", () => sortSortableGrid(targetId, select.value));
      }});
      window.addEventListener("hashchange", () => {{
        const nextHash = window.location.hash.replace("#", "");
        if (nextHash.startsWith("view-")) {{
          setActiveView(nextHash.replace("view-", ""));
          applyReaderSearch();
        }}
      }});
    </script>
  </body>
</html>
"""


def render_executive_item(item: Item) -> str:
    attrs = render_filter_attrs_for_item(item)
    return (
        f'<li class="searchable-row" {attrs} data-search="{escape_attr(search_text(item.title, item.summary, item.display_source, item.category, format_timestamp(item.published_at)))}">'
        f'<a href="{escape_attr(item.url)}">{escape(item.title)}</a> '
        f'<span class="meta-inline">({escape(item.display_source)}; {escape(format_timestamp(item.published_at))}; '
        f'{escape(item.category)}; relevance {item.relevance_score}/5)</span></li>'
    )


def render_global_site_nav() -> str:
    return (
        '<header class="site-nav-shell">'
        '<div class="site-nav-brand">'
        '<div class="eyebrow">The Pathogen Dispatch</div>'
        '<p class="site-nav-note">Unified desk navigation</p>'
        '</div>'
        '<nav class="site-nav-links" aria-label="Site navigation">'
        '<a class="site-nav-link" href="/">Edge home</a>'
        '<a class="site-nav-link active" href="#view-briefing">Latest briefing</a>'
        '<a class="site-nav-link" href="#view-tracking">Global watch</a>'
        '<a class="site-nav-link" href="#view-reference">Research + reference</a>'
        '<a class="site-nav-link" href="#view-archive">Archive + backfile</a>'
        '<a class="site-nav-link" href="./index.html">Site index</a>'
        '</nav>'
        '</header>'
    )


def render_view_switcher() -> str:
    links = [
        ("Briefing", "briefing"),
        ("Tracking", "tracking"),
        ("Reference", "reference"),
        ("Archive", "archive"),
    ]
    return "".join(
        f'<li><button class="view-button{" active" if target == "briefing" else ""}" type="button" data-view-target="{escape_attr(target)}" aria-pressed="{"true" if target == "briefing" else "false"}">{escape(label)}</button></li>'
        for label, target in links
    )


def render_story_update(update: StoryUpdate, story_record: dict | None = None) -> str:
    bullets = "".join(f"<li>{escape(bullet)}</li>" for bullet in update.bullets)
    new_story = (
        f'<p><span class="badge signal">Newly tracked</span> {update.item_count} item(s) across {update.source_count} source(s).</p>'
        if update.is_new_story
        else ""
    )
    story_link = (
        f'<p><a href="{escape_attr(story_record.get("story_url", ""))}">Open story file</a></p>'
        if story_record and story_record.get("story_url")
        else ""
    )
    attrs = render_filter_attrs_for_story_record(story_record)
    return (
        f'<article class="story-card" {attrs} data-search="{escape_attr(search_text(update.topic_name, update.lead_title, update.lead_source, " ".join(update.bullets)))}">'
        f'<div class="eyebrow">Outbreak File</div><h3>{escape(update.topic_name)}</h3>'
        f'<p><a href="{escape_attr(update.lead_url)}">{escape(update.lead_title)}</a> '
        f'<span class="meta-inline">({escape(update.lead_source)})</span></p>'
        f"{new_story}{story_link}<ul class=\"bullet-list\">{bullets}</ul></article>"
    )


def render_topic_block(topic_name: str, items: list[Item], story_record: dict | None = None) -> str:
    top_items = sorted(
        items,
        key=lambda item: (item.relevance_score, 1 if item.official else 0, sortable_datetime(item.published_at)),
        reverse=True,
    )
    lead = top_items[0]
    official_count = sum(1 for item in items if item.official)
    source_count = len({item.display_source for item in items})
    synopsis = build_topic_synopsis(topic_name, top_items)
    cluster_list = render_topic_item_list(top_items)
    story_link = (
        f'<p><a href="{escape_attr(story_record.get("story_url", ""))}">Open story file</a></p>'
        if story_record and story_record.get("story_url")
        else ""
    )
    attrs = render_filter_attrs_for_story_record(story_record, fallback_items=top_items)
    return (
        f'<article class="topic-card" {attrs} data-search="{escape_attr(search_text(topic_name, lead.title, synopsis, " ".join(item.display_source for item in top_items[:8])))}">'
        f'<div class="eyebrow">Outbreak Cluster</div><h3>{escape(topic_name)}</h3>'
        f'<p><a href="{escape_attr(lead.url)}">{escape(lead.title)}</a></p>'
        f'<div class="item-meta"><span class="badge">{len(items)} item(s)</span>'
        f'<span class="badge">{source_count} source(s)</span>'
        f'<span class="badge">{official_count} official</span></div>'
        f'<p>{escape(synopsis)}</p>'
        f'{story_link}'
        f'<details class="cluster-toggle"><summary>Open cluster items</summary><ol class="cluster-list">{cluster_list}</ol></details>'
        '</article>'
    )


def render_major_story_card(story: dict) -> str:
    related_reference_links = "".join(
        f'<a class="reference-link" href="{escape_attr(reference.get("reference_url", ""))}">{escape(reference.get("name", ""))}</a>'
        for reference in story.get("related_references", [])[:3]
    )
    related_reference_block = f'<div class="reference-links">{related_reference_links}</div>' if related_reference_links else ""
    attrs = render_filter_attrs_for_story_record(story)
    return (
        f'<article class="story-card sortable-card" {attrs} data-sort-ts="{sort_timestamp_value(story.get("latest_updated_at") or story.get("updated_at"))}" data-sort-source="{escape_attr(story.get("display_title", ""))}" data-sort-title="{escape_attr(story.get("display_title", ""))}" data-search="{escape_attr(search_text(story.get("display_title", ""), story.get("latest_update_summary", ""), " ".join(story.get("publisher_names", []))))}">'
        f'<div class="eyebrow">Lead outbreak file</div>'
        f'<h3><a href="{escape_attr(story.get("story_url", ""))}">{escape(story.get("display_title", ""))}</a></h3>'
        f'<div class="item-meta"><span class="badge">{story.get("item_count", 0)} item(s)</span><span class="badge">{story.get("source_count", 0)} source(s)</span><span class="badge">{len(story.get("official_item_ids", []))} official</span><span class="badge">{escape(story.get("current_status_summary", "Unknown"))}</span></div>'
        f'<p>{escape(story.get("latest_update_summary", "No latest summary available."))}</p>'
        f'{related_reference_block}'
        '</article>'
    )


def render_lead_story_rail_card(story: dict, index: int) -> str:
    feature_class = " feature" if index == 0 else ""
    related_reference_links = "".join(
        f'<a class="reference-link" href="{escape_attr(reference.get("reference_url", ""))}">{escape(reference.get("name", ""))}</a>'
        for reference in story.get("related_references", [])[:2]
    )
    related_reference_block = f'<div class="reference-links">{related_reference_links}</div>' if related_reference_links else ""
    eyebrow = "Lead outbreak file" if index == 0 else "Live story file"
    attrs = render_filter_attrs_for_story_record(story)
    return (
        f'<article class="lead-story-card{feature_class}" {attrs} data-search="{escape_attr(search_text(story.get("display_title", ""), story.get("latest_update_summary", ""), " ".join(story.get("publisher_names", []))))}">'
        f'<div class="eyebrow">{escape(eyebrow)}</div>'
        f'<h3><a href="{escape_attr(story.get("story_url", ""))}">{escape(story.get("display_title", ""))}</a></h3>'
        f'<p>{escape(story.get("latest_update_summary", "No latest summary available."))}</p>'
        f'<div class="item-meta"><span class="badge">{story.get("item_count", 0)} item(s)</span><span class="badge">{story.get("source_count", 0)} source(s)</span><span class="badge">{len(story.get("official_item_ids", []))} official</span></div>'
        f'{related_reference_block}'
        '</article>'
    )


def render_reference_desk_card(reference: dict) -> str:
    categories = "".join(f'<span class="badge">{escape(category)}</span>' for category in reference.get("categories", [])[:3])
    related_story_links = "".join(
        f'<a class="reference-link" href="{escape_attr(story.get("story_url", ""))}">{escape(story.get("display_title", ""))}</a>'
        for story in reference.get("related_stories", [])[:2]
    )
    related_story_block = f'<div class="reference-links">{related_story_links}</div>' if related_story_links else ""
    attrs = render_filter_attrs_for_reference_record(reference)
    return (
        f'<article class="reference-card" {attrs} data-search="{escape_attr(search_text(reference.get("name", ""), reference.get("pathogen", ""), reference.get("transmission", ""), " ".join(reference.get("categories", []))))}">'
        f'<div class="eyebrow">Reference</div>'
        f'<h3><a href="{escape_attr(reference.get("reference_url", ""))}">{escape(reference.get("name", ""))}</a></h3>'
        f'<p><strong>Pathogen:</strong> {escape(reference.get("pathogen", ""))}</p>'
        f'<p><strong>Transmission:</strong> {escape(reference.get("transmission", ""))}</p>'
        f'<div class="item-meta">{categories}</div>'
        f'<p>{escape(reference.get("why_reporters_care", ""))}</p>'
        f'<p class="meta-inline"><strong>Desk note:</strong> {escape(reference.get("research_caveats") or reference.get("surveillance_note", ""))}</p>'
        f'{related_story_block}'
        '</article>'
    )


def render_topic_item_list(items: list[Item]) -> str:
    rows: list[str] = []
    for item in items:
        official_badge = ' <span class="badge signal">Official</span>' if item.official else ""
        rows.append(
            "<li>"
            f'<a class="cluster-item-title" href="{escape_attr(item.url)}">{escape(item.title)}</a>'
            f'<div class="item-meta"><span class="badge">{escape(item.display_source)}</span>'
            f'<span class="badge">{escape(format_timestamp(item.published_at))}</span>'
            f'<span class="badge">{escape(item.category)}</span>{official_badge}</div>'
            f'<p>{escape(item.summary)}</p>'
            "</li>"
        )
    return "".join(rows)


def render_priority_card(item: Item) -> str:
    doi_line = f'<p><strong>DOI:</strong> {escape(item.doi)}</p>' if item.doi else ""
    region_badge = f'<span class="badge">{escape(infer_region(item))}</span>'
    local_badge = '<span class="badge local">Rural / local signal</span>' if has_local_signal(item) else ""
    publisher_tier_badge = render_publisher_tier_badge(item)
    access_badge = render_access_badge(item)
    attrs = render_filter_attrs_for_item(item)
    return (
        f'<article class="priority-card sortable-card" {attrs} data-sort-ts="{sort_timestamp_value(item.published_at.isoformat() if item.published_at else "")}" data-sort-source="{escape_attr(item.publisher_name)}" data-sort-title="{escape_attr(item.title)}" data-search="{escape_attr(search_text(item.title, item.summary, item.display_source, item.category, item.why_it_matters, item.caveats, item.doi or ""))}">'
        f'<div class="eyebrow">{escape(item.category)}</div><h3><a href="{escape_attr(item.url)}">{escape(item.title)}</a></h3>'
        f'<div class="item-meta"><span class="badge accent">{item.relevance_score}/5</span>'
        f'<span class="badge">{escape(item.publisher_name)}</span>{publisher_tier_badge}{access_badge}{region_badge}{local_badge}'
        f'<span class="badge">{escape(format_timestamp(item.published_at))}</span></div>'
        f'<p>{escape(item.summary)}</p>'
        f'<p><strong>Why it matters:</strong> {escape(item.why_it_matters)}</p>'
        f'<p><strong>Caveats:</strong> {escape(item.caveats)}</p>{doi_line}</article>'
    )


def render_feature_priority_card(item: Item) -> str:
    doi_line = f'<p><strong>DOI:</strong> {escape(item.doi)}</p>' if item.doi else ""
    region_badge = f'<span class="badge">{escape(infer_region(item))}</span>'
    local_badge = '<span class="badge local">Rural / local signal</span>' if has_local_signal(item) else ""
    publisher_tier_badge = render_publisher_tier_badge(item)
    access_badge = render_access_badge(item)
    official_badge = '<span class="badge signal">Official source</span>' if item.official else ""
    publisher_badge = f'<span class="badge">{escape(item.publisher_name)}</span>' if item.publisher_name else ""
    attrs = render_filter_attrs_for_item(item)
    return (
        f'<article class="priority-card feature-priority sortable-card" {attrs} data-sort-ts="{sort_timestamp_value(item.published_at.isoformat() if item.published_at else "")}" data-sort-source="{escape_attr(item.publisher_name)}" data-sort-title="{escape_attr(item.title)}" data-search="{escape_attr(search_text(item.title, item.summary, item.display_source, item.category, item.why_it_matters, item.caveats, item.doi or ""))}">'
        f'<div class="eyebrow">Lead file • {escape(item.category)}</div>'
        f'<h3><a href="{escape_attr(item.url)}">{escape(item.title)}</a></h3>'
        f'<div class="item-meta"><span class="badge accent">{item.relevance_score}/5</span>'
        f'{publisher_badge}{publisher_tier_badge}{access_badge}{official_badge}{region_badge}{local_badge}'
        f'<span class="badge">{escape(format_timestamp(item.published_at))}</span></div>'
        f'<p>{escape(item.summary)}</p>'
        f'<p><strong>Why it matters:</strong> {escape(item.why_it_matters)}</p>'
        f'<p><strong>Caveats / uncertainty:</strong> {escape(item.caveats)}</p>'
        f'{doi_line}</article>'
    )


def render_secondary_priority_card(item: Item) -> str:
    region_badge = f'<span class="badge">{escape(infer_region(item))}</span>'
    official_badge = '<span class="badge signal">Official</span>' if item.official else ""
    publisher_badge = f'<span class="badge">{escape(item.publisher_name)}</span>' if item.publisher_name else ""
    doi_line = f'<p><strong>DOI:</strong> {escape(item.doi)}</p>' if item.doi else ""
    attrs = render_filter_attrs_for_item(item)
    return (
        f'<article class="priority-card secondary-priority sortable-card" {attrs} data-sort-ts="{sort_timestamp_value(item.published_at.isoformat() if item.published_at else "")}" data-sort-source="{escape_attr(item.publisher_name)}" data-sort-title="{escape_attr(item.title)}" data-search="{escape_attr(search_text(item.title, item.summary, item.display_source, item.category, item.why_it_matters))}">'
        f'<div class="eyebrow">{escape(item.category)}</div>'
        f'<h3><a href="{escape_attr(item.url)}">{escape(item.title)}</a></h3>'
        f'<div class="item-meta"><span class="badge accent">{item.relevance_score}/5</span>'
        f'{publisher_badge}{official_badge}{region_badge}<span class="badge">{escape(format_timestamp(item.published_at))}</span></div>'
        f'<p>{escape(item.summary)}</p>'
        f'{doi_line}'
        '</article>'
    )


def render_compact_item(item: Item) -> str:
    locality_note = " | Rural / local signal" if has_local_signal(item) else ""
    attrs = render_filter_attrs_for_item(item)
    return (
        f'<article class="compact-card sortable-card" {attrs} data-sort-ts="{sort_timestamp_value(item.published_at.isoformat() if item.published_at else "")}" data-sort-source="{escape_attr(item.publisher_name)}" data-sort-title="{escape_attr(item.title)}" data-search="{escape_attr(search_text(item.title, item.summary, item.display_source, item.category, format_timestamp(item.published_at)))}">'
        f'<div class="eyebrow">Publisher coverage • {escape(item.publisher_name)} | {escape(label_for_publisher_tier(item.publisher_tier))} | {escape(infer_region(item))}{escape(locality_note)} | {escape(format_timestamp(item.published_at))}</div>'
        f'<p><a href="{escape_attr(item.preferred_url)}">{escape(item.title)}</a></p>'
        f'<p>{escape(item.summary)}</p></article>'
    )


def render_paper_card(item: Item) -> str:
    attrs = render_filter_attrs_for_item(item)
    return (
        f'<article class="paper-card" {attrs} data-search="{escape_attr(search_text(item.title, item.summary, item.display_source, item.journal or "", item.doi or ""))}">'
        f'<div class="eyebrow">Research brief • {escape(item.journal or item.display_source)}</div>'
        f'<h3><a href="{escape_attr(item.url)}">{escape(item.title)}</a></h3>'
        f'<p><strong>Evidence type:</strong> {escape(label_for_evidence_type(item.evidence_type))}</p>'
        f'<p><strong>Study design / source:</strong> {escape(item.journal or item.display_source)}</p>'
        f'<p><strong>Main claim:</strong> {escape(item.summary)}</p>'
        f'<p><strong>Why it matters:</strong> {escape(paper_why_it_matters(item))}</p>'
        f'<p><strong>Evidence caveat:</strong> {escape(paper_evidence_caveat(item))}</p>'
        f'<p><strong>DOI:</strong> {escape(item.doi or "Unknown")}</p>'
        f'<p><strong>Abstract:</strong> <a href="{escape_attr(item.abstract_url or item.url)}">{escape(item.abstract_url or item.url)}</a></p></article>'
    )


def render_historical_item(item: Item) -> str:
    attrs = render_filter_attrs_for_item(item)
    return (
        f'<article class="historical-card" {attrs} data-search="{escape_attr(search_text(item.title, item.summary, item.display_source, item.category))}">'
        f'<div class="eyebrow">{escape(item.display_source)} | {escape(infer_region(item))}</div>'
        f'<p><a href="{escape_attr(item.url)}">{escape(item.title)}</a></p>'
        f'<p>{escape(item.summary)}</p></article>'
    )


def render_region_watch(items: list[Item]) -> str:
    grouped: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        region = infer_region(item)
        if region in {"Global / Maritime", "Cross-region / unassigned"}:
            continue
        if item_is_background_system_report(item):
            continue
        if item_is_background_context_piece(item):
            continue
        if item_is_pseudo_regional_maritime_story(item):
            continue
        if not item_is_regional_watchworthy(item):
            continue
        if item.relevance_score < 2 and not item.official and not has_local_signal(item):
            continue
        if (item.source_type or "").lower() in {"pubmed", "medrxiv", "biorxiv"} and item.relevance_score < 4:
            continue
        if not item_has_outbreak_focus(item):
            continue
        grouped[region].append(item)

    if not grouped:
        return '<p class="empty-note">No regional outbreak signal is dominant in this update.</p>'

    cards: list[str] = []
    for region, region_items in sorted(grouped.items(), key=lambda pair: max(sortable_datetime(item.published_at) for item in pair[1]), reverse=True):
        region_items = sorted(
            region_items,
            key=lambda item: (item.relevance_score, 1 if has_local_signal(item) else 0, sortable_datetime(item.published_at)),
            reverse=True,
        )[:7]
        local_count = sum(1 for item in region_items if has_local_signal(item))
        list_items = []
        for item in region_items:
            local_badge = ' <span class="badge local">Rural / local signal</span>' if has_local_signal(item) else ""
            list_items.append(
                "<li>"
                f'<a href="{escape_attr(item.url)}">{escape(item.title)}</a>'
                f'<div class="item-meta"><span class="badge">{escape(item.publisher_name)}</span>{render_publisher_tier_badge(item)}{render_access_badge(item)}'
                f'<span class="badge">{escape(format_timestamp(item.published_at))}</span>{local_badge}</div>'
                "</li>"
            )
        cards.append(
            f'<article class="region-card sortable-card" {render_filter_attrs_for_region_group(region, region_items)} data-sort-ts="{sort_timestamp_value(max((item.published_at.isoformat() if item.published_at else "") for item in region_items))}" data-sort-source="{escape_attr(region)}" data-sort-title="{escape_attr(region)}" data-search="{escape_attr(search_text(region, " ".join(item.title for item in region_items)))}">'
            f'<div class="eyebrow">Regional outbreak watch</div><h3>{escape(region)}</h3>'
            f'<div class="item-meta"><span class="badge">{len(region_items)} item(s)</span><span class="badge">{local_count} rural / local</span></div>'
            f'<ul class="region-list">{"".join(list_items)}</ul></article>'
        )
    return "".join(cards)


def item_is_pseudo_regional_maritime_story(item: Item) -> bool:
    text = item_signal_text(item)
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


def item_is_background_system_report(item: Item) -> bool:
    text = item_signal_text(item)
    if not any(
        term in text
        for term in (
            "health workforce",
            "workforce financing",
            "health labour market",
            "health labor market",
            "investment charter",
            "plan, train and retain",
            "state of the health workforce",
        )
    ):
        return False
    return not item_has_outbreak_focus(item)


def item_is_background_context_piece(item: Item) -> bool:
    text = item_signal_text(item)
    if not any(
        term in text
        for term in (
            "study finds",
            "fact check",
            "what to know",
            "how hantavirus spreads",
            "published in the lancet",
            "child death reduction",
            "averting an estimated",
        )
    ):
        return False
    return not any(
        term in text
        for term in (
            "outbreak",
            "cluster",
            "declining",
            "spread",
            "spreading",
            "confirmed",
            "suspected",
            "under investigation",
            "epidemic",
            "epicenter",
        )
    )


def item_has_outbreak_focus(item: Item) -> bool:
    text = item_signal_text(item)
    disease_terms = (
        "measles",
        "cholera",
        "hantavirus",
        "mpox",
        "dengue",
        "avian influenza",
        "h5n1",
        "marburg",
        "ebola",
        "polio",
        "tuberculosis",
        "legionnaires",
        "pertussis",
        "meningococcal",
        "malaria",
        "norovirus",
        "hepatitis a",
        "cyclospora",
        "cyclosporiasis",
        "campylobacter",
        "shigella",
        "vibrio",
        "yersinia",
        "botulism",
        "rabies",
        "anthrax",
        "mers",
        "nipah",
        "chikungunya",
        "yellow fever",
        "zika",
        "diphtheria",
        "oropouche",
        "rift valley fever",
        "arbovirus",
        "respiratory",
        "waterborne",
        "foodborne",
        "salmonella",
        "lassa",
    )
    development_terms = (
        "outbreak",
        "cluster",
        "surveillance",
        "cases",
        "case",
        "deaths",
        "death",
        "declining",
        "spread",
        "spreading",
        "surge",
        "spike",
        "health alert",
        "under investigation",
        "contain",
        "containment",
        "confirmed",
        "suspected",
        "epidemiological update",
        "situation report",
        "vaccination drive",
        "vaccination campaign",
        "epidemic",
        "epicenter",
        "detected",
        "reported",
        "reports",
    )
    return any(term in text for term in disease_terms) and any(term in text for term in development_terms)


def item_is_regional_watchworthy(item: Item) -> bool:
    text = item_signal_text(item)
    if item_has_outbreak_focus(item):
        return True
    if has_local_signal(item) and any(
        term in text
        for term in (
            "cholera",
            "dengue",
            "mpox",
            "marburg",
            "ebola",
            "lassa",
            "anthrax",
            "yellow fever",
            "malaria",
            "measles",
            "polio",
            "tuberculosis",
            "avian influenza",
            "h5n1",
            "rabies",
            "diphtheria",
        )
    ):
        return True
    return False


def item_content_text(item: Item) -> str:
    return " ".join(
        part.lower()
        for part in (
            item.title,
            item.summary,
            item.why_it_matters,
            item.caveats,
            item.extracted_text,
        )
        if part
    )


def item_signal_text(item: Item) -> str:
    return " ".join(
        part.lower()
        for part in (
            item.title,
            item.summary,
            item.extracted_text,
        )
        if part
    )


def render_sort_bar(target_id: str, source_label: str = "Source A-Z") -> str:
    return (
        '<div class="sort-bar">'
        f'<label class="sort-control">Sort by '
        f'<select class="sort-select" data-sort-target="{escape_attr(target_id)}">'
        '<option value="newest">Newest first</option>'
        '<option value="oldest">Oldest first</option>'
        f'<option value="source">{escape(source_label)}</option>'
        '</select></label>'
        '</div>'
    )


def render_source_health_note(source_health: list[dict]) -> str:
    if not source_health:
        return ""
    live = sum(1 for entry in source_health if entry.get("mode") == "live")
    refresh_cache = sum(1 for entry in source_health if entry.get("mode") == "refresh_cache")
    fallback_cache = sum(1 for entry in source_health if entry.get("mode") == "fallback_cache")
    failed = sum(1 for entry in source_health if entry.get("mode") == "failed")
    return (
        f'<span class="meta-pill">Sources: {live} live · {refresh_cache} refresh cache · '
        f'{fallback_cache} fallback cache · {failed} failed</span>'
    )


def render_desk_health_panel(source_health: list[dict]) -> str:
    if not source_health:
        return '<p class="empty-note">No source-health summary was exported for this run.</p>'
    live = [entry for entry in source_health if entry.get("mode") == "live"]
    refresh_cache = [entry for entry in source_health if entry.get("mode") == "refresh_cache"]
    fallback_cache = [entry for entry in source_health if entry.get("mode") == "fallback_cache"]
    failed = [entry for entry in source_health if entry.get("mode") == "failed"]
    summary = (
        f'<article class="compact-card searchable-card" data-region="" data-source-kind="health" data-pathogen="" data-setting="" data-official="false" data-age-days="0" '
        f'data-search="{escape_attr(search_text("desk health source health live cache failed freshness"))}">'
        '<div class="eyebrow">Run state</div>'
        f'<p><strong>{len(live)} live</strong> · <strong>{len(refresh_cache)} refresh cache</strong> · '
        f'<strong>{len(fallback_cache)} fallback cache</strong> · <strong>{len(failed)} failed</strong></p>'
        '<p>This run stays visible even when a few sources wobble, but the desk now tells you when cached or failed collection paths shaped the file.</p>'
        '</article>'
    )
    source_cards = [
        render_health_source_card("Refresh cache sources", refresh_cache, "Cached because the source was intentionally reused inside the refresh window."),
        render_health_source_card("Fallback cache sources", fallback_cache, "These sources failed live but still contributed recent cached payloads."),
        render_health_source_card("Failed sources", failed, "These sources failed and did not contribute fresh content to this run."),
    ]
    return f'<div class="compact-grid">{summary}{"".join(source_cards)}</div>'


def render_health_source_card(title: str, entries: list[dict], description: str) -> str:
    if not entries:
        note = '<p class="empty-note">None in this run.</p>'
    else:
        note = "".join(
            f'<li>{escape(entry.get("source", "Unknown source"))}'
            f'{f" — {escape(str(entry.get("error", "")))}" if entry.get("error") else ""}</li>'
            for entry in entries[:8]
        )
        note = f'<ul class="bullet-list">{note}</ul>'
    return (
        f'<article class="compact-card searchable-card" data-region="" data-source-kind="health" data-pathogen="" data-setting="" data-official="false" data-age-days="0" '
        f'data-search="{escape_attr(search_text(title, description, " ".join(str(entry.get("source", "")) for entry in entries)))}">'
        f'<div class="eyebrow">{escape(title)}</div>'
        f'<p>{escape(description)}</p>'
        f'{note}'
        '</article>'
    )


def render_outbreak_reference(entries: list[DiseaseReference], references_by_name: dict[str, dict] | None = None) -> str:
    if not entries:
        return '<p class="empty-note">No outbreak reference entries have been curated yet.</p>'

    references_by_name = references_by_name or {}
    cards: list[str] = []
    for entry in entries:
        category_badges = "".join(f'<span class="badge">{escape(category)}</span>' for category in entry.categories[:4])
        reference_record = references_by_name.get(entry.name, {})
        title_link = reference_record.get("reference_url")
        title_html = f'<a href="{escape_attr(title_link)}">{escape(entry.name)}</a>' if title_link else escape(entry.name)
        field_guide_block = ""
        if entry.field_guide_links:
            field_guide_links = "".join(
                f'<a class="reference-link" href="{escape_attr(link.url)}">{escape(link.label)}</a>'
                for link in entry.field_guide_links
            )
            field_guide_block = f'<div class="reference-links">{field_guide_links}</div>'
        notable_block = ""
        if entry.notable_outbreaks:
            notable_items = "".join(f"<li>{escape(note)}</li>" for note in entry.notable_outbreaks[:4])
            notable_block = f'<ul class="reference-notes">{notable_items}</ul>'
        surveillance_note = (
            f'<p><strong>Desk note:</strong> {escape(entry.surveillance_note)}</p>'
            if entry.surveillance_note
            else ""
        )
        research_caveat = (
            f'<p><strong>Research caveat:</strong> {escape(entry.research_caveats)}</p>'
            if entry.research_caveats
            else ""
        )
        why_reporters_care = (
            f'<p><strong>Why reporters care:</strong> {escape(entry.why_reporters_care)}</p>'
            if entry.why_reporters_care
            else ""
        )
        cards.append(
            f'<article class="reference-card" {render_filter_attrs_for_disease_reference(entry)} data-search="{escape_attr(search_text(entry.name, entry.pathogen, entry.transmission, " ".join(entry.categories), entry.latest_outbreak.label, entry.latest_outbreak.location, entry.latest_outbreak.summary, " ".join(entry.notable_outbreaks), " ".join(link.label for link in entry.field_guide_links)))}">'
            f'<div class="eyebrow">Last major outbreak on file</div>'
            f'<h3>{title_html}</h3>'
            f'<p><strong>Pathogen:</strong> {escape(entry.pathogen)}</p>'
            f'<p><strong>Transmission:</strong> {escape(entry.transmission)}</p>'
            f'<div class="item-meta">{category_badges}<span class="badge accent">{escape(entry.latest_outbreak.period)}</span><span class="badge signal">{escape(entry.latest_outbreak.location)}</span></div>'
            f'<p><strong>{escape(entry.latest_outbreak.label)}</strong> — {escape(entry.latest_outbreak.summary)}</p>'
            f'<p><strong>Source:</strong> <a href="{escape_attr(entry.latest_outbreak.source_url)}">{escape(entry.latest_outbreak.source_name)}</a> <span class="meta-inline">({escape(entry.latest_outbreak.as_of)})</span></p>'
            f'{field_guide_block}{why_reporters_care}{surveillance_note}{research_caveat}{notable_block}</article>'
        )
    return "".join(cards)


def render_archive_sidebar(entries: list[ArchiveEntry], target_date: date) -> str:
    if not entries:
        return '<p class="empty-note">No dated HTML archives have been written yet.</p>'

    by_year: dict[int, dict[int, list[ArchiveEntry]]] = defaultdict(lambda: defaultdict(list))
    for entry in entries:
        by_year[entry.target_date.year][entry.target_date.month].append(entry)

    year_blocks: list[str] = []
    for year in sorted(by_year.keys(), reverse=True):
        month_blocks: list[str] = []
        for month in sorted(by_year[year].keys(), reverse=True):
            links = "".join(render_archive_link(entry, target_date) for entry in sorted(by_year[year][month], key=lambda item: item.target_date, reverse=True))
            month_blocks.append(
                f'<details class="archive-month" open><summary class="archive-summary">{date(year, month, 1).strftime("%B")}</summary>'
                f'<ul class="archive-links">{links}</ul></details>'
            )
        year_blocks.append(
            f'<details class="archive-year" open><summary class="archive-summary">{year}</summary>'
            f'{"".join(month_blocks)}</details>'
        )

    latest_uri = latest_html_filename().resolve().as_uri()
    return (
        '<div class="archive-block">'
        f'<a class="archive-toplink" href="{escape_attr(latest_uri)}" data-archive-search="latest newest current dossier">Open latest briefing</a>'
        f'{"".join(year_blocks)}'
        '</div>'
    )


def render_archive_link(entry: ArchiveEntry, target_date: date) -> str:
    date_text = entry.target_date.strftime("%b %d")
    current_badge = '<span class="archive-current">Current</span>' if entry.target_date == target_date else ""
    search_value = search_text(entry.target_date.isoformat(), entry.target_date.strftime("%B %Y"), date_text)
    return (
        f'<li class="archive-link" data-archive-search="{escape_attr(search_value)}">'
        f'<a href="{escape_attr(entry.html_path.resolve().as_uri())}"><time datetime="{entry.target_date.isoformat()}">{escape(date_text)}</time></a>'
        f'{current_badge}</li>'
    )


def render_publisher_tier_badge(item: Item) -> str:
    label = label_for_publisher_tier(item.publisher_tier)
    if not label:
        return ""
    return f'<span class="badge signal">{escape(label)}</span>'


def render_access_badge(item: Item) -> str:
    label = label_for_publisher_access(item.publisher_access)
    if not label:
        return ""
    return f'<span class="badge">{escape(label)}</span>'


def label_for_publisher_tier(tier: str) -> str:
    return {
        "official": "Official",
        "wire": "Wire",
        "major_newsroom": "Major newsroom",
        "specialist_health": "Specialist health",
        "general": "General",
    }.get(tier, normalize_whitespace(tier.replace("_", " ")).title())


def label_for_publisher_access(access: str) -> str:
    return {
        "open": "Open access",
        "subscription": "Login likely",
        "mixed": "Partial paywall",
    }.get(access, "")


def label_for_evidence_type(evidence_type: str) -> str:
    return {
        "official_update": "Official update",
        "news_report": "News report",
        "journal_article": "Journal article",
        "preprint": "Preprint",
        "reference": "Reference",
        "mixed_reporting": "Mixed reporting",
        "research_linked": "Research-linked story",
    }.get(evidence_type, normalize_whitespace(evidence_type.replace("_", " ")).title())


def paper_why_it_matters(item: Item) -> str:
    why = normalize_whitespace(item.why_it_matters)
    if not why or why == "Comes from an official or primary-source channel.":
        return "Useful for mechanism, transmission, or surveillance context beyond the daily outbreak file."
    return why


def paper_evidence_caveat(item: Item) -> str:
    caveat = normalize_whitespace(item.caveats)
    if not caveat or caveat == "Summary stays within source text and metadata; no outside facts were added.":
        return "Interpret in light of study design, setting, sample size, and how directly the findings travel to the current outbreak picture."
    return caveat


PATHOGEN_TAG_RULES = {
    "hantavirus": ("hantavirus", "andes virus"),
    "measles": ("measles",),
    "avian_influenza": ("h5n1", "avian influenza", "bird flu"),
    "covid": ("covid", "sars-cov-2"),
    "tuberculosis": ("tuberculosis", " tb ", "mycobacterium tuberculosis"),
    "dengue": ("dengue", "arbovirus", "oropouche", "rift valley fever", "chikungunya"),
    "cholera": ("cholera",),
    "mpox": ("mpox",),
    "polio": ("polio", "poliovirus"),
}

SETTING_TAG_RULES = {
    "maritime": ("cruise ship", "ship", "docking", "port", "maritime", "aboard"),
    "healthcare": ("hospital", "clinic", "healthcare", "facility"),
    "rural_local": ("rural", "village", "district", "county", "province", "remote"),
    "occupational": ("occupational", "worker", "niosh", "osha", "exposure"),
    "wastewater": ("wastewater",),
    "school": ("school", "campus", "student"),
    "travel": ("travel", "airport", "border", "flight"),
}


def build_filter_options(
    items: list[Item],
    story_records: list[dict],
    reference_records: list[dict],
    generated_at: datetime,
) -> dict[str, list[tuple[str, str]]]:
    regions = sorted({infer_region(item) for item in items if infer_region(item)})
    source_kinds = {
        "official": "Official",
        "research": "Research",
        "wire": "Wire",
        "major_newsroom": "Major newsroom",
        "specialist_health": "Specialist health",
        "aggregator_only": "Aggregator / wrapper",
        "general": "General",
        "metadata_only_signal": "Metadata-only signal",
    }
    evidence_types = {
        "official_update": "Official update",
        "news_report": "News report",
        "journal_article": "Journal article",
        "preprint": "Preprint",
        "reference": "Reference",
    }
    link_quality = {
        "direct_article": "Direct article",
        "resolved_article": "Resolved article",
        "resolved_nonarticle": "Resolved non-article",
        "wrapper_only": "Wrapper only",
        "metadata_only": "Metadata only",
    }
    access_types = {
        "open": "Open access",
        "subscription": "Login likely",
        "mixed": "Partial paywall",
        "unknown": "Access unknown",
    }
    story_statuses = {
        "expanding_coverage": "Expanding coverage",
        "active_investigation": "Active investigation",
        "official_follow_up_only": "Official follow-up only",
        "quiet_retained": "Quiet but retained",
        "archival_watch": "Archival watch",
    }
    pathogen_tags = set()
    setting_tags = set()
    for item in items:
        pathogen_tags.update(detect_pathogen_tags(item.title, item.summary, item.category))
        setting_tags.update(detect_setting_tags(item.title, item.summary, item.category))
    for reference in reference_records:
        pathogen_tags.update(detect_pathogen_tags(reference.get("name", ""), reference.get("pathogen", ""), reference.get("transmission", "")))
        setting_tags.update(detect_setting_tags(reference.get("name", ""), reference.get("transmission", ""), " ".join(reference.get("categories", []))))
    return {
        "region": [("all", "All regions")] + [(value, value) for value in regions],
        "sourceKind": [("all", "All source types")] + list(source_kinds.items()),
        "pathogen": [("all", "All pathogens")] + [(value, format_filter_label(value)) for value in sorted(pathogen_tags)],
        "setting": [("all", "All settings")] + [(value, format_filter_label(value)) for value in sorted(setting_tags)],
        "dateWindow": [("all", "Any date"), ("1", "Past 24 hours"), ("3", "Past 3 days"), ("7", "Past 7 days")],
        "officialOnly": [("all", "Official + publisher"), ("official", "Official only")],
        "linkQuality": [("all", "All link types")] + list(link_quality.items()),
        "access": [("all", "All access")] + list(access_types.items()),
        "evidenceType": [("all", "All evidence")] + list(evidence_types.items()),
        "storyStatus": [("all", "All story states")] + list(story_statuses.items()),
    }


def render_structured_filter_controls(options: dict[str, list[tuple[str, str]]]) -> str:
    controls = [
        ("region", "Region"),
        ("sourceKind", "Source type"),
        ("pathogen", "Pathogen"),
        ("setting", "Setting"),
        ("linkQuality", "Link quality"),
        ("access", "Access"),
        ("evidenceType", "Evidence"),
        ("storyStatus", "Story status"),
        ("dateWindow", "Date range"),
        ("officialOnly", "Scope"),
    ]
    blocks: list[str] = []
    for key, label in controls:
        choices = options.get(key, [])
        option_html = "".join(
            f'<option value="{escape_attr("" if value == "all" else value)}">{escape(text)}</option>'
            for value, text in choices
        )
        blocks.append(
            f'<label class="filter-group"><span class="filter-label">{escape(label)}</span>'
            f'<select class="filter-select" data-structured-filter="{escape_attr(key)}">{option_html}</select></label>'
        )
    return "".join(blocks)


def render_filter_attrs_for_item(item: Item) -> str:
    return render_filter_attrs(
        region=infer_region(item),
        source_kind=item_source_kind(item),
        pathogen_tags=detect_pathogen_tags(item.title, item.summary, item.category),
        setting_tags=detect_setting_tags(item.title, item.summary, item.category),
        official=item.official and not item_is_research_item(item),
        age_days=item_age_days(item.published_at),
        link_quality=item.link_quality,
        access=item.publisher_access,
        evidence_type=item.evidence_type,
    )


def render_filter_attrs_for_story_record(story: dict | None, fallback_items: list[Item] | None = None) -> str:
    if not story and not fallback_items:
        return render_filter_attrs()
    title = story.get("display_title", "") if story else ""
    summary = story.get("latest_update_summary", "") if story else ""
    source_kinds = set()
    if story:
        source_kinds.update(kind for kind, count in (story.get("source_kind_counts") or {}).items() if count)
        if story.get("official_item_ids"):
            source_kinds.add("official")
    if not source_kinds and fallback_items:
        source_kinds.update(item_source_kind(item) for item in fallback_items)
    region = None
    if fallback_items:
        region = infer_region(fallback_items[0]) if fallback_items else None
    return render_filter_attrs(
        region=region,
        source_kind=" ".join(sorted(source_kinds)),
        pathogen_tags=detect_pathogen_tags(title, summary),
        setting_tags=detect_setting_tags(title, summary),
        official=bool(story and story.get("official_item_ids")),
        age_days=age_days_from_iso(story.get("latest_updated_at") if story else None),
        story_status=(story or {}).get("status", ""),
        evidence_type=(story or {}).get("evidence_type", ""),
    )


def render_filter_attrs_for_reference_record(reference: dict) -> str:
    return render_filter_attrs(
        region=reference.get("latest_outbreak", {}).get("location", ""),
        source_kind="reference",
        pathogen_tags=detect_pathogen_tags(reference.get("name", ""), reference.get("pathogen", ""), reference.get("transmission", "")),
        setting_tags=detect_setting_tags(reference.get("name", ""), reference.get("transmission", ""), " ".join(reference.get("categories", []))),
        official=False,
        age_days=9999,
        evidence_type=reference.get("evidence_type", "reference"),
    )


def render_filter_attrs_for_disease_reference(reference: DiseaseReference) -> str:
    return render_filter_attrs(
        region=reference.latest_outbreak.location,
        source_kind="reference",
        pathogen_tags=detect_pathogen_tags(reference.name, reference.pathogen, reference.transmission),
        setting_tags=detect_setting_tags(reference.name, reference.transmission, " ".join(reference.categories)),
        official=False,
        age_days=9999,
        evidence_type="reference",
    )


def render_filter_attrs_for_region_group(region: str, items: list[Item]) -> str:
    source_kinds = " ".join(sorted({item_source_kind(item) for item in items}))
    pathogen_tags = sorted({tag for item in items for tag in detect_pathogen_tags(item.title, item.summary, item.category)})
    setting_tags = sorted({tag for item in items for tag in detect_setting_tags(item.title, item.summary, item.category)})
    latest_age = min((item_age_days(item.published_at) for item in items), default=9999)
    return render_filter_attrs(
        region=region,
        source_kind=source_kinds,
        pathogen_tags=pathogen_tags,
        setting_tags=setting_tags,
        official=any(item.official for item in items),
        age_days=latest_age,
        evidence_type="news_report",
    )


def render_filter_attrs(
    *,
    region: str | None = None,
    source_kind: str | None = None,
    pathogen_tags: list[str] | set[str] | tuple[str, ...] | None = None,
    setting_tags: list[str] | set[str] | tuple[str, ...] | None = None,
    official: bool | None = None,
    age_days: int | None = None,
    link_quality: str | None = None,
    access: str | None = None,
    evidence_type: str | None = None,
    story_status: str | None = None,
) -> str:
    attrs = {
        "data-region": normalize_filter_token(region or ""),
        "data-source-kind": normalize_filter_token(source_kind or ""),
        "data-pathogen": " ".join(sorted(normalize_filter_token(tag) for tag in (pathogen_tags or []) if normalize_filter_token(tag))),
        "data-setting": " ".join(sorted(normalize_filter_token(tag) for tag in (setting_tags or []) if normalize_filter_token(tag))),
        "data-official": "true" if official else "false",
        "data-age-days": str(age_days if age_days is not None else 9999),
        "data-link-quality": normalize_filter_token(link_quality or ""),
        "data-access": normalize_filter_token(access or ""),
        "data-evidence-type": normalize_filter_token(evidence_type or ""),
        "data-story-status": normalize_filter_token(story_status or ""),
    }
    return " ".join(f'{key}="{escape_attr(value)}"' for key, value in attrs.items())


def item_source_kind(item: Item) -> str:
    if item_is_research_item(item):
        return "research"
    if item.official:
        return "official"
    if item.source_confidence == "aggregator_only":
        return "aggregator_only"
    if item.source_confidence == "metadata_only_signal":
        return "metadata_only_signal"
    return normalize_filter_token(item.publisher_tier or "general")


def detect_pathogen_tags(*parts: str) -> list[str]:
    text = search_text(*parts)
    matches = [tag for tag, needles in PATHOGEN_TAG_RULES.items() if any(needle in text for needle in needles)]
    return matches


def detect_setting_tags(*parts: str) -> list[str]:
    text = search_text(*parts)
    matches = [tag for tag, needles in SETTING_TAG_RULES.items() if any(needle in text for needle in needles)]
    return matches


def item_age_days(published_at: datetime | None) -> int:
    if not published_at:
        return 9999
    now = datetime.now(published_at.tzinfo) if published_at.tzinfo else datetime.now()
    return max((now - published_at).days, 0)


def age_days_from_iso(value: str | None) -> int:
    if not value:
        return 9999
    try:
        return item_age_days(datetime.fromisoformat(value))
    except ValueError:
        return 9999


def normalize_filter_token(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", normalize_whitespace(value).lower()).strip("_")
    return cleaned


def format_filter_label(value: str) -> str:
    return normalize_whitespace(value.replace("_", " ")).title()


def item_is_historical(item: Item) -> bool:
    text = " ".join([item.title.lower(), item.summary.lower(), item.category.lower(), item.display_source.lower()])
    return any(
        term in text
        for term in (
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
            "yersinia pestis",
            "variola",
            "treponemal",
        )
    )


def search_text(*parts: str) -> str:
    return " ".join(part for part in parts if part).lower()


def sort_timestamp_value(value: str | None) -> int:
    if not value:
        return 0
    try:
        return int(datetime.fromisoformat(value).timestamp())
    except ValueError:
        return 0


def escape(value: str) -> str:
    return html.escape(value or "", quote=False)


def escape_attr(value: str) -> str:
    return html.escape(value or "", quote=True)


def render_logo_mark() -> str:
    return """
<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="The Edge of Epidemiology mark">
  <defs>
    <linearGradient id="dispatchPlate" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0E2438"/>
      <stop offset="100%" stop-color="#173B58"/>
    </linearGradient>
    <linearGradient id="dispatchAccent" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#E7B83D"/>
      <stop offset="100%" stop-color="#FFD97A"/>
    </linearGradient>
  </defs>
  <rect x="12" y="12" width="96" height="96" rx="24" fill="url(#dispatchPlate)"/>
  <rect x="19" y="19" width="82" height="82" rx="18" fill="none" stroke="url(#dispatchAccent)" stroke-width="2.2" opacity="0.95"/>
  <path d="M34 30 H86" stroke="#D6E3EE" stroke-width="2.6" stroke-linecap="round" opacity="0.85"/>
  <path d="M34 90 H86" stroke="#D6E3EE" stroke-width="2.6" stroke-linecap="round" opacity="0.72"/>
  <path d="M37 44 H82" stroke="#284D6B" stroke-width="16" stroke-linecap="round"/>
  <path d="M39 44 H80" stroke="#F8FBFD" stroke-width="11.5" stroke-linecap="round"/>
  <path d="M47 44 H72" stroke="#15324F" stroke-width="3.2" stroke-linecap="round" stroke-dasharray="1 7"/>
  <path d="M41 66 C47 55, 53 77, 59 61 C63 50, 69 68, 75 58 C78 54, 81 51, 84 46" fill="none" stroke="#FFD24A" stroke-width="4.8" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="41" cy="66" r="3.1" fill="#FFD24A"/>
  <circle cx="59" cy="61" r="3.1" fill="#F8FBFD"/>
  <circle cx="75" cy="58" r="3.1" fill="#FFD24A"/>
  <circle cx="84" cy="46" r="3.1" fill="#F8FBFD"/>
  <path d="M34 77 H56" stroke="#95ADBF" stroke-width="3" stroke-linecap="round"/>
  <path d="M63 77 H86" stroke="#95ADBF" stroke-width="3" stroke-linecap="round"/>
</svg>
"""


def render_banner_mark() -> str:
    return """
<svg viewBox="0 0 1280 180" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="The Pathogen Dispatch banner">
  <defs>
    <linearGradient id="dispatchBannerBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0C1F30"/>
      <stop offset="58%" stop-color="#15344E"/>
      <stop offset="100%" stop-color="#194A6C"/>
    </linearGradient>
    <linearGradient id="dispatchBannerLine" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#E7B83D" stop-opacity="0.98"/>
      <stop offset="100%" stop-color="#E7B83D" stop-opacity="0.1"/>
    </linearGradient>
    <pattern id="dispatchGrid" width="32" height="32" patternUnits="userSpaceOnUse">
      <path d="M32 0 H0 V32" fill="none" stroke="#ffffff" stroke-opacity="0.05" stroke-width="1"/>
    </pattern>
  </defs>
  <rect width="1280" height="180" fill="url(#dispatchBannerBg)"/>
  <rect width="1280" height="180" fill="url(#dispatchGrid)"/>
  <rect x="0" y="0" width="1280" height="16" fill="#091824" opacity="0.58"/>
  <path d="M0 148 C126 132, 236 166, 354 151 C468 136, 590 170, 702 152 C830 134, 952 168, 1068 152 C1152 142, 1218 150, 1280 146" fill="none" stroke="#ffffff" stroke-opacity="0.12" stroke-width="4" stroke-linecap="round"/>
  <path d="M74 128 H1204" stroke="url(#dispatchBannerLine)" stroke-width="5" stroke-linecap="round"/>
  <g transform="translate(72 46)">
    <text x="0" y="0" fill="#F7FBFE" font-family="'Avenir Next Condensed', 'Franklin Gothic Medium', sans-serif" font-size="15" font-weight="700" letter-spacing="5.2">MORNING INFECTIOUS DISEASE DESK</text>
    <text x="0" y="42" fill="#E7B83D" font-family="'Avenir Next', 'Helvetica Neue', sans-serif" font-size="16" font-weight="700" letter-spacing="2.6">FIELD SIGNALS  •  OFFICIAL ALERTS  •  FOLLOW-UP REPORTING</text>
    <text x="0" y="78" fill="#EAF2F8" font-family="'Avenir Next', 'Helvetica Neue', sans-serif" font-size="15.5" letter-spacing="1.08">A source-first global outbreak reader for reporters, editors, and public-health desks.</text>
  </g>
  <g transform="translate(744 54)">
    <rect x="0" y="0" width="112" height="52" rx="18" fill="#F7FBFE" fill-opacity="0.96"/>
    <text x="18" y="22" fill="#15324F" font-family="'Avenir Next Condensed', 'Franklin Gothic Medium', sans-serif" font-size="12" font-weight="700" letter-spacing="2.2">SIGNALS</text>
    <text x="18" y="40" fill="#4B6173" font-family="'Avenir Next', 'Helvetica Neue', sans-serif" font-size="12.5">Fresh leads</text>
    <rect x="126" y="0" width="112" height="52" rx="18" fill="#F7FBFE" fill-opacity="0.96"/>
    <text x="144" y="22" fill="#15324F" font-family="'Avenir Next Condensed', 'Franklin Gothic Medium', sans-serif" font-size="12" font-weight="700" letter-spacing="2.2">SCOPE</text>
    <text x="144" y="40" fill="#4B6173" font-family="'Avenir Next', 'Helvetica Neue', sans-serif" font-size="12.5">Global and rural</text>
    <rect x="252" y="0" width="124" height="52" rx="18" fill="#F7FBFE" fill-opacity="0.96"/>
    <text x="270" y="22" fill="#15324F" font-family="'Avenir Next Condensed', 'Franklin Gothic Medium', sans-serif" font-size="12" font-weight="700" letter-spacing="2.2">SOURCING</text>
    <text x="270" y="40" fill="#4B6173" font-family="'Avenir Next', 'Helvetica Neue', sans-serif" font-size="12.5">Official and press</text>
    <rect x="390" y="0" width="112" height="52" rx="18" fill="#F7FBFE" fill-opacity="0.96"/>
    <text x="408" y="22" fill="#15324F" font-family="'Avenir Next Condensed', 'Franklin Gothic Medium', sans-serif" font-size="12" font-weight="700" letter-spacing="2.2">TRACKING</text>
    <text x="408" y="40" fill="#4B6173" font-family="'Avenir Next', 'Helvetica Neue', sans-serif" font-size="12.5">Live files</text>
  </g>
</svg>
"""
