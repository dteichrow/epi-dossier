from __future__ import annotations

import argparse
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from .database import SeenItemsDB
from .main import parse_target_date, run_once
from .outbreak_dashboard_quality import build_report as build_outbreak_dashboard_report
from .outbreak_dashboard_quality import run_quality_checks as run_outbreak_dashboard_quality_checks
from .render_html import validate_reader_story_sections
from .render_site import (
    items_for_edition,
    render_atlas_page,
    render_notebook_page,
    render_public_archive_page,
    render_public_desk_page,
    render_public_homepage,
    render_reference_page,
    render_site_index,
    render_story_page,
    stories_for_edition,
)
from .utils import (
    EditionConfig,
    app_exports_dir,
    atomic_write_json,
    archive_relpath,
    docs_archive_filename,
    docs_archive_index_filename,
    docs_desk_filename,
    docs_dir,
    docs_index_filename,
    docs_reference_filename,
    docs_story_filename,
    format_timestamp,
    latest_filename,
    latest_html_filename,
    list_briefing_archives,
    load_editions_config,
    reference_filename,
    safe_html_filename,
    setup_logging,
    site_index_filename,
    story_filename,
)


SITE_BUILD_LOG = Path(__file__).resolve().parent.parent / "logs" / "site-build.log"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Pathogen Dispatch static site surfaces.")
    parser.add_argument("--days", type=int, default=7, help="Search window in days ending at the target date.")
    parser.add_argument("--date", type=str, help="Target date in YYYY-MM-DD format.")
    parser.add_argument("--output-mode", choices=("local", "web", "both"), default="local", help="Choose whether to write local reader files, docs/ web files, or both.")
    parser.add_argument("--deploy-dir", type=str, default="docs", help="Deploy directory for public web output.")
    parser.add_argument("--site-base-url", type=str, default="/", help="Reserved for future base-path aware deployments.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logger = setup_logging()
    target_date = parse_target_date(args.date)
    write_local = args.output_mode in {"local", "both"}
    write_web = args.output_mode in {"web", "both"}

    payload = run_once(
        target_date,
        args.days,
        False,
        logger,
        return_payload=True,
        write_local_artifacts=write_local,
    )
    if not payload:
        return 1

    latest_snapshot = payload["latest_snapshot"]
    story_records = payload.get("render_story_records") or latest_snapshot.get("stories", [])
    reference_records = payload.get("render_reference_records") or latest_snapshot.get("reference", [])
    publication_snapshot = deepcopy(latest_snapshot)
    publication_snapshot["stories"] = deepcopy(story_records)
    publication_snapshot["story_count"] = len(story_records)
    publication_snapshot["reference"] = deepcopy(reference_records)
    reader_html = payload["html_output"]
    html_validation_issues = payload.get("html_validation_issues") or validate_reader_story_sections(reader_html, story_records)
    db = SeenItemsDB()
    try:
        items_by_id = build_story_items_index(publication_snapshot, story_records, db)
    finally:
        db.close()

    archive_entries = list_briefing_archives(include_date=target_date)
    archive_payload = build_archive_payload(archive_entries)
    editions = load_editions_config()

    if write_local:
        write_local_surfaces(
            payload,
            publication_snapshot,
            story_records,
            reference_records,
            items_by_id,
            archive_payload,
            reader_html,
            html_validation_issues,
        )
    if write_web:
        write_public_surfaces(
            payload,
            publication_snapshot,
            story_records,
            reference_records,
            items_by_id,
            archive_entries,
            archive_payload,
            editions,
            args.deploy_dir,
            reader_html,
            html_validation_issues,
        )

    append_site_build_log(
        target_date=payload["target_date"].isoformat(),
        generated_at=payload["generated_at"],
        latest_snapshot=publication_snapshot,
        promoted=payload["promote_latest"],
        source_failures=payload["source_failures"],
        docs_refreshed=write_web,
        reader_guard_ok=not html_validation_issues,
        story_render_fallback_used=bool(payload.get("story_render_fallback_used")),
    )
    write_overnight_summary(
        publication_snapshot,
        archive_payload,
        editions,
        args.deploy_dir,
        write_web,
        reader_guard_ok=not html_validation_issues,
        story_render_fallback_used=bool(payload.get("story_render_fallback_used")),
    )
    logger.info(
        "Built site surfaces for %s: %s story page(s), %s reference page(s), local=%s web=%s promoted latest=%s",
        payload["target_date"].isoformat(),
        len(story_records),
        len(reference_records),
        write_local,
        write_web,
        payload["promote_latest"],
    )
    return 0


def write_local_surfaces(
    payload: dict[str, Any],
    publication_snapshot: dict[str, Any],
    story_records: list[dict[str, Any]],
    reference_records: list[dict[str, Any]],
    items_by_id: dict[str, dict[str, Any]],
    archive_payload: list[dict[str, Any]],
    reader_html: str,
    html_validation_issues: list[str],
) -> None:
    for story in story_records:
        story_path = story_filename(story["story_id"], story["topic_name"])
        story_path.parent.mkdir(parents=True, exist_ok=True)
        story_path.write_text(
            render_story_page(story, items_by_id, payload["target_date"], payload["generated_at"]),
            encoding="utf-8",
        )

    for reference in reference_records:
        reference_path = reference_filename(reference["name"])
        reference_path.parent.mkdir(parents=True, exist_ok=True)
        reference_path.write_text(
            render_reference_page(reference, payload["target_date"], payload["generated_at"]),
            encoding="utf-8",
        )

    if not html_validation_issues:
        payload["paths"]["dated_html"].parent.mkdir(parents=True, exist_ok=True)
        payload["paths"]["legacy_html"].parent.mkdir(parents=True, exist_ok=True)
        payload["paths"]["dated_html"].write_text(reader_html, encoding="utf-8")
        payload["paths"]["legacy_html"].write_text(reader_html, encoding="utf-8")
        if payload["promote_latest"]:
            payload["paths"]["latest_html"].parent.mkdir(parents=True, exist_ok=True)
            payload["paths"]["latest_html"].write_text(reader_html, encoding="utf-8")

    site_index_filename().write_text(
        render_site_index(
            publication_snapshot,
            archive_payload,
            reference_records,
        ),
        encoding="utf-8",
    )
    (payload["paths"]["latest_html"].parent / "notebook.html").write_text(
        render_notebook_page(
            "Reporter's Notebook",
            "A working layer for reporters: what to ask next, which numbers matter, and which framing traps to avoid before writing.",
            story_records,
            reference_records,
            archive_payload,
            web_mode=False,
        ),
        encoding="utf-8",
    )
    (payload["paths"]["latest_html"].parent / "atlas.html").write_text(
        render_atlas_page(
            "Pathogen Atlas",
            "A curated origin-and-spread atlas that links geography, evidence, uncertainty, and prior Edge of Epidemiology writing.",
            publication_snapshot.get("atlas", []),
            archive_payload,
            web_mode=False,
            current_run_id=str(publication_snapshot.get("run_id", "")),
            current_generated_at=str(publication_snapshot.get("generated_at", "")),
        ),
        encoding="utf-8",
    )


def write_public_surfaces(
    payload: dict[str, Any],
    publication_snapshot: dict[str, Any],
    story_records: list[dict[str, Any]],
    reference_records: list[dict[str, Any]],
    items_by_id: dict[str, dict[str, Any]],
    archive_entries: list,
    archive_payload: list[dict[str, Any]],
    editions: list[EditionConfig],
    deploy_dir: str,
    reader_html: str,
    html_validation_issues: list[str],
) -> None:
    docs_root = Path(docs_dir(deploy_dir))
    docs_root.mkdir(parents=True, exist_ok=True)
    public_snapshot = transform_public_payload(deepcopy(publication_snapshot))
    public_story_records = public_snapshot.get("stories", [])
    public_reference_records = public_snapshot.get("reference", [])

    # Story URLs circulate through newsletters, social posts, search indexes, and
    # archive pages after they leave the active story list. Current stories are
    # overwritten below, but older story pages should remain available instead
    # of turning into public 404s after an automated refresh.
    prune_generated_public_pages(
        docs_root / "reference",
        {Path(reference.get("reference_web_path", "")).name for reference in public_reference_records if reference.get("reference_web_path")},
    )

    if not html_validation_issues:
        docs_latest_html = docs_root / "latest.html"
        docs_latest_html.write_text(
            inject_public_live_update_support(
                rewrite_local_reader_links(reader_html, ".", payload["paths"]["latest_html"].parent),
                "./app_exports/manifest.json",
                str(publication_snapshot.get("run_id", "")),
                str(publication_snapshot.get("generated_at", "")),
            ),
            encoding="utf-8",
        )
    (docs_root / "latest.md").write_text(payload["markdown_output"], encoding="utf-8")

    current_archive_html = docs_archive_filename(payload["target_date"], deploy_dir=deploy_dir, suffix=".html")
    current_archive_html.parent.mkdir(parents=True, exist_ok=True)
    if not html_validation_issues:
        current_archive_html.write_text(
            inject_public_live_update_support(
                rewrite_local_reader_links(reader_html, "../..", payload["paths"]["latest_html"].parent),
                "../../app_exports/manifest.json",
                str(publication_snapshot.get("run_id", "")),
                str(publication_snapshot.get("generated_at", "")),
            ),
            encoding="utf-8",
        )
    docs_archive_filename(payload["target_date"], deploy_dir=deploy_dir, suffix=".md").write_text(payload["markdown_output"], encoding="utf-8")

    for entry in archive_entries:
        if entry.target_date == payload["target_date"]:
            continue
        archive_target_html = docs_archive_filename(entry.target_date, deploy_dir=deploy_dir, suffix=".html")
        archive_target_html.parent.mkdir(parents=True, exist_ok=True)
        if entry.html_path.exists():
            archive_target_html.write_text(
                inject_public_live_update_support(
                    rewrite_local_reader_links(entry.html_path.read_text(encoding="utf-8"), "../.."),
                    "../../app_exports/manifest.json",
                    str(publication_snapshot.get("run_id", "")),
                    str(publication_snapshot.get("generated_at", "")),
                ),
                encoding="utf-8",
            )
        archive_target_md = docs_archive_filename(entry.target_date, deploy_dir=deploy_dir, suffix=".md")
        if entry.markdown_path.exists():
            archive_target_md.write_text(entry.markdown_path.read_text(encoding="utf-8"), encoding="utf-8")

    for story in public_story_records:
        story_path = docs_story_filename(story["story_id"], story["topic_name"], deploy_dir=deploy_dir)
        story_path.parent.mkdir(parents=True, exist_ok=True)
        story_path.write_text(
            render_story_page(
                story,
                items_by_id,
                payload["target_date"],
                payload["generated_at"],
                web_mode=True,
                current_run_id=str(publication_snapshot.get("run_id", "")),
            ),
            encoding="utf-8",
        )

    for reference in public_reference_records:
        reference_path = docs_reference_filename(reference["name"], deploy_dir=deploy_dir)
        reference_path.parent.mkdir(parents=True, exist_ok=True)
        reference_path.write_text(
            render_reference_page(
                reference,
                payload["target_date"],
                payload["generated_at"],
                web_mode=True,
                current_run_id=str(publication_snapshot.get("run_id", "")),
            ),
            encoding="utf-8",
        )

    docs_index_filename(deploy_dir).write_text(
        render_public_homepage(public_snapshot, archive_payload, public_reference_records),
        encoding="utf-8",
    )

    for edition in editions:
        if edition.key == "index":
            continue
        desk_path = docs_desk_filename(Path(edition.page).stem, deploy_dir)
        desk_path.write_text(
            render_public_desk_page(
                edition.label,
                edition.description,
                edition.key,
                stories_for_edition(public_story_records, edition.key)[: edition.max_stories],
                items_for_edition(public_snapshot.get("items", []), edition.key)[: edition.max_items],
                related_references_for_edition(public_reference_records, edition.key),
                archive_payload,
                atlas_entries=public_snapshot.get("atlas", []),
                current_run_id=str(public_snapshot.get("run_id", "")),
                current_generated_at=str(public_snapshot.get("generated_at", "")),
            ),
            encoding="utf-8",
        )

    (docs_root / "atlas.html").write_text(render_legacy_atlas_redirect_html(), encoding="utf-8")

    archive_index_path = docs_archive_index_filename(deploy_dir)
    archive_index_path.parent.mkdir(parents=True, exist_ok=True)
    archive_index_path.write_text(
        render_public_archive_page(archive_payload, public_snapshot, public_reference_records),
        encoding="utf-8",
    )
    write_public_exports(publication_snapshot, archive_payload, deploy_dir, story_items_by_id=items_by_id)
    dashboard_report = build_outbreak_dashboard_report(
        run_outbreak_dashboard_quality_checks(
            snapshot_path=docs_root / "app_exports" / "latest.json",
            docs_root=docs_root,
        )
    )
    if dashboard_report["summary"]["errors"]:
        detail = "; ".join(
            f"{issue['story_id']} {issue['metric']}: {issue['message']}"
            for issue in dashboard_report["issues"]
            if issue["severity"] == "error"
        )
        raise RuntimeError(f"Outbreak dashboard QA failed after public render: {detail}")


def render_legacy_atlas_redirect_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Redirecting to Pathogen Atlas</title>
    <meta http-equiv="refresh" content="0; url=/atlases/pathogen/" />
    <script>
      (function () {
        const target = new URL("/atlases/pathogen/", window.location.origin);
        target.search = window.location.search;
        target.hash = window.location.hash;
        window.location.replace(target.toString());
      })();
    </script>
    <style>
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: #f7f2e8;
        color: #1f2f42;
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
      }
      main {
        max-width: 38rem;
        padding: 2rem;
        text-align: center;
      }
      a {
        color: #1f5b89;
      }
    </style>
  </head>
  <body>
    <main>
      <h1>Redirecting to the Pathogen Atlas</h1>
      <p>The public atlas now lives in the unified Edge of Epidemiology site.</p>
      <p><a href="/atlases/pathogen/">Continue to the atlas</a></p>
    </main>
  </body>
