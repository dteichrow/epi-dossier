from __future__ import annotations

import html
import json
from collections import defaultdict
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
import re
from typing import Any

import yaml

from .dedupe import titles_similar
from .utils import format_timestamp, normalize_whitespace


MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
LOW_DETAIL_SUMMARY = "Limited detail was available from feed metadata alone."
DASHBOARD_OVERRIDES_PATH = Path(__file__).resolve().parents[1] / "config" / "outbreak_dashboard_overrides.yml"
BROAD_REGION_LABELS = {
    "",
    "africa",
    "asia",
    "cross-region / unassigned",
    "global",
    "global / maritime",
    "north america",
    "south asia",
    "east asia",
    "europe",
}
INTELLIGENCE_CATEGORY_LABELS = {
    "confirmed-epidemiologic-updates": "Confirmed epidemiologic updates",
    "operational-response": "Operational response",
    "border-regional-spread-concerns": "Border / regional spread concerns",
    "scientific-vaccine-therapeutic-context": "Scientific / vaccine / therapeutic context",
    "commentary-political-reaction-media-discourse": "Commentary / political reaction / media discourse",
}


def render_story_page(
    story: dict[str, Any],
    items_by_id: dict[str, dict[str, Any]],
    target_date: date,
    generated_at: datetime,
    *,
    web_mode: bool = False,
    current_run_id: str | None = None,
) -> str:
    official_items_raw = [items_by_id[item_id] for item_id in story.get("official_item_ids", []) if item_id in items_by_id]
    press_items_raw = [items_by_id[item_id] for item_id in story.get("press_item_ids", []) if item_id in items_by_id]
    raw_combined_items = official_items_raw + press_items_raw
    official_items = collapse_story_page_items(official_items_raw, max_low_detail_per_publisher=2)
    press_items = collapse_story_page_items(press_items_raw, max_low_detail_per_publisher=2)
    combined_items = official_items + press_items
    timeline = story.get("timeline", [])
    outbreak_dashboard = render_outbreak_dashboard(story, raw_combined_items)
    what_matters_now = render_what_matters_now(story, raw_combined_items)
    historical_sidebars = render_historical_epidemiology_sidebars(story, raw_combined_items)
    publisher_badges = "".join(f'<span class="badge">{escape(name)}</span>' for name in story.get("publisher_names", [])[:12])
    quality_badges = render_link_quality_badges(combined_items)
    freshness_badges = render_freshness_badges(combined_items, story.get("freshness_counts", {}))
    source_kind_badges = render_story_source_kind_badges(story.get("source_kind_counts", {}))
    source_confidence_badges = render_story_source_confidence_badges(story.get("source_confidence_counts", {}))
    story_filter_bar = render_story_filter_bar(combined_items)
    official_cards = "".join(render_story_item_card(item, "Official source") for item in official_items) or '<p class="empty-note">No official source items are attached to this story yet.</p>'
    press_cards = "".join(render_story_item_card(item, "Publisher coverage") for item in press_items) or '<p class="empty-note">No publisher coverage items are attached to this story yet.</p>'
    official_note = render_story_section_note(len(official_items_raw), len(official_items))
    press_note = render_story_section_note(len(press_items_raw), len(press_items))
    timeline_rows = "".join(render_timeline_row(entry) for entry in timeline) or '<p class="empty-note">No prior update timeline has been recorded yet.</p>'
    bullet_rows = "".join(f"<li>{escape(clean_story_text(bullet))}</li>" for bullet in story.get("latest_update_bullets", [])) or "<li>No new delta bullets were generated in this run.</li>"
    related_reference_cards = "".join(
        render_related_reference_card(reference, web_mode=web_mode, link_prefix="../") for reference in story.get("related_references", [])
    ) or '<p class="empty-note">No disease intelligence sheets were linked to this story yet.</p>'
    region_badges = "".join(
        f'<span class="badge">{escape(item.get("region", "Unknown"))}</span>'
        for item in dedupe_dicts_by_key([items_by_id[item_id] for item_id in story.get("item_ids", []) if item_id in items_by_id], "region")
        if item.get("region")
    )
    live_update_banner = render_live_update_banner() if web_mode else ""
    live_update_js = (
        live_update_script("../app_exports/manifest.json", current_run_id or str(story.get("run_id", "")), generated_at.isoformat(timespec="seconds"))
        if web_mode
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(story.get("display_title", "Story"))} | The Pathogen Dispatch</title>
    <style>{base_styles()}</style>
  </head>
  <body>
    <main class="page">
      {render_site_header_mode("../", nav_mode="web" if web_mode else "local", active_page="story")}
      {live_update_banner}
      <section class="hero" id="story-overview">
        <p class="kicker">Tracked outbreak file</p>
        <h1>{escape(story.get("display_title", "Story"))}</h1>
        <p class="subtitle">A durable desk file generated from the active dossier story cluster.</p>
        <div class="meta-row">
          <span class="badge accent">{story.get("item_count", 0)} item(s)</span>
          <span class="badge">{story.get("source_count", 0)} source(s)</span>
          <span class="badge">{len(story.get("official_item_ids", []))} official</span>
          <span class="badge">First seen: {escape(story.get("first_seen_at", "Unknown"))}</span>
          <span class="badge">Updated: {escape(story.get("latest_updated_at", "Unknown"))}</span>
        </div>
        <div class="meta-row"><span class="badge tone-official">Current status: {escape(story.get("current_status_summary", "Unknown"))}</span>{render_story_claim_badges(story.get("claim_types", []))}</div>
        <div class="meta-row">{source_kind_badges}</div>
        <div class="meta-row">{source_confidence_badges}</div>
        <div class="meta-row">{quality_badges}</div>
        <div class="meta-row">{freshness_badges}</div>
        <div class="meta-row">{publisher_badges}{region_badges}</div>
        <p class="lede"><a href="{escape_attr(story.get("lead_url", ""))}">{escape(story.get("lead_title", ""))}</a></p>
        <p><strong>Lead source:</strong> {escape(story.get("lead_source", "Unknown"))}</p>
        {outbreak_dashboard}
        <h2 class="hero-subhead">What happened</h2>
        <p>{escape(story.get("what_happened", story.get("lead_title", "No summary available.")))}</p>
        <h2 class="hero-subhead">Why it matters</h2>
        <p>{escape(story.get("why_it_matters", "No why-it-matters note is available yet."))}</p>
        <h2 class="hero-subhead">What changed in this run</h2>
        <p><strong>Latest summary:</strong> {escape(clean_story_text(story.get("latest_update_summary", "No update summary available.")))}</p>
        <ul class="bullet-list">{bullet_rows}</ul>
      </section>

      {render_page_section_nav(
          [
              ("Overview", "#story-overview"),
              ("Dashboard", "#outbreak-dashboard"),
              ("What Matters", "#what-matters-now"),
              ("Context", "#historical-context"),
              ("Filters", "#story-filters"),
              ("Official Sources", "#official-sources-panel"),
              ("Publisher Coverage", "#publisher-coverage-panel"),
              ("Disease Sheets", "#related-disease-intelligence"),
              ("Timeline", "#story-timeline-panel"),
              ("Methodology", "#methodology-note"),
          ]
      )}

      {what_matters_now}
      {historical_sidebars}

      <section class="panel utility-panel" id="story-filters">
        <h2>Filter This Story File</h2>
        <p class="muted-note">Use this desk bar to cut the outbreak file down by source quality, freshness, region, or link fidelity before you scan the cards.</p>
        {story_filter_bar}
      </section>

      <section class="panel-grid">
        <section class="panel" id="official-sources-panel">
          <h2>Official Sources</h2>
          {official_note}
          {render_sort_bar("official-sources")}
          <div id="official-sources" class="card-grid sortable-grid" data-default-sort="newest">{official_cards}</div>
        </section>
        <section class="panel" id="publisher-coverage-panel">
          <h2>Publisher Coverage</h2>
          {press_note}
          {render_sort_bar("publisher-coverage")}
          <div id="publisher-coverage" class="card-grid sortable-grid" data-default-sort="newest">{press_cards}</div>
        </section>
      </section>

      <section class="panel" id="related-disease-intelligence">
        <h2>Related Disease Intelligence</h2>
        <div class="card-grid">{related_reference_cards}</div>
      </section>

      <section class="panel" id="story-timeline-panel">
        <h2>Timeline</h2>
        {render_sort_bar("story-timeline", include_source=False)}
        <div id="story-timeline" class="timeline sortable-grid" data-default-sort="newest">{timeline_rows}</div>
      </section>

      {render_story_methodology_note()}
    </main>
    <script>{sort_script()}</script>
    <script>{story_filter_script()}</script>
    {f'<script>{live_update_js}</script>' if live_update_js else ''}
  </body>
</html>
"""


def render_reference_page(
    reference: dict[str, Any],
    target_date: date,
    generated_at: datetime,
    *,
    web_mode: bool = False,
    current_run_id: str | None = None,
) -> str:
    symptom_list = "".join(f"<li>{escape(symptom)}</li>" for symptom in reference.get("symptoms", []))
    field_guide_links = "".join(
        f'<a class="link-pill" href="{escape_attr(link["url"])}">{escape(link["label"])}</a>'
        for link in reference.get("field_guide_links", [])
    ) or '<span class="empty-note">No official field-guide links curated yet.</span>'
    settings = "".join(f'<span class="badge">{escape(setting)}</span>' for setting in reference.get("outbreak_settings", []))
    categories = "".join(f'<span class="badge">{escape(category)}</span>' for category in reference.get("categories", []))
    notable = "".join(f"<li>{escape(item)}</li>" for item in reference.get("notable_outbreaks", []))
    metrics = "".join(f"<li>{escape(item)}</li>" for item in reference.get("metrics_that_matter", []))
    latest = reference.get("latest_outbreak", {})
    atlas_link = (
        f'<a class="link-pill" href="../atlas.html?pathogen={escape_attr(reference.get("atlas_entry_slug", ""))}">View in Atlas</a>'
        if reference.get("atlas_entry_slug")
        else ""
    )
    related_story_cards = "".join(
        render_related_story_card(story, web_mode=web_mode, link_prefix="../") for story in reference.get("related_stories", [])
    ) or '<p class="empty-note">No active tracked stories are linked to this disease in the current run.</p>'
    live_update_banner = render_live_update_banner() if web_mode else ""
    live_update_js = (
        live_update_script("../app_exports/manifest.json", current_run_id or str(reference.get("run_id", "")), generated_at.isoformat(timespec="seconds"))
        if web_mode
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(reference.get("name", "Reference"))} | The Pathogen Dispatch</title>
    <style>{base_styles()}</style>
  </head>
  <body>
    <main class="page">
      {render_site_header_mode("../", nav_mode="web" if web_mode else "local", active_page="reference")}
      {live_update_banner}
      <section class="hero" id="story-overview">
        <p class="kicker">Disease intelligence sheet</p>
        <h1>{escape(reference.get("name", "Reference"))}</h1>
        <p class="subtitle">Curated desk background for reporters who need the pathogen, transmission, and outbreak frame fast.</p>
        <div class="meta-row">{categories}{settings}</div>
        {f'<div class="meta-row">{atlas_link}</div>' if atlas_link else ''}
        <p><strong>Pathogen / agent:</strong> {escape(reference.get("pathogen", "Unknown"))}</p>
        <p><strong>Transmission:</strong> {escape(reference.get("transmission", "Unknown"))}</p>
        {optional_line("Reservoir / vector", reference.get("reservoir_or_vector"))}
        {optional_line("Incubation", reference.get("incubation"))}
        {optional_line("Severity", reference.get("severity"))}
        {optional_line("Diagnostics", reference.get("diagnostics"))}
        {optional_line("Treatment", reference.get("treatment"))}
        {optional_line("Prevention", reference.get("prevention"))}
        {optional_line("Vaccine / prevention status", reference.get("vaccine_status"))}
      </section>

      {render_page_section_nav(
          [
              ("Overview", "#story-overview"),
              ("Clinical Pattern", "#clinical-pattern"),
              ("Current Story Files", "#current-story-files"),
              ("Why Reporters Care", "#why-reporters-care"),
              ("Desk Notes", "#desk-notes"),
          ]
      )}

      <section class="panel-grid">
        <section class="panel" id="clinical-pattern">
          <h2>Symptoms And Clinical Pattern</h2>
          <ul class="bullet-list">{symptom_list or '<li>No symptom summary curated yet.</li>'}</ul>
        </section>
        <section class="panel">
          <h2>Official Background Links</h2>
          <div class="meta-row">{field_guide_links}</div>
        </section>
      </section>

      <section class="panel" id="current-story-files">
        <h2>Current Story Files</h2>
        <div class="card-grid">{related_story_cards}</div>
      </section>

      <section class="panel" id="why-reporters-care">
        <h2>Why Reporters Care</h2>
        {optional_paragraph("Why this keeps becoming news", reference.get("why_reporters_care"))}
        {optional_paragraph("What journalists often get wrong", reference.get("what_reporters_get_wrong"))}
        <ul class="bullet-list">{metrics or '<li>No reporter-facing metrics are curated yet.</li>'}</ul>
      </section>

      <section class="panel">
        <h2>Last Major Outbreak On File</h2>
        <p><strong>{escape(latest.get("label", "Unknown event"))}</strong> | {escape(latest.get("location", "Unknown location"))} | {escape(latest.get("period", "Unknown period"))}</p>
        <p>{escape(latest.get("summary", ""))}</p>
        <p><strong>Source:</strong> <a href="{escape_attr(latest.get("source_url", ""))}">{escape(latest.get("source_name", "Unknown source"))}</a> ({escape(latest.get("as_of", "Unknown"))})</p>
      </section>

      <section class="panel" id="desk-notes">
        <h2>Desk Notes And Historical Signals</h2>
        {optional_paragraph("Desk note", reference.get("surveillance_note"))}
        {optional_paragraph("Research caveats", reference.get("research_caveats"))}
        <ul class="bullet-list">{notable or '<li>No notable earlier outbreaks have been curated yet.</li>'}</ul>
      </section>
    </main>
    {f'<script>{live_update_js}</script>' if live_update_js else ''}
  </body>
</html>
"""


def render_site_index(
    latest_snapshot: dict[str, Any],
    archive_entries: list[dict[str, Any]],
    reference_records: list[dict[str, Any]],
) -> str:
    notebook_entries = build_notebook_entries(latest_snapshot.get("stories", []), reference_records)
    atlas_entries = latest_snapshot.get("atlas", [])[:4]
    story_cards = "".join(
        f'<article class="site-card"><div class="kicker">Active outbreak file</div><h3><a href="{escape_attr(story["story_url"])}">{escape(story["display_title"])}</a></h3><p><strong>Status:</strong> {escape(story.get("current_status_summary", "Unknown"))}</p><p>{escape(story.get("latest_update_summary", ""))}</p></article>'
        for story in latest_snapshot.get("stories", [])[:10]
    ) or '<p class="empty-note">No major stories available in the current snapshot.</p>'
    reference_cards = "".join(
        f'<article class="site-card"><div class="kicker">Disease reference</div><h3><a href="{escape_attr(reference["reference_url"])}">{escape(reference["name"])}</a></h3><p>{escape(reference.get("pathogen", ""))}</p><p>{escape(reference.get("why_reporters_care", ""))}</p></article>'
        for reference in reference_records[:10]
    )
    archive_rows = "".join(
        f'<li><a href="{escape_attr(entry["html_url"])}">{escape(entry["date"])}</a></li>'
        for entry in archive_entries[:14]
    )
    notebook_cards = "".join(render_notebook_teaser_card(entry, web_mode=False, link_prefix="./") for entry in notebook_entries[:4]) or '<p class="empty-note">No notebook assignments are available in the current snapshot.</p>'
    atlas_cards = "".join(render_atlas_teaser_card(entry, link_prefix="./") for entry in atlas_entries) or '<p class="empty-note">No atlas entries have been curated yet.</p>'
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>The Pathogen Dispatch | Site Index</title>
    <style>{base_styles()}</style>
  </head>
  <body>
    <main class="page">
      {render_site_header("./")}
      <section class="hero">
        <p class="kicker">The Edge of Epidemiology</p>
        <h1>The Pathogen Dispatch</h1>
        <p class="subtitle">Static newsroom index for the current briefing, major tracked outbreak files, and the disease reference desk.</p>
      </section>
      {render_page_section_nav(
          [
              ("Active Outbreak Files", "#active-outbreak-files"),
              ("Reporter's Notebook", "#reporters-notebook"),
              ("Pathogen Atlas", "#pathogen-atlas"),
              ("Disease Reference Directory", "#disease-reference-directory"),
              ("Recent Archive Days", "#recent-archive-days"),
          ]
      )}
      <section class="panel" id="reporters-notebook">
        <h2>Reporter's Notebook</h2>
        <p class="muted-note">What to ask next, what numbers matter, and what framing mistakes to avoid before you write.</p>
        <p><a class="link-pill" href="./notebook.html">Open the full notebook</a></p>
        <div class="card-grid">{notebook_cards}</div>
      </section>
      <section class="panel-grid">
        <section class="panel" id="active-outbreak-files">
          <h2>Active Outbreak Files</h2>
          <div class="card-grid">{story_cards}</div>
        </section>
        <section class="panel" id="disease-reference-directory">
          <h2>Disease Reference Directory</h2>
          <div class="card-grid">{reference_cards}</div>
        </section>
      </section>
      <section class="panel" id="pathogen-atlas">
        <h2>Pathogen Atlas</h2>
        <p class="muted-note">A separate geography-and-evidence layer for origin zones, route logic, and linked writing.</p>
        <p><a class="link-pill" href="./atlas.html">Open the atlas</a></p>
        <div class="card-grid">{atlas_cards}</div>
      </section>
      <section class="panel" id="recent-archive-days">
        <h2>Recent Archive Days</h2>
        <ul class="bullet-list">{archive_rows}</ul>
      </section>
    </main>
  </body>
