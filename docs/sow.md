# Scope of Work

## 1. Problem Statement

Consulting Pauper decklists from MTGO tournaments is unnecessarily friction-heavy. Existing websites that publish decklists also serve articles, card promotions, and ads. A player interested only in browsing recent decklists must navigate through slow, cluttered pages with multiple clicks per deck.

## 2. Solution

**Merchant Scroll** is a single-purpose, static website that presents MTGO Pauper decklists in a TikTok-style vertical carousel. One deck fills the viewport at a time; the user scrolls (wheel, swipe, or arrow keys) to advance to the next deck. Decklists are ordered chronologically from most recent to oldest. Hovering (or tapping on mobile) a card name shows a preview image of the card.

The site is entirely static, hosted on GitHub Pages, and updated automatically every 2 hours via a GitHub Actions crawler that scrapes tournament data from MTGO.

## 3. Target Audience

Competitive and casual Pauper players who want to quickly browse recent tournament results without distractions.

## 4. Scope Boundaries

### In scope

- Pauper format only
- MTGO tournament decklists (Leagues, Challenges, Showcases, Preliminaries, and any other published event type)
- Automated data pipeline (crawl, enrich, deploy)
- Static frontend with card preview, search, color indicators, tournament badges, and interactive navigation

### Out of scope

- Other formats (Modern, Legacy, Standard, etc.)
- User accounts, comments, or social features
- Deck archetype classification or naming (e.g., labeling a deck as "Mono Red Aggro")
- Historical metagame analysis or statistics on the frontend
- Paper tournament data (only MTGO)

## 5. Architecture

### System components

| Component        | Technology                         | Runs on               |
|------------------|------------------------------------|-----------------------|
| Pipeline         | Python (orchestration)             | GitHub Actions (cron) |
| Crawler          | Python (requests, BeautifulSoup)   | GitHub Actions (cron) |
| Color enrichment | Python (Scryfall bulk data lookup) | GitHub Actions        |
| Frontend         | Static HTML, CSS, vanilla JS       | GitHub Pages          |
| Card images      | Scryfall API (client-side)         | User's browser        |

### Data flow

1. **GitHub Actions** triggers every 2 hours
2. **Pipeline** (`crawl.py`) orchestrates the full cycle:
   a. Downloads/caches Scryfall oracle data (refreshed once per day)
   b. Builds card color lookup table
   c. Discovers tournament URLs from MTGO
   d. Filters to Pauper-only URLs
   e. Skips tournaments already stored locally (deduplication by `site_name`)
   f. Crawls only new tournaments, with minification and color enrichment
   g. Rebuilds `assets/pauper/index.json` (sorted by date descending)
   h. Writes `info.json` with the current UTC timestamp
3. **GitHub Actions** commits and pushes any new/updated files
4. **GitHub Pages** automatically redeploys on push

### Key files

| File                              | Purpose                                               |
|-----------------------------------|-------------------------------------------------------|
| `crawl.py`                        | Entry point for the pipeline (what GitHub Actions runs)|
| `src/pipeline.py`                 | Orchestration: discover, filter, crawl, enrich, index  |
| `src/crawler.py`                  | MTGO page scraping and tournament data extraction      |
| `src/scryfall.py`                 | Scryfall bulk data download and card color lookup      |
| `src/utils.py`                    | Minification, date normalization, color enrichment     |
| `src/saver.py`                    | JSON file writing utility                              |
| `src/constants/`                  | Crawler headers, timeouts, regex patterns, format list |
| `index.html`                      | Frontend (single-file, inline JS)                      |
| `style.css`                       | Frontend styles                                        |
| `assets/pauper/raw/{site_name}.json` | Per-tournament data files                           |
| `assets/pauper/index.json`        | Tournament index (metadata + deck counts)              |
| `info.json`                       | Last update timestamp                                  |

## 6. Frontend

### 6.1 UX Model

The interface follows a **vertical carousel** pattern (TikTok-style):

- One decklist fills the available viewport at a time
- Scrolling (mouse wheel, touch swipe) or pressing arrow keys advances to the next or previous deck
- Scroll snaps to each deck — no partial views
- Decks are ordered chronologically: most recent tournament first, within each tournament ordered by player position/record
- Decks load lazily: tournament data is fetched on demand as the user scrolls forward

### 6.2 Interactive Navigation

A **persistent interactive breadcrumb** is always visible in the header, showing the user's current position:

```
Jun 5, 2026 ▾  ›  Pauper League ▾  ›  Deck 1 of 11 ▾
```

