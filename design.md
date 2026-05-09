# The Patogen Dispatch Design Specification

## Summary
This document defines the visual redesign for The Patogen Dispatch as a premium infectious disease newsroom and intelligence publication. It is written for direct implementation against the current static HTML architecture, with the primary rendering surfaces in `src/render_html.py` and `src/render_site.py`.

The redesign target is not a generic blog and not an analytics dashboard. It should feel like a specialist editorial product for reporters, editors, and public-health desks: fast to scan, visually disciplined, strongly hierarchical, and clearly organized by page role.

The design direction is locked to:
- Visual mode: `Editorial Desk`
- Site structure: `Hybrid Multi-Page`

The current main problem is not lack of features. The site already has switching, search, archive browsing, story pages, and reference pages. The problem is presentation: too many sections use nearly identical panel and card treatments, vertical drag remains high, and the reader still behaves like a polished long memo rather than a designed publication surface.

## Design Intent
### Core framing
- Treat the site as an `infectious disease newsroom / intelligence publication`.
- Prioritize editorial hierarchy over decorative flourish.
- Keep the tone visually serious, restrained, and source-first.
- Make the page useful in the first five seconds for a repeat morning reader.

### Anti-goals
- No generic dashboard language.
- No oversized hero or banner that consumes attention without adding utility.
- No single repeated “box of cards” rhythm from top to bottom.
- No design that depends on a framework migration.
- No visual treatment that hides sourcing, timestamps, or story/reference structure.

## Page Roles
The system should treat each HTML output as a different publication surface, not one template with swapped content.

### 1. `latest.html`
Purpose:
- The daily front page.
- Fastest route to “what changed today.”
- Strongest editorial hierarchy in the system.

Primary visual priorities:
- major story rail
- lead briefing hierarchy
- clear separation between today’s reporting and evergreen reference
- low-friction navigation into story files, reference pages, and archive

### 2. `stories/<story-id>.html`
Purpose:
- Durable live outbreak file.
- A page a reporter could keep open throughout the day.

Primary visual priorities:
- timeline-first reading
- strong separation of `official sources` and `publisher coverage`
- visible “what changed” state
- clear path back to `latest.html`

### 3. `reference/<disease>.html`
Purpose:
- Evergreen disease intelligence sheet.
- Field-guide layer for agent, transmission, severity, diagnostics, and related outbreaks.

Primary visual priorities:
- background context over urgency
- stable, library-like visual language
- visible links back to active story files

### 4. Archive and index pages
Purpose:
- Retrieval and browsing.
- Backfile navigation without overwhelming the current briefing.

Primary visual priorities:
- clarity and density
- less hero emphasis
- strong year/month/day browseability

## Information Architecture
### `latest.html` target structure
The front page should be organized in this order:

1. Masthead and desk controls
2. Lead story rail
3. Morning briefing strip
4. Tracking section
5. Regional watch
6. Reference and papers zone
7. Archive / retrieval footer zone

This replaces the current feeling of “hero, intro, panel, panel, panel” with a clearer editorial progression from urgent to durable.

### Required persistence across pages
- `latest.html` remains the main entrypoint.
- Story pages remain the main durable outbreak files.
- Reference pages remain the evergreen knowledge base.
- Archive pages remain accessible from the main reader, not buried.

## Layout System
### Three visual densities
Replace the current repeated boxed-panel rhythm with three explicit densities:

#### Feature modules
Use for:
- masthead
- lead story rail
- dominant lead item in briefing
- lead live story on story pages

Visual characteristics:
- more space
- stronger type hierarchy
- fewer but larger elements
- stronger contrast against background

Should not be used for:
- papers
- archive rows
- compact reading lists

#### Standard report modules
Use for:
- tracked story clusters
- regional watch blocks
- topic clusters
- standard reference cards

Visual characteristics:
- medium padding
- clear metadata rows
- structured but not oversized

Should not be used for:
- utility lists
- archive links
- minor readings

#### Compact utility modules
Use for:
- other notable readings
- papers worth saving
- archive rows
- side-library and secondary navigation items

Visual characteristics:
- tighter spacing
- smaller typography
- reduced decoration
- more items visible above the fold

Should not be used for:
- lead stories
- outbreak files
- major editorial summaries

### Desktop layout
Adopt a stronger asymmetric composition:
- Main column: approximately 1.6x to 1.9x the side column.
- Lead rail should span full width near the top.
- Briefing should place the dominant lead item in the main column and compact supporting items in an adjacent or subordinate grid.
- Reference and archive surfaces should visually read as library/retrieval zones, not more headline zones.

