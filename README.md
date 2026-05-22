# The Pathogen Dispatch

Local Python project for a source-first infectious disease newsroom and research desk. The canonical morning build is `python -m src.main`, which writes the dated Markdown dossier requested in `briefings/YYYY-MM-DD_epi_dossier.md`.

It generates:

- a local desktop reader under `Daily Dossiers/`
- app-facing JSON exports under `app_exports/`
- a deployable static publication under `docs/` for GitHub Pages

The system is conservative, failure-tolerant, and built to keep writing useful surfaces even when some upstream sources degrade.

## Features

- source-driven collection from RSS, official HTML listing pages, and APIs
- official intake coverage for CDC, WHO, ECDC, FDA, USDA APHIS, and state health departments including California, New York, Florida, Texas, Washington, and Oregon
- conservative summaries with no invented claims
- SQLite tracking for seen items, stories, topics, and story timelines
- graceful failure and cache fallback when live sources wobble
- durable tracked outbreak files and disease reference sheets
- local HTML reader plus public multi-desk `docs/` site
- machine-readable exports for items, stories, topics, health, archive, and overnight summaries

## Project layout

```text
epi-dossier/
  README.md
  requirements.txt
  .gitignore
  config/
    editions.yml
    editorial.yml
    outbreak_reference.yml
    publishers.yml
    search_terms.yml
    sources.yml
    email.yml
  src/
    main.py
    site_build.py
    fetchers.py
    parsers.py
    scoring.py
    summarize.py
    dedupe.py
    render_markdown.py
    render_html.py
    render_site.py
    app_exports.py
    database.py
    utils.py
  data/
    dossier.sqlite
  app_exports/
    latest.json
    items.json
    stories.json
    story_pages.json
    topics.json
    reference.json
    archive.json
    health.json
    overnight_summary.json
    manifest.json
    deltas/
      <run-id>.json
  briefings/
    YYYY-MM-DD_epi_dossier.md
    YYYY-MM-DD_epi_dossier.html
  Daily Dossiers/
    latest.md
    latest.html
    index.html
    stories/
    reference/
    YYYY/
      MM/
        YYYY-MM-DD.md
        YYYY-MM-DD.html
  docs/
    index.html
    latest.html
    watch.html
    africa.html
    asia.html
    research.html
    official.html
    historical.html
    archive/index.html
    stories/
    reference/
    YYYY/
      MM/
        YYYY-MM-DD.html
    app_exports/
  automation/
    com.codex.epi-dossier.daily-morning.plist
    com.codex.epi-dossier.workday-heartbeat.plist
    com.codex.epi-dossier.overnight-build.plist
  logs/
  tests/
```

## Setup

```bash
cd "/Users/devinteichrow/Downloads/Work and Statistics/Blogs/epi-dossier"
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional email delivery uses a Gmail app password:

```bash
export EPI_DOSSIER_EMAIL_APP_PASSWORD="your-16-character-app-password"
```

Then set `config/email.yml`:

```yaml
email:
  enabled: true
