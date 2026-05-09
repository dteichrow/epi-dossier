from __future__ import annotations

import html
from collections import defaultdict
from datetime import date, datetime
from typing import Any

from .dedupe import titles_similar
from .utils import format_timestamp, normalize_whitespace


def render_story_page(
    story: dict[str, Any],
    items_by_id: dict[str, dict[str, Any]],
    target_date: date,
    generated_at: datetime,
    *,
    web_mode: bool = False,
) -> str:
    official_items_raw = [items_by_id[item_id] for item_id in story.get("official_item_ids", []) if item_id in items_by_id]
    press_items_raw = [items_by_id[item_id] for item_id in story.get("press_item_ids", []) if item_id in items_by_id]
    official_items = collapse_story_page_items(official_items_raw, max_low_detail_per_publisher=2)
    press_items = collapse_story_page_items(press_items_raw, max_low_detail_per_publisher=2)
    combined_items = official_items + press_items
    timeline = story.get("timeline", [])
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
    bullet_rows = "".join(f"<li>{escape(bullet)}</li>" for bullet in story.get("latest_update_bullets", [])) or "<li>No new delta bullets were generated in this run.</li>"
    related_reference_cards = "".join(
        render_related_reference_card(reference, web_mode=web_mode, link_prefix="../") for reference in story.get("related_references", [])
    ) or '<p class="empty-note">No disease intelligence sheets were linked to this story yet.</p>'
    region_badges = "".join(
        f'<span class="badge">{escape(item.get("region", "Unknown"))}</span>'
        for item in dedupe_dicts_by_key([items_by_id[item_id] for item_id in story.get("item_ids", []) if item_id in items_by_id], "region")
        if item.get("region")
    )

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(story.get("display_title", "Story"))} | The Patogen Dispatch</title>
    <style>{base_styles()}</style>
  </head>
  <body>
    <main class="page">
      {render_site_header_mode("../", nav_mode="web" if web_mode else "local", active_page="story")}
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
        <h2 class="hero-subhead">What happened</h2>
        <p>{escape(story.get("what_happened", story.get("lead_title", "No summary available.")))}</p>
        <h2 class="hero-subhead">Why it matters</h2>
        <p>{escape(story.get("why_it_matters", "No why-it-matters note is available yet."))}</p>
        <h2 class="hero-subhead">What changed in this run</h2>
        <p><strong>Latest summary:</strong> {escape(story.get("latest_update_summary", "No update summary available."))}</p>
        <ul class="bullet-list">{bullet_rows}</ul>
      </section>

      {render_page_section_nav(
          [
              ("Overview", "#story-overview"),
              ("Filters", "#story-filters"),
              ("Official Sources", "#official-sources-panel"),
              ("Publisher Coverage", "#publisher-coverage-panel"),
              ("Disease Sheets", "#related-disease-intelligence"),
              ("Timeline", "#story-timeline-panel"),
          ]
      )}

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
    </main>
    <script>{sort_script()}</script>
    <script>{story_filter_script()}</script>
  </body>
</html>
"""


def render_reference_page(
    reference: dict[str, Any],
    target_date: date,
    generated_at: datetime,
    *,
    web_mode: bool = False,
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
    related_story_cards = "".join(
        render_related_story_card(story, web_mode=web_mode, link_prefix="../") for story in reference.get("related_stories", [])
    ) or '<p class="empty-note">No active tracked stories are linked to this disease in the current run.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(reference.get("name", "Reference"))} | The Patogen Dispatch</title>
    <style>{base_styles()}</style>
  </head>
  <body>
    <main class="page">
      {render_site_header_mode("../", nav_mode="web" if web_mode else "local", active_page="reference")}
      <section class="hero" id="story-overview">
        <p class="kicker">Disease intelligence sheet</p>
        <h1>{escape(reference.get("name", "Reference"))}</h1>
        <p class="subtitle">Curated desk background for reporters who need the pathogen, transmission, and outbreak frame fast.</p>
        <div class="meta-row">{categories}{settings}</div>
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
  </body>
</html>
"""


