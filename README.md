# The Pathogen Dispatch

Local Python project for a source-first infectious disease newsroom and research desk. The canonical morning build is `python -m src.main`, which writes the dated Markdown dossier requested in `briefings/YYYY-MM-DD_epi_dossier.md`.

It generates:

- a local desktop reader under `Daily Dossiers/`
- app-facing JSON exports under `app_exports/`
- a deployable static publication under `docs/` for GitHub Pages

The system is conservative, failure-tolerant, and built to keep writing useful surfaces even when some upstream sources degrade.

## Features

- source-driven collection from RSS, official HTML listing pages, and APIs
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

## Scheduling

If email delivery matters, make sure `EPI_DOSSIER_EMAIL_APP_PASSWORD` exists in the scheduled environment.

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
- writes `briefings/YYYY-MM-DD_epi_dossier.md` and `briefings/YYYY-MM-DD_epi_dossier.html`
- refreshes `Daily Dossiers/latest.md` and `Daily Dossiers/latest.html`
- starts at `06:30` local time every day

Install it:

```bash
cp automation/com.codex.epi-dossier.daily-morning.plist ~/Library/LaunchAgents/com.codex.epi-dossier.daily-morning.plist
launchctl unload ~/Library/LaunchAgents/com.codex.epi-dossier.daily-morning.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.codex.epi-dossier.daily-morning.plist
launchctl start com.codex.epi-dossier.daily-morning
```

### Workday heartbeat

Repo file:

- `automation/com.codex.epi-dossier.workday-heartbeat.plist`

Purpose:

- runs the full site builder during the workday
- keeps local reader surfaces current

### Overnight iteration

Repo file:

- `automation/com.codex.epi-dossier.overnight-build.plist`

Purpose:

- runs the full site builder
- writes both local and `docs/` surfaces
- refreshes hourly from `22:00` through `06:00`

Program:

```bash
python -m src.site_build --days 7 --output-mode both --deploy-dir docs
```

### launchd install

Install a plist into `~/Library/LaunchAgents/`, then reload:

```bash
cp automation/com.codex.epi-dossier.overnight-build.plist ~/Library/LaunchAgents/com.codex.epi-dossier.overnight-build.plist
launchctl unload ~/Library/LaunchAgents/com.codex.epi-dossier.overnight-build.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.codex.epi-dossier.overnight-build.plist
launchctl start com.codex.epi-dossier.overnight-build
```

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
