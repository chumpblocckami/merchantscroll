# Scope of Work

## 1. Problem Statement

Consulting Pauper decklists from MTGO tournaments is unnecessarily friction-heavy. Existing websites that publish decklists also serve articles, card promotions, and ads. A player interested only in browsing recent decklists must navigate through slow, cluttered pages with multiple clicks per deck.

## 2. Solution

**Merchant Scroll** is a single-purpose, static website that presents MTGO Pauper decklists in a TikTok-style vertical carousel. One deck fills the viewport at a time; the user scrolls (wheel, swipe, or arrow keys) to advance to the next deck. Decklists are ordered chronologically from most recent to oldest. Hovering (or tapping on mobile) a card name shows a preview image of the card.

The site is entirely static, hosted on GitHub Pages, and updated automatically every hour via a GitHub Actions crawler that scrapes tournament data from MTGO.

## 3. Target Audience

Competitive and casual Pauper players who want to quickly browse recent tournament results without distractions.

## 4. Scope Boundaries

### In scope

- Pauper format only
- MTGO tournament decklists (Leagues, Challenges, Showcases, Preliminaries, and any other published event type)
- Automated data pipeline (crawl, enrich, deploy)
- Static frontend with card preview, color indicators, tournament badges, and interactive navigation
- Deck archetype classification and naming (e.g., labeling a deck as "Mono Red Kuldotha")
- Metagame breakdown on the frontend: archetype presence per tournament, per day, and over a timespan

### Out of scope

- Other formats (Modern, Legacy, Standard, etc.)
- User accounts, comments, or social features
- Paper tournament data (only MTGO)
- Player search (planned for a future iteration)

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

1. **GitHub Actions** triggers every hour
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
| `src/utils.py`                    | Minification, date normalization, color & results enrichment |
| `src/saver.py`                    | JSON file writing utility                              |
| `src/constants/`                  | Crawler headers, timeouts, regex patterns, format list |
| `index.html`                      | Frontend (single-file, inline JS)                      |
| `style.css`                       | Frontend styles                                        |
| `assets/pauper/raw/{site_name}.json` | Per-tournament data files                           |
| `assets/pauper/index.json`        | Tournament index (metadata + deck counts)              |
| `assets/pauper/players.json`      | Player-to-tournament lookup (reserved for future search)|
| `src/meta_stats.py`               | Per-event archetype counts for the metagame overview    |
| `assets/pauper/meta/timeline.json`| Metagame timeline (archetype counts per event)          |
| `info.json`                       | Last update timestamp                                  |

## 6. Frontend

### 6.1 Visual Design

The frontend uses a **dark theme** optimized for night and tournament-side browsing:

- Near-black background (`#0f0f0f`), dark surfaces (`#1a1a1a`)
- Light text hierarchy (`#f0f0f0` primary, `#bbb` secondary, `#555` tertiary)
- Blue accent (`#4a9eff`) for links, active breadcrumb, and progress indicator
- No footer — all vertical space is dedicated to deck content
- Compact 2-line header: title + meta on line 1, breadcrumb on line 2

### 6.2 UX Model

The interface follows a **vertical carousel** pattern (TikTok-style):

- One decklist fills the available viewport at a time
- Scrolling (mouse wheel, touch swipe) or pressing arrow keys advances to the next or previous deck
- **Directional slide transitions**: swiping forward slides the new deck up from below; swiping back slides it down from above, creating a kinetic TikTok-like feel
- Scroll snaps to each deck — no partial views
- A thin **vertical progress indicator** on the right edge shows the user's position within the current tournament
- Decks are ordered chronologically: most recent tournament first. Within each tournament, challenge decklists are sorted by final placement (best results first); leagues retain their published order
- Decks load lazily: tournament data is fetched on demand as the user scrolls forward

### 6.3 Interactive Navigation

A **persistent interactive breadcrumb** is always visible in the header, showing the user's current position:

```
Jun 5, 2026 ▾  ›  Pauper League ▾  ›  Deck 1 of 11 ▾
```

Each segment is a **clickable dropdown trigger**:

