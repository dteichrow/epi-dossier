from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from . import render_site
from .utils import normalize_whitespace


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT_PATH = REPO_ROOT / "docs" / "app_exports" / "latest.json"
DEFAULT_DOCS_ROOT = REPO_ROOT / "docs"
DEFAULT_OVERRIDES_PATH = REPO_ROOT / "config" / "outbreak_dashboard_overrides.yml"
UNKNOWN_METRIC_VALUES = {"unknown", "not yet confirmed"}


@dataclass(frozen=True)
class DashboardQualityIssue:
    severity: str
    story_id: str
    metric: str
    message: str
    evidence: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "story_id": self.story_id,
            "metric": self.metric,
            "message": self.message,
            "evidence": self.evidence,
        }


def load_latest_snapshot(path: Path = DEFAULT_SNAPSHOT_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing latest snapshot: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Latest snapshot is not an object: {path}")
    return payload


def load_overrides(path: Path = DEFAULT_OVERRIDES_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return {}
    overrides = payload.get("overrides", {})
    return overrides if isinstance(overrides, dict) else {}


def run_quality_checks(
    *,
    snapshot_path: Path = DEFAULT_SNAPSHOT_PATH,
    docs_root: Path = DEFAULT_DOCS_ROOT,
    overrides_path: Path = DEFAULT_OVERRIDES_PATH,
) -> list[DashboardQualityIssue]:
    snapshot = load_latest_snapshot(snapshot_path)
    overrides = load_overrides(overrides_path)
    return validate_snapshot(snapshot, docs_root=docs_root, overrides=overrides)


def validate_snapshot(
    snapshot: dict[str, Any],
    *,
    docs_root: Path = DEFAULT_DOCS_ROOT,
    overrides: dict[str, Any] | None = None,
) -> list[DashboardQualityIssue]:
    overrides = overrides or {}
    stories = [story for story in snapshot.get("stories", []) if isinstance(story, dict)]
    items_by_id = snapshot_items_by_id(snapshot)
    story_ids = {story.get("story_id") for story in stories if story.get("story_id")}
    issues: list[DashboardQualityIssue] = []

    if snapshot.get("degraded"):
        failures = snapshot.get("source_failures") or []
        detail = "; ".join(normalize_whitespace(str(failure.get("source", ""))) for failure in failures if isinstance(failure, dict))
        issues.append(
            DashboardQualityIssue(
                "warn",
                "snapshot",
                "source-health",
                "Latest Newsdesk export is degraded; public pages should be read with source-health caveats.",
                detail or "degraded=true",
            )
        )

    issues.extend(validate_overrides(overrides, story_ids))
    for story in stories:
        if story_in_outbreak_quality_scope(story):
            issues.extend(validate_story_dashboard(story, items_by_id, docs_root=docs_root, overrides=overrides))
        else:
            issues.extend(validate_non_outbreak_story_page(story, docs_root=docs_root))
    return issues


def snapshot_items_by_id(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items_by_id: dict[str, dict[str, Any]] = {}
    for collection_name in ("items", "story_items"):
        for item in snapshot.get(collection_name, []) or []:
            if isinstance(item, dict) and item.get("item_id"):
                items_by_id.setdefault(item["item_id"], item)
    return items_by_id


def story_in_outbreak_quality_scope(story: dict[str, Any]) -> bool:
    return render_site.story_has_outbreak_dashboard(story)


def validate_non_outbreak_story_page(story: dict[str, Any], *, docs_root: Path) -> list[DashboardQualityIssue]:
    story_id = str(story.get("story_id") or story.get("id") or "unknown-story")
    story_path = normalize_whitespace(str(story.get("story_web_path", "")))
    if not story_path:
        return [DashboardQualityIssue("error", story_id, "html", "Story has no story_web_path; generated topic page cannot be verified.")]
    html_path = docs_root / story_path
    if not html_path.exists():
        return [DashboardQualityIssue("error", story_id, "html", "Generated story page is missing.", str(html_path))]
    html_text = html_path.read_text(encoding="utf-8", errors="replace")
    issues: list[DashboardQualityIssue] = []
    if 'id="outbreak-dashboard"' in html_text:
        issues.append(DashboardQualityIssue("error", story_id, "html", "Non-outbreak topic page still renders an outbreak dashboard."))
    if "Tracked outbreak file" in html_text:
        issues.append(DashboardQualityIssue("error", story_id, "html", "Non-outbreak topic page still presents itself as a tracked outbreak file."))
    return issues


def validate_overrides(overrides: dict[str, Any], current_story_ids: set[str]) -> list[DashboardQualityIssue]:
    issues: list[DashboardQualityIssue] = []
    for story_id, override in sorted(overrides.items()):
        story_id_text = str(story_id)
        if not isinstance(override, dict):
            issues.append(DashboardQualityIssue("error", story_id_text, "override", "Dashboard override must be a mapping."))
            continue
        if story_id_text not in current_story_ids:
            issues.append(
                DashboardQualityIssue(
                    "warn",
                    story_id_text,
                    "override",
                    "Dashboard override is not attached to a current story in latest.json.",
                )
            )
        for field in ("source_name", "source_url", "source_status", "as_of"):
            if not normalize_whitespace(str(override.get(field, ""))):
                issues.append(DashboardQualityIssue("error", story_id_text, "override", f"Dashboard override is missing {field}."))
        source_url = normalize_whitespace(str(override.get("source_url", "")))
        if source_url and not re.match(r"^https?://", source_url):
            issues.append(DashboardQualityIssue("error", story_id_text, "override", "Dashboard override source_url must be HTTP(S).", source_url))
        if override.get("as_of") and parse_datetime_value(str(override.get("as_of"))) <= 0:
            issues.append(DashboardQualityIssue("error", story_id_text, "override", "Dashboard override as_of is not parseable.", str(override.get("as_of"))))
        if not any(isinstance(override.get(metric), dict) and override.get(metric, {}).get("value") for metric in ("cases", "deaths")):
            issues.append(DashboardQualityIssue("error", story_id_text, "override", "Dashboard override must include at least one metric value."))
        for metric in ("cases", "deaths"):
            metric_payload = override.get(metric, {})
            if not isinstance(metric_payload, dict) or not metric_payload.get("value"):
                continue
            value = metric_number(metric_payload.get("value"))
            if value is None:
                issues.append(DashboardQualityIssue("error", story_id_text, metric, "Dashboard override metric value must contain a positive number.", str(metric_payload.get("value"))))
            elif value <= 0:
                issues.append(DashboardQualityIssue("error", story_id_text, metric, "Dashboard override metric value must be positive.", str(metric_payload.get("value"))))
            if not normalize_whitespace(str(metric_payload.get("note", ""))):
                issues.append(DashboardQualityIssue("error", story_id_text, metric, "Dashboard override metric requires a source/status note."))
    return issues


def validate_story_dashboard(
    story: dict[str, Any],
    items_by_id: dict[str, dict[str, Any]],
    *,
    docs_root: Path,
    overrides: dict[str, Any],
) -> list[DashboardQualityIssue]:
    story_id = str(story.get("story_id") or story.get("id") or "unknown-story")
    items = story_items(story, items_by_id)
    override = override_for_story(story, overrides)
    issues: list[DashboardQualityIssue] = []
    dashboard_metrics = {
        "cases": dashboard_metric(story, items, override, "cases"),
        "deaths": dashboard_metric(story, items, override, "deaths"),
    }

    story_path = normalize_whitespace(str(story.get("story_web_path", "")))
    if not story_path:
        issues.append(DashboardQualityIssue("error", story_id, "html", "Story has no story_web_path; generated dashboard cannot be verified."))
        html_text = ""
    else:
        html_path = docs_root / story_path
        if not html_path.exists():
            issues.append(DashboardQualityIssue("error", story_id, "html", "Generated story page is missing.", str(html_path)))
            html_text = ""
        else:
            html_text = html_path.read_text(encoding="utf-8", errors="replace")
            issues.extend(validate_story_html(story, dashboard_metrics, html_text))

    for metric_kind, metric in dashboard_metrics.items():
        issues.extend(validate_metric_against_candidates(story, items, override, metric_kind, metric))
    return issues


def story_items(story: dict[str, Any], items_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    ordered_ids = []
    ordered_ids.extend(story.get("official_item_ids", []) or [])
    ordered_ids.extend(story.get("press_item_ids", []) or [])
    if not ordered_ids:
        ordered_ids.extend(story.get("item_ids", []) or [])
    return [items_by_id[item_id] for item_id in ordered_ids if item_id in items_by_id]


def override_for_story(story: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    story_ids = [
        normalize_whitespace(str(story.get("story_id", ""))),
        normalize_whitespace(str(story.get("id", ""))),
    ]
    story_path = normalize_whitespace(str(story.get("story_web_path", "")))
    if story_path:
        story_ids.append(Path(story_path).stem)
    for story_id in story_ids:
        value = overrides.get(story_id)
        if story_id and isinstance(value, dict):
            return value
    return {}


def dashboard_metric(story: dict[str, Any], items: list[dict[str, Any]], override: dict[str, Any], metric_kind: str) -> dict[str, str]:
    return render_site.outbreak_dashboard_metric(story, items, override, metric_kind)


def validate_story_html(story: dict[str, Any], dashboard_metrics: dict[str, dict[str, str]], html_text: str) -> list[DashboardQualityIssue]:
    story_id = str(story.get("story_id") or story.get("id") or "unknown-story")
    issues: list[DashboardQualityIssue] = []
    required_sections = {
        "outbreak-dashboard": "Outbreak dashboard",
        "what-matters-now": "What Matters Now",
        "methodology-note": "Methodology Note",
    }
    for section_id, label in required_sections.items():
        if f'id="{section_id}"' not in html_text:
            issues.append(DashboardQualityIssue("error", story_id, "html", f"Generated story page is missing {label}."))
    latest_updated = normalize_whitespace(str(story.get("latest_updated_at") or story.get("updated_at") or ""))
    if latest_updated and html.escape(latest_updated) not in html_text:
        issues.append(
            DashboardQualityIssue(
                "error",
                story_id,
                "html",
                "Generated story page does not contain the latest_updated_at timestamp from latest.json.",
                latest_updated,
            )
        )
    for metric_kind, metric in dashboard_metrics.items():
        value = normalize_whitespace(str(metric.get("value", "")))
        if not value:
            continue
        label = normalize_whitespace(str(metric.get("label", "Deaths" if metric_kind == "deaths" else "Cases")))
        if not dashboard_value_present(html_text, label, value):
            issues.append(
                DashboardQualityIssue(
                    "error",
                    story_id,
                    metric_kind,
                    "Generated story page dashboard does not match the current snapshot policy.",
                    f"{label}={value}",
                )
            )
    return issues


def dashboard_value_present(html_text: str, label: str, value: str) -> bool:
    label_pattern = re.escape(html.escape(label))
    value_pattern = re.escape(html.escape(value))
    return bool(
        re.search(
            rf'<span class="dashboard-label">{label_pattern}</span>\s*<strong>{value_pattern}</strong>',
            html_text,
        )
    )


def validate_metric_against_candidates(
    story: dict[str, Any],
    items: list[dict[str, Any]],
    override: dict[str, Any],
    metric_kind: str,
    metric: dict[str, str],
) -> list[DashboardQualityIssue]:
    story_id = str(story.get("story_id") or story.get("id") or "unknown-story")
    issues: list[DashboardQualityIssue] = []
    candidates = render_site.collect_outbreak_metric_candidates(story, items, metric_kind)
    authoritative = [candidate for candidate in candidates if render_site.metric_candidate_is_dashboard_authoritative(candidate)]
    dashboard_value = metric_number(metric.get("value"))

    if authoritative and dashboard_value is None and normalize_whitespace(str(metric.get("value", ""))).lower() in UNKNOWN_METRIC_VALUES:
        newest = max(authoritative, key=candidate_recency_key)
        issues.append(
            DashboardQualityIssue(
                "error",
                story_id,
                metric_kind,
                "Dashboard is unknown/not-confirmed despite an authority-citing count in the story evidence.",
                candidate_evidence(newest),
            )
        )
        return issues

    if dashboard_value is None:
        return issues

    dashboard_timestamp = dashboard_metric_timestamp(story, items, override, metric_kind, metric, authoritative)
    for candidate in authoritative:
        candidate_timestamp = int(candidate.get("raw_timestamp") or 0)
        candidate_value = int(candidate.get("numeric_value") or 0)
        if candidate_value > dashboard_value and candidate_timestamp > dashboard_timestamp:
            issues.append(
                DashboardQualityIssue(
                    "error",
                    story_id,
                    metric_kind,
                    "Dashboard value is lower than a newer authority-citing count in the story evidence.",
                    f"dashboard={dashboard_value}; {candidate_evidence(candidate)}",
                )
            )
            break
    return issues


def dashboard_metric_timestamp(
    story: dict[str, Any],
    items: list[dict[str, Any]],
    override: dict[str, Any],
    metric_kind: str,
    metric: dict[str, str],
    authoritative: list[dict[str, Any]],
) -> int:
    if isinstance(override.get(metric_kind), dict) and override.get(metric_kind, {}).get("value"):
        return parse_datetime_value(str(override.get("as_of", "")))
    dashboard_value = metric_number(metric.get("value"))
    matching = [
        candidate
        for candidate in authoritative
        if dashboard_value is not None and int(candidate.get("numeric_value") or 0) == dashboard_value
    ]
    if matching:
        return max(int(candidate.get("raw_timestamp") or 0) for candidate in matching)
    selected_candidates = authoritative or render_site.collect_outbreak_metric_candidates(story, items, metric_kind)
    if selected_candidates:
        return int(render_site.select_metric_candidate(selected_candidates).get("raw_timestamp") or 0)
    return 0


def candidate_recency_key(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(candidate.get("raw_timestamp") or 0), int(candidate.get("numeric_value") or 0)


def candidate_evidence(candidate: dict[str, Any]) -> str:
    source = candidate.get("source") or {}
    source_name = normalize_whitespace(str(source.get("source") or "source item"))
    source_date = normalize_whitespace(str(source.get("date") or "date not captured"))
    return f"{candidate.get('value')} from {source_name} ({source_date})"


def metric_number(value: Any) -> int | None:
    text = normalize_whitespace(str(value or ""))
    match = re.search(r"\d[\d,]*", text)
    if not match:
        return None
    return int(match.group(0).replace(",", ""))


def parse_datetime_value(value: str) -> int:
    text = normalize_whitespace(value)
    if not text:
        return 0
    normalized = text.replace("Z", "+00:00")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
        normalized = f"{normalized}T00:00:00"
    try:
        return int(datetime.fromisoformat(normalized).timestamp())
    except ValueError:
        return render_site.sort_timestamp_value(text)


def build_report(issues: list[DashboardQualityIssue]) -> dict[str, Any]:
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warn"]
    return {
        "summary": {"errors": len(errors), "warnings": len(warnings), "issues": len(issues)},
        "issues": [issue.as_dict() for issue in issues],
    }


def print_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print(f"Outbreak dashboard QA: errors={summary['errors']} warnings={summary['warnings']}")
    for issue in report["issues"]:
        marker = "ERROR" if issue["severity"] == "error" else "WARN"
        evidence = f" | {issue['evidence']}" if issue.get("evidence") else ""
        print(f"[{marker}] {issue['story_id']} {issue['metric']}: {issue['message']}{evidence}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate generated outbreak dashboard counts and story pages.")
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    parser.add_argument("--docs-root", type=Path, default=DEFAULT_DOCS_ROOT)
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        issues = run_quality_checks(snapshot_path=args.snapshot, docs_root=args.docs_root, overrides_path=args.overrides)
    except (FileNotFoundError, ValueError) as exc:
        issues = [DashboardQualityIssue("error", "snapshot", "load", str(exc))]
    report = build_report(issues)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_report(report)
    return 1 if report["summary"]["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