</html>
"""


def render_public_homepage(
    latest_snapshot: dict[str, Any],
    archive_entries: list[dict[str, Any]],
    reference_records: list[dict[str, Any]],
) -> str:
    lead_stories = latest_snapshot.get("stories", [])[:4]
    terminal_items = items_for_edition(latest_snapshot.get("items", []), "outbreaks")[:10]
    global_watch_items = items_for_edition(latest_snapshot.get("items", []), "watch")
    changed_today = global_watch_items[:8]
    watch_followups = global_watch_items[8:16]
    research_items = items_for_edition(latest_snapshot.get("items", []), "research")[:6]
    reference_spotlight = [record for record in reference_records if record.get("spotlight")] or reference_records[:6]
    archive_cards = archive_entries[:10]
    notebook_entries = build_notebook_entries(latest_snapshot.get("stories", []), reference_records)
    atlas_entries = latest_snapshot.get("atlas", [])[:4]

    lead_story_cards = "".join(render_public_story_card(story, link_prefix="./") for story in lead_stories) or '<p class="empty-note">No active outbreak files are available in this run.</p>'
    terminal_cards = "".join(render_public_item_card(item) for item in terminal_items) or '<p class="empty-note">No outbreak-terminal items matched this run.</p>'
    changed_cards = "".join(render_public_item_card(item) for item in changed_today) or '<p class="empty-note">No major changed items were surfaced in this run.</p>'
    watch_cards = "".join(render_public_item_card(item) for item in watch_followups) or '<p class="empty-note">No additional watch items were surfaced in this run.</p>'
    notebook_cards = "".join(render_notebook_teaser_card(entry, web_mode=True, link_prefix="./") for entry in notebook_entries[:4]) or '<p class="empty-note">No notebook assignments were generated in this run.</p>'
    atlas_cards = "".join(render_atlas_teaser_card(entry, link_prefix="./") for entry in atlas_entries) or '<p class="empty-note">No atlas dossiers were curated in this run.</p>'
    research_cards = "".join(render_public_research_card(item) for item in research_items) or '<p class="empty-note">No research-linked items were surfaced in this run.</p>'
    reference_cards = "".join(render_public_reference_card(reference, link_prefix="./") for reference in reference_spotlight) or '<p class="empty-note">No reference sheets were spotlighted in this run.</p>'
    archive_rows = "".join(render_public_archive_row(entry, link_prefix="./") for entry in archive_cards) or '<p class="empty-note">No archive days are available yet.</p>'
    live_update_banner = render_live_update_banner()
    live_update_js = live_update_script("./app_exports/manifest.json", str(latest_snapshot.get("run_id", "")), str(latest_snapshot.get("generated_at", "")))

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>The Pathogen Dispatch</title>
    <style>{base_styles()}</style>
  </head>
  <body>
    <main class="page">
      {render_site_header_mode("./", nav_mode="web", active_page="home")}
      {live_update_banner}
      <section class="hero" id="top">
        <p class="kicker">The Edge of Epidemiology</p>
        <h1>The Pathogen Dispatch</h1>
        <p class="subtitle">A source-first infectious disease newsroom for reporters, editors, and public-health analysts who need to know what changed, how trustworthy it is, and where to click next.</p>
        <div class="meta-row">
          <span class="badge accent">{latest_snapshot.get("story_count", 0)} active file(s)</span>
          <span class="badge">{latest_snapshot.get("item_count", 0)} current item(s)</span>
          <span class="badge">Updated {escape(latest_snapshot.get("generated_at", "Unknown"))}</span>
        </div>
      </section>
      {render_source_health_notice(latest_snapshot)}
      {render_page_section_nav([("Lead Outbreak Files", "#lead-outbreak-files"), ("Outbreak Terminal", "#outbreak-terminal"), ("What Changed Today", "#what-changed-today"), ("Reporter's Notebook", "#reporters-notebook"), ("Pathogen Atlas", "#pathogen-atlas"), ("Global Watch", "#global-watch"), ("Research + Reference", "#research-reference"), ("Archive + Backfile", "#archive-backfile")])}
      <section class="panel" id="lead-outbreak-files">
        <h2>Lead Outbreak Files</h2>
        <p class="muted-note">The core live files that deserve attention before the wider desk.</p>
        <div class="story-grid">{lead_story_cards}</div>
      </section>
      <section class="panel" id="outbreak-terminal">
        <h2>Outbreak Terminal</h2>
        <p class="muted-note">High-signal outbreak movements: official alerts, emergency declarations, cross-border spread, contact tracing, case/death shifts, and operational response.</p>
        <p><a class="link-pill" href="./outbreaks.html">Open the full terminal</a></p>
        <div class="card-grid">{terminal_cards}</div>
      </section>
      <section class="panel" id="what-changed-today">
        <h2>What Changed Today</h2>
        <p class="muted-note">New developments that move the reporting picture rather than simply repeat it.</p>
        <div class="card-grid">{changed_cards}</div>
      </section>
      <section class="panel" id="reporters-notebook">
        <h2>Reporter's Notebook</h2>
        <p class="muted-note">A working layer for reporters: what to ask next, which numbers matter, and which framing traps to avoid before you write.</p>
        <p><a class="link-pill" href="./notebook.html">Open the full notebook</a></p>
        <div class="card-grid">{notebook_cards}</div>
      </section>
      <section class="panel" id="pathogen-atlas">
        <h2>Pathogen Atlas</h2>
        <p class="muted-note">A separate evidence-and-geography layer for where selected pathogens likely emerged, how they traveled, and where they intersect your own writing.</p>
        <p><a class="link-pill" href="./atlas.html">Open the atlas</a></p>
        <div class="card-grid">{atlas_cards}</div>
      </section>
      <section class="panel" id="global-watch">
        <h2>Global Watch</h2>
        <p class="muted-note">Major outbreaks, regional developments, and the cross-border signals worth following now.</p>
        <div class="card-grid">{watch_cards}</div>
      </section>
      <section class="panel-grid" id="research-reference">
        <section class="panel">
          <h2>Research Brief</h2>
          <div class="card-grid">{research_cards}</div>
        </section>
        <section class="panel">
          <h2>Reference Desk</h2>
          <div class="card-grid">{reference_cards}</div>
        </section>
      </section>
      <section class="panel" id="archive-backfile">
        <h2>Archive + Backfile</h2>
        <div class="archive-table">{archive_rows}</div>
      </section>
    </main>
    <script>{live_update_js}</script>
  </body>
</html>
"""


def render_source_health_notice(latest_snapshot: dict[str, Any]) -> str:
    if not latest_snapshot.get("degraded"):
        return ""
    failures = [
        normalize_whitespace(str(failure.get("source", "")))
        for failure in latest_snapshot.get("source_failures", [])
        if isinstance(failure, dict) and normalize_whitespace(str(failure.get("source", "")))
    ]
    failure_text = "; ".join(failures[:5]) if failures else "source failures reported"
    if len(failures) > 5:
        failure_text += f"; {len(failures) - 5} more"
    return (
        '<section class="source-health-notice" id="source-health-notice">'
        '<p><strong>Source health:</strong> This refresh is degraded. '
        f'Failed source(s): {escape(failure_text)}. '
        "Absence of a signal from a failed source should not be read as no activity.</p>"
        "</section>"
    )


def render_public_desk_page(
    title: str,
    description: str,
    active_page: str,
    stories: list[dict[str, Any]],
    items: list[dict[str, Any]],
    reference_records: list[dict[str, Any]],
    archive_entries: list[dict[str, Any]],
    *,
    atlas_entries: list[dict[str, Any]] | None = None,
    current_run_id: str = "",
    current_generated_at: str = "",
) -> str:
    if active_page == "notebook":
        return render_notebook_page(
            title,
            description,
            stories,
            reference_records,
            archive_entries,
            web_mode=True,
            current_run_id=current_run_id,
            current_generated_at=current_generated_at,
        )
    if active_page == "research":
        return render_public_research_page(
            title,
            description,
            stories,
            items,
            reference_records,
            archive_entries,
            current_run_id=current_run_id,
            current_generated_at=current_generated_at,
        )
    if active_page == "atlas":
        return render_atlas_page(
            title,
            description,
            atlas_entries or [],
            archive_entries,
            web_mode=True,
            current_run_id=current_run_id,
            current_generated_at=current_generated_at,
        )
    story_cards = "".join(render_public_story_card(story, link_prefix="./") for story in stories) or '<p class="empty-note">No tracked story files matched this desk in the current run.</p>'
    item_cards = "".join(render_public_item_card(item) for item in items) or '<p class="empty-note">No item cards matched this desk in the current run.</p>'
    reference_cards = "".join(render_public_reference_card(reference, link_prefix="./") for reference in reference_records[:4]) or '<p class="empty-note">No related disease sheets are linked here yet.</p>'
    archive_rows = "".join(render_public_archive_row(entry, link_prefix="./") for entry in archive_entries[:8]) or '<p class="empty-note">No archive days are available yet.</p>'
    live_update_banner = render_live_update_banner()
    live_update_js = live_update_script("./app_exports/manifest.json", current_run_id, current_generated_at)
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)} | The Pathogen Dispatch</title>
    <style>{base_styles()}</style>
  </head>
  <body>
    <main class="page">
      {render_site_header_mode("./", nav_mode="web", active_page=active_page)}
      {live_update_banner}
      <section class="hero" id="desk-top">
        <p class="kicker">Source-first desk</p>
        <h1>{escape(title)}</h1>
        <p class="subtitle">{escape(description)}</p>
      </section>
      {render_page_section_nav([("Tracked Files", "#tracked-files"), ("Latest Signals", "#latest-signals"), ("Reference", "#reference-links"), ("Archive", "#archive-links")])}
      <section class="panel" id="tracked-files">
        <h2>Tracked Files</h2>
        <div class="story-grid">{story_cards}</div>
      </section>
      <section class="panel" id="latest-signals">
        <h2>Latest Signals</h2>
        <div class="card-grid">{item_cards}</div>
      </section>
      <section class="panel-grid">
        <section class="panel" id="reference-links">
          <h2>Related Disease Sheets</h2>
          <div class="card-grid">{reference_cards}</div>
        </section>
        <section class="panel" id="archive-links">
          <h2>Recent Archive Days</h2>
          <div class="archive-table">{archive_rows}</div>
        </section>
      </section>
    </main>
    <script>{live_update_js}</script>
  </body>
</html>
"""


def render_public_research_page(
    title: str,
    description: str,
    stories: list[dict[str, Any]],
    items: list[dict[str, Any]],
    reference_records: list[dict[str, Any]],
    archive_entries: list[dict[str, Any]],
    *,
    current_run_id: str = "",
    current_generated_at: str = "",
) -> str:
    research_briefs = [
        item
        for item in items
        if item.get("evidence_type") in {"journal_article", "preprint", "research_linked"}
        and item.get("category") != "Virology and pathogen evolution"
    ]
    evolution_briefs = [item for item in items if item.get("category") == "Virology and pathogen evolution"]
    related_story_cards = collect_related_stories_from_references(reference_records, stories)
    research_cards = "".join(render_public_research_card(item) for item in research_briefs) or '<p class="empty-note">No current papers or preprints cleared the desk filters in this run.</p>'
    evolution_cards = "".join(render_public_research_card(item) for item in evolution_briefs) or '<p class="empty-note">No virology or pathogen-evolution briefs were surfaced in this run.</p>'
    story_cards = "".join(render_public_story_card(story, link_prefix="./") for story in related_story_cards) or '<p class="empty-note">No active outbreak files were directly touched by the current research set.</p>'
    reference_cards = "".join(render_public_reference_card(reference, link_prefix="./") for reference in reference_records[:6]) or '<p class="empty-note">No disease sheets are linked to the current research set yet.</p>'
    archive_rows = "".join(render_public_archive_row(entry, link_prefix="./") for entry in archive_entries[:8]) or '<p class="empty-note">No archive days are available yet.</p>'
    live_update_banner = render_live_update_banner()
    live_update_js = live_update_script("./app_exports/manifest.json", current_run_id, current_generated_at)
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)} | The Pathogen Dispatch</title>
    <style>{base_styles()}</style>
  </head>
  <body>
    <main class="page">
      {render_site_header_mode("./", nav_mode="web", active_page="research")}
      {live_update_banner}
      <section class="hero" id="desk-top">
        <p class="kicker">Source-first desk</p>
        <h1>{escape(title)}</h1>
        <p class="subtitle">{escape(description)}</p>
      </section>
      {render_page_section_nav([("Latest Papers And Preprints", "#latest-papers"), ("Virology + Evolution", "#virology-evolution"), ("Research-Linked Active Files", "#research-linked-files"), ("Disease Sheets", "#reference-links"), ("Archive", "#archive-links")])}
      <section class="panel" id="latest-papers">
        <h2>Latest Papers And Preprints</h2>
        <p class="muted-note">Research that adds mechanism, surveillance, transmission, or outbreak context beyond the daily news stream.</p>
        <div class="card-grid">{research_cards}</div>
      </section>
      <section class="panel" id="virology-evolution">
        <h2>Virology + Pathogen Evolution</h2>
        <p class="muted-note">Genomics, evolution, and laboratory-linked findings that shape how the desk should interpret the current signal environment.</p>
        <div class="card-grid">{evolution_cards}</div>
      </section>
      <section class="panel" id="research-linked-files">
        <h2>Research-Linked Active Files</h2>
        <div class="story-grid">{story_cards}</div>
      </section>
      <section class="panel-grid">
        <section class="panel" id="reference-links">
          <h2>Disease Sheets</h2>
          <div class="card-grid">{reference_cards}</div>
        </section>
        <section class="panel" id="archive-links">
          <h2>Recent Archive Days</h2>
          <div class="archive-table">{archive_rows}</div>
        </section>
      </section>
    </main>
    <script>{live_update_js}</script>
  </body>
    </html>
"""


def render_atlas_teaser_card(entry: dict[str, Any], *, link_prefix: str) -> str:
    atlas_href = f"{link_prefix}atlas.html?pathogen={escape_attr(entry.get('slug', ''))}"
    status = atlas_status_label(str(entry.get("status", "mixed")))
    writing_state = atlas_writing_state_label(str(entry.get("writing_state", "not_yet_written")))
    return (
        '<article class="site-card feature-card atlas-teaser-card">'
        '<div class="kicker">Pathogen atlas</div>'
        f'<h3><a href="{atlas_href}">{escape(entry.get("name", "Untitled atlas entry"))}</a></h3>'
        f'<p>{escape(entry.get("subtitle", ""))}</p>'
        f'<p>{escape(entry.get("summary", ""))}</p>'
        f'<div class="meta-row"><span class="badge accent">{escape(status)}</span><span class="badge">{entry.get("route_count", 0)} route(s)</span><span class="badge">{entry.get("citation_count", 0)} citation(s)</span></div>'
        f'<div class="meta-row"><span class="badge">{escape(writing_state)}</span></div>'
        '</article>'
    )


def render_atlas_hero_plate(entry: dict[str, Any]) -> str:
    visual_asset = entry.get("visual_asset") or {}
    status = atlas_status_label(str(entry.get("status", "mixed")))
    visual_status = str(visual_asset.get("status", "pending")).replace("_", " ").title()
    return (
        '<div class="atlas-plate-shell">'
        '<div class="atlas-plate-kicker">Editorial plate</div>'
        f'<h3>{escape(entry.get("name", ""))}</h3>'
        f'<p class="atlas-plate-subtitle">{escape(entry.get("subtitle", ""))}</p>'
        f'<div class="meta-row"><span class="badge accent">{escape(status)}</span><span class="badge">{escape(entry.get("atlas_scope", ""))}</span></div>'
        f'<p class="muted-note">{escape(entry.get("why_it_matters", ""))}</p>'
        f'<p class="atlas-plate-note">Visual asset pipeline: {escape(visual_status)}</p>'
        '</div>'
    )


def render_atlas_evidence_content(entry: dict[str, Any], *, link_prefix: str) -> str:
    origin = entry.get("origin_claim", {})
    routes = entry.get("spread_routes", [])
    route_rows = "".join(
        (
            '<article class="atlas-route-row">'
            f'<div class="atlas-route-head"><span class="badge">{escape(route.get("date_or_era", ""))}</span><span class="badge">{escape(route_confidence_label(str(route.get("confidence", ""))))}</span></div>'
            f'<h3>{escape(route.get("from_label", ""))} to {escape(route.get("to_label", ""))}</h3>'
            f'<p>{escape(route.get("narrative", ""))}</p>'
            '</article>'
        )
        for route in routes
    ) or '<p class="empty-note">No spread routes have been curated yet.</p>'
    citation_rows = "".join(
        (
            '<li>'
            f'<a href="{escape_attr(citation.get("url", ""))}">{escape(citation.get("short_citation", ""))}</a>'
            f'<div class="muted-note">{escape(citation.get("claim_supported", ""))}</div>'
            '</li>'
        )
        for citation in entry.get("citations", [])
    ) or '<li>No citations are attached to this entry yet.</li>'
    blog_posts = entry.get("linked_blog_posts", [])
    blog_rows = "".join(
        (
            '<li>'
            f'<a href="{escape_attr(post.get("url", ""))}">{escape(post.get("title", ""))}</a>'
            f' <span class="muted-note">({escape(post.get("published_at", ""))}; {escape(post.get("relation", "").replace("_", " "))})</span>'
            '</li>'
        )
        for post in blog_posts
    ) or '<li>No dedicated Edge of Epidemiology post is linked yet.</li>'
    story_rows = "".join(
        (
            '<li>'
            f'<a href="{escape_attr((link_prefix + story.get("story_web_path", "")) if story.get("story_web_path") else story.get("story_url", ""))}">{escape(story.get("display_title", ""))}</a>'
            f'<div class="muted-note">{escape(story.get("latest_update_summary", ""))}</div>'
            '</li>'
        )
        for story in entry.get("related_stories", [])
    ) or '<li>No active outbreak file is linked to this atlas entry right now.</li>'
    reference_link = (
        f'<a class="link-pill" href="{escape_attr(link_prefix + entry.get("reference_web_path", ""))}">Open disease sheet</a>'
        if entry.get("reference_web_path")
        else ""
    )
    writing_state = atlas_writing_state_label(str(entry.get("writing_state", "not_yet_written")))
    return f"""
      <div class="atlas-evidence-stack">
        <div class="meta-row">
          <span class="badge accent">{escape(atlas_status_label(str(entry.get("status", "mixed"))))}</span>
          <span class="badge">{escape(entry.get("pathogen_type", ""))}</span>
          <span class="badge">{escape(writing_state)}</span>
        </div>
        <div class="meta-row">{reference_link}</div>
        <section class="atlas-evidence-section">
          <div class="section-nav-label">Origin claim</div>
          <h3>{escape(origin.get("label", ""))}</h3>
          <p>{escape(origin.get("narrative", ""))}</p>
          <div class="meta-row"><span class="badge">{escape(origin.get("date_or_era", ""))}</span><span class="badge">{escape(route_confidence_label(str(origin.get("confidence", ""))))}</span></div>
        </section>
        <section class="atlas-evidence-section">
          <div class="section-nav-label">Route timeline</div>
          <div class="atlas-route-list">{route_rows}</div>
        </section>
        <section class="atlas-evidence-section">
          <div class="section-nav-label">What is unsettled</div>
          <ul class="bullet-list">{''.join(f'<li>{escape(item)}</li>' for item in entry.get("framing_traps", [])) or '<li>No uncertainty notes are attached yet.</li>'}</ul>
        </section>
        <section class="atlas-evidence-section">
          <div class="section-nav-label">Modern echoes</div>
          <ul class="bullet-list">{''.join(f'<li>{escape(item)}</li>' for item in entry.get("modern_echoes", [])) or '<li>No modern echoes were curated yet.</li>'}</ul>
        </section>
        <section class="atlas-evidence-section">
          <div class="section-nav-label">Supporting papers and source notes</div>
          <ul class="bullet-list atlas-citation-list">{citation_rows}</ul>
        </section>
        <section class="atlas-evidence-section">
          <div class="section-nav-label">Written at The Edge of Epidemiology</div>
          <ul class="bullet-list atlas-blog-list">{blog_rows}</ul>
        </section>
        <section class="atlas-evidence-section">
          <div class="section-nav-label">Linked live files</div>
          <ul class="bullet-list atlas-story-list">{story_rows}</ul>
        </section>
      </div>
    """


def render_atlas_page(
    title: str,
    description: str,
    atlas_entries: list[dict[str, Any]],
    archive_entries: list[dict[str, Any]],
    *,
    web_mode: bool,
    current_run_id: str = "",
    current_generated_at: str = "",
) -> str:
    selected = atlas_entries[0] if atlas_entries else {}
    link_prefix = "./"
    live_update_banner = render_live_update_banner() if web_mode else ""
    live_update_js = (
        live_update_script("./app_exports/manifest.json", current_run_id, current_generated_at)
        if web_mode
        else ""
    )
    atlas_cards = "".join(
        (
            '<button class="site-card atlas-selector-card" type="button" '
            f'data-atlas-select="{escape_attr(entry.get("slug", ""))}" '
            f'data-atlas-search="{escape_attr((entry.get("name", "") + " " + entry.get("subtitle", "") + " " + entry.get("summary", "")).lower())}">'
            f'<div class="kicker">{escape(entry.get("pathogen_type", "Pathogen"))}</div>'
            f'<h3>{escape(entry.get("name", ""))}</h3>'
            f'<p>{escape(entry.get("subtitle", ""))}</p>'
            f'<div class="meta-row"><span class="badge accent">{escape(atlas_status_label(str(entry.get("status", "mixed"))))}</span><span class="badge">{entry.get("route_count", 0)} route(s)</span></div>'
            '</button>'
        )
        for entry in atlas_entries
    ) or '<p class="empty-note">No atlas entries are available yet.</p>'
    archive_rows = "".join(render_public_archive_row(entry, link_prefix="./") for entry in archive_entries[:8]) or '<p class="empty-note">No archive days are available yet.</p>'
    evidence_templates = "".join(
        f'<template id="atlas-evidence-{escape_attr(entry.get("slug", ""))}">{render_atlas_evidence_content(entry, link_prefix=link_prefix)}</template>'
        for entry in atlas_entries
    )
    hero_templates = "".join(
        f'<template id="atlas-hero-{escape_attr(entry.get("slug", ""))}">{render_atlas_hero_plate(entry)}</template>'
        for entry in atlas_entries
    )
    atlas_json = json.dumps(atlas_entries, ensure_ascii=True)
    fallback_rows = "".join(
        (
            '<article class="site-card atlas-fallback-card">'
            f'<h3>{escape(entry.get("name", ""))}</h3>'
            f'<p>{escape(entry.get("summary", ""))}</p>'
            f'<p><strong>Origin:</strong> {escape(entry.get("origin_claim", {}).get("label", ""))}</p>'
            '</article>'
        )
        for entry in atlas_entries
    )

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)} | The Pathogen Dispatch</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin="" />
    <style>{base_styles()}</style>
  </head>
  <body>
    <main class="page">
      {render_site_header_mode("./" if web_mode else "./", nav_mode="web" if web_mode else "local", active_page="atlas")}
      {live_update_banner}
      <section class="hero atlas-hero" id="atlas-top">
        <p class="kicker">Source-first atlas</p>
        <h1>{escape(title)}</h1>
        <p class="subtitle">{escape(description)}</p>
        <div class="meta-row">
          <span class="badge accent">Consensus</span>
          <span class="badge">Mixed / debated</span>
          <span class="badge">Route confidence is explicit</span>
        </div>
        <div class="atlas-hero-grid">
          <div>
            <p class="muted-note">This desk is separate from the daily outbreak stream. It maps selected pathogens as geography problems: where the evidence places likely origin zones, which routes matter, what remains unsettled, and where your own writing already intersects the record.</p>
          </div>
          <div class="atlas-plate" id="atlas-hero-plate">{render_atlas_hero_plate(selected) if selected else '<p class="empty-note">No atlas plates are loaded yet.</p>'}</div>
        </div>
      </section>
      {render_page_section_nav([("Atlas Map", "#atlas-map-panel"), ("Pathogens", "#atlas-pathogens"), ("Evidence", "#atlas-evidence-panel"), ("Archive", "#atlas-archive-links")])}
      <section class="panel-grid atlas-layout">
        <section class="panel" id="atlas-map-panel">
          <h2>Global Atlas Map</h2>
          <p class="muted-note">The map shows the selected pathogen's origin zone plus curated route segments. Geometry comes from atlas data, not from generated imagery.</p>
          <div id="atlas-map" class="atlas-map">Loading map...</div>
          <div class="meta-row atlas-legend">
            <span class="badge accent">Origin marker</span>
            <span class="badge">Strong route</span>
            <span class="badge">Moderate route</span>
            <span class="badge">Debated route</span>
          </div>
        </section>
        <aside class="panel" id="atlas-evidence-panel">
          <h2>Evidence Panel</h2>
          <div id="atlas-evidence-content">{render_atlas_evidence_content(selected, link_prefix=link_prefix) if selected else '<p class="empty-note">No evidence panel is available yet.</p>'}</div>
        </aside>
      </section>
      <section class="panel" id="atlas-pathogens">
        <h2>Pathogen Selector</h2>
        <p class="muted-note">Start with a flagship pathogen whose route story is worth mapping. This is intentionally curated, not an automated everything-map.</p>
        <div class="story-filter-shell">
          <div class="filter-group">
            <label class="filter-label" for="atlas-search">Search atlas pathogens</label>
            <input class="filter-input" id="atlas-search" type="search" placeholder="Search pathogens, route ideas, or historical hooks" />
          </div>
        </div>
        <div class="atlas-selector-grid" id="atlas-selector-grid">{atlas_cards}</div>
        <p class="empty-note" id="atlas-selector-empty" hidden>No atlas pathogens match this search yet.</p>
      </section>
      <section class="panel" id="atlas-archive-links">
        <h2>Recent Archive Days</h2>
        <div class="archive-table">{archive_rows}</div>
      </section>
      <noscript>
        <section class="panel">
          <h2>Atlas Entries</h2>
          <div class="card-grid">{fallback_rows}</div>
        </section>
      </noscript>
    </main>
    {evidence_templates}
    {hero_templates}
    <script id="atlas-data" type="application/json">{atlas_json}</script>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
    <script>{atlas_page_script()}</script>
    {f'<script>{live_update_js}</script>' if live_update_js else ''}
  </body>
