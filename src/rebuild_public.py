"""Render existing public evidence with current contracts; no fetching or sending."""

from __future__ import annotations
import argparse
from datetime import date, datetime
import json
import re
from pathlib import Path
import shutil
from .public_contracts import normalize_snapshot, public_summary, item_date_label
from .render_site import (
    render_public_homepage,
    render_public_desk_page,
    render_story_page,
    render_reference_page,
    render_public_archive_page,
    stories_for_edition,
    items_for_edition,
)
from .utils import load_editions_config


def refresh_archived_palette(document: str) -> str:
    """Update retired design colours without rewriting archived reporting."""
    replacements = {
        "#35552b": "#61436e",
        "#173226": "#30233c",
        "#376846": "#65477a",
        "#d8f1dc": "#eee0f5",
        "#9fd0aa": "#cbb0df",
    }
    document = re.sub(
        r"#[0-9a-fA-F]{6}\b",
        lambda match: replacements.get(match[0].lower(), match[0]),
        document,
    )
    document = re.sub(r"rgba\(\s*60\s*,\s*88\s*,\s*48\s*,", "rgba(97,67,110,", document)
    return re.sub(r"rgba\(\s*31\s*,\s*42\s*,\s*45\s*,", "rgba(32,33,39,", document)


def rebuild(source_docs: Path, output_dir: Path):
    if source_docs.resolve() != output_dir.resolve():
        shutil.copytree(source_docs, output_dir, dirs_exist_ok=True)
    export_dir = output_dir / "app_exports"
    snapshot = normalize_snapshot(
        json.loads((source_docs / "app_exports/latest.json").read_text())
    )
    archive = json.loads((source_docs / "app_exports/archive.json").read_text()).get(
        "entries", []
    )
    references = snapshot.get("reference", [])
    items = {
        i["item_id"]: i
        for i in snapshot.get("items", []) + snapshot.get("story_items", [])
    }
    target = date.fromisoformat(snapshot["target_date"])
    generated = datetime.fromisoformat(snapshot["generated_at"])

    def write(route, text):
        path = output_dir / route
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    home = render_public_homepage(snapshot, archive, references)
    write("index.html", home)
    # A current source-led briefing uses the same verified export as the desk.
    write(
        "latest.html",
        home.replace(
            "<title>The Pathogen Dispatch</title>",
            "<title>Latest Pathogen Dispatch</title>",
        ),
    )
    for edition in load_editions_config():
        if edition.key == "index":
            continue
        write(
            Path(edition.page).name,
            render_public_desk_page(
                edition.label,
                edition.description,
                edition.key,
                stories_for_edition(snapshot.get("stories", []), edition.key)[
                    : edition.max_stories
                ],
                items_for_edition(snapshot.get("items", []), edition.key)[
                    : edition.max_items
                ],
                [r for r in references if edition.key in r.get("editions", [])][:6]
                or references[:4],
                archive,
                atlas_entries=snapshot.get("atlas", []),
                current_run_id=str(snapshot.get("run_id", "")),
                current_generated_at=snapshot["generated_at"],
            ),
        )
    for story in snapshot.get("stories", []):
        write(
            story["story_web_path"],
            render_story_page(
                story,
                items,
                target,
                generated,
                web_mode=True,
                current_run_id=snapshot.get("run_id"),
            ),
        )
    for reference in references:
        write(
            reference["reference_web_path"],
            render_reference_page(
                reference,
                target,
                generated,
                web_mode=True,
                current_run_id=snapshot.get("run_id"),
            ),
        )
    write(
        "archive/index.html", render_public_archive_page(archive, snapshot, references)
    )
    write(
        "app_exports/latest.json",
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
    )
    markdown = [
        "# The Pathogen Dispatch",
        f"Collection: {snapshot['generated_at']}",
        "",
    ]
    for story in snapshot.get("stories", []):
        markdown.extend(
            [
                "## " + story.get("display_title", story.get("topic_name", "Story")),
                story.get("latest_update_summary", ""),
                "",
            ]
        )
    for item in snapshot.get("items", []):
        markdown.extend(
            [
                f"### {item.get('title', 'Source report')}",
                item_date_label(item),
                item.get("summary", ""),
                item.get("preferred_url") or item.get("source_url", ""),
                "",
            ]
        )
    write("latest.md", "\n".join(markdown))
    # Older circulated story/archive URLs have no complete record snapshot to
    # rebuild. Remove processing notices without inventing historical updates.
    from bs4 import BeautifulSoup

    for path in list(output_dir.rglob("*.html")) + list(output_dir.rglob("*.svg")):
        original = path.read_text()
        refreshed = refresh_archived_palette(original)
        if refreshed != original:
            path.write_text(refreshed)
            original = refreshed
        if not any(
            term in original.lower()
            for term in (
                "baseline snapshot created",
                "story tracking is now active",
                "no new story delta",
                "clustered item(s)",
            )
        ):
            continue
        soup = BeautifulSoup(original, "html.parser")
        for node in soup.find_all(string=True):
            if node.parent.name in {"script", "style"}:
                continue
            if any(
                term in node.lower()
                for term in (
                    "baseline snapshot created",
                    "story tracking is now active",
                    "no new story delta",
                    "clustered item(s)",
                )
            ):
                node.replace_with(public_summary(str(node)))
        path.write_text(str(soup))
    return {
        "public_contract_version": 2,
        "generated_at": snapshot["generated_at"],
        "items": len(items),
        "stories": len(snapshot.get("stories", [])),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-docs", type=Path, default=Path("docs"))
    parser.add_argument("--output-dir", type=Path, default=Path("docs"))
    args = parser.parse_args()
    print(json.dumps(rebuild(args.source_docs, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
