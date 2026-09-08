"""Public evidence contracts: dates, coverage geography, and reader-facing summaries."""

from __future__ import annotations
import re
from datetime import datetime

COUNTRY_REGIONS = {
    **dict.fromkeys(
        [
            "Democratic Republic of the Congo",
            "Uganda",
            "South Sudan",
            "Rwanda",
            "Sierra Leone",
            "Liberia",
            "Guinea",
            "Nigeria",
            "Kenya",
            "Tanzania",
            "Ethiopia",
            "Ghana",
            "Cape Verde",
        ],
        "Africa",
    ),
    **dict.fromkeys(
        ["United Kingdom", "Spain", "France", "Germany", "Italy"], "Europe"
    ),
    **dict.fromkeys(["United States", "Canada"], "North America"),
    "India": "South Asia",
    "Brazil": "Latin America and Caribbean",
}


def coverage_geography(items, country_for, region_for):
    """Use the same evidence for country and region; retain multiple jurisdictions."""
    official = [
        country_for(item) for item in items if item.official and country_for(item)
    ]
    countries = sorted(
        {
            country
            for value in (official or [country_for(item) for item in items])
            for country in value.split(" / ")
            if country
        }
    )
    regions = sorted({COUNTRY_REGIONS[c] for c in countries if c in COUNTRY_REGIONS})
    if not countries:
        regions = sorted(
            {region_for(item) for item in items}
            - {"", "Cross-region / unassigned", "Multi-region"}
        )
    return {
        "countries": countries,
        "regions": regions,
        "country": " / ".join(countries),
        "primary_region": "Multi-region"
        if len(regions) > 1
        else regions[0]
        if regions
        else "Cross-region / unassigned",
        "geography_basis": "Named official-source jurisdictions"
        if official
        else "Places mentioned in source records",
        "geography_note": "Coverage geography is inferred from source records; mentions are not a geocoded count of cases.",
    }


def public_summary(text, lead_title=""):
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    internal = (
        "baseline snapshot created",
        "story tracking is now active",
        "no new story delta",
        "newly observed linked item",
        "new source(s)",
        "clustered item(s)",
    )
    if not value or any(token in value.lower() for token in internal):
        return (
            f"Monitoring: {lead_title}"
            if lead_title
            else "Monitoring source reports; no distinct new development is established in this update."
        )
    return value


def date_label(value):
    if not value or str(value).lower() in {"unknown", "none", "null"}:
        return "Publication date not established"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return "Published " + parsed.strftime("%b %d, %Y").replace(" 0", " ")
    except ValueError:
        return "Published " + str(value)


def item_date_label(item):
    publication = date_label(
        item.get("source_published_at")
        if "source_published_at" in item
        else item.get("published_at")
    )
    retrieved = item.get("last_retrieved_at")
    if retrieved:
        try:
            publication += " · Retrieved " + datetime.fromisoformat(
                str(retrieved).replace("Z", "+00:00")
            ).strftime("%b %d, %Y").replace(" 0", " ")
        except ValueError:
            pass
    return publication


def infer_country(item) -> str:
    # Publisher domains describe where an outlet is based, not where an outbreak
    # occurred. Geography therefore comes from the report text, except for named
    # official state and local public-health sources whose jurisdiction is clear.
    official_source = item.source.lower()
    if item.official and any(
        marker in official_source
        for marker in (
            "michigan department of health",
            "toledo-lucas county health",
            "ohio department of health",
        )
    ):
        return "United States"

    text = " ".join([item.title.lower(), item.summary.lower()])
    country_map = {
        "Democratic Republic of the Congo": (
            r"\bdemocratic republic of (?:the )?congo\b",
            r"\bdrc\b",
            r"\bdr congo\b",
            r"\bcongo\b",
            r"\bituri\b",
            r"\bnorth kivu\b",
            r"\bbunia\b",
            r"\bkinshasa\b",
        ),
        "Uganda": (r"\buganda\b", r"\bkampala\b"),
        "South Sudan": (r"\bsouth sudan\b",),
        "Rwanda": (r"\brwanda\b",),
        "Sierra Leone": (r"\bsierra leone\b",),
        "Liberia": (r"\bliberia\b",),
        "Guinea": (r"\bguinea\b",),
        "Nigeria": (r"\bnigeria\b",),
        "Kenya": (r"\bkenya\b",),
        "Tanzania": (r"\btanzania\b",),
        "Ethiopia": (r"\bethiopia\b",),
        "Ghana": (r"\bghana\b",),
        "United Kingdom": (
            r"\bunited kingdom\b",
            r"\bbritain\b",
            r"\bbritish\b",
            r"(?<!\w)uk(?!\w)",
        ),
        "Spain": (r"\bspain\b", r"\bcanary islands\b", r"\btenerife\b"),
        "Cape Verde": (r"\bcape verde\b",),
        "United States": (
            r"\bunited states\b",
            r"(?<!\w)u\.?s\.?a?(?!\w)",
            r"\bcalifornia\b",
            r"\bnew york\b",
            r"\btexas\b",
            r"\bmichigan\b",
            r"\bohio\b",
            r"\bwashington state\b",
            r"\boregon\b",
        ),
        "Canada": (r"\bcanada\b",),
        "India": (r"\bindia\b",),
        "Brazil": (r"\bbrazil\b",),
    }
    matches: list[str] = []
    for country, patterns in country_map.items():
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            matches.append(country)
    if len(matches) > 1:
        return " / ".join(matches)
    if matches:
        return matches[0]
    return ""


