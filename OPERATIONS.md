# Epi Dossier Operations

This repository produces the Newsdesk surfaces for The Edge of Epidemiology. Treat it as the upstream outbreak-monitoring and public-health signal pipeline, not as the final umbrella-site deployment system.

## Source Of Truth

- `config/sources.yml`: monitored source inventory.
- `config/search_terms.yml`: disease, outbreak, and topic routing terms.
- `src/main.py`: daily collection and dossier build entrypoint.
- `src/site_build.py`: generated Newsdesk HTML and JSON exports.
- `src/public_publish.py`: guarded publish wrapper.
- `docs/`: generated public Newsdesk output committed by the publisher.
- `docs/app_exports/latest.json`: public machine-readable latest item export.
- `story_items` inside `docs/app_exports/latest.json`: retained evidence items needed to reproduce current story pages even when an item is no longer in the newest feed window.
- `docs/stories/`: generated story-monitor pages.

## Normal Publish Path

Use the guarded publisher for public refreshes:

```bash
python src/public_publish.py --check
python src/public_publish.py
```

The GitHub Actions workflow `.github/workflows/newsdesk-public-publish.yml` runs the same guarded publisher on schedule, manual dispatch, and relevant pushes.

Important boundary: this repository is the Newsdesk producer. It commits generated `docs/` output here, then asks `dteichrow/dteichrow.github.io` to import that output through an explicit `newsdesk_published` repository dispatch when `EOE_UMBRELLA_DISPATCH_TOKEN` is configured. The umbrella repo also runs a scheduled pull import, so the live site does not depend on a sibling checkout being present on the runner.

The old local sibling-repo path remains a convenience for a Mac checkout that has both repositories side by side, but it is no longer the primary cloud publishing contract.

## Routine Health Check

Run the local repo health check before publish work:

```bash
python scripts/repo_doctor.py
python scripts/repo_doctor.py --json
```

Use live checks when diagnosing public drift:

```bash
python scripts/repo_doctor.py --check-live
```

Run the outbreak dashboard QA directly when a story monitor count looks wrong:

```bash
python -m src.outbreak_dashboard_quality
python -m src.outbreak_dashboard_quality --json
```

This check is also part of `python scripts/repo_doctor.py --json`, `python src/public_publish.py --check`, and the public site build. It blocks release when a generated story page does not match the current snapshot policy, when a dashboard override is not traceable, or when a dashboard value is lower than a newer authority-citing count in the same story evidence.

## Failure Triage

Start with these surfaces, in this order:

1. GitHub Actions run log for `Newsdesk public publish`.
2. `python src/public_publish.py --check`.
3. `git status --short --branch`.
4. `docs/app_exports/latest.json`.
5. The affected generated page under `docs/stories/` or `docs/reference/`.
6. Live public route on `https://dteichrow.github.io/newsdesk/`.

If the live site is stale but local `docs/` is current, the problem is deployment, not source collection. If local `docs/` is stale, inspect source collection, scoring, story grouping, and export generation.

## Generated File Policy

Generated public outputs under `docs/` are intentionally tracked because they are the published Newsdesk artifact. Local-only state should not be tracked:

- SQLite databases.
- `.env` files.
- logs.
- `tmp/` and `output/`.
- private notes.
- browser or mailbox artifacts.

Before staging anything, inspect the exact set:

```bash
git status --short
git diff --stat
git diff --cached --stat
```

## Dirty Checkout Policy

If the local checkout contains unrelated work, publish from a clean temporary clone or worktree based on `origin/main`. Do not mix operational fixes with generated news output unless that is the point of the commit.

## Manual Verification

After a publish, verify:

```text
https://dteichrow.github.io/newsdesk/
https://dteichrow.github.io/newsdesk/app_exports/latest.json
https://dteichrow.github.io/newsdesk/stories/story_56666e9c6c86e976-ebola-virus-disease.html
```

For outbreak pages, compare the top dashboard against the newest supported item in the feed and source links. If counts differ, label the dashboard as unknown, preliminary, or stale rather than presenting unsupported precision.

## Outbreak Dashboard Count Policy

- Official surveillance reports remain the preferred source for cleaned counts.
- Authority-citing public reports can update the dashboard when the text explicitly ties the number to a ministry, government data, WHO, CDC, ECDC, Africa CDC, or equivalent public-health authority.
- Metadata-only or aggregator-only count headlines do not become dashboard counts unless they pass the authority-citing rule or are curated in `config/outbreak_dashboard_overrides.yml`.
- Overrides must include `source_name`, `source_url`, `source_status`, `as_of`, a numeric value, and a note for each overridden metric.
- If a newer authority-citing count exceeds an override or rendered dashboard value, `src.outbreak_dashboard_quality` fails the build.
- The comparison uses the selected metric's source date. A superseded override's date must not be attached to a newly selected report; a later report can revise a total downward.
- Counts explicitly assigned to a named province, district, county, state, city, or health zone are withheld from broader topic dashboards unless that jurisdiction is named in the topic. This conservative text check does not establish complete geographic comparability; inspect the source before treating a media figure as a surveillance total.
- Preserve lower-bound qualifiers and distinguish cumulative counts from reporting-period additions, including paired case/death increments introduced by “a total of.”
- If a source refresh is degraded, the public Newsdesk home shows a source-health notice and the exported `health.json` carries the affected source list.

### October 20, 2026 publishing regression

Four consecutive public-publish runs failed after rendering the Ebola dashboard. A fresh collection reproduced the failure: an October 18 AP report carried by [SCMP](https://www.scmp.com/news/world/africa/article/3371328/dr-congos-fast-moving-ebola-outbreak-spreads-eighth-province) contained both outbreak-wide totals and two cases/one death in Nord-Ubangi province. The extractor recognized “has recorded” for the provincial figures but missed “authorities have recorded” for the broader totals. The recency selector then promoted the provincial figures. Separately, QA dated that selection using the superseded August override, producing misleading stale-count errors.

The repair recognizes the plural auxiliary, excludes explicitly narrower geographic counts from broad dashboards, carries the selected source date into QA, and includes comparison evidence in build failures. A paired-increment regression found during the replay is also covered. The failed collection was replayed without refetching: all six generated story pages passed dashboard QA. Regression tests cover local counts, qualified totals, paired increments, downward revisions, and genuinely stale selections. The gate remains blocking; no outbreak counts were manually overwritten.

## Recovery

- Re-run the failed workflow manually only after identifying whether the failure was source, build, publish, or Pages deployment.
- If a workflow created a bad generated commit, prefer `git revert` over history rewriting.
- If upstream source collection degraded, skip publication rather than overwriting a current public site with stale output.
