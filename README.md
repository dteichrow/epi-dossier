# The Pathogen Dispatch / Epi Dossier

Source-first infectious disease and epidemiology monitoring system for [The Edge of Epidemiology](https://dteichrow.github.io/).

This project collects, filters, scores, summarizes, and publishes public-health and infectious-disease signals into a local reader and a public static site. The goal is not to replace expert judgment. The goal is to make the first pass through noisy public-health information more structured, inspectable, and useful.

## What This Project Demonstrates

- source-driven collection from official public-health agencies, RSS feeds, HTML listing pages, and APIs;
- conservative summarization with explicit failure tolerance rather than invented certainty;
- deduplication, scoring, story grouping, disease reference pages, and timeline tracking;
- machine-readable JSON exports for downstream apps and static-site rendering;
- public HTML surfaces for daily briefings, outbreak monitoring, disease reference, and story pages;
- tests around source configuration, filtering, rendering, and public publish behavior.

For portfolio review, this repo is most useful as an example of building a small evidence pipeline: intake, cleaning, scoring, summarization, structured export, rendering, and publication.

## Why It Exists

Outbreak and public-health information arrives as a mess: official situation reports, state alerts, agency feeds, PubMed items, research notices, local news, and half-broken webpages. A human can read all of it, but the real bottleneck is remembering what changed, which sources are reliable, and how today’s signal fits into the longer disease story.

This project treats that as a data and evidence-translation problem:

1. collect candidate items from known source classes;
2. score and filter them conservatively;
3. group related items into durable stories and topics;
4. render briefings and reference pages;
5. export structured JSON so other tools can consume the same evidence state;
6. avoid publishing when upstream data or local state is not trustworthy.

## Core Outputs

The system generates:

- dated Markdown and HTML dossiers under `briefings/`;
- a local desktop reader under `Daily Dossiers/`;
- public static pages under `docs/`;
- machine-readable exports under `app_exports/`;
- disease reference sheets and story timelines;
- health/manifest files for automation and stale-site detection.

## Project Layout

```text
epi-dossier/
  config/        source lists, scoring terms, editorial settings
  src/           collection, parsing, scoring, summarization, rendering, publishing
  tests/         regression tests for source config, filtering, rendering, and publish behavior
  docs/          generated public static site
  app_exports/   generated JSON exports
  briefings/     dated dossier outputs
  data/          local SQLite state
  scripts/       publish and automation helpers
```

## Important Files

- `src/main.py`: canonical daily build entrypoint.
- `src/fetchers.py`: source retrieval and fallback behavior.
- `src/parsers.py`: parsing and normalization logic.
- `src/scoring.py`: item scoring and prioritization.
- `src/summarize.py`: conservative summaries and story framing.
- `src/render_markdown.py`: dossier rendering.
- `src/render_site.py`: public static-site rendering.
- `src/app_exports.py`: JSON export generation.
- `src/public_publish.py`: guarded public-publish wrapper.
- `config/sources.yml`: configured source inventory.
- `config/search_terms.yml`: monitored outbreak/disease/search terms.
- `tests/`: regression coverage for the above.

## Evidence And Safety Principles

This project is intentionally conservative:

- prefer official or source-proximate information when available;
- keep source URLs attached to downstream outputs;
- degrade gracefully when upstream pages fail;
- avoid treating generated summaries as facts without source support;
- preserve enough structured state to inspect what changed and why.

Those habits matter more than the specific disease list. The transferable workflow is evidence triage: gather messy source material, normalize it, rank it, summarize it, and publish only when the output can be inspected.

## Local Development

Use Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Dry run:

```bash
python -m src.main --dry-run
```

Generate a daily dossier and local reader:

```bash
python -m src.main
```

Build recent public site surfaces:

```bash
python -m src.site_build --days 7 --output-mode both --deploy-dir docs
```

Run tests:

```bash
pytest
```

## Operational Health

Use the repo doctor before publish work or after a failed automation run:

```bash
python scripts/repo_doctor.py
python scripts/repo_doctor.py --json
```

The operational runbook is in [OPERATIONS.md](OPERATIONS.md). It defines the source-of-truth files, publish boundary, stale-site triage path, generated-file policy, and manual live checks.

## Public Workflow

The project can publish generated `docs/` output to GitHub Pages, but the guarded publish path refuses to auto-publish when the repository has unsafe non-generated edits.

```bash
./scripts/publish_public_site.sh
```

The live public site is integrated into the broader Edge of Epidemiology umbrella site at:

- https://dteichrow.github.io/newsdesk/
- https://dteichrow.github.io/reference/
- https://dteichrow.github.io/stories/

Cloud publishing uses an explicit producer/consumer boundary. This repo publishes the Newsdesk artifact to its own `docs/` tree, then dispatches a `newsdesk_published` event to `dteichrow/dteichrow.github.io` when the `EOE_UMBRELLA_DISPATCH_TOKEN` secret is configured. The umbrella repo also pulls from `dteichrow/epi-dossier` on a schedule, so a missing local sibling checkout cannot strand the public site.

## Public Repo Hygiene

This repository is public. Keep the tracked surface limited to code, source configuration, tests, public documentation, and generated public `docs/` output.

Do not commit local job-search material, outreach queues, Gmail/message IDs, private operating notes, generated resumes, browser-control scripts, `.env` files, SQLite databases, logs, or one-off scratch output. The `.gitignore` intentionally blocks those local surfaces, especially `notes/`, `output/`, `tmp/`, local SQLite state, and session-specific automation scripts.

Before publishing from a dirty checkout, inspect exactly what would be staged:

```bash
git status --short
git diff --stat
git diff --cached --stat
```

If the checkout contains unrelated local work, prefer the guarded publisher or a clean temporary worktree from `origin/main` instead of committing from the messy working tree.

## Notes For Reviewers

This is a working personal research/publication system, not a packaged commercial product. The useful review target is the workflow: source intake, normalization, scoring, structured outputs, QA, and publication discipline.

The closest analogy in clinical evidence work is the front half of an evidence product: define the monitored domain, ingest imperfect real-world/public source material, structure it, check reliability, and produce an artifact that a reader can inspect rather than blindly trust.