Each segment is a **clickable dropdown trigger**:

- **Date segment** (e.g., "Jun 5, 2026 ▾"): Opens a scrollable dropdown listing all available dates, with the event count per date. Selecting a date loads that day's first tournament and jumps to its first deck.
- **Tournament segment** (e.g., "Pauper League ▾"): Opens a dropdown listing all tournaments on the current date, with deck counts. Selecting a tournament loads it (if not already loaded) and jumps to its first deck.
- **Deck segment** (e.g., "Deck 1 of 11 ▾"): Opens a dropdown listing all players in the current tournament, with color pips. Selecting a player jumps directly to their deck.

The dropdowns auto-scroll to highlight the currently active item and close when the user clicks outside or navigates via scroll/keyboard.

When the user selects a tournament that hasn't been loaded yet, the pipeline lazily fetches it on demand before navigating.

There are no visual section dividers or headers between tournaments in the scroll flow — the breadcrumb is the sole orientation mechanism.

### 6.3 Deck Display

Each deck view shows:

- **Player name** and win/loss record (if available)
- **Main deck** organized by category: Creatures, Spells, Lands — each with a subtotal count
- **Sideboard** as a flat list
- **Deck color indicator** (see 6.4)
- **Tournament type badge** (see 6.5)

### 6.4 Deck Color Indicators

Each decklist displays a set of colored pips representing the deck's color identity, derived from the union of all card color identities across main deck and sideboard, **excluding lands**:

| Symbol | Color     | Display color |
|--------|-----------|---------------|
| W      | White     | Yellow        |
| U      | Blue      | Blue          |
| B      | Black     | Black         |
| R      | Red       | Red           |
| G      | Green     | Green         |
| C      | Colorless | Gray          |

A mono-red deck shows a single red pip. A three-color deck (e.g., Esper: WUB) shows yellow, blue, and black pips. The colorless (C) pip is shown only if the deck contains zero colored non-land cards.

Lands are excluded from color computation entirely. Cards that produce mana of various colors (e.g., Prophetic Prism) do not contribute those colors — only the card's own `color_identity` as defined by Scryfall is used.

Color data is computed during the crawl/enrichment step and stored in each decklist's JSON.

### 6.5 Tournament Type Badges

Each deck displays a small colored badge indicating the tournament type (e.g., "League", "Challenge", "Showcase", "Preliminary"). The badge label is derived from the tournament's `site_name` field by extracting the type keyword from the hyphenated name (e.g., `pauper-league-...` → "League"). Badge colors are mapped per type:

| Type        | Color  |
|-------------|--------|
| League      | Green  |
| Challenge   | Blue   |
| Showcase    | Purple |
| Preliminary | Orange |
| Premier     | Red    |
| Classic     | Brown  |

### 6.6 Card Preview

Hovering over a card name (desktop) or tapping it (mobile) displays a floating preview of the card image, fetched from the Scryfall API:

```
https://api.scryfall.com/cards/named?exact={card_name}&format=image&version=normal
```

The preview tooltip follows the cursor and repositions to stay within the viewport.

### 6.7 Player Search

A search input in the header filters the loaded decks by player name (case-insensitive substring match). Search is debounced at 200ms. Filtering operates on already-loaded data; it does not trigger additional fetches.

## 7. Data Pipeline

### 7.1 Data Source

All data is scraped from `https://www.mtgo.com/decklists`. Tournament data is embedded in the page as a JavaScript object assigned to `window.MTGO.decklists.data` and extracted via regex pattern matching. This is a **fragile** dependency: any change to MTGO's page structure will break the crawler.

### 7.2 Pipeline Orchestration

The pipeline is orchestrated by `src/pipeline.py` and invoked via `crawl.py`. A single run performs:

1. **Scryfall cache**: Download `oracle-cards.json` if not already cached (refreshed once per day)
2. **Color lookup**: Build a `card_name → color_identity` mapping from the cached oracle data
3. **Discovery**: Fetch the MTGO decklists page, extract all tournament URLs
4. **Pauper filter**: Keep only URLs containing `/pauper-`
5. **Deduplication**: Compare discovered `site_name` values against existing files in `assets/pauper/raw/` — skip any already stored
6. **Crawl new**: For each new tournament:
   a. Fetch the tournament page
   b. Extract the embedded JSON data via regex (`window.MTGO.decklists.data`)
   c. Parse the Python-literal string (replacing JS booleans)
   d. Minify: keep only player, card names, quantities, card types, and win/loss records
   e. Enrich: compute deck color identity from Scryfall data, excluding lands
   f. Save to `assets/pauper/raw/{site_name}.json`