</html>
"""


def rewrite_local_reader_links(html_text: str, relative_prefix: str, local_reader_root: Path | None = None) -> str:
    roots = [latest_html_filename().parent]
    if local_reader_root is not None:
        roots.append(local_reader_root)
    rewritten = html_text
    for root in roots:
        local_prefix = root.resolve().as_uri()
        rewritten = rewritten.replace(local_prefix, relative_prefix)
    rewritten = re.sub(r"file:///[^\"']*/Daily%20Dossiers", relative_prefix, rewritten)
    return rewritten


def inject_public_live_update_support(
    html_text: str,
    manifest_path: str,
    current_run_id: str,
    current_generated_at: str,
) -> str:
    snippet = f"""
<style>
  .public-live-update-banner {{
    position: fixed;
    right: 18px;
    bottom: 18px;
    z-index: 9999;
    max-width: min(420px, calc(100vw - 28px));
    border-radius: 18px;
    border: 1px solid rgba(31, 91, 137, 0.24);
    background: rgba(255, 252, 247, 0.98);
    box-shadow: 0 18px 42px rgba(28, 20, 12, 0.18);
    padding: 14px 16px;
    display: grid;
    gap: 10px;
  }}
  .public-live-update-banner[hidden] {{
    display: none !important;
  }}
  .public-live-update-copy {{
    display: grid;
    gap: 6px;
  }}
  .public-live-update-label {{
    margin: 0;
    font-family: "Avenir Next Condensed", "Franklin Gothic Medium", sans-serif;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.74rem;
    color: #8d3f2f;
  }}
  .public-live-update-text {{
    margin: 0;
    font-family: "Avenir Next", "Helvetica Neue", sans-serif;
    color: #42515e;
  }}
  .public-live-update-actions {{
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    flex-wrap: wrap;
  }}
  .public-live-update-dismiss {{
    border: 0;
    background: transparent;
    color: #42515e;
    font-family: "Avenir Next", "Helvetica Neue", sans-serif;
    font-weight: 600;
    cursor: pointer;
    padding: 10px 4px;
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
  }}
  .public-live-update-dismiss:hover {{
    color: #1b2836;
  }}
  .public-live-update-button {{
    justify-self: start;
    border-radius: 999px;
    padding: 10px 14px;
    border: 1px solid rgba(31, 91, 137, 0.26);
    background: rgba(31, 91, 137, 0.12);
    color: #1f5b89;
    font-family: "Avenir Next", "Helvetica Neue", sans-serif;
    font-weight: 700;
    cursor: pointer;
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
  }}
  .public-live-update-button:hover {{
    background: rgba(31, 91, 137, 0.18);
  }}
  @media (max-width: 700px) {{
    .public-live-update-banner {{
      right: 12px;
      bottom: 12px;
      width: calc(100vw - 24px);
      max-width: none;
    }}
    .public-live-update-actions {{
      justify-content: space-between;
    }}
  }}
