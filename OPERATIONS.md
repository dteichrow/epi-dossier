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
- `docs/stories/`: generated story-monitor pages.

## Normal Publish Path

Use the guarded publisher for public refreshes:

```bash
python src/public_publish.py --check
python src/public_publish.py
```

The GitHub Actions workflow `.github/workflows/newsdesk-public-publish.yml` runs the same guarded publisher on schedule, manual dispatch, and relevant pushes.

Important boundary: this repository can generate and publish its own Newsdesk mirror. A full umbrella-site refresh depends on the public site repository being available to the publishing process. Do not assume this workflow alone updated every public route on `dteichrow.github.io`.

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

## Recovery

- Re-run the failed workflow manually only after identifying whether the failure was source, build, publish, or Pages deployment.
- If a workflow created a bad generated commit, prefer `git revert` over history rewriting.
- If upstream source collection degraded, skip publication rather than overwriting a current public site with stale output.