7. **Index rebuild**: Regenerate `assets/pauper/index.json` from all raw files (sorted by `starttime` descending)
8. **Timestamp**: Write `info.json` with the current UTC datetime

If no new tournaments are found, steps 7-8 are skipped and no files are modified.

### 7.3 Color Enrichment

Deck color identity is derived using Scryfall's bulk data:

1. Download `oracle-cards.json` from Scryfall's bulk data endpoint (refreshed once per day, cached at `.cache/oracle-cards.json`)
2. Build a lookup table: `card_name → color_identity` (list of W/U/B/R/G). Split cards (e.g., "Fire // Ice") are indexed by both the full name and each face.
3. For each deck, compute the union of all card color identities across main deck and sideboard, **excluding cards with card type LAND**
4. Store the result as a `colors` array (e.g., `["U", "B"]`) on each decklist object

### 7.4 Storage Format

- **Per-tournament file**: `assets/pauper/raw/{site_name}.json` — contains full tournament metadata and all minified decklists with color data
- **Index file**: `assets/pauper/index.json` — array of tournament summaries (`site_name`, `starttime`, `deck_count`) sorted by date descending, used by the frontend to discover and lazily load tournaments
- **Info file**: `info.json` — contains `last_update` timestamp displayed in the frontend header

### 7.5 Scheduling

The crawler runs as a GitHub Actions workflow on a cron schedule (every 2 hours). The workflow:

1. Checks out the repository
2. Installs uv and Python dependencies
3. Runs `uv run crawl.py`
4. Commits and pushes any new/updated JSON files (if changes exist)
5. GitHub Pages automatically redeploys on push

## 8. Third-Party Dependencies

| Dependency         | Usage                             | Risk                                            |
|--------------------|-----------------------------------|-------------------------------------------------|
| MTGO (mtgo.com)    | Source of all tournament data     | Page structure changes break the crawler         |
| Scryfall API       | Card preview images (client-side) | Rate limits (10 req/s); API downtime             |
| Scryfall Bulk Data | Card color identity (build-time)  | Data format changes; download size (~80MB)       |
| GitHub Pages       | Static site hosting               | GitHub Pages limits (100GB bandwidth/month)      |
| GitHub Actions     | Crawler scheduling                | Action minutes quota; cron not guaranteed exact   |

## 9. Non-Functional Requirements

### 9.1 Performance

- The frontend is a single static HTML file with inline JavaScript — no build step, no framework
- Tournament data is loaded lazily (one tournament at a time, on demand)
- On-demand loading via breadcrumb navigation fetches specific tournaments without loading the full dataset
- Card images are loaded on hover/tap, not preloaded
- Target: first meaningful paint under 1 second on a 3G connection

### 9.2 SEO

- OpenGraph and Twitter Card meta tags for link previews
- JSON-LD structured data (WebSite schema)
- Canonical URL: `https://merchant-scroll.com/`
- Descriptive `<title>` and `<meta description>`

### 9.3 Analytics

- **Google Analytics** (G-FWXMHTS3R3) for traffic and user behavior
- **Microsoft Clarity** for session recordings and heatmaps

### 9.4 Mobile / Responsive

- Responsive layout via CSS media queries (breakpoint at 640px)
- Touch-friendly: swipe to navigate, tap for card preview
- Main deck and sideboard stack vertically on narrow screens
- Breadcrumb dropdowns resize for narrow viewports

### 9.5 Accessibility

- Keyboard navigation (arrow keys)
- Semantic HTML structure
- Sufficient color contrast (to be verified)

## 10. Risks and Mitigations

| Risk                                        | Impact | Mitigation                                                    |
|---------------------------------------------|--------|---------------------------------------------------------------|
| MTGO changes page structure                 | High   | Monitor crawler failures; add alerts to GitHub Actions        |
| MTGO rotates tournaments off the page       | Medium | 2-hour cron schedule minimizes the window; no backfill exists |
| Scryfall API downtime                       | Medium | Card previews degrade gracefully (broken image, no crash)     |
| GitHub Pages bandwidth limit hit            | Low    | Minified JSON keeps data small; images served by Scryfall     |
| Scryfall bulk data format changes           | Low    | Pin to known fields; add validation in enrichment step        |
| MTGO stops publishing decklists             | High   | No mitigation — the entire service depends on this data source|
| GitHub Actions cron delays or quota exceeded | Low    | Monitor action runs; keep pipeline fast (~30s per run)        |