</style>
<section class="public-live-update-banner" id="public-live-update-banner" hidden aria-live="polite" data-live-update-banner="true">
  <div class="public-live-update-copy">
    <p class="public-live-update-label">New edition available</p>
    <p class="public-live-update-text" id="public-live-update-text">An updated edition is available. Load the latest run when you are ready.</p>
  </div>
  <div class="public-live-update-actions">
    <button class="public-live-update-dismiss" id="public-live-update-dismiss" type="button" onclick="(function(btn){{const banner=btn.closest('[data-live-update-banner]');if(banner){{banner.hidden=true;banner.style.display='none';const runId=(banner.dataset&&banner.dataset.pendingRunId)||'';const key=(banner.dataset&&banner.dataset.dismissKey)||('pathogen-dispatch-live-update-dismissed:'+window.location.pathname);try{{window.sessionStorage.setItem(key, window.location.pathname+'::'+(runId||'unknown'));}}catch(error){{}}}}return false;}})(this)">Keep reading</button>
    <button class="public-live-update-button" id="public-live-update-refresh" type="button" onclick="(function(btn){{const banner=btn.closest('[data-live-update-banner]');if(banner){{banner.hidden=true;banner.style.display='none';}}const url=new URL(window.location.href);url.searchParams.set('_edition', String(Date.now()));window.location.replace(url.toString());return false;}})(this)">Load latest</button>
  </div>