def render_site_index(
    latest_snapshot: dict[str, Any],
    archive_entries: list[dict[str, Any]],
    reference_records: list[dict[str, Any]],
) -> str:
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
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>The Patogen Dispatch | Site Index</title>
    <style>{base_styles()}</style>
  </head>
  <body>
    <main class="page">
      {render_site_header("./")}
      <section class="hero">
        <p class="kicker">The Edge of Epidemiology</p>
        <h1>The Patogen Dispatch</h1>
        <p class="subtitle">Static newsroom index for the current briefing, major tracked outbreak files, and the disease reference desk.</p>
      </section>
      {render_page_section_nav(
          [
              ("Active Outbreak Files", "#active-outbreak-files"),
              ("Disease Reference Directory", "#disease-reference-directory"),
              ("Recent Archive Days", "#recent-archive-days"),
          ]
      )}
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
    global_watch_items = items_for_edition(latest_snapshot.get("items", []), "watch")
    changed_today = global_watch_items[:8]
    watch_followups = global_watch_items[8:16]
    research_items = items_for_edition(latest_snapshot.get("items", []), "research")[:6]
    reference_spotlight = [record for record in reference_records if record.get("spotlight")] or reference_records[:6]
    archive_cards = archive_entries[:10]

    lead_story_cards = "".join(render_public_story_card(story, link_prefix="./") for story in lead_stories) or '<p class="empty-note">No active outbreak files are available in this run.</p>'
    changed_cards = "".join(render_public_item_card(item) for item in changed_today) or '<p class="empty-note">No major changed items were surfaced in this run.</p>'
    watch_cards = "".join(render_public_item_card(item) for item in watch_followups) or '<p class="empty-note">No additional watch items were surfaced in this run.</p>'
    research_cards = "".join(render_public_item_card(item) for item in research_items) or '<p class="empty-note">No research-linked items were surfaced in this run.</p>'
    reference_cards = "".join(render_public_reference_card(reference, link_prefix="./") for reference in reference_spotlight) or '<p class="empty-note">No reference sheets were spotlighted in this run.</p>'
    archive_rows = "".join(render_public_archive_row(entry, link_prefix="./") for entry in archive_cards) or '<p class="empty-note">No archive days are available yet.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>The Patogen Dispatch</title>
    <style>{base_styles()}</style>
  </head>
  <body>
    <main class="page">
      {render_site_header_mode("./", nav_mode="web", active_page="home")}
      <section class="hero" id="top">
        <p class="kicker">The Edge of Epidemiology</p>
        <h1>The Patogen Dispatch</h1>
        <p class="subtitle">A source-first infectious disease newsroom for reporters, editors, and public-health analysts who need to know what changed, how trustworthy it is, and where to click next.</p>
        <div class="meta-row">
          <span class="badge accent">{latest_snapshot.get("story_count", 0)} active file(s)</span>
          <span class="badge">{latest_snapshot.get("item_count", 0)} current item(s)</span>
          <span class="badge">Updated {escape(latest_snapshot.get("generated_at", "Unknown"))}</span>
        </div>
      </section>
      {render_page_section_nav([("Lead Outbreak Files", "#lead-outbreak-files"), ("What Changed Today", "#what-changed-today"), ("Global Watch", "#global-watch"), ("Research + Reference", "#research-reference"), ("Archive + Backfile", "#archive-backfile")])}
      <section class="panel" id="lead-outbreak-files">
        <h2>Lead Outbreak Files</h2>
        <p class="muted-note">The core live files that deserve attention before the wider desk.</p>
        <div class="story-grid">{lead_story_cards}</div>
      </section>
      <section class="panel" id="what-changed-today">
        <h2>What Changed Today</h2>
        <p class="muted-note">New developments that move the reporting picture rather than simply repeat it.</p>
        <div class="card-grid">{changed_cards}</div>
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
  </body>
</html>
"""


def render_public_desk_page(
    title: str,
    description: str,
    active_page: str,
    stories: list[dict[str, Any]],
    items: list[dict[str, Any]],
    reference_records: list[dict[str, Any]],
    archive_entries: list[dict[str, Any]],
) -> str:
    story_cards = "".join(render_public_story_card(story, link_prefix="./") for story in stories) or '<p class="empty-note">No tracked story files matched this desk in the current run.</p>'
    item_cards = "".join(render_public_item_card(item) for item in items) or '<p class="empty-note">No item cards matched this desk in the current run.</p>'
    reference_cards = "".join(render_public_reference_card(reference, link_prefix="./") for reference in reference_records[:4]) or '<p class="empty-note">No related disease sheets are linked here yet.</p>'
    archive_rows = "".join(render_public_archive_row(entry, link_prefix="./") for entry in archive_entries[:8]) or '<p class="empty-note">No archive days are available yet.</p>'
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)} | The Patogen Dispatch</title>
    <style>{base_styles()}</style>
  </head>
  <body>
    <main class="page">
      {render_site_header_mode("./", nav_mode="web", active_page=active_page)}
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
  </body>
</html>
"""


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
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Archive | The Patogen Dispatch</title>
    <style>{base_styles()}</style>
  </head>
  <body>
    <main class="page">
      {render_site_header_mode("../", nav_mode="web", active_page="archive")}
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
  </body>
