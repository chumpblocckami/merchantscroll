# Feature 3: Reading Decklists from Pauperwave (Local Tournaments)

**Status:** Done

## Summary

Extend the data pipeline to ingest decklists from **Pauperwave** local (IRL) tournaments, in addition to the existing MTGO data source. This brings paper Pauper tournament results into Merchant Scroll, covering a data source that MTGO cannot provide.

## Motivation

Merchant Scroll currently only shows MTGO tournament results. The Italian Pauper community (and broader paper Pauper scenes) run regular local tournaments whose results are published or tracked by Pauperwave. Adding this data source:

- Gives visibility to the IRL Pauper metagame alongside the MTGO metagame
- Makes Merchant Scroll a more complete reference for Pauper players who play both online and in paper
- Supports the player profile feature (Feature 4) by connecting online and IRL results

## Scope

### In scope

- Reading and parsing decklist data from Pauperwave's published local tournament results
- Storing IRL tournament data in a format consistent with the existing MTGO data structure
- Displaying IRL decklists in the frontend carousel alongside MTGO decklists
- Visually distinguishing IRL tournaments from MTGO tournaments (e.g., a distinct badge like "IRL" or "Local")

### Out of scope (for first iteration)

- Crawling Pauperwave automatically on a schedule (manual import is acceptable initially)
- Supporting arbitrary third-party tournament organizers — only Pauperwave is targeted
- Backfilling historical Pauperwave data

## Data Source

Pauperwave publishes decklists as **Markdown files in a public GitHub repository**:

```
https://github.com/Pauperwave/blog/tree/main/content/blog/decklists
```

### Repository Structure

Each tournament is a single `.md` file named `{YYYY-MM-DD}-{event-slug}.md`. As of June 2026, the repo contains 50+ tournament files spanning from June 2023 to the present. Two templates define the formats:

- `0000-00-00-decklist-template.md` — standard (individual) tournaments
- `0000-00-00-trio-template.md` — team (trio) tournaments

### File Format

Each file uses **YAML frontmatter** for tournament metadata and **`::magic-decklist` components** (Nuxt Content custom components) for the actual decklists.

**Frontmatter** contains:

```yaml
---
title: "LP Brescia Summer 2026"
description: "Decklists Top 8"
tags:
 - Top 8
 - League
location: Brescia
date: 2026-06-13
author: Alessandro Moretti
thumbnail: /assets/blog/logo/brescia.jpg
published: true
---
```

Key fields: `title`, `date`, `location`, `tags` (tournament type indicators), `published` (boolean).

A metadata table follows the frontmatter:

```
| Informazione | Dettagli |
|---|---|
| Giocatori | 8 |
| Data | 13 June 2026 |
| Struttura del torneo | 3 Rounds of Swiss + Single Elimination Top 4 |
```

**Decklists** use the `::magic-decklist` component:

```markdown
::magic-decklist
---
name: UB Faeries
player: Michael Calegari
placement: Winner
headerGradient: dimir
---
Creatures
4 Faerie Miscreant
4 Faerie Seer
...

Instants
4 Counterspell
4 Snuff Out
...

Sideboard
3 Annul
2 Blue Elemental Blast
...
::
```

Each decklist block provides:

| Field | Description |
|-------|-------------|
| `name` | Archetype name (Pauperwave's naming convention — see Feature 2) |
| `player` | Player's real name (IRL, not an MTGO username) |
| `placement` | Final standing: `Winner`, `Finalist`, `Top 4`, or `Top 8` |
| `headerGradient` | Color theme hint (e.g., `dimir`, `monored`, `golgari`, `simic`) |

Card entries follow the `{qty} {card_name}` format, grouped under category headers (`Creatures`, `Instants`, `Sorceries`, `Enchantments`, `Lands`, `Sideboard`).

### Access Method

Since the data lives in a public GitHub repo, the pipeline can fetch it via:

1. **GitHub raw content** — `https://raw.githubusercontent.com/Pauperwave/blog/main/content/blog/decklists/{filename}`
2. **GitHub API** — list directory contents, then fetch individual files
3. **Git clone/pull** — clone the repo (or a sparse checkout of `content/blog/decklists/`) and parse locally

Option 2 (GitHub API) is recommended for the pipeline: list files in the directory to discover new tournaments, then fetch only the ones not already imported.

## Proposed Data Model

IRL tournament data should follow the same structure as MTGO data where possible:

```json
{
  "site_name": "pauperwave-local-2026-06-10-roma",
  "description": "Pauperwave Local — Roma",
  "starttime": "2026-06-10",
  "source": "pauperwave",
  "format": "pauper",
  "decklists": [
    {
      "player": "chumpblocckami",
      "final_rank": 1,
      "wins": { "wins": "4", "losses": "0" },
      "colors": ["R", "G"],
      "main_deck": [...],
      "sideboard_deck": [...]
    }
  ]
}
```

Key additions:

- `source` field to distinguish `"mtgo"` from `"pauperwave"` data
- `site_name` prefixed with `pauperwave-` to avoid collisions with MTGO tournament IDs
- Tournament metadata may include location info (city, venue) not present in MTGO data

## Frontend Integration

- IRL tournaments appear in the same carousel and breadcrumb navigation as MTGO tournaments
- A distinct badge (e.g., "IRL" in a unique color) differentiates them from online events
- The date dropdown shows both MTGO and IRL events on the same date, if any

## Pipeline Integration

- A new crawler module (e.g., `src/pauperwave_crawler.py`) handles fetching and parsing Pauperwave data
- The pipeline orchestrator (`src/pipeline.py`) calls the Pauperwave crawler alongside the MTGO crawler
- IRL data is stored in `assets/pauper/raw/` with the same conventions, distinguished by the `pauperwave-` prefix in `site_name`
- The index rebuild step includes both MTGO and Pauperwave tournaments

## Parsing Logic

The parser needs to handle the `::magic-decklist` Markdown component format:

1. **Split** the file into frontmatter (YAML between `---` delimiters) and body
2. **Parse frontmatter** to extract `title`, `date`, `location`, `tags`
3. **Extract decklist blocks** by splitting on `::magic-decklist` / `::` delimiters
4. **Parse each block's YAML header** (`name`, `player`, `placement`, `headerGradient`)
5. **Parse card lines** — each line matching `{qty} {card_name}` under category headers
6. **Map placement strings** to numeric ranks: `Winner` → 1, `Finalist` → 2, `Top 4` → 3–4, `Top 8` → 5–8
7. **Derive deck colors** using the same Scryfall color enrichment as MTGO data, or infer from `headerGradient` as a fallback

### Trio (Team) Format

Team tournament files (`*-trio-*.md`) group decklists under team headers (`## Winner: TeamName`, `## Finalist: TeamName`, etc.) with three decklists per team. The parser should handle this variant by associating a team name with each group of three decks.

## Open Questions

- Should IRL and MTGO results be interleaved by date in the carousel, or separated into tabs/sections?
- How to handle incomplete decklists (if a top-8 player didn't submit their list)?
- Should the pipeline auto-discover new files via the GitHub API, or be triggered manually?
- How to handle the `headerGradient` field — use it as a color hint, or always recompute colors from Scryfall?
- GitHub API rate limits (60 req/hour unauthenticated, 5000/hour with token) — is a token needed given the volume?
- Should team tournament results feed into individual player profiles (Feature 4), or be tracked separately?