- **Date segment** (e.g., "Jun 5, 2026 ▾"): Opens a scrollable dropdown listing all available dates, with the event count per date. Selecting a date loads that day's first tournament and jumps to its first deck.
- **Tournament segment** (e.g., "Pauper League ▾"): Opens a dropdown listing all tournaments on the current date, with deck counts. Selecting a tournament loads it (if not already loaded) and jumps to its first deck.
- **Deck segment** (e.g., "Deck 1 of 11 ▾"): Opens a dropdown listing all players in the current tournament, with color pips and win/loss records (for challenges). Selecting a player jumps directly to their deck.

The dropdowns auto-scroll to highlight the currently active item and close when the user clicks outside or navigates via scroll/keyboard.

When the user selects a tournament that hasn't been loaded yet, the pipeline lazily fetches it on demand before navigating.

There are no visual section dividers or headers between tournaments in the scroll flow — the breadcrumb is the sole orientation mechanism.

### 6.4 Deck Display

Each deck view shows:

- **Player name** and win/loss record (displayed for both leagues and challenges when available, e.g., "5-0", "6-2")
- **Main deck** organized by category: Creatures, Spells, Lands — each with a subtotal count
- **Sideboard** as a flat list
- **Deck color indicator** (see 6.4)
- **Tournament type badge** (see 6.5)

### 6.5 Deck Color Indicators

Each decklist displays a set of large colored pips (20px desktop, 24px mobile) representing the deck's colors as the primary visual element, derived from the colors its **main deck** has to be able to produce, **excluding lands**:

| Symbol | Color     | Display color |
|--------|-----------|---------------|
| W      | White     | Yellow        |
| U      | Blue      | Blue          |
| B      | Black     | Black         |
| R      | Red       | Red           |
| G      | Green     | Green         |
| C      | Colorless | Gray          |

A mono-red deck shows a single red pip. A three-color deck (e.g., Esper: WUB) shows yellow, blue, and black pips. The colorless (C) pip is shown only if the deck contains zero colored non-land cards.

Lands are excluded from color computation entirely, and so is the sideboard: those cards come in against specific matchups, and one of them should not recolor the whole deck. Cards that produce mana of various colors (e.g., Prophetic Prism) do not contribute those colors.

A card contributes a color only if you have to produce that colored mana to play it (see 7.4). This is narrower than Scryfall's `color_identity`, which counts colored mana in abilities too and used to paint decks with colors they never cast.

Color data is computed during the crawl/enrichment step and stored in each decklist's JSON.

### 6.6 Tournament Type Badges

Each deck displays a small colored badge indicating the tournament type (e.g., "League", "Challenge", "Showcase", "Preliminary"). The badge label is derived from the tournament's `site_name` field by extracting the type keyword from the hyphenated name (e.g., `pauper-league-...` → "League"). Badge colors are mapped per type:

| Type        | Color  |
|-------------|--------|
| League      | Green  |
| Challenge   | Blue   |
| Showcase    | Purple |
| Preliminary | Orange |
| Premier     | Red    |
| Classic     | Brown  |

### 6.7 Card Preview

Hovering over a card name (desktop) or tapping it (mobile) displays a floating preview of the card image, fetched from the Scryfall API:

```
https://api.scryfall.com/cards/named?exact={card_name}&format=image&version=normal
```

The preview tooltip follows the cursor and repositions to stay within the viewport.

### 6.8 Deck Count

The header displays a persistent total deck count (e.g., "4,832 decks across 312 events") computed from the tournament index at page load. This number represents the total decks available in the database for the current year, not just the currently loaded ones.

### 6.9 Metagame Overview

A header button (or the **M** key) opens an overlay ranking every archetype in a chosen slice of the data by its presence percentage. The slice is switchable between the tournament on screen, that tournament's day, a rolling 7/30/90-day window, the current year, and all time, and can be narrowed to leagues, challenges, or IRL events.

Because leagues publish only 5-0 decks, challenges only the top 32, and IRL events only the top 8, the percentage is the share of *winning* decks rather than of the field. The overlay states this in a note that changes with the event-type filter.