### Mobile layout
Do not simply collapse desktop into a generic one-column stack.

Required mobile behavior:
- masthead compresses aggressively
- lead story rail becomes a swipe-free stacked priority sequence
- dominant lead item stays visually dominant
- utility modules collapse into tighter list forms
- archive stays browseable without multiple open accordions filling the page

## Section-by-Section Changes
### Masthead and desk controls
Current issue:
- hero, banner, search, and sticky view shell together create too much top-of-page weight

Required changes:
- reduce masthead vertical height
- demote banner art beneath information hierarchy
- fold freshness, date, and search into a tighter desk-control band
- keep the sticky desk switcher, but visually integrate it with the masthead system instead of treating it as a second independent strip

### Lead story rail
Add a new lead rail immediately below desk controls.

Behavior:
- surface 2 to 4 top active story files
- first card is clearly dominant
- remaining cards are secondary but still editorial, not tiny pills

Source of content:
- derive from current `story_records`, sorted by urgency/relevance/current movement

### Morning briefing strip
Current issue:
- `Highest Priority Items` reads like another vertical card stack

Required changes:
- convert the section into an editorial lead grid
- first item becomes a `lead story card`
- next 2 to 4 items become `secondary lead cards`
- `Executive Scan` becomes a tighter, more newspaper-like summary strip rather than a standalone block competing equally with the lead items

### Tracking section
Current issue:
- `Major Story Files`, `Ongoing Stories`, and `Major Topics` use similar card rhythms

Required changes:
- make `Major Story Files` a high-contrast live desk rail
- make `Ongoing Stories And What Changed` more timeline-oriented
- visually demote `Major Topics` into a structured analysis sidebar

### Regional watch
Current issue:
- region cards are useful but visually blended into everything else

Required changes:
- give regional watch a distinct atlas/intelligence-board tone
- emphasize geography and setting badges over article-like card rhythm
- make rural/local signal markers more legible without looking alarmist

### Reference and papers zone
Current issue:
- `Reference Desk`, `Last Major Outbreaks On File`, and `Papers Worth Saving` are too visually similar

Required changes:
- treat `Reference Desk` as a side library rail
- treat `Last Major Outbreaks On File` as a field-guide grid
- treat `Papers Worth Saving` as compact scholarly citations, not feature cards
- keep `Historical Epi / Weird Corner` clearly separate as a specialty module

### Archive / retrieval footer zone
Current issue:
- archive exists, but still feels like utility bolted onto the bottom

Required changes:
- move archive into a deliberately calmer retrieval zone
- reduce decorative weight
- make year/month/day navigation feel like a backfile, not like collapsible leftovers
- keep `Open latest briefing` visible but subordinate to the archive structure

## Component System
The redesign should use explicit component roles instead of styling everything as a generic card.

### Masthead
Purpose:
- define brand, desk identity, and freshness

Visual weight:
- high

Typical content:
- publication title
- section label
- freshness / time state
- compact desk controls

Do not use for:
- long explanatory copy

### Top navigation / desk switcher
Purpose:
- switch between briefing, tracking, reference, archive

Visual weight:
- medium

Typical content:
- 4 persistent desk tabs
- clear active state

Do not use for:
- filter chips
- source badges

### Lead story card
Purpose:
- anchor the top story or dominant outbreak development

Visual weight:
- highest card weight

Typical content length:
- 1 headline
- 1 short dek
- 1 compact metadata row

Do not use for:
- reference content
- minor follow-up links

### Secondary story card
Purpose:
- support the lead rail and top briefing

Visual weight:
- medium-high

Do not use for:
- archive items
- papers

### Topic cluster card
Purpose:
- summarize multi-item topic clusters

Visual weight:
- medium

Should include:
- item count
- source count
- official count
- expansion affordance

Do not use for:
- lead stories

### Compact reading card
Purpose:
- secondary links and short items

Visual weight:
- low

Should be visually compressed.

### Reference card
Purpose:
- disease sheet entrypoint or outbreak reference entry

Visual weight:
- medium

Should emphasize:
- pathogen
- transmission
- reference role

Do not style like a breaking-news card.

### Archive row
Purpose:
- retrieve dated entries quickly

Visual weight:
- low

Should optimize for scan speed, not flair.

### Metadata badge system
Purpose:
- communicate source type, confidence, region, and setting

Required badge groups:
- source confidence
- source type
- region
- local/rural signal
- access state when relevant

Badge behavior:
- keep concise
- avoid decorative overload
- stack only when space is constrained

### Timeline row
Purpose:
- story-page update chronology