</html>
"""


def items_for_edition(items: list[dict[str, Any]], edition_key: str) -> list[dict[str, Any]]:
    return [item for item in items if edition_key in item.get("editions", [])]


def stories_for_edition(stories: list[dict[str, Any]], edition_key: str) -> list[dict[str, Any]]:
    return [story for story in stories if edition_key in story.get("editions", [])]


def render_public_story_card(story: dict[str, Any], *, link_prefix: str) -> str:
    href = f'{link_prefix}{story.get("story_web_path", "")}'
    badges = "".join(
        f'<span class="badge">{escape(label)}</span>'
        for label in [story.get("current_status_summary", ""), story.get("primary_region", ""), story.get("country", "")]
        if label
    )
    return (
        f'<article class="site-card feature-card">'
        f'<div class="kicker">Outbreak file</div>'
        f'<h3><a href="{escape_attr(href)}">{escape(story.get("display_title", ""))}</a></h3>'
        f'<p>{escape(story.get("latest_update_summary", ""))}</p>'
        f'<div class="meta-row"><span class="badge accent">{story.get("item_count", 0)} item(s)</span><span class="badge">{story.get("source_count", 0)} source(s)</span>{badges}</div>'
        f"</article>"
    )


def render_public_reference_card(reference: dict[str, Any], *, link_prefix: str) -> str:
    href = f'{link_prefix}{reference.get("reference_web_path", "")}'
    return (
        f'<article class="site-card">'
        f'<div class="kicker">Reference</div>'
        f'<h3><a href="{escape_attr(href)}">{escape(reference.get("name", ""))}</a></h3>'
        f'<p><strong>Pathogen:</strong> {escape(reference.get("pathogen", ""))}</p>'
        f'<p>{escape(reference.get("why_reporters_care", ""))}</p>'
        f"</article>"
    )


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
    if item.get("official"):
        return "Official update"
    if item.get("content_class") == "research_context":
        return "Research"
    if item.get("content_class") == "metadata_only_signal":
        return "Metadata-only signal"
    return "Publisher coverage"


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


def render_story_item_card(item: dict[str, Any], label: str) -> str:
    published_at = item.get("published_at", "")
    summary_text = (item.get("summary") or "").strip()
    is_low_detail = bool(item.get("low_detail")) or summary_text == "Limited detail was available from feed metadata alone."
    summary_html = "" if is_low_detail or not summary_text else f'<p>{escape(summary_text)}</p>'
    card_class = "site-card sortable-card compact-card" if is_low_detail else "site-card sortable-card"
    link_quality_label = normalize_link_quality_label(str(item.get("link_quality", "direct_article")))
    freshness_badge = render_story_item_freshness_badge(item)
    source_kind_badge = render_source_kind_badge(item)
    source_confidence_badge = render_story_item_source_confidence_badge(item)
    access_badge = render_access_badge(item)
    metadata_badge = '<span class="badge">Metadata only</span>' if is_low_detail else ""
    region = normalize_whitespace(str(item.get("region", ""))) or "Unknown"
    source_kind = story_item_source_kind(item)
    access = story_item_access(item)
    age_bucket = story_item_date_bucket(published_at)
    scope = "official" if item.get("official") else "publisher"
    claim_type = story_item_claim_type(item)
    story_status = normalize_whitespace(str(item.get("story_status", ""))).lower().replace(" ", "_") or "active_investigation"
    return (
        f'<article class="{card_class} searchable-card" data-sort-ts="{sort_timestamp_value(published_at)}" data-sort-source="{escape_attr(str(item.get("publisher_name", item.get("display_source", "Unknown"))))}" data-sort-title="{escape_attr(str(item.get("title", "")))}" data-search="{escape_attr(story_item_search_text(item))}" data-source-kind="{escape_attr(source_kind)}" data-freshness="{escape_attr(str(item.get("freshness_state") or "live"))}" data-link-quality="{escape_attr(str(item.get("link_quality") or "direct_article"))}" data-region="{escape_attr(region)}" data-access="{escape_attr(access)}" data-date-window="{escape_attr(age_bucket)}" data-scope="{escape_attr(scope)}" data-official="{escape_attr('true' if item.get('official') else 'false')}" data-story-status="{escape_attr(story_status)}" data-claim-type="{escape_attr(claim_type)}">'
        f'<div class="kicker">{escape(label)}</div>'
        f'<h3><a href="{escape_attr(item.get("preferred_url") or item.get("source_url", ""))}">{escape(item.get("title", ""))}</a></h3>'
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
    bullets = "".join(f"<li>{escape(bullet)}</li>" for bullet in entry.get("bullets", [])) or "<li>No bullet text captured.</li>"
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
            ("home", "Home", f"{base_path}index.html"),
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
            ("briefing", "Latest briefing", f"{base_path}latest.html#view-briefing"),
            ("tracking", "Global watch", f"{base_path}latest.html#view-tracking"),
            ("reference", "Research + reference", f"{base_path}latest.html#view-reference"),
            ("archive", "Archive + backfile", f"{base_path}latest.html#view-archive"),
            ("index", "Site index", f"{base_path}index.html"),
        ]
        title = "Unified Desk Navigation"
    links = "".join(render_nav_link(label, href, key == active_page) for key, label, href in nav_items)
    return (
        '<header class="site-header">'
        '<div class="site-header-copy">'
        '<div class="kicker">The Patogen Dispatch</div>'
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


def render_related_reference_card(reference: dict[str, Any], *, web_mode: bool = False, link_prefix: str = "./") -> str:
    href = f"{link_prefix}{reference.get('reference_web_path', '')}" if web_mode else reference.get("reference_url", "")
    return (
        f'<article class="site-card">'
        f'<div class="kicker">Disease sheet</div>'
        f'<h3><a href="{escape_attr(href)}">{escape(reference.get("name", ""))}</a></h3>'
        f'<p><strong>Pathogen:</strong> {escape(reference.get("pathogen", ""))}</p>'
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


def base_styles() -> str:
    return """
      :root { --bg: #e8e1d3; --bg-deep: #d8cebc; --surface: #f8f4ea; --surface-alt: #f2ebde; --paper: #fffdf8; --ink: #1b2836; --ink-soft: #42515e; --line: #d6cab7; --accent: #8d3f2f; --accent-soft: rgba(141,63,47,0.10); --signal: #1f5b89; --signal-soft: rgba(31,91,137,0.12); --shadow: 0 24px 56px rgba(49, 36, 22, 0.10); }
      * { box-sizing: border-box; }
      body { margin: 0; background: radial-gradient(circle at top left, rgba(181,138,49,0.10), transparent 28%), radial-gradient(circle at bottom right, rgba(31,91,137,0.12), transparent 24%), linear-gradient(180deg, #f2ede3 0%, var(--bg) 40%, var(--bg-deep) 100%); color: var(--ink); font-family: "Iowan Old Style", Georgia, serif; line-height: 1.58; }
      a { color: var(--signal); text-decoration: none; }
      a:hover { text-decoration: underline; }
      .page { max-width: 1240px; margin: 0 auto; padding: 28px 22px 64px; display: grid; gap: 22px; }
      .site-header, .section-nav { background: linear-gradient(180deg, rgba(255,253,248,0.98), rgba(248,243,233,0.98)); border: 1px solid rgba(187,169,143,0.85); border-radius: 24px; box-shadow: var(--shadow); }
      .site-header { padding: 16px 20px; display: flex; justify-content: space-between; gap: 18px; align-items: center; }
      .site-header-title { margin: 0; color: var(--ink-soft); font-family: "Avenir Next", "Helvetica Neue", sans-serif; font-size: 0.96rem; }
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
      .panel-grid { display: grid; gap: 22px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .story-grid { display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
      .card-grid { display: grid; gap: 14px; }
      .archive-table { display: grid; gap: 12px; }
      .archive-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 16px; background: rgba(255,252,247,0.9); border: 1px solid rgba(187,169,143,0.68); border-radius: 18px; font-family: "Avenir Next", "Helvetica Neue", sans-serif; }
      .archive-row-meta { color: var(--ink-soft); font-size: 0.92rem; }
      .sort-bar { display: flex; justify-content: flex-end; margin: 10px 0 14px; }
      .sort-control { display: inline-flex; align-items: center; gap: 8px; font-family: "Avenir Next", "Helvetica Neue", sans-serif; color: var(--ink-soft); font-size: 0.88rem; }
      .sort-select { border: 1px solid rgba(187,169,143,0.88); background: rgba(255,252,247,0.96); border-radius: 999px; padding: 8px 12px; color: var(--ink); font: inherit; }
      .sort-select:hover { background: var(--accent-soft); }
      .story-filter-shell { display: grid; gap: 10px; }
      .story-filter-grid { display: grid; grid-template-columns: minmax(0, 1.8fr) repeat(4, minmax(150px, 1fr)); gap: 10px; align-items: end; }
      .filter-group { display: grid; gap: 6px; }
      .filter-search-wide { min-width: 0; }
      .filter-label { font-family: "Avenir Next Condensed", "Franklin Gothic Medium", sans-serif; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--ink-soft); }
      .filter-input, .filter-select { border: 1px solid rgba(187,169,143,0.88); background: rgba(255,252,247,0.96); border-radius: 14px; padding: 10px 12px; color: var(--ink); font: inherit; font-family: "Avenir Next", "Helvetica Neue", sans-serif; }
      .filter-input::placeholder { color: var(--ink-soft); }
      .utility-panel { background: linear-gradient(180deg, rgba(248,243,233,0.98), rgba(240,232,220,0.96)); }
      .site-card, .timeline-row { background: var(--paper); border: 1px solid rgba(187,169,143,0.68); border-radius: 22px; padding: 18px 18px 16px; box-shadow: 0 12px 26px rgba(49, 36, 22, 0.06); }
      .feature-card { background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(245,239,228,0.98)); }
      .compact-card { padding-top: 16px; padding-bottom: 14px; }
      .meta-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; font-family: "Avenir Next", "Helvetica Neue", sans-serif; }
      .badge, .link-pill { border-radius: 999px; padding: 6px 10px; font-size: 0.78rem; line-height: 1; border: 1px solid rgba(187,169,143,0.72); background: rgba(255,252,245,0.94); color: var(--ink-soft); display: inline-flex; align-items: center; }
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
      h1 { font-size: clamp(2.4rem, 4.8vw, 4.4rem); line-height: 0.94; letter-spacing: -0.03em; }
      h2 { font-size: 1.4rem; }
      h3 { font-size: 1.06rem; }
      .site-card h3 { line-height: 1.12; }
      @media (max-width: 1100px) { .story-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
      @media (max-width: 900px) { .panel-grid { grid-template-columns: 1fr; } .page { padding: 16px 14px 42px; } .hero, .panel, .site-header, .section-nav { padding: 18px; border-radius: 22px; } .site-header { align-items: flex-start; flex-direction: column; } .story-filter-grid { grid-template-columns: 1fr; } .story-grid { grid-template-columns: 1fr; } }
      @media (max-width: 620px) { .site-nav, .section-nav-links { flex-wrap: nowrap; overflow-x: auto; -webkit-overflow-scrolling: touch; padding-bottom: 2px; } .site-header-copy { min-width: 0; } .archive-row { flex-direction: column; align-items: flex-start; } .badge, .link-pill { line-height: 1.2; } }
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
          const matchesSourceKind = activeFilters["source-kind"] === "all" || normalizeStoryFilterText(card.dataset.sourceKind) === activeFilters["source-kind"];
          const matchesFreshness = activeFilters["freshness"] === "all" || normalizeStoryFilterText(card.dataset.freshness) === activeFilters["freshness"];
          const matchesLinkQuality = activeFilters["link-quality"] === "all" || normalizeStoryFilterText(card.dataset.linkQuality) === activeFilters["link-quality"];
          const matchesRegion = activeFilters["region"] === "all" || normalizeStoryFilterText(card.dataset.region).replace(/\\s+/g, "_") === activeFilters["region"];
          const matchesAccess = activeFilters["access"] === "all" || normalizeStoryFilterText(card.dataset.access) === activeFilters["access"];
          const matchesDateWindow = activeFilters["date-window"] === "all" || normalizeStoryFilterText(card.dataset.dateWindow) === activeFilters["date-window"];
          const matchesStoryStatus = activeFilters["story-status"] === "all" || normalizeStoryFilterText(card.dataset.storyStatus) === activeFilters["story-status"];
          const matchesClaimType = activeFilters["claim-type"] === "all" || normalizeStoryFilterText(card.dataset.claimType) === activeFilters["claim-type"];
          const visible = matchesQuery && matchesSourceKind && matchesFreshness && matchesLinkQuality && matchesRegion && matchesAccess && matchesDateWindow && matchesStoryStatus && matchesClaimType;
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