def normalize_snapshot(snapshot):
    """Upgrade a cached public export without pretending it was fetched again.

    Legacy HTML dates could have come from HTTP Last-Modified. Preserve those
    separately, but do not call them publication dates without provenance.
    """
    from copy import deepcopy
    from types import SimpleNamespace
    from .utils import infer_region

    result = deepcopy(snapshot)
    all_items = result.get("items", []) + result.get("story_items", [])
    items_by_id = {}
    models = {}
    for item in all_items:
        model = SimpleNamespace(
            title=item.get("title", ""),
            summary=item.get("summary", ""),
            source=item.get("source", ""),
            official=item.get("official", False),
        )
        item["country"] = infer_country(model)
        country_regions = {
            COUNTRY_REGIONS[c]
            for c in item["country"].split(" / ")
            if c in COUNTRY_REGIONS
        }
        item["region"] = (
            "Multi-region"
            if len(country_regions) > 1
            else next(iter(country_regions))
            if country_regions
            else infer_region(model)
        )
        if "source_published_at" not in item:
            reported = item.get("published_at")
            valid = reported and str(reported).lower() != "unknown"
            if item.get("source_type") in {"rss", "pubmed"}:
                item["source_published_at"] = reported if valid else None
                item["publication_date_source"] = item["source_type"] if valid else None
            else:
                item["legacy_reported_date"] = reported
                item["source_published_at"] = None
                item["publication_date_source"] = None
                item["published_at"] = "Unknown"
        item.setdefault("first_discovered_at", None)
        item.setdefault("last_retrieved_at", item.get("source_cached_at"))
        item.setdefault("source_last_modified_at", None)
        item["summary"] = public_summary(item.get("summary"), item.get("title", ""))
        if item.get("item_id"):
            items_by_id[item["item_id"]] = item
            models[item["item_id"]] = model
    for story in result.get("stories", []):
        ids = list(
            dict.fromkeys(
                story.get("item_ids", [])
                + story.get("official_item_ids", [])
                + story.get("press_item_ids", [])
            )
        )
        story_items = [models[id] for id in ids if id in models]
        story.update(coverage_geography(story_items, infer_country, infer_region))
        for key in ("latest_update_summary", "current_status_summary", "what_happened"):
            if key in story:
                story[key] = public_summary(
                    story[key],
                    story.get("lead_title") or story.get("display_title", ""),
                )
        story["latest_update_bullets"] = [
            public_summary(b, story.get("lead_title", ""))
            for b in story.get("latest_update_bullets", [])
        ]
        for update in story.get("timeline", []):
            for key in ("summary", "update_summary"):
                if key in update:
                    update[key] = public_summary(
                        update[key], story.get("lead_title", "")
                    )
            if isinstance(update.get("bullets"), list):
                update["bullets"] = [
                    public_summary(b, story.get("lead_title", ""))
                    for b in update["bullets"]
                ]
    result["public_contract_version"] = 2
    return clean_public_tree(result)


def clean_public_tree(value, lead_title=""):
    if isinstance(value, dict):
        title = (
            value.get("lead_title")
            or value.get("display_title")
            or value.get("title")
            or lead_title
        )
        return {key: clean_public_tree(child, title) for key, child in value.items()}
    if isinstance(value, list):
        return [clean_public_tree(child, lead_title) for child in value]
    if isinstance(value, str) and any(
        term in value.lower()
        for term in (
            "baseline snapshot created",
            "story tracking is now active",
            "no new story delta",
            "clustered item(s)",
        )
    ):
        return public_summary(value, lead_title)
    return value
