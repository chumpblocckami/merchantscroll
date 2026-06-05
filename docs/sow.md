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
- Static frontend with card preview, search, color indicators, and tournament badges

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
| Crawler          | Python (requests, BeautifulSoup)   | GitHub Actions (cron) |
| Color enrichment | Python (Scryfall bulk data lookup) | GitHub Actions        |
| Frontend         | Static HTML, CSS, vanilla JS       | GitHub Pages          |
| Card images      | Scryfall API (client-side)         | User's browser        |

### Data flow

1. **GitHub Actions** triggers every 2 hours
2. **Crawler** fetches the MTGO decklists page (`https://www.mtgo.com/decklists`), discovers tournament URLs
3. **Crawler** scrapes each new tournament page, extracting deck data from the embedded `window.MTGO.decklists.data` JavaScript variable
4. **Enrichment step** maps each card name to its WUBRG color identity using a locally cached copy of Scryfall's `oracle-cards.json` bulk data (refreshed once per day)
5. **Minification** strips unnecessary fields, keeping only card names, quantities, types, and colors
6. **Storage** writes one JSON file per tournament to `assets/pauper/raw/` and updates `assets/pauper/index.json`
7. **GitHub Pages** serves the updated static site

## 6. Frontend

### 6.1 UX Model

The interface follows a **vertical carousel** pattern (TikTok-style):

- One decklist fills the available viewport at a time
- Scrolling (mouse wheel, touch swipe) or pressing arrow keys advances to the next or previous deck
- Scroll snaps to each deck — no partial views
- Decks are ordered chronologically: most recent tournament first, within each tournament ordered by player position/record
- Decks load lazily: tournament data is fetched on demand as the user scrolls forward

### 6.2 Navigation Context

A **persistent breadcrumb/progress bar** is always visible, showing the user's current position in the dataset:

```
June 3, 2026  ›  Pauper Challenge  ›  Deck 4 of 32
```

This bar updates in real time as the user scrolls. There are no visual section dividers or headers between tournaments in the scroll flow — the breadcrumb is the sole orientation mechanism.

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

Each deck displays a small colored badge indicating the tournament type (e.g., "League", "Challenge", "Showcase", "Preliminary"). The badge label is derived from the tournament's `site_name` or `description` field by extracting the relevant segment of the hyphenated name (e.g., `pauper-league-...` → "League"). Badge colors are assigned dynamically based on the derived label.

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

### 7.2 Crawl Process

1. Fetch the MTGO decklists index page
2. Extract all tournament URLs (links containing `/decklist/`)
3. For each tournament URL not already stored locally:
   a. Fetch the tournament page
   b. Extract the embedded JSON data via regex
   c. Parse the Python-literal string (replacing JS booleans)
   d. Minify: keep only player, card names, quantities, card types, and win/loss records
   e. Enrich: add color identity per deck (see 7.3)
   f. Save to `assets/pauper/raw/{site_name}.json`
4. Regenerate `assets/pauper/index.json` with tournament metadata and deck counts

### 7.3 Color Enrichment

Deck color identity is derived using Scryfall's bulk data:

1. Download `oracle-cards.json` from Scryfall's bulk data endpoint (refreshed once per day, cached between runs)
2. Build a lookup table: `card_name → color_identity` (list of W/U/B/R/G)
3. For each deck, compute the union of all card color identities across main deck and sideboard, **excluding cards with card type LAND**
4. Store the result as a `colors` array (e.g., `["U", "B"]`) on each decklist object

### 7.4 Storage Format

- **Per-tournament file**: `assets/pauper/raw/{site_name}.json` — contains full tournament metadata and all minified decklists
- **Index file**: `assets/pauper/index.json` — array of tournament summaries (site_name, starttime, deck_count) used by the frontend to discover and lazily load tournaments

### 7.5 Scheduling

The crawler runs as a GitHub Actions workflow on a cron schedule (every 2 hours). The workflow:

1. Checks out the repository
2. Runs the crawler script
3. Commits and pushes any new/updated JSON files
4. GitHub Pages automatically redeploys on push

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

### 9.5 Accessibility

- Keyboard navigation (arrow keys)
- Semantic HTML structure
- Sufficient color contrast (to be verified)

## 10. Risks and Mitigations

| Risk                                | Impact | Mitigation                                                    |
|-------------------------------------|--------|---------------------------------------------------------------|
| MTGO changes page structure         | High   | Monitor crawler failures; add alerts to GitHub Actions        |
| Scryfall API downtime              | Medium | Card previews degrade gracefully (broken image, no crash)     |
| GitHub Pages bandwidth limit hit   | Low    | Minified JSON keeps data small; images served by Scryfall     |
| Scryfall bulk data format changes  | Low    | Pin to known fields; add validation in enrichment step        |
| MTGO stops publishing decklists    | High   | No mitigation — the entire service depends on this data source |