</html>
"""


def atlas_page_script() -> str:
    return """
      const atlasEntries = JSON.parse(document.getElementById("atlas-data")?.textContent || "[]");
      const atlasSelectorGrid = document.getElementById("atlas-selector-grid");
      const atlasSelectorButtons = Array.from(document.querySelectorAll("[data-atlas-select]"));
      const atlasSearch = document.getElementById("atlas-search");
      const atlasEmpty = document.getElementById("atlas-selector-empty");
      const atlasEvidence = document.getElementById("atlas-evidence-content");
      const atlasHeroPlate = document.getElementById("atlas-hero-plate");
      const atlasBySlug = Object.fromEntries(atlasEntries.map((entry) => [entry.slug, entry]));
      let atlasMap = null;
      let atlasLayerGroup = null;
      let atlasUserInteracted = false;
      let atlasRotateIndex = 0;

      function atlasSelectedSlug() {
        const params = new URLSearchParams(window.location.search);
        const requested = params.get("pathogen");
        if (requested && atlasBySlug[requested]) return requested;
        return atlasEntries[0] ? atlasEntries[0].slug : "";
      }

      function atlasTemplateHtml(prefix, slug) {
        return document.getElementById(`${prefix}-${slug}`)?.innerHTML || "";
      }

      function atlasRouteStyle(confidence) {
        if (confidence === "strong") return {color: "#8d3f2f", weight: 4, opacity: 0.88, dashArray: ""};
        if (confidence === "moderate") return {color: "#1f5b89", weight: 3, opacity: 0.82, dashArray: "8 6"};
        return {color: "#5f6a73", weight: 2.5, opacity: 0.76, dashArray: "3 7"};
      }

      function initAtlasMap() {
        const mapNode = document.getElementById("atlas-map");
        if (!mapNode || !window.L || atlasMap) return;
        atlasMap = L.map(mapNode, {zoomControl: true, attributionControl: true}).setView([15, 10], 2);
        L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
          maxZoom: 6,
          minZoom: 2,
          attribution: "&copy; OpenStreetMap &copy; CARTO"
        }).addTo(atlasMap);
        atlasLayerGroup = L.layerGroup().addTo(atlasMap);
      }

      function renderAtlasMap(entry, shouldFit) {
        if (!atlasMap || !atlasLayerGroup || !entry) return;
        atlasLayerGroup.clearLayers();
        const bounds = [];
        const origin = entry.origin_claim || {};
        const originCoords = origin.coordinates || [];
        if (originCoords.length === 2) {
          const originLatLng = [originCoords[1], originCoords[0]];
          bounds.push(originLatLng);
          L.circleMarker(originLatLng, {
            radius: 8,
            color: "#8d3f2f",
            weight: 2,
            fillColor: "#8d3f2f",
            fillOpacity: 0.92
          }).bindPopup(`<strong>${origin.label || entry.name}</strong><br>${origin.date_or_era || ""}`).addTo(atlasLayerGroup);
        }
        (entry.spread_routes || []).forEach((route) => {
          const fromCoords = route.from_coordinates || [];
          const toCoords = route.to_coordinates || [];
          if (fromCoords.length !== 2 || toCoords.length !== 2) return;
          const fromLatLng = [fromCoords[1], fromCoords[0]];
          const toLatLng = [toCoords[1], toCoords[0]];
          bounds.push(fromLatLng, toLatLng);
          L.polyline([fromLatLng, toLatLng], atlasRouteStyle(route.confidence || "")).bindPopup(
            `<strong>${route.from_label || ""} to ${route.to_label || ""}</strong><br>${route.date_or_era || ""}<br>${route.narrative || ""}`
          ).addTo(atlasLayerGroup);
          L.circleMarker(toLatLng, {
            radius: 5,
            color: "#1b2836",
            weight: 1,
            fillColor: "#f8f4ea",
            fillOpacity: 0.95
          }).addTo(atlasLayerGroup);
        });
        if (shouldFit && bounds.length > 1) {
          atlasMap.fitBounds(bounds, {padding: [24, 24], maxZoom: 4});
        }
      }

      function setAtlasSelection(slug, options = {}) {
        const entry = atlasBySlug[slug];
        if (!entry) return;
        atlasSelectorButtons.forEach((button) => {
          button.classList.toggle("atlas-selector-active", button.dataset.atlasSelect === slug);
        });
        if (atlasEvidence) atlasEvidence.innerHTML = atlasTemplateHtml("atlas-evidence", slug);
        if (atlasHeroPlate) atlasHeroPlate.innerHTML = atlasTemplateHtml("atlas-hero", slug);
        renderAtlasMap(entry, options.fitMap !== false);
        if (options.updateUrl !== false) {
          const url = new URL(window.location.href);
          url.searchParams.set("pathogen", slug);
          window.history.replaceState({}, "", url.toString());
        }
      }

      function filterAtlasSelectors() {
        const query = String(atlasSearch?.value || "").trim().toLowerCase();
        let visible = 0;
        atlasSelectorButtons.forEach((button) => {
          const matches = !query || String(button.dataset.atlasSearch || "").includes(query);
          button.hidden = !matches;
          if (matches) visible += 1;
        });
        if (atlasEmpty) atlasEmpty.hidden = visible !== 0;
      }

      initAtlasMap();
      const initialSlug = atlasSelectedSlug();
      setAtlasSelection(initialSlug, {updateUrl: false});
      filterAtlasSelectors();

      atlasSelectorButtons.forEach((button) => {
        button.addEventListener("click", () => {
          atlasUserInteracted = true;
          setAtlasSelection(button.dataset.atlasSelect || "");
        });
      });

      if (atlasSearch) {
        atlasSearch.addEventListener("input", () => {
          atlasUserInteracted = true;
          filterAtlasSelectors();
        });
      }

      if (atlasEntries.length > 1) {
        window.setInterval(() => {
          if (atlasUserInteracted) return;
          atlasRotateIndex = (atlasRotateIndex + 1) % atlasEntries.length;
          setAtlasSelection(atlasEntries[atlasRotateIndex].slug, {updateUrl: false});
        }, 7000);
      }
    """


def render_notebook_page(
    title: str,
    description: str,
    stories: list[dict[str, Any]],
    reference_records: list[dict[str, Any]],
    archive_entries: list[dict[str, Any]],
    *,
    web_mode: bool,
    current_run_id: str = "",
    current_generated_at: str = "",
) -> str:
    notebook_entries = build_notebook_entries(stories, reference_records)
    notebook_reference_cards = "".join(
        render_notebook_reference_card(reference, web_mode=web_mode, link_prefix="./")
        for reference in collect_notebook_references(notebook_entries)[:8]
    ) or '<p class="empty-note">No linked disease sheets were attached to the current notebook run.</p>'
    call_sheet_cards = "".join(
        render_notebook_call_card(entry, web_mode=web_mode, link_prefix="./") for entry in notebook_entries
    ) or '<p class="empty-note">No active outbreak files are available for the notebook right now.</p>'
    question_cards = "".join(render_notebook_question_card(entry) for entry in notebook_entries) or '<p class="empty-note">No reporting questions were generated in this run.</p>'
    metric_cards = "".join(render_notebook_metric_card(entry) for entry in notebook_entries) or '<p class="empty-note">No metrics were generated in this run.</p>'
    trap_cards = "".join(render_notebook_trap_card(entry) for entry in notebook_entries) or '<p class="empty-note">No framing traps were generated in this run.</p>'
    archive_rows = "".join(render_notebook_archive_row(entry, web_mode=web_mode, link_prefix="./") for entry in archive_entries[:8]) or '<p class="empty-note">No archive days are available yet.</p>'
    live_update_banner = render_live_update_banner() if web_mode else ""
    live_update_js = live_update_script("./app_exports/manifest.json", current_run_id, current_generated_at) if web_mode else ""
    nav_mode = "web" if web_mode else "local"
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)} | The Pathogen Dispatch</title>
    <style>{base_styles()}</style>
  </head>
  <body>
    <main class="page">
      {render_site_header_mode("./", nav_mode=nav_mode, active_page="notebook")}
      {live_update_banner}
      <section class="hero" id="desk-top">
        <p class="kicker">Working layer</p>
        <h1>{escape(title)}</h1>
        <p class="subtitle">{escape(description)}</p>
        <div class="meta-row"><span class="badge accent">{len(notebook_entries)} active assignment(s)</span><span class="badge">{len(collect_notebook_references(notebook_entries))} linked disease sheet(s)</span></div>
      </section>
      {render_page_section_nav([("Call Sheet", "#call-sheet"), ("Questions To Chase", "#questions-to-chase"), ("Numbers To Watch", "#numbers-to-watch"), ("Framing Traps", "#framing-traps"), ("Disease Sheets", "#disease-sheets"), ("Archive", "#archive-links")])}
      <section class="panel" id="call-sheet">
        <h2>Call Sheet</h2>
        <p class="muted-note">The current live files, why they matter, and the next move that would make the reporting stronger.</p>
        <div class="story-grid">{call_sheet_cards}</div>
      </section>
      <section class="panel" id="questions-to-chase">
        <h2>Questions To Chase</h2>
        <p class="muted-note">The fastest routes to turning the current story stack into a cleaner reported file.</p>
        <div class="card-grid">{question_cards}</div>
      </section>
      <section class="panel-grid">
        <section class="panel" id="numbers-to-watch">
          <h2>Numbers To Watch</h2>
          <div class="card-grid">{metric_cards}</div>
        </section>
        <section class="panel" id="framing-traps">
          <h2>Framing Traps</h2>
          <div class="card-grid">{trap_cards}</div>
        </section>
      </section>
      <section class="panel-grid">
        <section class="panel" id="disease-sheets">
          <h2>Disease Sheets</h2>
          <div class="card-grid">{notebook_reference_cards}</div>
        </section>
        <section class="panel" id="archive-links">
          <h2>Recent Archive Days</h2>
          <div class="archive-table">{archive_rows}</div>
        </section>
      </section>
    </main>
    {f'<script>{live_update_js}</script>' if live_update_js else ''}
  </body>
</html>
"""