The top 12 archetypes appear as bars with share, deck count, and the change in share against the previous equivalent window; the remaining tail expands on demand. Above them, a stacked area chart drawn as inline SVG (no charting library) shows how those shares moved over time, bucketed by day, week, or month depending on the range.

The overlay reads a single precomputed artifact, `assets/pauper/meta/timeline.json` (see 7.7), fetched once per session. Full detail lives in `docs/features/metagame-overview.md`.

## 7. Data Pipeline

### 7.1 Data Source

All data is scraped from `https://www.mtgo.com/decklists`. Tournament data is embedded in the page as a JavaScript object assigned to `window.MTGO.decklists.data` and extracted via regex pattern matching. This is a **fragile** dependency: any change to MTGO's page structure will break the crawler.

### 7.2 Pipeline Orchestration

The pipeline is orchestrated by `src/pipeline.py` and invoked via `crawl.py`. A single run performs:

1. **Scryfall cache**: Download `oracle-cards.jsonl.gz` if not already cached (refreshed once per day)
2. **Color lookup**: Build a `card_name → color_identity` mapping from the cached oracle data
3. **Discovery**: Fetch the MTGO decklists page, extract all tournament URLs
4. **Pauper filter**: Keep only URLs containing `/pauper-`
5. **Deduplication**: Compare discovered `site_name` values against existing files in `assets/pauper/raw/` — skip any already stored
6. **Crawl new**: For each new tournament:
   a. Fetch the tournament page
   b. Extract the embedded JSON data via regex (`window.MTGO.decklists.data`)
   c. Parse the Python-literal string (replacing JS booleans)
   d. Enrich challenge results: map `winloss` and `final_rank` arrays to each decklist by `loginid`, sort decklists by final placement
   e. Minify: keep only player, card names, quantities, card types, win/loss records, and final rank
   f. Enrich: compute deck color identity from Scryfall data, excluding lands
   g. Save to `assets/pauper/raw/{site_name}.json`
7. **Index rebuild**: Regenerate `assets/pauper/index.json` from all raw files (sorted by `starttime` descending)
8. **Player index rebuild**: Regenerate `assets/pauper/players.json` mapping player names to their tournament `site_name`s
9. **Profile rebuild**: Regenerate the per-player and per-archetype profiles
10. **Metagame timeline rebuild**: Regenerate `assets/pauper/meta/timeline.json` with per-event archetype counts
11. **Timestamp**: Write `info.json` with the current UTC datetime

If no new tournaments are found, steps 7-10 are skipped and no files are modified.

### 7.3 Challenge Results Enrichment

Challenge tournaments include additional metadata not present in league data:

- **`winloss`** array: Each entry contains `loginid`, `wins`, and `losses` for a player
- **`final_rank`** array: Each entry contains `loginid` and `rank` (final placement)

During enrichment, these top-level arrays are mapped to individual decklists by matching `loginid`. Each deck receives:

- `wins`: `{ "wins": "6", "losses": "2" }` — the player's match record
- `final_rank`: integer — the player's final placement in the tournament

Decklists within a challenge are then sorted by `final_rank` ascending, so the best-performing players appear first in the carousel.

### 7.4 Color Enrichment

Deck colors are derived using Scryfall's bulk data:

1. Download `oracle-cards.jsonl.gz` from Scryfall's bulk data endpoint (refreshed once per day, cached at `.cache/oracle-cards.jsonl.gz`)
2. Build a lookup table: `card_name → required colors` (list of W/U/B/R/G)
3. For each deck, compute the union across the **main deck only**, **excluding cards with card type LAND**
4. Store the result as a `colors` array (e.g., `["U", "B"]`) on each decklist object

**Required colors** come from the mana cost rather than Scryfall's `color_identity`, which also counts colored mana appearing in abilities — Nihil Spellbomb costs `{1}` and only asks for `{B}` in an optional draw trigger, yet its identity is black, which used to paint thousands of colorless decks black. Symbols payable without their color are skipped: Phyrexian mana (`{R/P}` on Gut Shot) takes 2 life instead, and monocolored hybrid (`{2/W}`) takes generic mana. Note this reads the cost, not the printed color: Writhing Chrysalis prints as colorless but costs `{2}{R}{G}` and counts as red-green.