Visual weight:
- medium

Should emphasize:
- timestamp
- what changed
- item/source counts

## Typography
### Typeface roles
- Display serif:
  - page titles
  - lead story headlines
  - major editorial moments
- Sans family:
  - navigation
  - metadata
  - badges
  - utility text

### Hierarchy
Use a fixed, repeatable scale:
- Page title
- Section title
- Lead card headline
- Standard card headline
- Compact item title
- Metadata / eyebrow / caption

### Usage rules
- Major headlines should not share the same size treatment as standard cards.
- Metadata should default inline for compact modules and stacked only on feature modules.
- Explanatory copy should be short and sparse; the page should not repeatedly explain itself.

## Color and Tokens
### Core tokens
- Primary ink / navy
- Accent blue
- Signal gold
- Muted utility gray-blue
- Paper / background warm off-white

### Color rules
- Use severity/status colors only when semantically justified.
- Do not let yellow/gold become a second accent everywhere.
- Keep reference surfaces calmer than live story surfaces.
- Keep archive surfaces lowest-contrast in the hierarchy, but still readable.

## Interaction and Navigation
### Search
- Keep global search.
- Search must remain able to expose matching content across briefing, tracking, reference, and archive.
- Search UI should visually read as a desk tool, not as a decorative hero widget.

### View switching
- Keep desk-level switching.
- Add a stronger active state and “you are here” language or visual cue.
- Make the switcher feel like section navigation, not pills floating above content.

### Linking rules
- Lead and secondary story cards link to story pages.
- Reference cards link to reference pages.
- Archive rows link to dated dossier pages.
- Source links within items continue to link outward to the original reporting or official source.

### Cross-page behavior
- Story pages must always expose a clear path back to `latest.html`.
- Reference pages must always expose related active story files when available.
- Archive pages must remain browseable by year/month/day without visual clutter or deeply nested navigation.

## Current Renderer Mapping
This section is implementation guidance tied to current code.

### `src/render_html.py`
The redesign should regroup and visually demote or elevate these current sections:

Elevate:
- `major-story-files`
- `highest-priority`
- `story-updates`
- `reference-desk-rail`

Demote or compress:
- repeated `view-intro` blocks
- oversized banner treatment
- `other-readings`
- `papers-worth-saving`
- archive explanatory utility cards

Rework structurally:
- current `.hero`
- current `.view-shell`
- current `.panel-grid` and `.layout`
- current repeated grid family: `.story-grid`, `.topic-grid`, `.priority-grid`, `.compact-grid`, `.paper-grid`, `.historical-grid`, `.region-grid`, `.reference-grid`

The redesign should avoid simply adding more CSS on top of the current structure if the section grouping remains wrong. A controlled refactor of the render template is preferred over incremental drift.

### `src/render_site.py`
Shared styling should be aligned across:
- story-page masthead
- reference-page masthead
- card vocabulary
- timeline rows
- archive/index surface

Story and reference pages should feel like part of the same publication system, not like separate mini-sites.

## What Should Be Removed or Simplified
Likely removals or simplifications:
- oversized hero/banner footprint
- repeated boxed intros before every view
- too many visually equivalent card types
- chip rows that feel decorative rather than operational
- redundant explanatory blurbs once the user already understands the page model

## What Must Remain
These are product-critical and should survive redesign:
- search
- view switching
- archive browsing
- story/reference crosslinks
- source-first metadata
- freshness / generated-at cues

## Phased Rollout
### Phase 1
- Restructure `latest.html`
- Introduce feature / standard / compact densities
- Add lead story rail and editorial lead grid

### Phase 2
- Align story and reference page styling with the new system
- Make story pages feel like live desk files
- Make reference pages feel like a field-guide library

### Phase 3
- Refine archive and retrieval surface
- Improve backfile legibility and reduce archive clutter

### Phase 4
- Polish iconography, logo, and banner treatment after hierarchy and navigation are stable

## Acceptance Criteria
The redesign is successful when:
- the front page no longer feels like one long repeated card stack
- the top 2 to 4 stories are visually obvious within a few seconds
- briefing, tracking, reference, and archive views feel distinct
- story pages feel like durable outbreak files rather than homepage copies
- reference pages feel like a field guide, not another feed
- mobile preserves hierarchy and scanability
- the visual result feels closer to a premium specialist publication than a personal dashboard

## Implementation Defaults
- Assume the current static HTML pipeline stays in place.
- Assume no framework migration.
- Assume branding can evolve later, but hierarchy and structure must be solved first.
- Assume the redesign should preserve auditability and source visibility over ornamental polish.