def build_notebook_entries(stories: list[dict[str, Any]], reference_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reference_lookup = {reference.get("name", ""): reference for reference in reference_records}
    entries: list[dict[str, Any]] = []
    for story in stories:
        linked_references = []
        for reference_stub in story.get("related_references", []):
            name = str(reference_stub.get("name", ""))
            linked_references.append(reference_lookup.get(name, reference_stub))
        entries.append(
            {
                "story": story,
                "references": linked_references,
                "next_move": notebook_next_move(story, linked_references),
                "questions": notebook_reporting_questions(story, linked_references),
                "metrics": notebook_reporting_metrics(story, linked_references),
                "traps": notebook_framing_traps(story, linked_references),
                "care_note": notebook_care_note(story, linked_references),
            }
        )
    return entries


def collect_notebook_references(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    ordered: list[dict[str, Any]] = []
    for entry in entries:
        for reference in entry.get("references", []):
            name = str(reference.get("name", "")).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            ordered.append(reference)
    return ordered


def notebook_story_href(story: dict[str, Any], *, web_mode: bool, link_prefix: str) -> str:
    if web_mode:
        story_web_path = normalize_whitespace(str(story.get("story_web_path", "")))
        if story_web_path:
            return f"{link_prefix}{story_web_path}"
    return str(story.get("story_url") or "")


def notebook_reference_href(reference: dict[str, Any], *, web_mode: bool, link_prefix: str) -> str:
    if web_mode:
        reference_web_path = normalize_whitespace(str(reference.get("reference_web_path", "")))
        if reference_web_path:
            return f"{link_prefix}{reference_web_path}"
    return str(reference.get("reference_url") or "")


def notebook_archive_href(entry: dict[str, Any], *, web_mode: bool, link_prefix: str) -> str:
    if web_mode:
        archive_web_path = normalize_whitespace(str(entry.get("html_web_path", "")))
        if archive_web_path:
            return f"{link_prefix}{archive_web_path}"
    return str(entry.get("html_url") or "")


def notebook_care_note(story: dict[str, Any], references: list[dict[str, Any]]) -> str:
    for reference in references:
        note = normalize_whitespace(str(reference.get("why_reporters_care", "")))
        if note:
            return note
    return normalize_whitespace(str(story.get("why_it_matters", "This file remains useful because the outbreak is still moving.")))


def notebook_next_move(story: dict[str, Any], references: list[dict[str, Any]]) -> str:
    claim_types = set(story.get("claim_types", []))
    official_count = len(story.get("official_item_ids", []))
    metadata_count = int((story.get("source_kind_counts") or {}).get("metadata_only_signal", 0))
    if official_count == 0:
        return "Get a direct official confirmation or denial before the next write-through."
    if "transmission_change" in claim_types:
        return "Pin down whether the transmission language reflects evidence, concern, or pure precaution."
    if "policy_or_travel" in claim_types:
        return "Separate the operational move from the underlying epidemiology before you frame the story."
    if "suspected_case" in claim_types and "confirmed_case" in claim_types:
        return "Keep the suspected and confirmed lines clean, and find out what testing still has not come back."
    if "new_geography" in claim_types:
        return "Figure out whether the new place is a site of transmission, a site of care, or simply a site of detection."
    if metadata_count >= max(4, official_count + 3):
        return "Push past the thin metadata layer and anchor the story to at least one fully reported or direct-source piece."
    if references and normalize_whitespace(str(references[0].get("surveillance_note", ""))):
        return normalize_whitespace(str(references[0]["surveillance_note"]))
    return "Compare the newest follow-up against the first official line and isolate what actually changed."


def notebook_reporting_questions(story: dict[str, Any], references: list[dict[str, Any]]) -> list[str]:
    claim_types = set(story.get("claim_types", []))
    official_count = len(story.get("official_item_ids", []))
    metadata_count = int((story.get("source_kind_counts") or {}).get("metadata_only_signal", 0))
    questions = []
    if official_count == 0:
        questions.append("Which public-health or government source has still not spoken on the record, and who should be pressed first?")
    else:
        questions.append("What does the official source actually confirm, and where are follow-up reports going beyond that line?")
    if "suspected_case" in claim_types:
        questions.append("How many cases are still suspected, under what case definition, and when will testing resolve them?")
    if "confirmed_case" in claim_types:
        questions.append("How many cases are laboratory confirmed, by which assay, and how recent is that count?")
    if "severity_or_death" in claim_types:
        questions.append("How many hospitalizations, ICU admissions, or deaths are confirmed, and do they cluster in one exposure group?")
    if "transmission_change" in claim_types:
        questions.append("Is there evidence of human-to-human spread, or only precautionary language around the possibility?")
    if "policy_or_travel" in claim_types:
        questions.append("What operational change actually took effect: evacuation, quarantine, travel notice, screening, or something narrower?")
    if "new_geography" in claim_types:
        questions.append("Is the new geography a place of transmission, a place of care, or just where exposed travelers were identified?")
    if metadata_count:
        questions.append("Which of today's links are still thin metadata signals, and what direct or fully reported piece should anchor the file instead?")
    return unique_notebook_lines(questions, limit=6)


def notebook_reporting_metrics(story: dict[str, Any], references: list[dict[str, Any]]) -> list[str]:
    metrics: list[str] = []
    for reference in references:
        metrics.extend(reference.get("metrics_that_matter", []))
    if not metrics:
        claim_types = set(story.get("claim_types", []))
        if "confirmed_case" in claim_types:
            metrics.append("Confirmed case counts by report date and jurisdiction, not just the biggest headline total.")
        if "suspected_case" in claim_types:
            metrics.append("Suspected versus ruled-out counts, because early rumor totals drift fast.")
        if "severity_or_death" in claim_types:
            metrics.append("Severity markers such as hospitalization, ICU care, shock, ventilation, or deaths.")
        if "transmission_change" in claim_types:
            metrics.append("Exposure chains, close-contact links, and whether secondary transmission is actually documented.")
        if "policy_or_travel" in claim_types:
            metrics.append("How many people are subject to evacuation, quarantine, travel guidance, or monitoring, and for how long.")
        if "new_geography" in claim_types:
            metrics.append("Whether the geography count reflects new transmission, imported detection, or patient transfer.")
    return unique_notebook_lines(metrics, limit=3)


def notebook_framing_traps(story: dict[str, Any], references: list[dict[str, Any]]) -> list[str]:
    traps: list[str] = [str(reference.get("what_reporters_get_wrong", "")) for reference in references if reference.get("what_reporters_get_wrong")]
    claim_types = set(story.get("claim_types", []))
    metadata_count = int((story.get("source_kind_counts") or {}).get("metadata_only_signal", 0))
    if "new_geography" in claim_types:
        traps.append("Do not confuse place of care, evacuation, or detection with place of transmission.")
    if "suspected_case" in claim_types and "confirmed_case" in claim_types:
        traps.append("Do not blur suspected and confirmed cases in the headline or lead.")
    if "policy_or_travel" in claim_types:
        traps.append("Do not treat evacuation, quarantine, or travel action as automatic proof that the underlying epidemiology has worsened.")
    if metadata_count:
        traps.append("Do not let thin metadata-only follow-ups outrun what direct or fully reported sources actually establish.")
    if not traps:
        traps.append("Do not let the newest angle bury the basic accounting of who is confirmed, where exposure happened, and what officials have actually said.")
    return unique_notebook_lines(traps, limit=3)


def unique_notebook_lines(values: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = normalize_whitespace(str(value))
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
        if len(ordered) >= limit:
            break
    return ordered


def render_notebook_call_card(entry: dict[str, Any], *, web_mode: bool, link_prefix: str) -> str:
    story = entry["story"]
    href = notebook_story_href(story, web_mode=web_mode, link_prefix=link_prefix)
    badges = [
        f'<span class="badge accent">{story.get("item_count", 0)} item(s)</span>',
        f'<span class="badge">{story.get("source_count", 0)} source(s)</span>',
    ]
    for label in [story.get("current_status_summary", ""), story.get("primary_region", ""), story.get("country", "")]:
        if label:
            badges.append(f'<span class="badge">{escape(label)}</span>')
    reference_links = "".join(
        f'<a class="link-pill" href="{escape_attr(notebook_reference_href(reference, web_mode=web_mode, link_prefix=link_prefix))}">Field guide: {escape(reference.get("name", ""))}</a>'
        for reference in entry.get("references", [])[:2]
    )
    return (
        '<article class="site-card feature-card">'
        '<div class="kicker">Call sheet</div>'
        f'<h3><a href="{escape_attr(href)}">{escape(story.get("display_title", ""))}</a></h3>'
        f'<p>{escape(entry.get("care_note", ""))}</p>'
        f'<p><strong>Next move:</strong> {escape(entry.get("next_move", ""))}</p>'
        f'<p>{escape(story.get("latest_update_summary", ""))}</p>'
        f'<div class="meta-row">{"".join(badges)}</div>'
        f'{f"<div class=\"meta-row\">{reference_links}</div>" if reference_links else ""}'
        '</article>'
    )


def render_notebook_question_card(entry: dict[str, Any]) -> str:
    story = entry["story"]
    bullets = "".join(f"<li>{escape(question)}</li>" for question in entry.get("questions", [])) or "<li>No reporting questions were generated yet.</li>"
    return (
        '<article class="site-card">'
        '<div class="kicker">Questions to chase</div>'
        f'<h3>{escape(story.get("display_title", ""))}</h3>'
        f'<ul class="bullet-list">{bullets}</ul>'
        '</article>'
    )


def render_notebook_metric_card(entry: dict[str, Any]) -> str:
    story = entry["story"]
    bullets = "".join(f"<li>{escape(metric)}</li>" for metric in entry.get("metrics", [])) or "<li>No metrics were generated yet.</li>"
    return (
        '<article class="site-card">'
        '<div class="kicker">Numbers to watch</div>'
        f'<h3>{escape(story.get("display_title", ""))}</h3>'
        f'<ul class="bullet-list">{bullets}</ul>'
        '</article>'
    )


def render_notebook_trap_card(entry: dict[str, Any]) -> str:
    story = entry["story"]
    bullets = "".join(f"<li>{escape(trap)}</li>" for trap in entry.get("traps", [])) or "<li>No framing traps were generated yet.</li>"
    return (
        '<article class="site-card">'
        '<div class="kicker">Framing trap</div>'
        f'<h3>{escape(story.get("display_title", ""))}</h3>'
        f'<ul class="bullet-list">{bullets}</ul>'
        '</article>'
    )


def render_notebook_reference_card(reference: dict[str, Any], *, web_mode: bool, link_prefix: str) -> str:
    href = notebook_reference_href(reference, web_mode=web_mode, link_prefix=link_prefix)
    metrics = "".join(f"<li>{escape(metric)}</li>" for metric in reference.get("metrics_that_matter", [])[:2])
    return (
        '<article class="site-card">'
        '<div class="kicker">Disease sheet</div>'
        f'<h3><a href="{escape_attr(href)}">{escape(reference.get("name", ""))}</a></h3>'
        f'<p>{escape(reference.get("why_reporters_care", ""))}</p>'
        f'{f"<ul class=\"bullet-list\">{metrics}</ul>" if metrics else ""}'
        '</article>'
    )


def render_notebook_archive_row(entry: dict[str, Any], *, web_mode: bool, link_prefix: str) -> str:
    href = notebook_archive_href(entry, web_mode=web_mode, link_prefix=link_prefix)
    return (
        '<article class="archive-row">'
        f'<a href="{escape_attr(href)}"><strong>{escape(entry.get("date", ""))}</strong></a>'
        f'<span class="archive-row-meta">{escape(entry.get("month_name", ""))} {escape(str(entry.get("year", "")))}</span>'
        '</article>'
    )


def render_notebook_teaser_card(entry: dict[str, Any], *, web_mode: bool, link_prefix: str) -> str:
    story = entry["story"]
    href = notebook_story_href(story, web_mode=web_mode, link_prefix=link_prefix)
    first_question = next(iter(entry.get("questions", [])), "")
    return (
        '<article class="site-card">'
        '<div class="kicker">Notebook line</div>'
        f'<h3><a href="{escape_attr(href)}">{escape(story.get("display_title", ""))}</a></h3>'
        f'<p><strong>Next move:</strong> {escape(entry.get("next_move", ""))}</p>'
        f'{f"<p><strong>Question:</strong> {escape(first_question)}</p>" if first_question else ""}'
        '</article>'
    )


def render_public_archive_page(
    archive_entries: list[dict[str, Any]],
    latest_snapshot: dict[str, Any],
    reference_records: list[dict[str, Any]],
) -> str:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in archive_entries:
        grouped[f'{entry["year"]}-{entry["month"]}'].append(entry)
    month_blocks = []
    for month_key in sorted(grouped.keys(), reverse=True):
        month_entries = grouped[month_key]
        month_blocks.append(
            '<section class="panel"><h2>'
            f'{escape(month_entries[0]["month_name"])} {escape(str(month_entries[0]["year"]))}'
            '</h2><div class="archive-table">'
            f'{"".join(render_public_archive_row(entry, link_prefix="../") for entry in month_entries)}'
            '</div></section>'
        )
    story_cards = "".join(render_public_story_card(story, link_prefix="../") for story in latest_snapshot.get("stories", [])[:5])
    reference_cards = "".join(render_public_reference_card(reference, link_prefix="../") for reference in reference_records[:6])
    live_update_banner = render_live_update_banner()
    live_update_js = live_update_script("../app_exports/manifest.json", str(latest_snapshot.get("run_id", "")), str(latest_snapshot.get("generated_at", "")))
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Archive | The Pathogen Dispatch</title>
    <style>{base_styles()}</style>
  </head>
  <body>
    <main class="page">
      {render_site_header_mode("../", nav_mode="web", active_page="archive")}
      {live_update_banner}
      <section class="hero">
        <p class="kicker">Archive + Backfile</p>
        <h1>Archive</h1>
        <p class="subtitle">Daily briefing backfile plus quick paths into the active outbreak files and the disease reference directory.</p>
      </section>
      {render_page_section_nav([("Archive Days", "#archive-days"), ("Active Files", "#active-files"), ("Reference Directory", "#reference-directory")])}
      <div id="archive-days">{"".join(month_blocks) or '<section class="panel"><p class="empty-note">No archive days are available yet.</p></section>'}</div>
      <section class="panel" id="active-files">
        <h2>Active Files</h2>
        <div class="story-grid">{story_cards}</div>
      </section>
      <section class="panel" id="reference-directory">
        <h2>Reference Directory</h2>
        <div class="card-grid">{reference_cards}</div>
      </section>
    </main>
    <script>{live_update_js}</script>
  </body>
</html>
"""


def items_for_edition(items: list[dict[str, Any]], edition_key: str) -> list[dict[str, Any]]:
    return [item for item in items if edition_key in item.get("editions", [])]


def stories_for_edition(stories: list[dict[str, Any]], edition_key: str) -> list[dict[str, Any]]:
    return [story for story in stories if edition_key in story.get("editions", [])]


def render_public_story_card(story: dict[str, Any], *, link_prefix: str) -> str:
    href = f'{link_prefix}{story.get("story_web_path", "")}'
    badges = []
    item_count = story.get("item_count")
    source_count = story.get("source_count")
    if item_count is not None:
        badges.append(f'<span class="badge accent">{item_count} item(s)</span>')
    if source_count is not None:
        badges.append(f'<span class="badge">{source_count} source(s)</span>')
    badges.extend(
        f'<span class="badge">{escape(label)}</span>'
        for label in [story.get("current_status_summary", ""), story.get("primary_region", ""), story.get("country", "")]
        if label
    )
    return (
        f'<article class="site-card feature-card">'
        f'<div class="kicker">Outbreak file</div>'
        f'<h3><a href="{escape_attr(href)}">{escape(story.get("display_title", ""))}</a></h3>'
        f'<p>{escape(story.get("latest_update_summary", ""))}</p>'
        f'{"<div class=\"meta-row\">" + "".join(badges) + "</div>" if badges else ""}'
        f"</article>"
    )


def render_public_reference_card(reference: dict[str, Any], *, link_prefix: str) -> str:
    href = f'{link_prefix}{reference.get("reference_web_path", "")}'
    atlas_href = f'{link_prefix}atlas.html?pathogen={reference.get("atlas_entry_slug", "")}' if reference.get("atlas_entry_slug") else ""
    return (
        f'<article class="site-card">'
        f'<div class="kicker">Reference</div>'
        f'<h3><a href="{escape_attr(href)}">{escape(reference.get("name", ""))}</a></h3>'
        f'<p><strong>Pathogen:</strong> {escape(reference.get("pathogen", ""))}</p>'
        f'<p>{escape(reference.get("why_reporters_care", ""))}</p>'
        f'{f"<div class=\"meta-row\"><a class=\"link-pill\" href=\"{escape_attr(atlas_href)}\">View in Atlas</a></div>" if atlas_href else ""}'
        f"</article>"
    )


def render_public_research_card(item: dict[str, Any]) -> str:
    evidence_label = public_research_evidence_label(str(item.get("evidence_type", "")))
    source_label = item.get("journal") or item.get("publisher_name") or item.get("source", "Unknown source")
    freshness = humanize_data_value("freshness", str(item.get("freshness_state", "live")))
    why_it_matters = research_why_it_matters(item)
    caveats = research_evidence_caveat(item)
    doi = normalize_whitespace(str(item.get("doi", "")))
    abstract_url = item.get("abstract_url") or item.get("preferred_url") or item.get("source_url", "")
    return (
        f'<article class="site-card">'
        f'<div class="kicker">{escape(evidence_label)}</div>'
        f'<h3><a href="{escape_attr(item.get("preferred_url") or item.get("source_url", ""))}">{escape(item.get("title", ""))}</a></h3>'
        f'<p>{escape(item.get("summary", ""))}</p>'
        f'<p><strong>Source:</strong> {escape(source_label)}</p>'
        f'{f"<p><strong>Why it matters:</strong> {escape(why_it_matters)}</p>" if why_it_matters else ""}'
        f'{f"<p><strong>Evidence caveat:</strong> {escape(caveats)}</p>" if caveats else ""}'
        f'<div class="meta-row"><span class="badge">{escape(item.get("published_at", "Unknown"))}</span><span class="badge">{escape(freshness)}</span>{f"<span class=\"badge\">DOI: {escape(doi)}</span>" if doi else ""}{f"<a class=\"link-pill\" href=\"{escape_attr(abstract_url)}\">Abstract</a>" if abstract_url else ""}</div>'
        f"</article>"
    )


def collect_related_stories_from_references(reference_records: list[dict[str, Any]], stories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    story_map: dict[str, dict[str, Any]] = {}
    for story in stories:
        story_key = str(story.get("story_id") or story.get("display_title") or "")
        if story_key and story_key not in story_map:
            story_map[story_key] = story
    for reference in reference_records:
        for story in reference.get("related_stories", []):
            story_key = str(story.get("story_id") or story.get("display_title") or "")
            if story_key and story_key not in story_map:
                story_map[story_key] = story
    return list(story_map.values())[:6]


def render_public_item_card(item: dict[str, Any]) -> str:
    quality = normalize_link_quality_label(str(item.get("link_quality", "direct_article")))
    source_confidence = humanize_data_value("source_kind", str(item.get("source_confidence", "")))
    freshness = humanize_data_value("freshness", str(item.get("freshness_state", "live")))
    return (
        f'<article class="site-card">'
        f'<div class="kicker">{escape(public_item_kicker(item))}</div>'
        f'<h3><a href="{escape_attr(item.get("preferred_url") or item.get("source_url", ""))}">{escape(item.get("title", ""))}</a></h3>'
        f'<p>{escape(item.get("summary", ""))}</p>'
        f'<div class="meta-row"><span class="badge">{escape(item.get("publisher_name", item.get("source", "Unknown")))}</span><span class="badge">{escape(item.get("region", ""))}</span><span class="badge">{escape(item.get("published_at", "Unknown"))}</span><span class="badge">{escape(source_confidence)}</span><span class="badge">{escape(freshness)}</span><span class="badge">{escape(quality)}</span></div>'
        f"</article>"
    )


def render_public_archive_row(entry: dict[str, Any], *, link_prefix: str) -> str:
    href = f'{link_prefix}{entry.get("html_web_path", "")}'
    return (
        f'<article class="archive-row">'
        f'<a href="{escape_attr(href)}"><strong>{escape(entry.get("date", ""))}</strong></a>'
        f'<span class="archive-row-meta">{escape(entry.get("month_name", ""))} {escape(str(entry.get("year", "")))}</span>'
        f"</article>"
    )


def public_item_kicker(item: dict[str, Any]) -> str:
    if item.get("content_class") == "research_context":
        return "Research"
    if item.get("official"):
        return "Official update"
    if item.get("content_class") == "metadata_only_signal":
        return "Metadata-only signal"
    return "Publisher coverage"


def public_research_evidence_label(value: str) -> str:
    labels = {
        "journal_article": "Journal article",
        "preprint": "Preprint",
        "research_linked": "Research-linked reporting",
    }
    return labels.get(value, "Research brief")


def research_why_it_matters(item: dict[str, Any]) -> str:
    why_it_matters = normalize_whitespace(str(item.get("why_it_matters", "")))
    if why_it_matters and why_it_matters != "Comes from an official or primary-source channel.":
        return why_it_matters
    if item.get("evidence_type") in {"journal_article", "preprint"}:
        return "Useful for mechanism, transmission, or surveillance context beyond the daily story file."
    return "Reporter-facing research coverage that can sharpen how the desk reads the broader outbreak signal."


def research_evidence_caveat(item: dict[str, Any]) -> str:
    caveat = normalize_whitespace(str(item.get("caveats", "")))
    if caveat and caveat != "Summary stays within source text and metadata; no outside facts were added.":
        return caveat
    if item.get("evidence_type") in {"journal_article", "preprint"}:
        return "Interpret in light of study design, setting, sample size, and how directly the findings travel to the current outbreak picture."
    return "Useful context, but it should not be treated as equivalent to a primary paper or formal preprint."


def humanize_data_value(key: str, value: str) -> str:
    normalized = normalize_whitespace(str(value)).lower().replace(" ", "_")
    if key == "source_kind":
        labels = {
            "official_agency": "Official agency",
            "wire": "Wire",
            "major_newsroom": "Major newsroom",
            "specialist_health": "Specialist health",
            "general_outlet": "General outlet",
            "aggregator_only": "Aggregator only",
            "metadata_only_signal": "Metadata-only signal",
        }
        return labels.get(normalized, value.replace("_", " ").title())
    if key == "freshness":
        labels = {
            "live": "Live fetch",
            "refresh_cache": "Refresh cache",
            "fallback_cache": "Fallback cache",
            "retained": "Retained",
            "unknown": "Unknown",
        }
        return labels.get(normalized, value.replace("_", " ").title())
    return value.replace("_", " ").title()


def render_outbreak_dashboard(story: dict[str, Any], items: list[dict[str, Any]]) -> str:
    override = outbreak_dashboard_override_for_story(story)
    cases = outbreak_dashboard_metric(story, items, override, "cases")
    deaths = outbreak_dashboard_metric(story, items, override, "deaths")
    affected_countries = infer_affected_countries(story, items)
    emergency_status = infer_emergency_status(story, items)
    pathogen_lineage = infer_pathogen_lineage(story, items)
    last_updated = normalize_whitespace(str(story.get("latest_updated_at") or story.get("updated_at") or "Unknown")) or "Unknown"
    rows = [
        (cases.get("label", "Cases"), cases["value"], cases["note"]),
        ("Deaths", deaths["value"], deaths["note"]),
        ("Affected countries", affected_countries["value"], affected_countries["note"]),
        ("WHO / emergency status", emergency_status["value"], emergency_status["note"]),
        ("Virus / species / lineage", pathogen_lineage["value"], pathogen_lineage["note"]),
        ("Last updated", last_updated, "Monitor timestamp for this story file."),
    ]
    cards = "".join(
        '<div class="dashboard-item">'
        f'<span class="dashboard-label">{escape(label)}</span>'
        f'<strong>{escape(value)}</strong>'
        f'<span class="dashboard-note">{escape(note)}</span>'
        "</div>"
        for label, value, note in rows
    )
    return (
        '<div class="outbreak-dashboard-block" id="outbreak-dashboard">'
        '<h2 class="hero-subhead">Outbreak dashboard</h2>'
        f'<div class="outbreak-dashboard">{cards}</div>'
        "</div>"
    )


def outbreak_dashboard_metric(story: dict[str, Any], items: list[dict[str, Any]], override: dict[str, Any], metric_kind: str) -> dict[str, str]:
    override_metric = dashboard_override_metric(override, metric_kind)
    if override_metric and not dashboard_override_metric_is_stale(story, items, override, metric_kind, override_metric):
        return override_metric
    return infer_outbreak_metric(story, items, metric_kind)


@lru_cache(maxsize=1)
def load_outbreak_dashboard_overrides() -> dict[str, Any]:
    if not DASHBOARD_OVERRIDES_PATH.exists():
        return {}
    payload = yaml.safe_load(DASHBOARD_OVERRIDES_PATH.read_text()) or {}
    if not isinstance(payload, dict):
        return {}
    overrides = payload.get("overrides", {})
    return overrides if isinstance(overrides, dict) else {}


def outbreak_dashboard_override_for_story(story: dict[str, Any]) -> dict[str, Any]:
    overrides = load_outbreak_dashboard_overrides()
    story_ids = [
        normalize_whitespace(str(story.get("story_id", ""))),
        normalize_whitespace(str(story.get("id", ""))),
    ]
    story_path = normalize_whitespace(str(story.get("story_web_path", "")))
    if story_path:
        story_ids.append(Path(story_path).stem)
    for story_id in story_ids:
        if story_id and isinstance(overrides.get(story_id), dict):
            return overrides[story_id]
    return {}


def dashboard_override_metric(override: dict[str, Any], metric_kind: str) -> dict[str, str] | None:
    metric = override.get(metric_kind, {}) if isinstance(override, dict) else {}
    if not isinstance(metric, dict) or not metric.get("value"):
        return None
    result = {
        "value": normalize_whitespace(str(metric.get("value", ""))),
        "note": dashboard_override_metric_note(override, metric),
    }
    if metric_kind == "cases":
        result["label"] = normalize_whitespace(str(metric.get("label") or "Reported cases"))
    return result


def dashboard_override_metric_note(override: dict[str, Any], metric: dict[str, Any]) -> str:
    note = normalize_whitespace(str(metric.get("note", "")))
    if note:
        return note
    source_name = normalize_whitespace(str(override.get("source_name") or "curated source"))
    source_status = normalize_whitespace(str(override.get("source_status") or "Curated public report"))
    as_of = normalize_whitespace(str(override.get("as_of") or "date not captured"))
    return f"{source_status} from {source_name} ({as_of}); verify against official surveillance updates."


def dashboard_override_metric_is_stale(
    story: dict[str, Any],
    items: list[dict[str, Any]],
    override: dict[str, Any],
    metric_kind: str,
    metric: dict[str, str],
) -> bool:
    override_value = metric_numeric_value(metric.get("value"))
    if override_value is None:
        return False
    override_timestamp = sort_timestamp_value(str(override.get("as_of", "")))
    candidates = collect_outbreak_metric_candidates(story, items, metric_kind)
    for candidate in candidates:
        if not metric_candidate_is_dashboard_authoritative(candidate):
            continue
        candidate_value = int(candidate.get("numeric_value") or 0)
        candidate_timestamp = int(candidate.get("raw_timestamp") or 0)
        if candidate_value > override_value and candidate_timestamp > override_timestamp:
            return True
    return False


def metric_numeric_value(value: Any) -> int | None:
    text = normalize_whitespace(str(value or ""))
    match = re.search(r"\d[\d,]*", text)
    if not match:
        return None
    return int(match.group(0).replace(",", ""))


def infer_outbreak_metric(story: dict[str, Any], items: list[dict[str, Any]], metric_kind: str) -> dict[str, str]:
    candidates = collect_outbreak_metric_candidates(story, items, metric_kind)
    authoritative_candidates = [candidate for candidate in candidates if metric_candidate_is_dashboard_authoritative(candidate)]
    if authoritative_candidates:
        selected = select_metric_candidate(authoritative_candidates)
        value = selected["value"]
        source = selected["source"]
        metric_label = selected["metric_label"]
        result = {"value": value, "note": metric_note_for_source(source, metric_kind, metric_label)}
        if metric_kind == "cases":
            result["label"] = metric_label or "Cases"
        return result
    if candidates:
        note = (
            "Media or preliminary reports mention case counts, but this monitor does not have an official or report-grade total."
            if metric_kind == "cases"
            else "Media or preliminary reports mention deaths, but this monitor does not have an official or report-grade total."
        )
        result = {"value": "Not yet confirmed", "note": note}
        if metric_kind == "cases":
            result["label"] = "Cases"
        return result
    fallback = "Unknown"
    note = (
        "The monitor does not expose a firm case total."
        if metric_kind == "cases"
        else "The monitor does not expose a firm death total."
    )
    result = {"value": fallback, "note": note}
    if metric_kind == "cases":
        result["label"] = "Cases"
    return result


def collect_outbreak_metric_candidates(story: dict[str, Any], items: list[dict[str, Any]], metric_kind: str) -> list[dict[str, Any]]:
    patterns = metric_patterns(metric_kind)
    candidates: list[dict[str, Any]] = []
    for source in story_analysis_sources(story, items):
        text = source["text"]
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.I):
                if metric_context_looks_historical(text, match.start(), match.end()):
                    continue
                qualifier = metric_display_qualifier(match.groupdict().get("qualifier", ""), text, match.start(), match.end())
                value = format_metric_value(qualifier, match.group("number"))
                numeric_value = int(match.group("number").replace(",", ""))
                metric_label = case_metric_label(match.groupdict().get("case_status", "")) if metric_kind == "cases" else ""
                candidates.append(
                    {
                        "score": metric_candidate_score(source, text),
                        "raw_timestamp": sort_timestamp_value(source.get("date", "")),
                        "numeric_value": numeric_value,
                        "precision_score": metric_precision_score(qualifier, text, match.start(), match.end()),
                        "value": value,
                        "source": source,
                        "metric_label": metric_label,
                    }
                )
    return candidates


def select_metric_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    newest_raw_timestamp = max(int(candidate.get("raw_timestamp", 0)) for candidate in candidates)
    recent_window_start = newest_raw_timestamp - (36 * 60 * 60)
    recent_candidates = [
        candidate
        for candidate in candidates
        if int(candidate.get("raw_timestamp", 0)) >= recent_window_start
    ]
    candidate_pool = recent_candidates or candidates
    return max(
        candidate_pool,
        key=lambda candidate: (
            int(candidate.get("precision_score", 0)),
            int(candidate.get("numeric_value", 0)),
            int(candidate.get("score", 0)),
        ),
    )


def metric_candidate_is_dashboard_authoritative(candidate: dict[str, Any]) -> bool:
    source = candidate.get("source", {})
    source_status = source.get("source_status", "")
    source_kind = source.get("source_kind", "")
    if source_status in {"Official report", "Confirmed"}:
        return True
    if source_kind == "official":
        return True
    return metric_source_reports_authority_count(source)


def metric_source_reports_authority_count(source: dict[str, Any]) -> bool:
    source_kind = str(source.get("source_kind", ""))
    if source_kind == "aggregator_only":
        return False
    text = str(source.get("text", "")).lower()
    authority_patterns = [
        r"\b(?:congo|drc|health ministry|ministry of health|health authorities|authorities|government|officials)\s+(?:says?|said|reported|recorded|confirmed|announced)\b",
        r"\b(?:according to|citing)\s+(?:congo|drc|the health ministry|the ministry of health|health authorities|authorities|officials|government|who)\b",
        r"\b(?:who|africa cdc|cdc|ecdc)\s+(?:says?|said|reported|confirmed|warns?)\b",
        r"\blatest government data\b",
    ]
    return any(re.search(pattern, text) for pattern in authority_patterns)


def metric_patterns(metric_kind: str) -> list[str]:
    number = r"(?P<number>\d[\d,]*)"
    qualifier = r"(?P<qualifier>at least|more than|over|about|around|approximately|approx\.?|almost|nearly|close to)?\s*"
    if metric_kind == "cases":
        return [
            rf"{qualifier}{number}\s+(?P<case_status>suspected|probable|laboratory-confirmed|confirmed|reported|total)?\s*(?:[a-z-]+\s+){{0,3}}cases?",
            rf"{qualifier}{number}\s+(?:[a-z-]+\s+){{0,4}}cases?\s+(?P<case_status>suspected|probable|laboratory-confirmed|confirmed|reported|under investigation)",
            rf"(?P<case_status>suspected|probable|laboratory-confirmed|confirmed|reported|total)\s+(?:[a-z-]+\s+){{0,4}}cases?\s+(?:(?:now|total(?:ing)?|reach(?:es|ed|ing)?|at|to|of)\s+){{0,2}}{qualifier}{number}",
            rf"cases?\s+(?:top|hit|rise(?:s)? to|climb(?:s)? to|reach(?:es)?|reaching|exceed(?:s)?|surpass(?:es)?)\s+{qualifier}{number}",
        ]
    return [
        rf"{qualifier}{number}\s+(?:(?:suspected|probable|confirmed|reported|total|associated)\s+)?(?:deaths?|dead|fatalities)",
        rf"(?:deaths?|death toll|fatalities)\s+(?:top|hit|rise(?:s)? to|climb(?:s)? to|reach(?:es)?|reaching|exceed(?:s)?|surpass(?:es)?)\s+{qualifier}{number}",
        rf"{qualifier}{number}\s+associated deaths?",
    ]


def story_analysis_sources(story: dict[str, Any], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda item: sort_timestamp_value(str(item.get("published_at", ""))), reverse=True):
        text = normalize_whitespace(" ".join([str(item.get("title", "")), str(item.get("summary", ""))]))
        if not text:
            continue
        sources.append(
            {
                "text": text,
                "source": str(item.get("publisher_name") or item.get("display_source") or "source item"),
                "date": str(item.get("published_at") or ""),
                "source_status": story_item_source_status(item)[1],
                "source_kind": story_item_source_kind(item),
            }
        )
    for reference in story.get("related_references", []):
        latest = reference.get("latest_outbreak", {}) if isinstance(reference.get("latest_outbreak"), dict) else {}
        ref_text = normalize_whitespace(
            " ".join(
                str(value)
                for value in [
                    reference.get("pathogen", ""),
                    latest.get("label", ""),
                    latest.get("location", ""),
                    latest.get("summary", ""),
                    reference.get("surveillance_note", ""),
                    reference.get("vaccine_status", ""),
                    reference.get("treatment", ""),
                    reference.get("research_caveats", ""),
                ]
                if value
            )
        )
        if ref_text:
            sources.append(
                {
                    "text": ref_text,
                    "source": str(latest.get("source_name") or reference.get("name") or "reference desk"),
                    "date": str(latest.get("as_of") or ""),
                    "source_status": "Official report" if latest.get("source_name") else "Reference context",
                    "source_kind": "official" if latest.get("source_name") else "reference",
                }
            )
    story_text = normalize_whitespace(
        " ".join(
            [
                str(story.get("display_title", "")),
                str(story.get("lead_title", "")),
                str(story.get("what_happened", "")),
                str(story.get("latest_update_summary", "")),
                " ".join(str(bullet) for bullet in story.get("latest_update_bullets", [])),
            ]
        )
    )
    if story_text:
        sources.append(
            {
                "text": story_text,
                "source": str(story.get("lead_source") or "story monitor"),
                "date": str(story.get("latest_updated_at") or story.get("updated_at") or ""),
                "source_status": "Monitor synthesis",
                "source_kind": "monitor",
            }
        )
    return sources


def metric_candidate_score(source: dict[str, str], text: str) -> int:
    lowered = text.lower()
    score = sort_timestamp_value(source.get("date", ""))
    source_kind = source.get("source_kind", "")
    source_status = source.get("source_status", "")
    if source_status == "Official report":
        score += 72 * 60 * 60
    elif source_kind in {"wire", "specialist_health"}:
        score += 24 * 60 * 60
    elif source_kind == "major_newsroom":
        score += 12 * 60 * 60
    elif source_status == "Needs verification":
        score -= 6 * 60 * 60
    if re.search(r"\bwho says\b|\bsays who\b|\bwho chief\b|\baccording to who\b", lowered):
        score += 12 * 60 * 60
    if "per bbc" in lowered or any(term in lowered for term in ("pre-world cup", "world cup", "fifa", "training camp")):
        score -= 72 * 60 * 60
    return score


def metric_context_looks_historical(text: str, start: int, end: int) -> bool:
    context = text[max(0, start - 90) : min(len(text), end + 90)].lower()
    return any(token in context for token in ("2007", "2014", "2016", "first identified", "past outbreaks", "historical"))


def metric_display_qualifier(qualifier: str, text: str, start: int, end: int) -> str:
    normalized_qualifier = normalize_whitespace(qualifier).lower()
    if normalized_qualifier:
        return normalized_qualifier
    if metric_context_has_threshold_language(text, start, end):
        return "over"
    return ""


def metric_precision_score(qualifier: str, text: str, start: int, end: int) -> int:
    normalized_qualifier = normalize_whitespace(qualifier).lower()
    if normalized_qualifier or metric_context_has_threshold_language(text, start, end):
        return 1
    return 2


def metric_context_has_threshold_language(text: str, start: int, end: int) -> bool:
    context = text[max(0, start - 45) : min(len(text), end + 25)].lower()
    return bool(re.search(r"\b(top|tops|topped|exceed(?:s|ed)?|surpass(?:es|ed)?)\b", context))


def format_metric_value(qualifier: str, number: str) -> str:
    normalized_qualifier = normalize_whitespace(qualifier).lower().replace("approx.", "approximately")
    qualifier_labels = {
        "at least": "At least",
        "more than": "More than",
        "over": "Over",
        "about": "About",
        "around": "Around",
        "approximately": "Approximately",
        "almost": "Almost",
        "nearly": "Nearly",
        "close to": "Close to",
    }
    number = number.replace(",", "")
    formatted = f"{int(number):,}" if number.isdigit() else number
    if normalized_qualifier:
        return f"{qualifier_labels.get(normalized_qualifier, normalized_qualifier.title())} {formatted}"
    return formatted


def case_metric_label(case_status: str) -> str:
    status = (
        normalize_whitespace(case_status)
        .lower()
        .replace("under investigation", "suspected")
        .replace("laboratory-confirmed", "confirmed")
    )
    labels = {
        "suspected": "Suspected cases",
        "probable": "Probable cases",
        "confirmed": "Confirmed cases",
        "reported": "Reported cases",
        "total": "Total cases",
    }
    return labels.get(status, "Cases")


def metric_note_for_source(source: dict[str, str], metric_kind: str, metric_label: str = "") -> str:
    source_name = source.get("source") or "monitor source"
    date_text = source.get("date") or "date not captured"
    source_status = source.get("source_status") or "Needs verification"
    subject = metric_note_subject(metric_kind, metric_label)
    if source_status in {"Official report", "Confirmed"} or source.get("source_kind") == "official":
        return f"Official-source {subject} as of {metric_source_as_of(date_text)}; definitions may still change with case finding."
    if metric_source_reports_authority_count(source):
        return f"Authority-citing public report from {source_name} ({date_text}); verify against official surveillance updates."
    if source_status == "Needs verification":
        return f"Observed in {source_name} ({date_text}); treat as not yet confirmed by this monitor."
    return f"Public-report {subject} from {source_name} ({date_text}); compare against official updates."


def metric_source_as_of(date_text: str) -> str:
    normalized = normalize_whitespace(date_text)
    if re.match(r"^\d{4}-\d{2}-\d{2}", normalized):
        return normalized[:10]
    return normalized or "date not captured"


def metric_note_subject(metric_kind: str, metric_label: str = "") -> str:
    if metric_kind != "cases":
        return "death count"
    normalized_label = normalize_whitespace(metric_label).lower()
    if not normalized_label or normalized_label == "cases":
        return "case count"
    if normalized_label.endswith(" cases"):
        return f"{normalized_label[:-6]}-case count"
    return f"{normalized_label} count"


def infer_affected_countries(story: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, str]:
    countries: list[str] = []
    for item in items:
        if item.get("official") or item.get("source_confidence") == "official_agency":
            countries.extend(split_country_field(str(item.get("country", ""))))
    countries.extend(split_country_field(str(story.get("country", ""))))
    for reference in story.get("related_references", []):
        latest = reference.get("latest_outbreak", {}) if isinstance(reference.get("latest_outbreak"), dict) else {}
        countries.extend(extract_country_mentions(str(latest.get("location", ""))))
        countries.extend(extract_country_mentions(str(latest.get("summary", ""))))
    normalized = dedupe_preserve_order(public_country_label(country) for country in countries if country)
    if not normalized:
        return {"value": "Unknown", "note": "No affected-country field was firm enough to summarize."}
    return {"value": "; ".join(normalized), "note": "Derived from official/reference country fields where available."}


def split_country_field(value: str) -> list[str]:
    cleaned = normalize_whitespace(value)
    if not cleaned:
        return []
    if cleaned.lower() in BROAD_REGION_LABELS:
        return []
    return [part.strip() for part in re.split(r"\s*/\s*|\s+and\s+|;", cleaned) if part.strip()]


def extract_country_mentions(text: str) -> list[str]:
    mentions: list[str] = []
    for pattern, label in [
        (r"\bDemocratic Republic of (?:the )?Congo\b|\bDRC\b|\bCongo\b", "DRC"),
        (r"\bUganda\b", "Uganda"),
        (r"\bSouth Sudan\b", "South Sudan"),
        (r"\bRwanda\b", "Rwanda"),
        (r"\bKenya\b", "Kenya"),
    ]:
        if re.search(pattern, text, flags=re.I):
            mentions.append(label)
    return mentions


def public_country_label(country: str) -> str:
    cleaned = normalize_whitespace(country)
    replacements = {
        "Democratic Republic of the Congo": "DRC",
        "Democratic Republic of Congo": "DRC",
        "Congo": "DRC",
    }
    return replacements.get(cleaned, cleaned)


def infer_emergency_status(story: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, str]:
    sources = story_analysis_sources(story, items)
    official_text = emergency_status_text(sources, official_or_reference_status_source)
    if has_who_pheic_language(official_text):
        return {"value": "WHO PHEIC declared", "note": "Emergency status appears in the official/reference layer."}
    if has_africa_cdc_phecs_language(official_text):
        return {"value": "Africa CDC continental emergency", "note": "Official/reference layer reports a continental emergency declaration."}
    public_report_text = emergency_status_text(sources, public_report_status_source)
    if has_who_pheic_language(public_report_text):
        return {"value": "WHO PHEIC reported, not verified", "note": "Reported in public-source text; confirm against WHO emergency notices."}
    all_text = emergency_status_text(sources, lambda _source: True)
    if re.search(r"\bWHO\b.{0,80}\bemergency\b|\bemergency\b.{0,80}\bWHO\b", all_text, flags=re.I):
        return {"value": "WHO emergency language reported", "note": "The exact emergency category was not confirmed by the official/reference layer."}
    return {"value": "Unknown", "note": "No formal WHO/emergency status was extracted from the monitor data."}


def emergency_status_text(sources: list[dict[str, Any]], predicate) -> str:
    return normalize_whitespace(" ".join(str(source.get("text", "")) for source in sources if predicate(source)))


def official_or_reference_status_source(source: dict[str, Any]) -> bool:
    return source.get("source_status") == "Official report" or source.get("source_kind") in {"official", "reference"}


def public_report_status_source(source: dict[str, Any]) -> bool:
    return source.get("source_status") in {"Confirmed", "Media report"} or source.get("source_kind") in {"wire", "major_newsroom", "specialist_health"}


def has_who_pheic_language(text: str) -> bool:
    return bool(re.search(r"public health emergency of international concern|\bPHEIC\b", text, flags=re.I))


def has_africa_cdc_phecs_language(text: str) -> bool:
    return bool(re.search(r"public health emergency of continental security|\bPHECS\b", text, flags=re.I))


def infer_pathogen_lineage(story: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, str]:
    for reference in story.get("related_references", []):
        pathogen = normalize_whitespace(str(reference.get("pathogen", "")))
        if pathogen:
            return {"value": pathogen, "note": "From the linked disease intelligence sheet."}
    text = combined_story_text(story, items)
    if re.search(r"\bBundibugyo\b", text, flags=re.I):
        return {"value": "Bundibugyo virus / ebolavirus species", "note": "Species language appears in source text."}
    return {"value": "Unknown", "note": "The monitor does not expose a specific lineage/species field."}


def render_what_matters_now(story: dict[str, Any], items: list[dict[str, Any]]) -> str:
    bullets = build_what_matters_bullets(story, items)
    rows = "".join(f"<li>{escape(bullet)}</li>" for bullet in bullets[:5])
    return (
        '<section class="panel intelligence-panel" id="what-matters-now">'
        "<h2>What Matters Now</h2>"
        '<p class="muted-note">A short epidemiologic read of the active signal, bounded by what the monitor has actually captured.</p>'
        f'<ul class="bullet-list intelligence-bullets">{rows}</ul>'
        "</section>"
    )


def build_what_matters_bullets(story: dict[str, Any], items: list[dict[str, Any]]) -> list[str]:
    text = combined_story_text(story, items)
    lower = text.lower()
    bullets: list[str] = []
    emergency_status = infer_emergency_status(story, items)
    if emergency_status["value"] != "Unknown":
        bullets.append("Emergency declarations are coordination signals; epidemic size still depends on cleaned surveillance data.")
    elif "who" in lower and "emergency" in lower:
        bullets.append("Emergency language appears in the reporting cluster; the exact authority and category should be checked against official notices.")
    if any(term in lower for term in ("suspected case", "suspected cases", "suspected death", "suspected deaths", "confirmed case", "confirmed cases")):
        bullets.append("Suspected and confirmed counts are moving on different clocks: illness recognition, testing, reporting, and retrospective linkage can all lag.")
    if any(term in lower for term in ("kampala", "kinshasa", "urban", "capital", "city", "imported case", "imported cases")):
        bullets.append("Urban or referral-hospital signals matter because transport, care seeking, and dense contact networks can change the response problem quickly.")
    if any(term in lower for term in ("border", "regional", "screening", "entry ban", "travel", "imported", "uganda", "rwanda", "south sudan", "kenya")):
        bullets.append("Cross-border alerts and screening mark regional risk; sustained transmission outside the core outbreak area still needs source-level confirmation.")
    if any(term in lower for term in ("health worker", "health workers", "healthcare worker", "healthcare workers", "hospital", "clinic")):
        bullets.append("Healthcare-worker infections or deaths are an infection-prevention warning: the response system can become part of the transmission chain.")
    if any(term in lower for term in ("ituri", "eastern drc", "conflict", "insecurity", "violence", "militia")):
        bullets.append("Ituri and eastern-DRC signals require attention to access, security, transport, and laboratory-turnaround constraints alongside headline totals.")
    if any(term in lower for term in ("vaccine", "therapeutic", "treatment", "no cure", "no vaccine", "experimental drug")):
        bullets.append("Vaccine and therapeutic limits matter because countermeasure availability depends on species- and setting-specific guidance.")
    if not bullets:
        bullets.append("The file is active because the source cluster is still changing; watch official updates before treating publisher repetition as new evidence.")
        bullets.append("The practical question is whether new reports change case definition, geography, severity, or response capacity.")
        bullets.append("Source confidence matters: official updates, wire reports, and metadata-only signals should not be weighted as if they were the same object.")
    return dedupe_preserve_order(bullets)[:5]


def render_historical_epidemiology_sidebars(story: dict[str, Any], items: list[dict[str, Any]]) -> str:
    text = combined_story_text(story, items)
    lower = text.lower()
    callouts: list[tuple[str, str]] = []
    if any(term in lower for term in ("kampala", "kinshasa", "urban", "capital", "city", "referral hospital", "airport")):
        callouts.append(
            (
                "Urban Spread",
                "Urban spread changes the outbreak problem: delays, care seeking, contact tracing, hospital exposure, rumor control, and institutional coordination all become harder at once.",
            )
        )
    if any(term in lower for term in ("ituri", "eastern drc", "conflict", "insecurity", "violence", "militia")):
        callouts.append(
            (
                "Conflict-Zone Response",
                "Conflict and insecurity distort surveillance and response: missed deaths, delayed samples, unsafe burials, interrupted contact follow-up, and distrust all change the denominator.",
            )
        )
    callouts.append(
        (
            "Suspected Vs Confirmed Counts",
            "Early outbreak counts reflect case definitions, testing access, laboratory turnaround, and retrospective case finding. Suspected cases can rise before confirmation catches up, and cleaned totals can change after field investigation.",
        )
    )
    callout_html = "".join(
        '<article class="context-callout">'
        f'<h3>{escape(title)}</h3>'
        f'<p>{escape(body)}</p>'
        "</article>"
        for title, body in callouts[:3]
    )
    return (
        '<section class="panel historical-context-panel" id="historical-context">'
        "<h2>Historical Epidemiology Context</h2>"
        f'<div class="context-callout-grid">{callout_html}</div>'
        "</section>"
    )


def combined_story_text(story: dict[str, Any], items: list[dict[str, Any]]) -> str:
    parts: list[str] = [
        str(story.get("display_title", "")),
        str(story.get("lead_title", "")),
        str(story.get("what_happened", "")),
        str(story.get("why_it_matters", "")),
        str(story.get("latest_update_summary", "")),
        " ".join(str(bullet) for bullet in story.get("latest_update_bullets", [])),
    ]
    for reference in story.get("related_references", []):
        latest = reference.get("latest_outbreak", {}) if isinstance(reference.get("latest_outbreak"), dict) else {}
        parts.extend(
            str(value)
            for value in [
                reference.get("pathogen", ""),
                reference.get("vaccine_status", ""),
                reference.get("treatment", ""),
                reference.get("surveillance_note", ""),
                reference.get("research_caveats", ""),
                latest.get("label", ""),
                latest.get("location", ""),
                latest.get("summary", ""),
            ]
            if value
        )
    for item in items:
        parts.extend([str(item.get("title", "")), str(item.get("summary", "")), str(item.get("country", "")), str(item.get("region", ""))])
    return normalize_whitespace(" ".join(parts))


def render_story_methodology_note() -> str:
    return (
        '<section class="panel methodology-note" id="methodology-note">'
        "<h2>Methodology Note</h2>"
        "<p>This rolling monitor aggregates public reporting, official public-health updates, and source metadata. Official surveillance dashboards remain the authority for final counts, line lists, and cleaned outbreak chronologies.</p>"
        "<p>Counts may differ across sources because reporting lags, suspected versus confirmed definitions, retrospective case finding, laboratory turnaround, and duplicate publisher coverage can all move faster than cleaned surveillance data.</p>"
        "</section>"
    )


def story_item_intelligence_category(item: dict[str, Any]) -> tuple[str, str]:
    text = " ".join([str(item.get("title", "")), str(item.get("summary", "")), str(item.get("category", ""))]).lower()
    if any(term in text for term in ("opinion", "commentary", "reaction", "rubio", "trump", "panic", "media", "what to know", "all you need to know")):
        key = "commentary-political-reaction-media-discourse"
    elif any(term in text for term in ("border", "screening", "entry ban", "travel", "imported", "regional coordination", "alert", "uganda", "rwanda", "south sudan", "kenya", "asia")):
        key = "border-regional-spread-concerns"
    elif any(term in text for term in ("response", "support", "deploy", "clinic", "health worker", "health workers", "contact tracing", "fund", "pledges", "scale up", "monitoring")):
        key = "operational-response"
    elif any(term in text for term in ("vaccine", "therapeutic", "treatment", "no cure", "no vaccine", "experimental", "strain", "species", "lineage", "genomic", "analysis of past")):
        key = "scientific-vaccine-therapeutic-context"
    else:
        key = "confirmed-epidemiologic-updates"
    return key, INTELLIGENCE_CATEGORY_LABELS[key]


def story_item_source_status(item: dict[str, Any]) -> tuple[str, str]:
    text = " ".join([str(item.get("title", "")), str(item.get("summary", ""))]).lower()
    confidence = normalize_whitespace(str(item.get("source_confidence", ""))).lower().replace(" ", "_")
    link_quality = normalize_whitespace(str(item.get("link_quality", ""))).lower().replace(" ", "_")
    if any(term in text for term in ("opinion", "commentary", "reaction")) and not item.get("official"):
        return "commentary", "Commentary"
    if item.get("official") or confidence == "official_agency":
        if "confirmed" in text and "not confirmed" not in text:
            return "confirmed", "Confirmed"
        return "official-report", "Official report"
    if any(term in text for term in ("preliminary", "suspected", "reportedly", "under investigation", "not yet confirmed")):
        return "preliminary", "Preliminary"
    if confidence in {"aggregator_only", "metadata_only_signal"} or link_quality == "metadata_only":
        return "needs-verification", "Needs verification"
    return "media-report", "Media report"


def render_story_location_line(item: dict[str, Any]) -> str:
    location = infer_story_item_location(item)
    if not location:
        return ""
    return f'<p class="story-location-line"><strong>Location:</strong> {escape(location)}</p>'


def infer_story_item_location(item: dict[str, Any]) -> str:
    text = " ".join([str(item.get("title", "")), str(item.get("summary", "")), str(item.get("country", ""))])
    country = normalize_whitespace(str(item.get("country", "")))
    region = normalize_whitespace(str(item.get("region", "")))
    if re.search(r"\bMongbwalu\b", text, flags=re.I):
        return "DRC / Ituri / Mongbwalu"
    if re.search(r"\bRwampara\b", text, flags=re.I):
        return "DRC / Ituri / Rwampara"
    if re.search(r"\bIturi\b", text, flags=re.I):
        return "DRC / Ituri"
    if re.search(r"\bKampala\b", text, flags=re.I):
        return "Uganda / Kampala"
    if re.search(r"\bKinshasa\b", text, flags=re.I):
        return "DRC / Kinshasa"
    text_countries = dedupe_preserve_order(public_country_label(country) for country in extract_country_mentions(text))
    if text_countries:
        return " / ".join(text_countries)
    if country:
        parts = [public_country_label(part) for part in split_country_field(country)]
        if parts:
            return " / ".join(dedupe_preserve_order(parts))
    if region and region.lower() not in BROAD_REGION_LABELS:
        return region
    if story_item_intelligence_category(item)[0] == "border-regional-spread-concerns":
        return "Regional"
    return ""


def dedupe_preserve_order(values) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        cleaned = normalize_whitespace(str(value))
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        deduped.append(cleaned)
    return deduped


def render_story_item_card(item: dict[str, Any], label: str) -> str:
    published_at = item.get("published_at", "")
    summary_text = (item.get("summary") or "").strip()
    is_low_detail = bool(item.get("low_detail")) or summary_text == LOW_DETAIL_SUMMARY
    summary_html = "" if is_low_detail or not summary_text else f'<p>{escape(summary_text)}</p>'
    card_class = "site-card sortable-card compact-card" if is_low_detail else "site-card sortable-card"
    link_quality_label = normalize_link_quality_label(str(item.get("link_quality", "direct_article")))
    freshness_badge = render_story_item_freshness_badge(item)
    source_kind_badge = render_source_kind_badge(item)
    source_confidence_badge = render_story_item_source_confidence_badge(item)
    access_badge = render_access_badge(item)
    metadata_badge = '<span class="badge">Metadata only</span>' if is_low_detail else ""
    category_key, category_label = story_item_intelligence_category(item)
    source_status_key, source_status_label = story_item_source_status(item)
    location_line = render_story_location_line(item)
    region = normalize_whitespace(str(item.get("region", ""))) or "Unknown"
    source_kind = story_item_source_kind(item)
    access = story_item_access(item)
    age_bucket = story_item_date_bucket(published_at)
    scope = "official" if item.get("official") else "publisher"
    claim_type = story_item_claim_type(item)
    story_status = normalize_whitespace(str(item.get("story_status", ""))).lower().replace(" ", "_") or "active_investigation"
    return (
        f'<article class="{card_class} searchable-card" data-sort-ts="{sort_timestamp_value(published_at)}" data-sort-source="{escape_attr(str(item.get("publisher_name", item.get("display_source", "Unknown"))))}" data-sort-title="{escape_attr(str(item.get("title", "")))}" data-search="{escape_attr(story_item_search_text(item))}" data-source-kind="{escape_attr(source_kind)}" data-freshness="{escape_attr(str(item.get("freshness_state") or "live"))}" data-link-quality="{escape_attr(str(item.get("link_quality") or "direct_article"))}" data-region="{escape_attr(region)}" data-access="{escape_attr(access)}" data-date-window="{escape_attr(age_bucket)}" data-scope="{escape_attr(scope)}" data-official="{escape_attr('true' if item.get('official') else 'false')}" data-story-status="{escape_attr(story_status)}" data-claim-type="{escape_attr(claim_type)}" data-intel-category="{escape_attr(category_key)}">'
        f'<div class="kicker">{escape(label)}</div>'
        '<div class="story-card-labels">'
        f'<span class="badge story-category story-category-{escape_attr(category_key)}">{escape(category_label)}</span>'
        f'<span class="badge source-status source-status-{escape_attr(source_status_key)}">{escape(source_status_label)}</span>'
        "</div>"
        f'<h3><a href="{escape_attr(item.get("preferred_url") or item.get("source_url", ""))}">{escape(item.get("title", ""))}</a></h3>'
        f"{location_line}"
        f"{summary_html}"
        f'<div class="meta-row"><span class="badge">{escape(item.get("publisher_name", item.get("display_source", "Unknown")))}</span>{source_kind_badge}{source_confidence_badge}{access_badge}{freshness_badge}<span class="badge">{escape(region)}</span><span class="badge">{escape(item.get("published_at", "Unknown"))}</span><span class="badge">{link_quality_label}</span>{metadata_badge}</div>'
        f"</article>"
    )


def render_story_section_note(total_count: int, shown_count: int) -> str:
    if total_count <= shown_count:
        return ""
    hidden_count = total_count - shown_count
    return f'<p class="section-note">Showing {shown_count} of {total_count} items after collapsing {hidden_count} near-duplicate follow-up{"s" if hidden_count != 1 else ""}.</p>'


def render_link_quality_badges(items: list[dict[str, Any]]) -> str:
    direct = sum(1 for item in items if item.get("link_quality") == "direct_article")
    resolved = sum(1 for item in items if item.get("link_quality") == "resolved_article")
    resolved_nonarticle = sum(1 for item in items if item.get("link_quality") == "resolved_nonarticle")
    aggregator_only = sum(1 for item in items if item.get("link_quality") == "wrapper_only")
    metadata_only = sum(1 for item in items if item.get("link_quality") == "metadata_only")
    return "".join(
        [
            f'<span class="badge">Direct links: {direct}</span>',
            f'<span class="badge">Resolved links: {resolved}</span>',
            f'<span class="badge">Resolved non-article: {resolved_nonarticle}</span>',
            f'<span class="badge">Wrapper-only: {aggregator_only}</span>',
            f'<span class="badge">Metadata only: {metadata_only}</span>',
        ]
    )


def render_freshness_badges(items: list[dict[str, Any]], story_freshness_counts: dict[str, int]) -> str:
    counts = dict(story_freshness_counts or {})
    if not counts:
        counts = count_freshness_states(items)
    return "".join(
        [
            f'<span class="badge">Live fetches: {counts.get("live", 0)}</span>',
            f'<span class="badge">Refresh cache: {counts.get("refresh_cache", 0)}</span>',
            f'<span class="badge">Fallback cache: {counts.get("fallback_cache", 0)}</span>',
            f'<span class="badge">Retained: {counts.get("retained", 0)}</span>',
        ]
    )


def count_freshness_states(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"live": 0, "refresh_cache": 0, "fallback_cache": 0, "retained": 0}
    for item in items:
        state = str(item.get("freshness_state") or "live")
        if state not in counts:
            continue
        counts[state] += 1
    return counts


def render_story_item_freshness_badge(item: dict[str, Any]) -> str:
    state = str(item.get("freshness_state") or "").strip()
    if not state:
        return ""
    labels = {
        "live": "Live",
        "refresh_cache": "Refresh cache",
        "fallback_cache": "Fallback cache",
        "retained": "Retained",
    }
    return f'<span class="badge">{escape(labels.get(state, state.replace("_", " ").title()))}</span>'


def normalize_link_quality_label(value: str) -> str:
    labels = {
        "direct_article": "Direct article",
        "resolved_article": "Resolved article",
        "resolved_nonarticle": "Resolved non-article",
        "wrapper_only": "Wrapper only",
        "metadata_only": "Metadata only",
    }
    return labels.get(value, value.replace("_", " "))


def render_source_kind_badge(item: dict[str, Any]) -> str:
    if item.get("official"):
        return '<span class="badge tone-official">Official</span>'
    publisher_tier = normalize_whitespace(str(item.get("publisher_tier", ""))).lower()
    if publisher_tier == "wire":
        return '<span class="badge tone-wire">Wire</span>'
    if publisher_tier in {"major_newsroom", "major newsroom"}:
        return '<span class="badge tone-major">Major newsroom</span>'
    if publisher_tier in {"specialist_health", "specialist health"}:
        return '<span class="badge tone-specialist">Specialist health</span>'
    if item.get("source_confidence") == "aggregator_only":
        return '<span class="badge">Aggregator-only</span>'
    if item.get("source_confidence") == "metadata_only_signal":
        return '<span class="badge">Metadata-only</span>'
    return '<span class="badge">General outlet</span>'


def render_story_item_source_confidence_badge(item: dict[str, Any]) -> str:
    confidence = normalize_whitespace(str(item.get("source_confidence", ""))).lower().replace(" ", "_")
    labels = {
        "official_agency": "Official agency",
        "wire": "Wire confidence",
        "major_newsroom": "Major newsroom confidence",
        "specialist_health": "Specialist health confidence",
        "general_outlet": "General outlet confidence",
        "aggregator_only": "Aggregator-only signal",
        "metadata_only_signal": "Metadata-only signal",
    }
    if not confidence:
        return ""
    return f'<span class="badge">{escape(labels.get(confidence, confidence.replace("_", " ").title()))}</span>'


def render_access_badge(item: dict[str, Any]) -> str:
    access = normalize_whitespace(str(item.get("publisher_access", ""))).lower()
    if access == "subscription":
        return '<span class="badge">Login likely</span>'
    if access == "open":
        return '<span class="badge">Open access</span>'
    return ""


def story_item_access(item: dict[str, Any]) -> str:
    access = normalize_whitespace(str(item.get("publisher_access", ""))).lower()
    if access in {"subscription", "open"}:
        return access
    return "unknown"


def story_item_source_kind(item: dict[str, Any]) -> str:
    if item.get("official"):
        return "official"
    publisher_tier = normalize_whitespace(str(item.get("publisher_tier", ""))).lower().replace(" ", "_")
    if publisher_tier in {"wire", "major_newsroom", "specialist_health"}:
        return publisher_tier
    if item.get("source_confidence") == "aggregator_only":
        return "aggregator_only"
    if item.get("source_confidence") == "metadata_only_signal":
        return "metadata_only_signal"
    return "general_outlet"


def story_item_claim_type(item: dict[str, Any]) -> str:
    text = " ".join([str(item.get("title", "")), str(item.get("summary", ""))]).lower()
    if "suspected" in text or "under investigation" in text:
        return "suspected_case"
    if "confirmed" in text:
        return "confirmed_case"
    if any(term in text for term in ("death", "fatal", "critical", "hospital")):
        return "severity_or_death"
    if any(term in text for term in ("transmission", "human-to-human", "person-to-person")):
        return "transmission_change"
    if any(term in text for term in ("quarantine", "dock", "evacuation", "travel", "advisory")):
        return "policy_or_travel"
    return "general_update"


def story_item_search_text(item: dict[str, Any]) -> str:
    return " ".join(
        normalize_whitespace(
            str(value)
        )
        for value in [
            item.get("title", ""),
            item.get("summary", ""),
            item.get("publisher_name", item.get("display_source", "")),
            item.get("region", ""),
            item.get("preferred_url", ""),
        ]
        if value
    )


def render_story_source_kind_badges(source_kind_counts: dict[str, int]) -> str:
    normalized = {
        "official": int(source_kind_counts.get("official", 0) or 0),
        "wire": int(source_kind_counts.get("wire", 0) or 0),
        "major_newsroom": int(source_kind_counts.get("major_newsroom", 0) or 0),
        "specialist_health": int(source_kind_counts.get("specialist_health", 0) or 0),
        "general_outlet": int(source_kind_counts.get("general_outlet", 0) or 0),
        "aggregator_only": int(source_kind_counts.get("aggregator_only", 0) or 0),
        "metadata_only_signal": int(source_kind_counts.get("metadata_only_signal", 0) or 0),
    }
    labels = [
        ("Official sources", normalized["official"]),
        ("Wire", normalized["wire"]),
        ("Major newsroom", normalized["major_newsroom"]),
        ("Specialist health", normalized["specialist_health"]),
        ("General outlet", normalized["general_outlet"]),
        ("Aggregator-only", normalized["aggregator_only"]),
        ("Metadata-only", normalized["metadata_only_signal"]),
    ]
    return "".join(f'<span class="badge">{escape(label)}: {count}</span>' for label, count in labels)


def render_story_source_confidence_badges(source_confidence_counts: dict[str, int]) -> str:
    labels = [
        ("Official", int(source_confidence_counts.get("official_agency", 0) or 0)),
        ("Wire", int(source_confidence_counts.get("wire", 0) or 0)),
        ("Major newsroom", int(source_confidence_counts.get("major_newsroom", 0) or 0)),
        ("Specialist health", int(source_confidence_counts.get("specialist_health", 0) or 0)),
        ("General", int(source_confidence_counts.get("general_outlet", 0) or 0)),
        ("Wrapper only", int(source_confidence_counts.get("aggregator_only", 0) or 0)),
    ]
    return "".join(f'<span class="badge">{escape(label)} confidence: {count}</span>' for label, count in labels)


def render_story_claim_badges(claim_types: list[str]) -> str:
    if not claim_types:
        return ""
    return "".join(f'<span class="badge">{escape(format_claim_type_label(value))}</span>' for value in claim_types[:6])


def render_story_filter_bar(items: list[dict[str, Any]]) -> str:
    intel_category_options = build_story_filter_options(items, "intel_category", lambda item: story_item_intelligence_category(item)[0])
    source_kind_options = build_story_filter_options(items, "source_kind", source_kinds_for_item)
    freshness_options = build_story_filter_options(items, "freshness", lambda item: str(item.get("freshness_state") or "live"))
    link_quality_options = build_story_filter_options(items, "link_quality", lambda item: str(item.get("link_quality") or "direct_article"))
    region_options = build_story_filter_options(items, "region", lambda item: normalize_whitespace(str(item.get("region", ""))) or "Unknown")
    access_options = build_story_filter_options(items, "access", story_item_access)
    date_window_options = build_story_filter_options(items, "date_window", lambda item: story_item_date_bucket(item.get("published_at", "")))
    story_status_options = build_story_filter_options(items, "story_status", lambda item: normalize_whitespace(str(item.get("story_status", "active_investigation"))))
    claim_type_options = build_story_filter_options(items, "claim_type", story_item_claim_type)
    return (
        '<div class="story-filter-shell">'
        '<div class="story-filter-grid">'
        f'{render_story_search_field()}'
        f'{render_story_filter_select("Category", "intel-category", intel_category_options)}'
        f'{render_story_filter_select("Source type", "source-kind", source_kind_options)}'
        f'{render_story_filter_select("Freshness", "freshness", freshness_options)}'
        f'{render_story_filter_select("Link quality", "link-quality", link_quality_options)}'
        f'{render_story_filter_select("Region", "region", region_options)}'
        f'{render_story_filter_select("Access", "access", access_options)}'
        f'{render_story_filter_select("Date range", "date-window", date_window_options)}'
        f'{render_story_filter_select("Story status", "story-status", story_status_options)}'
        f'{render_story_filter_select("Claim type", "claim-type", claim_type_options)}'
        "</div>"
        '<p id="story-filter-status" class="muted-note">Showing all story-file cards.</p>'
        "</div>"
    )


def render_story_search_field() -> str:
    return (
        '<label class="filter-group filter-search-wide">'
        '<span class="filter-label">Search</span>'
        '<input id="story-filter-search" class="filter-input" type="search" placeholder="Search titles, publishers, places, or phrases" />'
        "</label>"
    )


def render_story_filter_select(label: str, key: str, options: list[tuple[str, str]]) -> str:
    option_html = ['<option value="all">All</option>']
    option_html.extend(
        f'<option value="{escape_attr(value)}">{escape(display)}</option>'
        for value, display in options
    )
    return (
        '<label class="filter-group">'
        f'<span class="filter-label">{escape(label)}</span>'
        f'<select class="filter-select" data-story-filter="{escape_attr(key)}">{"".join(option_html)}</select>'
        "</label>"
    )


def build_story_filter_options(
    items: list[dict[str, Any]],
    key: str,
    extractor,
) -> list[tuple[str, str]]:
    seen: set[str] = set()
    options: list[tuple[str, str]] = []
    for item in items:
        raw_value = normalize_whitespace(str(extractor(item))).strip()
        if not raw_value:
            continue
        value = raw_value.lower().replace(" ", "_")
        if value in seen:
            continue
        seen.add(value)
        options.append((value, format_story_filter_label(key, raw_value)))
    options.sort(key=lambda pair: pair[1])
    return options


def format_story_filter_label(key: str, value: str) -> str:
    normalized = value.lower().replace("_", " ")
    if key == "source_kind":
        labels = {
            "official": "Official",
            "wire": "Wire",
            "major newsroom": "Major newsroom",
            "specialist health": "Specialist health",
            "aggregator only": "Aggregator-only",
            "general outlet": "General outlet",
            "metadata only signal": "Metadata-only signal",
            "other": "Other",
        }
        return labels.get(normalized, value.title())
    if key == "intel_category":
        return INTELLIGENCE_CATEGORY_LABELS.get(value, value.replace("-", " ").replace("_", " ").title())
    if key == "freshness":
        labels = {
            "live": "Live fetch",
            "refresh cache": "Refresh cache",
            "fallback cache": "Fallback cache",
            "retained": "Retained",
        }
        return labels.get(normalized, value.title())
    if key == "link_quality":
        labels = {
            "direct article": "Direct article",
            "resolved article": "Resolved article",
            "resolved nonarticle": "Resolved non-article",
            "wrapper only": "Wrapper only",
            "metadata only": "Metadata only",
        }
        return labels.get(normalized, value.replace("_", " ").title())
    if key == "access":
        labels = {
            "open": "Open access",
            "subscription": "Login likely",
            "unknown": "Access unknown",
        }
        return labels.get(normalized, value.title())
    if key == "date_window":
        labels = {
            "1": "Past 24 hours",
            "3": "Past 3 days",
            "7": "Past 7 days",
            "older": "Older",
            "unknown": "Unknown date",
        }
        return labels.get(normalized, value.title())
    if key == "story_status":
        return humanize_story_status(value)
    if key == "claim_type":
        return format_claim_type_label(value)
    return value


def source_kinds_for_item(item: dict[str, Any]) -> str:
    return story_item_source_kind(item)


def story_item_date_bucket(published_at: str | None) -> str:
    if not published_at:
        return "unknown"
    timestamp = sort_timestamp_value(published_at)
    if not timestamp:
        return "unknown"
    age_days = max((datetime.now().timestamp() - timestamp) / 86400, 0)
    if age_days <= 1:
        return "1"
    if age_days <= 3:
        return "3"
    if age_days <= 7:
        return "7"
    return "older"


def render_timeline_row(entry: dict[str, Any]) -> str:
    bullets = "".join(f"<li>{escape(clean_story_text(bullet))}</li>" for bullet in entry.get("bullets", [])) or "<li>No bullet text captured.</li>"
    return (
        f'<article class="timeline-row sortable-card" data-sort-ts="{sort_timestamp_value(entry.get("generated_at", ""))}" data-sort-title="{escape_attr(str(entry.get("generated_at", "Unknown")))}">'
        f'<div class="meta-row"><span class="badge accent">{escape(entry.get("generated_at", "Unknown"))}</span>'
        f'<span class="badge">{entry.get("item_count", 0)} item(s)</span><span class="badge">{entry.get("source_count", 0)} source(s)</span></div>'
        f'<ul class="bullet-list">{bullets}</ul>'
        f"</article>"
    )


def render_site_header(base_path: str) -> str:
    return render_site_header_mode(base_path, nav_mode="local", active_page="index")


def render_site_header_mode(base_path: str, *, nav_mode: str, active_page: str) -> str:
    if nav_mode == "web":
        nav_items = [
            ("edge_home", "Edge home", "/"),
            ("home", "Home", f"{base_path}index.html"),
            ("notebook", "Notebook", f"{base_path}notebook.html"),
            ("atlas", "Atlas", f"{base_path}atlas.html"),
            ("outbreaks", "Outbreak terminal", f"{base_path}outbreaks.html"),
            ("watch", "Global watch", f"{base_path}watch.html"),
            ("africa", "Africa", f"{base_path}africa.html"),
            ("asia", "Asia", f"{base_path}asia.html"),
            ("research", "Research", f"{base_path}research.html"),
            ("official", "Official alerts", f"{base_path}official.html"),
            ("archive", "Archive", f"{base_path}archive/index.html"),
        ]
        title = "Source-first newsroom desks"
    else:
        nav_items = [
            ("edge_home", "Edge home", "/"),
            ("briefing", "Latest briefing", f"{base_path}latest.html#view-briefing"),
            ("tracking", "Global watch", f"{base_path}latest.html#view-tracking"),
            ("atlas", "Atlas", f"{base_path}atlas.html"),
            ("reference", "Research + reference", f"{base_path}latest.html#view-reference"),
            ("notebook", "Notebook", f"{base_path}notebook.html"),
            ("archive", "Archive + backfile", f"{base_path}latest.html#view-archive"),
            ("index", "Site index", f"{base_path}index.html"),
        ]
        title = "Unified Desk Navigation"
    links = "".join(render_nav_link(label, href, key == active_page) for key, label, href in nav_items)
    return (
        '<header class="site-header">'
        '<div class="site-header-copy">'
        '<div class="kicker">The Pathogen Dispatch</div>'
        f'<p class="site-header-title">{escape(title)}</p>'
        '</div>'
        '<nav class="site-nav" aria-label="Site navigation">'
        f"{links}"
        '</nav>'
        '</header>'
    )


def render_nav_link(label: str, href: str, active: bool) -> str:
    active_class = " active" if active else ""
    current = ' aria-current="page"' if active else ""
    return f'<a class="site-nav-link{active_class}" href="{escape_attr(href)}"{current}>{escape(label)}</a>'


def render_page_section_nav(links: list[tuple[str, str]]) -> str:
    link_html = "".join(
        f'<a class="section-nav-link" href="{escape_attr(target)}">{escape(label)}</a>'
        for label, target in links
    )
    return (
        '<nav class="section-nav panel utility-panel" aria-label="Section navigation">'
        '<div class="section-nav-label">On this page</div>'
        f'<div class="section-nav-links">{link_html}</div>'
        '</nav>'
    )


def render_live_update_banner() -> str:
    return (
        '<section class="live-update-banner panel utility-panel" id="live-update-banner" hidden aria-live="polite" role="status" data-live-update-banner="true">'
        '<div class="live-update-copy">'
        '<div class="section-nav-label">New edition available</div>'
        '<p class="live-update-text" id="live-update-text">An updated edition is available. Load the latest run when you are ready.</p>'
        '</div>'
        '<div class="live-update-actions">'
        '<button class="live-update-dismiss" id="live-update-dismiss" type="button" '
        "onclick=\"(function(btn){const banner=btn.closest('[data-live-update-banner]');if(banner){banner.hidden=true;banner.style.display='none';const runId=(banner.dataset&&banner.dataset.pendingRunId)||'';const key=(banner.dataset&&banner.dataset.dismissKey)||('pathogen-dispatch-live-update-dismissed:'+window.location.pathname);try{window.sessionStorage.setItem(key, window.location.pathname+'::'+(runId||'unknown'));}catch(error){}}return false;})(this)\">Keep reading</button>"
        '<button class="live-update-button" id="live-update-refresh" type="button" '
        "onclick=\"(function(btn){const banner=btn.closest('[data-live-update-banner]');if(banner){banner.hidden=true;banner.style.display='none';}const url=new URL(window.location.href);url.searchParams.set('_edition', String(Date.now()));window.location.replace(url.toString());return false;})(this)\">Load latest</button>"
        "</div>"
        '</section>'
    )


def live_update_script(manifest_path: str, current_run_id: str, current_generated_at: str) -> str:
    return f"""
      const liveUpdateBanner = document.getElementById("live-update-banner");
      const liveUpdateButton = document.getElementById("live-update-refresh");
      const liveUpdateDismiss = document.getElementById("live-update-dismiss");
      const liveUpdateText = document.getElementById("live-update-text");
      const currentRunId = {current_run_id!r};
      const currentGeneratedAt = {current_generated_at!r};
      const manifestPath = {manifest_path!r};
      const liveUpdateStorageKey = `pathogen-dispatch-live-update-dismissed:${{window.location.pathname}}`;
      const liveUpdateStart = Date.now();
      let pendingLiveUpdateRunId = "";

      function liveUpdateShouldRun() {{
        return window.location.protocol === "https:" || window.location.protocol === "http:";
      }}

      function getManifestRunId(manifest) {{
        return String(manifest.latest_run_id || manifest.run_id || "").trim();
      }}

      function liveUpdateDismissValue(runId) {{
        return `${{window.location.pathname}}::${{runId || "unknown"}}`;
      }}

      function isLiveUpdateDismissed(runId) {{
        try {{
          return window.sessionStorage.getItem(liveUpdateStorageKey) === liveUpdateDismissValue(runId);
        }} catch (error) {{
          return false;
        }}
      }}

      function dismissLiveUpdate(runId) {{
        if (!liveUpdateBanner) return;
        liveUpdateBanner.hidden = true;
        liveUpdateBanner.dataset.pendingRunId = "";
        pendingLiveUpdateRunId = "";
        try {{
          window.sessionStorage.setItem(liveUpdateStorageKey, liveUpdateDismissValue(runId));
        }} catch (error) {{
          // Ignore storage failures and simply hide the notice for this page view.
        }}
      }}

      function formatManifestTime(generatedAt) {{
        const parsed = new Date(generatedAt);
        if (Number.isNaN(parsed.getTime())) {{
          return "";
        }}
        return parsed.toLocaleString([], {{
          month: "short",
          day: "numeric",
          hour: "numeric",
          minute: "2-digit",
        }});
      }}

      function markLiveUpdateAvailable(manifest) {{
        if (!liveUpdateBanner) return;
        const nextRunId = getManifestRunId(manifest);
        if (isLiveUpdateDismissed(nextRunId)) {{
          return;
        }}
        pendingLiveUpdateRunId = nextRunId;
        liveUpdateBanner.dataset.pendingRunId = nextRunId;
        liveUpdateBanner.dataset.dismissKey = liveUpdateStorageKey;
        if (liveUpdateText) {{
          const publishedAt = formatManifestTime(manifest.generated_at);
          const nextRun = publishedAt
            ? `Updated edition available from ${{publishedAt}}. Load the latest run when you are ready.`
            : "An updated edition is available. Load the latest run when you are ready.";
          liveUpdateText.textContent = nextRun;
        }}
        liveUpdateBanner.hidden = false;
      }}

      function isNewerManifest(manifest) {{
        const nextRunId = String(manifest.latest_run_id || "").trim();
        const nextGeneratedAt = String(manifest.generated_at || "").trim();
        if (currentRunId && nextRunId) {{
          return nextRunId !== currentRunId;
        }}
        if (currentGeneratedAt && nextGeneratedAt) {{
          return nextGeneratedAt !== currentGeneratedAt;
        }}
        return false;
      }}

      function liveUpdatePageHasAged() {{
        return Date.now() - liveUpdateStart >= 360000;
      }}

      async function checkForLiveUpdate() {{
        if (!liveUpdateShouldRun()) return;
        if (!liveUpdatePageHasAged()) return;
        try {{
          const response = await fetch(`${{manifestPath}}?ts=${{Date.now()}}`, {{ cache: "no-store" }});
          if (!response.ok) return;
          const manifest = await response.json();
          if (isNewerManifest(manifest)) {{
            markLiveUpdateAvailable(manifest);
          }}
        }} catch (error) {{
          // Ignore polling failures; readers should never see an error state for this.
        }}
      }}

      window.__pathogenDismissLiveUpdate = function (button) {{
        const banner = button && button.closest ? button.closest("[data-live-update-banner]") : liveUpdateBanner;
        const pendingRunId = banner && banner.dataset ? banner.dataset.pendingRunId || "" : "";
        dismissLiveUpdate(pendingRunId);
      }};

      window.__pathogenLoadLatest = function (button) {{
        const banner = button && button.closest ? button.closest("[data-live-update-banner]") : liveUpdateBanner;
        if (banner) {{
          banner.hidden = true;
        }}
        const url = new URL(window.location.href);
        url.searchParams.set("_edition", String(Date.now()));
        window.location.replace(url.toString());
      }};

      if (liveUpdateButton) {{
        liveUpdateButton.addEventListener("click", (event) => {{
          event.preventDefault();
          window.__pathogenLoadLatest(liveUpdateButton);
        }});
      }}
      if (liveUpdateDismiss) {{
        liveUpdateDismiss.addEventListener("click", (event) => {{
          event.preventDefault();
          window.__pathogenDismissLiveUpdate(liveUpdateDismiss);
        }});
      }}
      if (liveUpdateShouldRun()) {{
        window.setTimeout(checkForLiveUpdate, 360000);
        window.setInterval(checkForLiveUpdate, 600000);
      }}
    """


def render_related_reference_card(reference: dict[str, Any], *, web_mode: bool = False, link_prefix: str = "./") -> str:
    href = f"{link_prefix}{reference.get('reference_web_path', '')}" if web_mode else reference.get("reference_url", "")
    atlas_href = f"{link_prefix}atlas.html?pathogen={reference.get('atlas_entry_slug', '')}" if web_mode and reference.get("atlas_entry_slug") else ""
    return (
        f'<article class="site-card">'
        f'<div class="kicker">Disease sheet</div>'
        f'<h3><a href="{escape_attr(href)}">{escape(reference.get("name", ""))}</a></h3>'
        f'<p><strong>Pathogen:</strong> {escape(reference.get("pathogen", ""))}</p>'
        f'{f"<div class=\"meta-row\"><a class=\"link-pill\" href=\"{escape_attr(atlas_href)}\">View in Atlas</a></div>" if atlas_href else ""}'
        f"</article>"
    )


def render_related_story_card(story: dict[str, Any], *, web_mode: bool = False, link_prefix: str = "./") -> str:
    href = f"{link_prefix}{story.get('story_web_path', '')}" if web_mode else story.get("story_url", "")
    return (
        f'<article class="site-card">'
        f'<div class="kicker">Active story file</div>'
        f'<h3><a href="{escape_attr(href)}">{escape(story.get("display_title", ""))}</a></h3>'
        f'<p>{escape(story.get("latest_update_summary", ""))}</p>'
        f"</article>"
    )


def collapse_story_page_items(items: list[dict[str, Any]], *, max_low_detail_per_publisher: int) -> list[dict[str, Any]]:
    ordered = sorted(items, key=lambda item: sort_timestamp_value(item.get("published_at", "")), reverse=True)
    selected: list[dict[str, Any]] = []
    low_detail_counts: dict[str, int] = {}
    for item in ordered:
        publisher = normalize_whitespace(str(item.get("publisher_name", item.get("display_source", "Unknown"))))
        if any(story_items_are_near_duplicates(item, existing) for existing in selected):
            continue
        if story_item_is_low_detail(item):
            if low_detail_counts.get(publisher, 0) >= max_low_detail_per_publisher:
                continue
            low_detail_counts[publisher] = low_detail_counts.get(publisher, 0) + 1
        selected.append(item)
    return selected


def story_items_are_near_duplicates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_url = normalize_whitespace(str(left.get("preferred_url") or left.get("source_url") or ""))
    right_url = normalize_whitespace(str(right.get("preferred_url") or right.get("source_url") or ""))
    if left_url and left_url == right_url:
        return True
    left_publisher = normalize_whitespace(str(left.get("publisher_name", left.get("display_source", ""))))
    right_publisher = normalize_whitespace(str(right.get("publisher_name", right.get("display_source", ""))))
    if left_publisher and left_publisher == right_publisher and titles_similar(str(left.get("title", "")), str(right.get("title", "")), threshold=0.86):
        return True
    if left_publisher and left_publisher == right_publisher:
        left_day = str(left.get("published_at", ""))[:10]
        right_day = str(right.get("published_at", ""))[:10]
        if left_day and left_day == right_day and (
            title_overlap_ratio(str(left.get("title", "")), str(right.get("title", ""))) >= 0.72
            or story_item_claim_type(left) == story_item_claim_type(right)
        ):
            return True
    return False


def title_overlap_ratio(left: str, right: str) -> float:
    left_tokens = normalized_title_tokens(left)
    right_tokens = normalized_title_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = left_tokens.intersection(right_tokens)
    return len(overlap) / max(min(len(left_tokens), len(right_tokens)), 1)


def normalized_title_tokens(value: str) -> set[str]:
    tokens = {
        token
        for token in normalize_whitespace(value).lower().replace("-", " ").replace("'", "").split()
        if len(token) >= 4 and token not in {"with", "from", "after", "this", "that", "says", "said", "will", "have"}
    }
    return tokens


def story_item_is_low_detail(item: dict[str, Any]) -> bool:
    summary = normalize_whitespace(str(item.get("summary", ""))).lower()
    return bool(item.get("low_detail")) or summary == "limited detail was available from feed metadata alone."


def clean_story_text(value: str) -> str:
    cleaned = MARKDOWN_LINK_RE.sub(r"\1", str(value or ""))
    return normalize_whitespace(cleaned)


def base_styles() -> str:
    return """
      :root { --bg: #e8e1d3; --bg-deep: #d8cebc; --surface: #f8f4ea; --surface-alt: #f2ebde; --paper: #fffdf8; --ink: #1b2836; --ink-soft: #42515e; --line: #d6cab7; --accent: #8d3f2f; --accent-soft: rgba(141,63,47,0.10); --signal: #1f5b89; --signal-soft: rgba(31,91,137,0.12); --shadow: 0 24px 56px rgba(49, 36, 22, 0.10); }
      * { box-sizing: border-box; }
      body { margin: 0; background: radial-gradient(circle at top left, rgba(181,138,49,0.10), transparent 28%), radial-gradient(circle at bottom right, rgba(31,91,137,0.12), transparent 24%), linear-gradient(180deg, #f2ede3 0%, var(--bg) 40%, var(--bg-deep) 100%); color: var(--ink); font-family: "Iowan Old Style", Georgia, serif; line-height: 1.58; overflow-x: hidden; }
      a { color: var(--signal); text-decoration: none; }
      a:hover { text-decoration: underline; }
      .page { width: 100%; max-width: 1120px; margin: 0 auto; padding: 24px 16px 56px; display: grid; gap: 20px; overflow-x: clip; }
      .page > *, .hero > *, .panel > *, .site-header > *, .section-nav > *, .live-update-banner > * { min-width: 0; }
      h1, h2, h3, p, li, .subtitle, .empty-note, .muted-note, .section-note, .live-update-text, .site-header-title, .archive-row, .lede { overflow-wrap: anywhere; word-break: break-word; }
      .site-header, .section-nav { background: linear-gradient(180deg, rgba(255,253,248,0.98), rgba(248,243,233,0.98)); border: 1px solid rgba(187,169,143,0.85); border-radius: 24px; box-shadow: var(--shadow); }
      .site-header { padding: 16px 20px; display: flex; justify-content: space-between; gap: 18px; align-items: center; flex-wrap: wrap; }
      .site-header-title { margin: 0; color: var(--ink-soft); font-family: "Avenir Next", "Helvetica Neue", sans-serif; font-size: 0.96rem; }
      .live-update-banner { position: fixed; right: 18px; bottom: 18px; width: min(420px, calc(100vw - 28px)); padding: 14px 16px; display: grid; gap: 12px; z-index: 40; box-shadow: 0 18px 36px rgba(29, 24, 18, 0.16); }
      .live-update-banner[hidden] { display: none !important; }
      .live-update-copy { min-width: 0; display: grid; gap: 4px; }
      .live-update-text { margin: 0; color: var(--ink-soft); font-family: "Avenir Next", "Helvetica Neue", sans-serif; }
      .live-update-actions { display: flex; justify-content: flex-end; gap: 10px; flex-wrap: wrap; }
      .live-update-dismiss { border: 0; background: transparent; color: var(--ink-soft); font-family: "Avenir Next", "Helvetica Neue", sans-serif; font-weight: 600; cursor: pointer; padding: 10px 4px; touch-action: manipulation; -webkit-tap-highlight-color: transparent; }
      .live-update-dismiss:hover { color: var(--ink); }
      .live-update-button { border-radius: 999px; padding: 10px 14px; border: 1px solid rgba(31,91,137,0.26); background: rgba(31,91,137,0.12); color: var(--signal); font-family: "Avenir Next", "Helvetica Neue", sans-serif; font-weight: 700; cursor: pointer; white-space: nowrap; touch-action: manipulation; -webkit-tap-highlight-color: transparent; }
      .live-update-button:hover { background: rgba(31,91,137,0.18); }
      .site-nav, .section-nav-links { display: flex; flex-wrap: wrap; gap: 10px; }
      .site-nav-link, .section-nav-link { border-radius: 999px; padding: 9px 14px; border: 1px solid rgba(187,169,143,0.78); background: rgba(255,252,245,0.94); color: var(--ink); font-family: "Avenir Next", "Helvetica Neue", sans-serif; font-size: 0.92rem; white-space: nowrap; }
      .site-nav-link:hover, .section-nav-link:hover { text-decoration: none; background: var(--accent-soft); }
      .site-nav-link.active { background: rgba(31,91,137,0.10); color: var(--signal); border-color: rgba(31,91,137,0.22); }
      .section-nav { padding: 16px 18px; display: grid; gap: 10px; }
      .section-nav-label { font-family: "Avenir Next Condensed", "Franklin Gothic Medium", sans-serif; text-transform: uppercase; letter-spacing: 0.14em; color: var(--accent); font-size: 0.74rem; }
      .hero, .panel { background: linear-gradient(180deg, rgba(255,253,248,0.98), rgba(248,243,233,0.98)); border: 1px solid rgba(187,169,143,0.85); border-radius: 28px; box-shadow: var(--shadow); padding: 24px; }
      .hero { background: linear-gradient(180deg, rgba(255,255,255,0.42), rgba(255,255,255,0)), linear-gradient(135deg, rgba(248,244,234,0.98), rgba(242,235,222,0.98)); position: relative; overflow: hidden; }
      .hero::before { content: ""; position: absolute; inset: 0; background-image: linear-gradient(rgba(23,48,70,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(23,48,70,0.04) 1px, transparent 1px); background-size: 28px 28px; opacity: 0.35; pointer-events: none; }
      .hero > * { position: relative; z-index: 1; }
      .source-health-notice { border: 1px solid rgba(141,63,47,0.28); border-left: 4px solid rgba(141,63,47,0.58); background: rgba(255,252,247,0.86); border-radius: 16px; padding: 12px 16px; font-family: "Avenir Next", "Helvetica Neue", sans-serif; color: var(--ink-soft); }
      .source-health-notice p { margin: 0; }
      .source-health-notice strong { color: var(--accent); }
      .atlas-hero-grid { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.95fr); gap: 18px; align-items: stretch; }
      .atlas-layout { align-items: start; grid-template-columns: minmax(0, 1.55fr) minmax(280px, 0.95fr); }
      .atlas-map { min-height: 460px; border-radius: 22px; overflow: hidden; border: 1px solid rgba(187,169,143,0.74); background: linear-gradient(180deg, rgba(223,231,236,0.92), rgba(214,223,228,0.92)); }
      .atlas-legend { margin-top: 14px; }
      .atlas-selector-grid { display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(min(220px, 100%), 1fr)); }
      .atlas-selector-card { text-align: left; cursor: pointer; width: 100%; }
      .atlas-selector-card.atlas-selector-active { border-color: rgba(31,91,137,0.32); box-shadow: inset 0 0 0 2px rgba(31,91,137,0.14); background: linear-gradient(180deg, rgba(245,250,255,0.96), rgba(239,246,252,0.96)); }
      .atlas-plate { background: linear-gradient(160deg, rgba(24,43,60,0.96), rgba(48,69,93,0.94)); color: #f2ebde; border-radius: 24px; padding: 20px; min-height: 220px; box-shadow: 0 18px 36px rgba(29, 24, 18, 0.14); }
      .atlas-plate h3, .atlas-plate p, .atlas-plate .muted-note { color: inherit; }
      .atlas-plate-kicker, .atlas-plate-note { font-family: "Avenir Next Condensed", "Franklin Gothic Medium", sans-serif; letter-spacing: 0.12em; text-transform: uppercase; }
      .atlas-plate-kicker { color: rgba(248,244,234,0.88); font-size: 0.74rem; }
      .atlas-plate-note { color: rgba(248,244,234,0.72); font-size: 0.72rem; }
      .atlas-plate-subtitle { font-size: 1rem; margin: 8px 0 12px; }
      .atlas-evidence-stack, .atlas-route-list { display: grid; gap: 14px; }
      .atlas-evidence-section { display: grid; gap: 8px; }
      .atlas-route-row { background: rgba(255,252,247,0.92); border: 1px solid rgba(187,169,143,0.64); border-radius: 18px; padding: 14px; }
      .atlas-route-head { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
      .atlas-teaser-card p:last-child { margin-bottom: 0; }
      .atlas-citation-list li, .atlas-blog-list li, .atlas-story-list li { margin-bottom: 10px; }
      .panel-grid { display: grid; gap: 22px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .story-grid { display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(min(220px, 100%), 1fr)); }
      .card-grid { display: grid; gap: 14px; }
      .archive-table { display: grid; gap: 12px; }
      .archive-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 16px; background: rgba(255,252,247,0.9); border: 1px solid rgba(187,169,143,0.68); border-radius: 18px; font-family: "Avenir Next", "Helvetica Neue", sans-serif; }
      .archive-row-meta { color: var(--ink-soft); font-size: 0.92rem; }
      .sort-bar { display: flex; justify-content: flex-end; margin: 10px 0 14px; }
      .sort-control { display: inline-flex; align-items: center; gap: 8px; font-family: "Avenir Next", "Helvetica Neue", sans-serif; color: var(--ink-soft); font-size: 0.88rem; }
      .sort-select { border: 1px solid rgba(187,169,143,0.88); background: rgba(255,252,247,0.96); border-radius: 999px; padding: 8px 12px; color: var(--ink); font: inherit; }
      .sort-select:hover { background: var(--accent-soft); }
      .outbreak-dashboard-block { margin-top: 18px; }
      .outbreak-dashboard { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
      .dashboard-item { min-width: 0; display: grid; gap: 5px; padding: 12px 14px; border: 1px solid rgba(187,169,143,0.70); border-radius: 16px; background: rgba(255,252,247,0.70); }
      .dashboard-label, .dashboard-note, .story-location-line, .story-card-labels { font-family: "Avenir Next", "Helvetica Neue", sans-serif; }
      .dashboard-label { color: var(--accent); font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; }
      .dashboard-item strong { color: var(--ink); font-size: 1rem; line-height: 1.2; }
      .dashboard-note { color: var(--ink-soft); font-size: 0.82rem; line-height: 1.35; }
      .intelligence-panel { background: linear-gradient(180deg, rgba(255,253,248,0.98), rgba(245,239,228,0.96)); }
      .intelligence-bullets li { margin-bottom: 8px; }
      .historical-context-panel { background: linear-gradient(180deg, rgba(248,243,233,0.98), rgba(242,235,222,0.96)); }
      .context-callout-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
      .context-callout { min-width: 0; border-left: 3px solid rgba(141,63,47,0.35); padding: 2px 0 2px 14px; }
      .context-callout h3 { margin-bottom: 8px; font-size: 1rem; }
      .context-callout p { margin: 0; color: var(--ink-soft); font-size: 0.95rem; }
      .story-card-labels { display: flex; flex-wrap: wrap; gap: 7px; margin: -2px 0 10px; }
      .story-location-line { margin: 8px 0 0; color: var(--ink-soft); font-size: 0.9rem; }
      .source-status-confirmed, .source-status-official-report { background: rgba(31,91,137,0.12); color: #1f5b89; border-color: rgba(31,91,137,0.24); }
      .source-status-media-report { background: rgba(60,88,48,0.10); color: #35552b; border-color: rgba(60,88,48,0.20); }
      .source-status-preliminary, .source-status-needs-verification { background: rgba(181,138,49,0.12); color: #8c6a17; border-color: rgba(181,138,49,0.22); }
      .source-status-commentary { background: rgba(110,89,68,0.10); color: #6e5944; border-color: rgba(110,89,68,0.22); }
      .story-category-scientific-vaccine-therapeutic-context { background: rgba(31,91,137,0.09); color: #1f5b89; border-color: rgba(31,91,137,0.20); }
      .story-category-border-regional-spread-concerns { background: rgba(141,63,47,0.10); color: #8d3f2f; border-color: rgba(141,63,47,0.20); }
      .story-category-operational-response { background: rgba(60,88,48,0.10); color: #35552b; border-color: rgba(60,88,48,0.20); }
      .story-category-commentary-political-reaction-media-discourse { background: rgba(110,89,68,0.10); color: #6e5944; border-color: rgba(110,89,68,0.22); }
      .story-filter-shell { display: grid; gap: 10px; }
      .story-filter-grid { display: grid; grid-template-columns: minmax(0, 1.6fr) repeat(4, minmax(130px, 1fr)); gap: 10px; align-items: end; }
      .filter-group { display: grid; gap: 6px; }
      .filter-search-wide { min-width: 0; }
      .filter-label { font-family: "Avenir Next Condensed", "Franklin Gothic Medium", sans-serif; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--ink-soft); }
      .filter-input, .filter-select { border: 1px solid rgba(187,169,143,0.88); background: rgba(255,252,247,0.96); border-radius: 14px; padding: 10px 12px; color: var(--ink); font: inherit; font-family: "Avenir Next", "Helvetica Neue", sans-serif; }
      .filter-input::placeholder { color: var(--ink-soft); }
      .utility-panel { background: linear-gradient(180deg, rgba(248,243,233,0.98), rgba(240,232,220,0.96)); }
      .site-card, .timeline-row { background: var(--paper); border: 1px solid rgba(187,169,143,0.68); border-radius: 22px; padding: 18px 18px 16px; box-shadow: 0 12px 26px rgba(49, 36, 22, 0.06); }
      .feature-card { background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(245,239,228,0.98)); }
      .compact-card { padding-top: 16px; padding-bottom: 14px; }
      .meta-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; font-family: "Avenir Next", "Helvetica Neue", sans-serif; min-width: 0; }
      .badge, .link-pill { border-radius: 999px; padding: 6px 10px; font-size: 0.78rem; line-height: 1.2; border: 1px solid rgba(187,169,143,0.72); background: rgba(255,252,245,0.94); color: var(--ink-soft); display: inline-flex; align-items: center; max-width: 100%; }
      .badge.accent { background: var(--accent-soft); color: var(--accent); border-color: rgba(141,63,47,0.24); }
      .badge.tone-official { background: rgba(31,91,137,0.12); color: #1f5b89; border-color: rgba(31,91,137,0.24); }
      .badge.tone-wire { background: rgba(60,88,48,0.10); color: #35552b; border-color: rgba(60,88,48,0.20); }
      .badge.tone-major { background: rgba(181,138,49,0.12); color: #8c6a17; border-color: rgba(181,138,49,0.22); }
      .badge.tone-specialist { background: rgba(141,63,47,0.10); color: #8d3f2f; border-color: rgba(141,63,47,0.20); }
      .kicker { font-family: "Avenir Next Condensed", "Franklin Gothic Medium", sans-serif; text-transform: uppercase; letter-spacing: 0.16em; color: var(--accent); font-size: 0.74rem; margin: 0 0 10px; }
      .subtitle, .empty-note, .muted-note { color: var(--ink-soft); font-family: "Avenir Next", "Helvetica Neue", sans-serif; }
      .section-note { margin: 0 0 10px; color: var(--ink-soft); font-family: "Avenir Next", "Helvetica Neue", sans-serif; font-size: 0.95rem; }
      .lede { font-size: 1.06rem; }
      .hero-subhead { margin: 16px 0 8px; font-size: 1.08rem; }
      .bullet-list { margin: 10px 0 0; padding-left: 18px; }
      h1, h2, h3 { margin: 0; color: #173046; }
      h1 { font-size: clamp(2rem, 4.2vw, 4rem); line-height: 0.98; letter-spacing: -0.03em; }
      h2 { font-size: 1.4rem; }
      h3 { font-size: 1.06rem; }
      .site-card h3 { line-height: 1.12; }
      @media (max-width: 1180px) { .panel-grid, .atlas-layout, .atlas-hero-grid, .context-callout-grid { grid-template-columns: 1fr; } .story-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .outbreak-dashboard { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
      @media (max-width: 900px) { .page { padding: 16px 14px 42px; } .hero, .panel, .site-header, .section-nav { padding: 18px; border-radius: 22px; } .site-header { align-items: flex-start; flex-direction: column; } .story-filter-grid { grid-template-columns: 1fr; } .story-grid, .atlas-selector-grid { grid-template-columns: 1fr; } .atlas-map { min-height: 340px; } h1 { font-size: clamp(1.9rem, 10vw, 3.2rem); } }
      @media (max-width: 620px) { .site-nav, .section-nav-links { flex-wrap: nowrap; overflow-x: auto; -webkit-overflow-scrolling: touch; padding-bottom: 2px; } .site-header-copy { min-width: 0; } .archive-row { flex-direction: column; align-items: flex-start; } .badge, .link-pill { line-height: 1.2; } .outbreak-dashboard { grid-template-columns: 1fr; } .dashboard-item { padding: 11px 12px; } .live-update-banner { right: 12px; bottom: 12px; width: calc(100vw - 24px); } .live-update-actions { justify-content: space-between; } }
    """


def render_sort_bar(target_id: str, include_source: bool = True) -> str:
    options = [
        '<option value="newest">Newest first</option>',
        '<option value="oldest">Oldest first</option>',
    ]
    if include_source:
        options.append('<option value="source">Source A-Z</option>')
    return (
        '<div class="sort-bar">'
        f'<label class="sort-control">Sort by '
        f'<select class="sort-select" data-sort-target="{escape_attr(target_id)}">{"".join(options)}</select>'
        '</label>'
        '</div>'
    )


def sort_script() -> str:
    return """
      const storySorters = Array.from(document.querySelectorAll("[data-sort-target]"));

      function sortSortableGrid(targetId, mode) {
        const container = document.getElementById(targetId);
        if (!container) return;
        const cards = Array.from(container.querySelectorAll(".sortable-card"));
        const normalizedMode = mode || container.dataset.defaultSort || "newest";
        cards.sort((left, right) => {
          if (normalizedMode === "oldest") {
            return Number(left.dataset.sortTs || 0) - Number(right.dataset.sortTs || 0);
          }
          if (normalizedMode === "source") {
            const sourceCompare = (left.dataset.sortSource || "").localeCompare(right.dataset.sortSource || "");
            if (sourceCompare !== 0) return sourceCompare;
            return (left.dataset.sortTitle || "").localeCompare(right.dataset.sortTitle || "");
          }
          return Number(right.dataset.sortTs || 0) - Number(left.dataset.sortTs || 0);
        });
        cards.forEach((card) => container.appendChild(card));
      }

      storySorters.forEach((select) => {
        const targetId = select.dataset.sortTarget;
        sortSortableGrid(targetId, select.value);
        select.addEventListener("change", () => sortSortableGrid(targetId, select.value));
      });
    """


def story_filter_script() -> str:
    return """
      const storyFilterSearch = document.getElementById("story-filter-search");
      const storyFilterControls = Array.from(document.querySelectorAll("[data-story-filter]"));
      const storyFilterStatus = document.getElementById("story-filter-status");
      const storyFilterCards = Array.from(document.querySelectorAll(".searchable-card"));

      function normalizeStoryFilterText(value) {
        return String(value || "").toLowerCase().trim();
      }

      function applyStoryFilters() {
        const query = normalizeStoryFilterText(storyFilterSearch ? storyFilterSearch.value : "");
        const activeFilters = Object.fromEntries(
          storyFilterControls.map((select) => [select.dataset.storyFilter, normalizeStoryFilterText(select.value)])
        );
        let visibleCount = 0;
        storyFilterCards.forEach((card) => {
          const matchesQuery = !query || normalizeStoryFilterText(card.dataset.search).includes(query);
          const matchesIntelCategory = activeFilters["intel-category"] === "all" || normalizeStoryFilterText(card.dataset.intelCategory) === activeFilters["intel-category"];
          const matchesSourceKind = activeFilters["source-kind"] === "all" || normalizeStoryFilterText(card.dataset.sourceKind) === activeFilters["source-kind"];
          const matchesFreshness = activeFilters["freshness"] === "all" || normalizeStoryFilterText(card.dataset.freshness) === activeFilters["freshness"];
          const matchesLinkQuality = activeFilters["link-quality"] === "all" || normalizeStoryFilterText(card.dataset.linkQuality) === activeFilters["link-quality"];
          const matchesRegion = activeFilters["region"] === "all" || normalizeStoryFilterText(card.dataset.region).replace(/\\s+/g, "_") === activeFilters["region"];
          const matchesAccess = activeFilters["access"] === "all" || normalizeStoryFilterText(card.dataset.access) === activeFilters["access"];
          const matchesDateWindow = activeFilters["date-window"] === "all" || normalizeStoryFilterText(card.dataset.dateWindow) === activeFilters["date-window"];
          const matchesStoryStatus = activeFilters["story-status"] === "all" || normalizeStoryFilterText(card.dataset.storyStatus) === activeFilters["story-status"];
          const matchesClaimType = activeFilters["claim-type"] === "all" || normalizeStoryFilterText(card.dataset.claimType) === activeFilters["claim-type"];
          const visible = matchesQuery && matchesIntelCategory && matchesSourceKind && matchesFreshness && matchesLinkQuality && matchesRegion && matchesAccess && matchesDateWindow && matchesStoryStatus && matchesClaimType;
          card.hidden = !visible;
          if (visible) visibleCount += 1;
        });
        if (storyFilterStatus) {
          const total = storyFilterCards.length;
          const visibleOfficial = storyFilterCards.filter((card) => !card.hidden && card.dataset.scope === "official").length;
          const visiblePublisher = storyFilterCards.filter((card) => !card.hidden && card.dataset.scope === "publisher").length;
          storyFilterStatus.textContent = visibleCount === total
            ? `Showing all ${total} story-file cards (${visibleOfficial} official, ${visiblePublisher} publisher).`
            : `Showing ${visibleCount} of ${total} story-file cards after filtering (${visibleOfficial} official, ${visiblePublisher} publisher).`;
        }
      }

      if (storyFilterSearch) storyFilterSearch.addEventListener("input", applyStoryFilters);
      storyFilterControls.forEach((select) => select.addEventListener("change", applyStoryFilters));
      applyStoryFilters();
    """


def humanize_story_status(value: str) -> str:
    normalized = normalize_whitespace(str(value)).lower().replace(" ", "_")
    labels = {
        "expanding_coverage": "Expanding coverage",
        "active_investigation": "Active investigation",
        "official_follow_up_only": "Official follow-up only",
        "quiet_retained": "Quiet but retained",
        "archival_watch": "Archival watch",
    }
    return labels.get(normalized, value.replace("_", " ").title())


def atlas_status_label(value: str) -> str:
    normalized = normalize_whitespace(str(value)).lower().replace(" ", "_")
    labels = {
        "consensus": "Consensus",
        "mixed": "Mixed / debated",
        "contested": "Contested",
        "weakly_supported": "Weakly supported",
    }
    return labels.get(normalized, value.replace("_", " ").title())


def atlas_writing_state_label(value: str) -> str:
    normalized = normalize_whitespace(str(value)).lower().replace(" ", "_")
    labels = {
        "direct": "Written here directly",
        "adjacent": "Adjacent writing exists",
        "not_yet_written": "No dedicated post yet",
    }
    return labels.get(normalized, value.replace("_", " ").title())


def route_confidence_label(value: str) -> str:
    normalized = normalize_whitespace(str(value)).lower().replace(" ", "_")
    labels = {
        "strong": "Strong support",
        "moderate": "Moderate support",
        "weak": "Weak support",
        "debated": "Debated",
    }
    return labels.get(normalized, value.replace("_", " ").title())


def format_claim_type_label(value: str) -> str:
    normalized = normalize_whitespace(str(value)).lower().replace(" ", "_")
    labels = {
        "new_official_source": "New official source",
        "suspected_case": "Suspected case",
        "confirmed_case": "Confirmed case",
        "severity_or_death": "Severity or death",
        "transmission_change": "Transmission concern",
        "policy_or_travel": "Policy or travel change",
        "new_geography": "New geography",
        "general_update": "General update",
    }
    return labels.get(normalized, value.replace("_", " ").title())


def optional_line(label: str, value: str | None) -> str:
    if not value:
        return ""
    return f'<p><strong>{escape(label)}:</strong> {escape(value)}</p>'


def optional_paragraph(label: str, value: str | None) -> str:
    if not value:
        return '<p class="empty-note">No desk note has been curated yet.</p>'
    return f'<p><strong>{escape(label)}:</strong> {escape(value)}</p>'


def dedupe_dicts_by_key(records: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    for record in records:
        value = normalize_whitespace(str(record.get(key, "")))
        if not value or value in seen:
            continue
        seen.add(value)
        kept.append(record)
    return kept


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