Two cases the card data cannot express are handled separately:

- Cards a deck never pays for at all are listed in `FREE_TO_PLAY_CARDS` in `src/scryfall.py`. Sneaky Snacker costs `{U}{B}` but is discarded and returns itself from the graveyard, so mono-red decks play it without a blue or black source.
- Oracle data also carries art series and playtest cards, which reuse real card names and are legal nowhere. They are filtered by legality, otherwise the "Delver of Secrets // Delver of Secrets" art card claims the name and every Delver deck reads as colorless.

Name spellings are reconciled in the lookup, since MTGO writes split cards without spaces (`Fire/Ice`), names a double-faced card by its front face, and serves some names as UTF-8 bytes reread as Latin-1 (`Troll of Khazad-dÃ»m`). A card the lookup does not know at all — typically one printed after the cached snapshot — falls back to MTGO's own color field.

### 7.5 Storage Format

- **Per-tournament file**: `assets/pauper/raw/{site_name}.json` — contains full tournament metadata and all minified decklists with color data
- **Index file**: `assets/pauper/index.json` — array of tournament summaries (`site_name`, `starttime`, `deck_count`) sorted by date descending, used by the frontend to discover and lazily load tournaments
- **Player index**: `assets/pauper/players.json` — maps lowercase player names to arrays of `site_name` strings they appear in. Generated by the pipeline for future use (player search is currently out of scope)
- **Info file**: `info.json` — contains `last_update` timestamp displayed in the frontend header

### 7.7 Metagame Timeline

`assets/pauper/meta/timeline.json` holds the archetype census the metagame overview (6.9) reads. Archetype names are listed once in an `archetypes` table with their deck-profile `slugs`, and each event carries `s` (site name), `d` (date), `t` (event type), `n` (description), and `c`: pairs of `[archetype index, deck count]`.

Storing names once instead of per event keeps the entire history at 173 KB (24 KB gzipped over 851 events and 20,707 decks), small enough for a single fetch that answers every scope in the browser. Without it the frontend would have to read the 202 MB of raw tournament files to compute a share.

Decks with no archetype label are counted as `Unclassified` rather than bucketed by color identity, which is how deck profiles treat them: a color string is not an archetype and would rank alongside real ones.

Written by `src/meta_stats.py` as part of the derived-artifact rebuild, after the deck profiles.

### 7.6 Scheduling

The crawler runs as a GitHub Actions workflow on a cron schedule (every hour). The workflow:

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

- Dark theme with `theme-color` meta tag for native browser chrome integration
- Responsive layout via CSS media queries (breakpoint at 640px)
- Touch-friendly: swipe to navigate, tap for card preview (centered overlay on mobile)
- Main deck rendered in a compact 2-column layout on mobile; sideboard stacks below
- Deck content is vertically centered in the viewport on mobile to avoid dead space below short decklists
- 24px mana pips on mobile for easy scanning
- Breadcrumb dropdowns resize for narrow viewports
- No footer — all vertical space dedicated to deck content

### 9.5 Accessibility

- Keyboard navigation (arrow keys)
- Semantic HTML structure
- Sufficient color contrast (to be verified)

## 10. Risks and Mitigations

| Risk                                        | Impact | Mitigation                                                    |
|---------------------------------------------|--------|---------------------------------------------------------------|
| MTGO changes page structure                 | High   | Monitor crawler failures; add alerts to GitHub Actions        |
| MTGO rotates tournaments off the page       | Medium | Hourly cron schedule minimizes the window; no backfill exists |
| Scryfall API downtime                       | Medium | Card previews degrade gracefully (broken image, no crash)     |
| GitHub Pages bandwidth limit hit            | Low    | Minified JSON keeps data small; images served by Scryfall     |
| Scryfall bulk data format changes           | Low    | Pin to known fields; add validation in enrichment step        |
| MTGO stops publishing decklists             | High   | No mitigation — the entire service depends on this data source|
| GitHub Actions cron delays or quota exceeded | Low    | Monitor action runs; keep pipeline fast (~30s per run)        |