</section>
<script>
  (function () {{
    const banner = document.getElementById("public-live-update-banner");
    const button = document.getElementById("public-live-update-refresh");
    const dismiss = document.getElementById("public-live-update-dismiss");
    const text = document.getElementById("public-live-update-text");
    const currentRunId = {current_run_id!r};
    const currentGeneratedAt = {current_generated_at!r};
    const manifestPath = {manifest_path!r};
    const storageKey = `pathogen-dispatch-live-update-dismissed:${{window.location.pathname}}`;
    const liveUpdateStart = Date.now();
    let pendingRunId = "";

    function shouldCheckForUpdates() {{
      return window.location.protocol === "https:" || window.location.protocol === "http:";
    }}

    function getManifestRunId(manifest) {{
      return String(manifest.latest_run_id || manifest.run_id || "").trim();
    }}

    function dismissValue(runId) {{
      return `${{window.location.pathname}}::${{runId || "unknown"}}`;
    }}

    function isDismissed(runId) {{
      try {{
        return window.sessionStorage.getItem(storageKey) === dismissValue(runId);
      }} catch (error) {{
        return false;
      }}
    }}

    function dismissNotice(runId) {{
      if (!banner) return;
      banner.hidden = true;
      banner.dataset.pendingRunId = "";
      pendingRunId = "";
      try {{
        window.sessionStorage.setItem(storageKey, dismissValue(runId));
      }} catch (error) {{
        // Ignore storage failures and just hide the notice for this page view.
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

    function newerManifest(manifest) {{
      const nextRunId = getManifestRunId(manifest);
      const nextGeneratedAt = String(manifest.generated_at || "").trim();
      if (currentRunId && nextRunId) {{
        return nextRunId !== currentRunId;
      }}
      if (currentGeneratedAt && nextGeneratedAt) {{
        return nextGeneratedAt !== currentGeneratedAt;
      }}
      return false;
    }}

    function pageHasAged() {{
      return Date.now() - liveUpdateStart >= 360000;
    }}

    async function checkForUpdates() {{
      if (!shouldCheckForUpdates()) return;
      if (!pageHasAged()) return;
      try {{
        const response = await fetch(`${{manifestPath}}?ts=${{Date.now()}}`, {{ cache: "no-store" }});
        if (!response.ok) return;
        const manifest = await response.json();
        if (!newerManifest(manifest)) return;
        const nextRunId = getManifestRunId(manifest);
        if (isDismissed(nextRunId)) return;
        pendingRunId = nextRunId;
        if (banner) {{
          banner.dataset.pendingRunId = nextRunId;
          banner.dataset.dismissKey = storageKey;
        }}
        if (text) {{
          const publishedAt = formatManifestTime(manifest.generated_at);
          text.textContent = publishedAt
            ? `Updated edition available from ${{publishedAt}}. Load the latest run when you are ready.`
            : "An updated edition is available. Load the latest run when you are ready.";
        }}
        if (banner) banner.hidden = false;
      }} catch (error) {{
        // Ignore update-check failures to keep the reader surface quiet.
      }}
    }}

    window.__pathogenDismissPublicUpdate = function (button) {{
      const currentBanner = button && button.closest ? button.closest("[data-live-update-banner]") : banner;
      const runId = currentBanner && currentBanner.dataset ? currentBanner.dataset.pendingRunId || "" : "";
      dismissNotice(runId);
    }};

    window.__pathogenLoadPublicLatest = function (button) {{
      const currentBanner = button && button.closest ? button.closest("[data-live-update-banner]") : banner;
      if (currentBanner) {{
        currentBanner.hidden = true;
      }}
      const url = new URL(window.location.href);
      url.searchParams.set("_edition", String(Date.now()));
      window.location.replace(url.toString());
    }};

    if (button) {{
      button.addEventListener("click", (event) => {{
        event.preventDefault();
        window.__pathogenLoadPublicLatest(button);
      }});
    }}
    if (dismiss) {{
      dismiss.addEventListener("click", (event) => {{
        event.preventDefault();
        window.__pathogenDismissPublicUpdate(dismiss);
      }});
    }}
    if (shouldCheckForUpdates()) {{
      window.setTimeout(checkForUpdates, 360000);
      window.setInterval(checkForUpdates, 600000);
    }}
  }})();
</script>
"""
    if "</body>" not in html_text:
        return f"{html_text}\n{snippet}"
    return html_text.replace("</body>", f"{snippet}\n</body>", 1)


def related_references_for_edition(reference_records: list[dict[str, Any]], edition_key: str) -> list[dict[str, Any]]:
    if edition_key == "notebook":
        return reference_records[:10]
    if edition_key == "atlas":
        return [reference for reference in reference_records if reference.get("atlas_entry_slug")][:8] or reference_records[:6]
    return [reference for reference in reference_records if edition_key in reference.get("editions", [])][:6] or reference_records[:4]


def build_story_items_index(latest_snapshot: dict, story_records: list[dict], db: SeenItemsDB) -> dict[str, dict]:
    items_by_id = {item["item_id"]: item for item in latest_snapshot.get("items", []) if item.get("item_id")}
    live_item_ids = set(items_by_id)
    required_item_ids: set[str] = set()
    for story in story_records:
        required_item_ids.update(story.get("item_ids", []))
        required_item_ids.update(story.get("official_item_ids", []))
        required_item_ids.update(story.get("press_item_ids", []))
    if required_item_ids.difference(items_by_id):
        stored_items = db.load_app_feed_items()
        for item_id in required_item_ids:
            if item_id in items_by_id:
                continue
            stored = stored_items.get(item_id)
            if stored:
                retained = dict(stored)
                retained["freshness_state"] = retained.get("freshness_state") or "retained"
                items_by_id[item_id] = retained
    for item_id in live_item_ids:
        items_by_id[item_id]["freshness_state"] = items_by_id[item_id].get("freshness_state") or "live"
    return items_by_id


def build_archive_payload(entries: list) -> list[dict[str, Any]]:
    return [
        {
            "date": entry.target_date.isoformat(),
            "year": entry.target_date.year,
            "month": f"{entry.target_date:%m}",
            "month_name": entry.target_date.strftime("%B"),
            "day": f"{entry.target_date:%d}",
            "html_url": entry.html_path.resolve().as_uri(),
            "html_web_path": archive_relpath(entry.target_date, suffix=".html").as_posix(),
            "markdown_web_path": archive_relpath(entry.target_date, suffix=".md").as_posix(),
        }
        for entry in entries
    ]


def append_site_build_log(
    target_date: str,
    generated_at: datetime,
    latest_snapshot: dict,
    promoted: bool,
    source_failures: list[dict[str, str]],
    *,
    docs_refreshed: bool,
    reader_guard_ok: bool,
    story_render_fallback_used: bool,
) -> None:
    SITE_BUILD_LOG.parent.mkdir(parents=True, exist_ok=True)
    freshness = latest_snapshot.get("freshness_summary", {})
    source_health = latest_snapshot.get("source_health", [])
    cache_sources = sum(1 for entry in source_health if entry.get("mode") in {"refresh_cache", "fallback_cache"})
    failed_sources = sum(1 for entry in source_health if entry.get("mode") == "failed")
    wrapper_only = sum(1 for item in latest_snapshot.get("items", []) if item.get("link_quality") == "wrapper_only")
    metadata_only = sum(1 for item in latest_snapshot.get("items", []) if item.get("link_quality") == "metadata_only")
    line = (
        f"{generated_at.isoformat(timespec='seconds')} "
        f"target_date={target_date} items={latest_snapshot.get('item_count', 0)} "
        f"stories={latest_snapshot.get('story_count', 0)} reference={len(latest_snapshot.get('reference', []))} "
        f"live_items={freshness.get('live', 0)} refresh_cache_items={freshness.get('refresh_cache', 0)} "
        f"fallback_cache_items={freshness.get('fallback_cache', 0)} retained_items={freshness.get('retained', 0)} "
        f"cache_sources={cache_sources} failed_sources={failed_sources} "
        f"wrapper_only={wrapper_only} metadata_only={metadata_only} "
        f"degraded={bool(latest_snapshot.get('degraded'))} promoted_latest={promoted} docs_refreshed={docs_refreshed} "
        f"reader_guard={'ok' if reader_guard_ok else 'blocked'} "
        f"story_fallback={'yes' if story_render_fallback_used else 'no'}\n"
    )
    with SITE_BUILD_LOG.open("a", encoding="utf-8") as handle:
        handle.write(line)


def write_public_exports(
    latest_snapshot: dict[str, Any],
    archive_payload: list[dict[str, Any]],
    deploy_dir: str,
    *,
    story_items_by_id: dict[str, dict[str, Any]] | None = None,
) -> None:
    public_dir = Path(docs_dir(deploy_dir)) / "app_exports"
    public_dir.mkdir(parents=True, exist_ok=True)
    public_latest = transform_public_payload(deepcopy(latest_snapshot))
    public_story_items = build_public_story_items(public_latest, story_items_by_id or {})
    public_latest["story_items"] = public_story_items
    public_latest["story_item_count"] = len(public_story_items)
    atomic_write_json(public_dir / "latest.json", public_latest)
    atomic_write_json(public_dir / "atlas.json", {"atlas": public_latest.get("atlas", []), "generated_at": latest_snapshot.get("generated_at"), "run_id": latest_snapshot.get("run_id")})
    atomic_write_json(
        public_dir / "archive.json",
        {
            "generated_at": latest_snapshot.get("generated_at"),
            "latest": {"html_url": "latest.html", "public_home": "index.html", "html_web_path": "latest.html"},
            "entries": [
                {
                    **entry,
                    "html_url": entry.get("html_web_path", ""),
                    "markdown_url": entry.get("markdown_web_path", ""),
                }
                for entry in archive_payload
            ],
        },
    )
    atomic_write_json(
        public_dir / "health.json",
        {
            "generated_at": latest_snapshot.get("generated_at"),
            "degraded": latest_snapshot.get("degraded", False),
            "source_failures": latest_snapshot.get("source_failures", []),
            "freshness_summary": latest_snapshot.get("freshness_summary", {}),
            "editor_summary": latest_snapshot.get("editor_summary") or {},
        },
    )
    atomic_write_json(
        public_dir / "manifest.json",
        {
            "latest_run_id": latest_snapshot.get("run_id"),
            "generated_at": latest_snapshot.get("generated_at"),
            "files": {
                "home": "index.html",
                "latest": "latest.json",
                "atlas": "atlas.json",
                "archive": "archive.json",
                "health": "health.json",
            },
        },
    )


def build_public_story_items(public_latest: dict[str, Any], story_items_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    current_item_ids = {item.get("item_id") for item in public_latest.get("items", []) if isinstance(item, dict) and item.get("item_id")}
    required_item_ids: list[str] = []
    for story in public_latest.get("stories", []):
        if not isinstance(story, dict):
            continue
        for key in ("official_item_ids", "press_item_ids", "item_ids"):
            for item_id in story.get(key, []) or []:
                if item_id and item_id not in required_item_ids:
                    required_item_ids.append(item_id)

    retained_items = [
        story_items_by_id[item_id]
        for item_id in required_item_ids
        if item_id not in current_item_ids and item_id in story_items_by_id
    ]
    return transform_public_payload(retained_items)


def prune_generated_public_pages(directory: Path, expected_filenames: set[str]) -> None:
    if not directory.exists():
        return
    for candidate in directory.glob("*.html"):
        if candidate.name not in expected_filenames:
            candidate.unlink()


def transform_public_payload(payload: Any) -> Any:
    local_prefix = latest_html_filename().parent.resolve().as_uri() + "/"
    if isinstance(payload, str) and payload.startswith(local_prefix):
        return payload.removeprefix(local_prefix)
    if isinstance(payload, list):
        return [transform_public_payload(value) for value in payload]
    if not isinstance(payload, dict):
        return payload

    transformed = {}
    for key, value in payload.items():
        if key == "story_url" and payload.get("story_web_path"):
            transformed[key] = payload.get("story_web_path")
            continue
        if key == "reference_url" and payload.get("reference_web_path"):
            transformed[key] = payload.get("reference_web_path")
            continue
        if key == "html_url" and payload.get("html_web_path"):
            transformed[key] = payload.get("html_web_path")
            continue
        if key == "markdown_url" and payload.get("markdown_web_path"):
            transformed[key] = payload.get("markdown_web_path")
            continue
        transformed[key] = transform_public_payload(value)
    return transformed


def write_overnight_summary(
    latest_snapshot: dict[str, Any],
    archive_payload: list[dict[str, Any]],
    editions: list[EditionConfig],
    deploy_dir: str,
    docs_refreshed: bool,
    *,
    reader_guard_ok: bool,
    story_render_fallback_used: bool,
) -> None:
    summary = {
        "generated_at": latest_snapshot.get("generated_at"),
        "run_id": latest_snapshot.get("run_id"),
        "attempted_sources": [entry.get("source") for entry in latest_snapshot.get("source_health", [])],
        "attempted_source_count": len(latest_snapshot.get("source_health", [])),
        "desk_counts": {
            edition.key: {
                "items": len(items_for_edition(latest_snapshot.get("items", []), edition.key)),
                "stories": len(stories_for_edition(latest_snapshot.get("stories", []), edition.key)),
            }
            for edition in editions
        },
        "regional_coverage_counts": build_region_counts(latest_snapshot.get("items", [])),
        "wrapper_only_count": sum(1 for item in latest_snapshot.get("items", []) if item.get("link_quality") == "wrapper_only"),
        "metadata_only_count": sum(1 for item in latest_snapshot.get("items", []) if item.get("link_quality") == "metadata_only"),
        "failed_sources": latest_snapshot.get("source_failures", []),
        "promoted_lead_stories": [story.get("display_title") for story in latest_snapshot.get("stories", [])[:4]],
        "docs_refreshed": docs_refreshed,
        "reader_guard_ok": reader_guard_ok,
        "story_render_fallback_used": story_render_fallback_used,
        "public_deploy_dir": deploy_dir,
        "archive_days_available": len(archive_payload),
    }
    atomic_write_json(app_exports_dir() / "overnight_summary.json", summary)


def build_region_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        region = item.get("region", "")
        if not region:
            continue
        counts[region] = counts.get(region, 0) + 1
    return counts


if __name__ == "__main__":
    raise SystemExit(main())