```

## Core commands

Dry run:

```bash
python -m src.main --dry-run
```

Generate the daily Markdown dossier and local reader:

```bash
python -m src.main
python -m src.main --days 7
python -m src.main --date 2026-05-08
python -m src.main --backfill 7
```

Build the full site surfaces:

```bash
python -m src.site_build --days 7
python -m src.site_build --days 7 --output-mode web --deploy-dir docs
python -m src.site_build --days 7 --output-mode both --deploy-dir docs
```

Build, commit, and push the public site when generated `docs/` files changed:

```bash
./scripts/publish_public_site.sh
```

Launchd uses the wrapper around that script so it can run by absolute path and recover from old lock directories:

```bash
python src/public_publish.py --check
python src/public_publish.py
```

## CLI notes

`src.main`

- `--dry-run`: inspect candidates without writing final artifacts or marking items seen
- `--days N`: search window in days ending at target date. Default `7`
- `--date YYYY-MM-DD`: build a specific day
- `--backfill N`: build the previous `N` days

`src.site_build`

- `--days N`: search window in days ending at target date. Default `7`
- `--date YYYY-MM-DD`: build a specific day
- `--output-mode local|web|both`: choose whether to write local reader files, deployable `docs/` files, or both
- `--deploy-dir docs`: choose the public output directory
- `--site-base-url /`: reserved for future non-root hosting layouts

`src.main` is the canonical entrypoint for the morning dossier requirement. `src.site_build` is the broader site/publication build when you also want the full local reader and `docs/` web surfaces regenerated in one pass.

## Output surfaces

Local desktop surfaces:

- `Daily Dossiers/latest.md`
- `Daily Dossiers/latest.html`
- `Daily Dossiers/index.html`
- `Daily Dossiers/stories/<story-id>-<slug>.html`
- `Daily Dossiers/reference/<disease-slug>.html`
- `Daily Dossiers/YYYY/MM/YYYY-MM-DD.html`

Legacy dated artifacts:

- `briefings/YYYY-MM-DD_epi_dossier.md`
- `briefings/YYYY-MM-DD_epi_dossier.html`

Public web output:

- `docs/index.html` for the public landing page
- `docs/watch.html`, `docs/africa.html`, `docs/asia.html`, `docs/research.html`, `docs/official.html`, `docs/historical.html`
- `docs/archive/index.html`
- `docs/stories/<story-id>-<slug>.html`
- `docs/reference/<disease-slug>.html`
- `docs/YYYY/MM/YYYY-MM-DD.html`
- `docs/app_exports/*.json`

Machine-readable local exports:

- `app_exports/latest.json`
- `app_exports/items.json`
- `app_exports/stories.json`
- `app_exports/story_pages.json`
- `app_exports/topics.json`
- `app_exports/reference.json`
- `app_exports/archive.json`
- `app_exports/health.json`
- `app_exports/overnight_summary.json`
- `app_exports/deltas/<run-id>.json`

## Local vs public workflow

The project now treats local and public output as parallel surfaces from the same run.

- `Daily Dossiers/latest.html` is the desktop reader
- `docs/index.html` is the public landing page
- `docs/latest.html` is the web-safe public copy of the briefing view
- story pages and disease sheets are written to both local and public trees
- public exports use web-safe relative paths instead of `file:///` URLs
- the live GitHub Pages site updates only after a newer `docs/` build has been pushed
- `scripts/publish_public_site.sh` is the guarded public publish path; it rebuilds the site, refuses to auto-publish if non-generated repo files are dirty, and pushes only generated `docs/` changes
- `src/public_publish.py` is the automation-safe wrapper around that script; it pins the repo path, clears old empty publish locks, publishes from a clean temporary worktree when the local checkout has non-generated edits, uses checked-out Git credentials when no local SSH key exists, and terminates stuck runs after the configured timeout
- `.github/workflows/newsdesk-public-publish.yml` is the primary cloud scheduler; it runs hourly from GitHub Actions so the public Newsdesk does not depend on the laptop being awake
- `src/public_publish_watchdog.py` checks the live public manifest every 15 minutes and invokes the wrapper if the site is stale or unreachable
- public pages poll `docs/app_exports/manifest.json` and show a refresh prompt when a newer run has landed while a reader is still on the page

## Scheduling

If email delivery matters, make sure `EPI_DOSSIER_EMAIL_APP_PASSWORD` exists in the scheduled environment.

### Primary cloud publish

Repo file:

- `.github/workflows/newsdesk-public-publish.yml`

Purpose:

- runs from GitHub Actions, not the local Mac
- publishes hourly at minute `:17` UTC and can also be started manually with `workflow_dispatch`
- checks the live public manifest at `:05`, `:20`, `:35`, and `:50` UTC and repairs the publish if the site is stale
- checks out `dteichrow/epi-dossier` and `dteichrow/dteichrow.github.io` side by side
- creates fresh virtualenvs for both repos
- runs `python src/public_publish.py` for scheduled and manual publishes
- runs `python src/public_publish_watchdog.py` for cloud-side stale checks
- pushes generated Newsdesk output back to both repos through the same guarded publish path used locally

Required GitHub secret:

- `NEWSDESK_PUBLISH_TOKEN`

The token should be a fine-grained GitHub token with repository access to:

- `dteichrow/epi-dossier`
- `dteichrow/dteichrow.github.io`

Required permission:

- `Contents: Read and write`

The workflow deliberately fails early if this secret is missing, because the default `GITHUB_TOKEN` can write to `epi-dossier` but cannot safely publish the umbrella GitHub Pages repository.

### Cron

Run the morning dossier every day at 6:30 AM local time:

```bash
crontab -e
```

Add:

```cron
30 6 * * * cd "/Users/devinteichrow/Downloads/Work and Statistics/Blogs/epi-dossier" && "/Users/devinteichrow/Downloads/Work and Statistics/Blogs/epi-dossier/.venv/bin/python" -m src.main >> "/Users/devinteichrow/Downloads/Work and Statistics/Blogs/epi-dossier/logs/daily-morning.out.log" 2>> "/Users/devinteichrow/Downloads/Work and Statistics/Blogs/epi-dossier/logs/daily-morning.err.log"
```

This schedules the dated Markdown dossier build at `06:30` every day and appends stdout/stderr to the morning log files.

### Daily morning launchd job

Repo file:

- `automation/com.codex.epi-dossier.daily-morning.plist`

Purpose:

- runs `python -m src.main`
- writes the dated local dossier plus refreshed `Daily Dossiers/latest.*`
- starts at `06:30` local time every day

Install it:

```bash
cp automation/com.codex.epi-dossier.daily-morning.plist ~/Library/LaunchAgents/com.codex.epi-dossier.daily-morning.plist
launchctl unload ~/Library/LaunchAgents/com.codex.epi-dossier.daily-morning.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.codex.epi-dossier.daily-morning.plist
launchctl start com.codex.epi-dossier.daily-morning
```

This is the conservative local-first scheduler described in the original brief. It does not push anything to GitHub.

### Workday heartbeat launchd job

Repo file:

- `automation/com.codex.epi-dossier.workday-heartbeat.plist`

Purpose:

- runs `python src/public_publish.py`
- acts as the canonical live-site updater
- rebuilds and republishes the public site hourly at `:15`
- uses the same guarded publish lock as the overnight job, so overlapping triggers exit cleanly

Install it:

```bash
cp automation/com.codex.epi-dossier.workday-heartbeat.plist ~/Library/LaunchAgents/com.codex.epi-dossier.workday-heartbeat.plist
launchctl unload ~/Library/LaunchAgents/com.codex.epi-dossier.workday-heartbeat.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.codex.epi-dossier.workday-heartbeat.plist
launchctl start com.codex.epi-dossier.workday-heartbeat
```

### Overnight build launchd job

Repo file:

- `automation/com.codex.epi-dossier.overnight-build.plist`

Purpose:

- runs `python src/public_publish.py`
- rebuilds and republishes the public site hourly at `:15`
- keeps the historical launchd label, but no longer depends on a brittle relative-path shell invocation

### Public publish watchdog launchd job

Repo file:

- `automation/com.codex.epi-dossier.public-publish-watchdog.plist`

Purpose:

- runs `python src/public_publish_watchdog.py`
- checks the live public manifest at `:05`, `:20`, `:35`, and `:50`
- invokes the guarded public publisher if the live site is older than 90 minutes or the manifest cannot be fetched

## GitHub Pages

The public site is designed for GitHub Pages from `docs/`.

Typical workflow:

```bash
python -m src.site_build --days 7 --output-mode both --deploy-dir docs
```

Then publish the repository and configure GitHub Pages to serve from:

- branch: your default branch
- folder: `/docs`

Public landing page:

- `docs/index.html`

Local landing page:

- `Daily Dossiers/latest.html`

## Source policy

- prefer RSS, official APIs, and official listing pages
- keep summaries grounded in source metadata and extracted source text
- do not invent canonical article URLs when wrapper resolution fails
- preserve prior good reader surfaces when degraded runs cannot confidently improve them
