# Feature 2: Naming Convention from Pauperwave

**Status:** Done

## Summary

Adopt the deck archetype naming convention used by the **Pauperwave** community to label each decklist with a recognizable archetype name. Instead of inventing a new naming taxonomy, Merchant Scroll aligns with the names already established and understood by the Italian/international Pauper community.

## Motivation

The existing "Deck Classification" feature proposal (see `docs/new_features.md`) describes a generic signature-card matching system. This feature refines that approach by sourcing archetype names and definitions directly from Pauperwave, the de-facto reference for the Italian Pauper community. Using Pauperwave's naming convention means:

- Players see names they already recognize from Pauperwave tournaments and content
- No need to invent or debate archetype labels — Pauperwave has already done this work
- Classification stays current as Pauperwave updates their taxonomy for new archetypes

## Proposed Behavior

1. Maintain a mapping of **Pauperwave archetype names** to their signature card lists
2. During the crawl pipeline (or at render time), classify each decklist by matching its cards against the mapping
3. Display the Pauperwave archetype name in the deck header, below the player name (e.g., "Altar Tron", "Dimir Faeries", "Golgari Gardens")

## Data Source

The archetype names and their defining cards are sourced from Pauperwave's published taxonomy. This could be:

- A manually curated JSON file (`archetypes/pauperwave.json`) updated periodically from Pauperwave's classification
- An automated sync if Pauperwave exposes structured data (API, spreadsheet, or machine-readable format)

## Example Mapping

```json
{
  "Altar Tron": ["Ashnod's Altar", "Myr Retriever", "Urza's Tower"],
  "Dimir Faeries": ["Spellstutter Sprite", "Faerie Seer", "Snuff Out"],
  "Golgari Gardens": ["Tithing Blade", "Basilisk Gate", "Khalni Garden"],
  "Mono Red Kuldotha": ["Kuldotha Rebirth", "Experimental Synthesizer", "Goblin Blast-Runner"],
  "Pizza Druid": ["Arbor Elf", "Utopia Sprawl", "Annoyed Altisaur"]
}
```

## Relationship to Deck Classification

This feature builds on top of the generic classification system described in `docs/new_features.md`. The matching algorithm (signature-card scoring with a threshold) remains the same — this feature simply specifies **where the names come from** (Pauperwave) and commits to keeping them aligned with that community standard.

## Open Questions

- How frequently does Pauperwave update their archetype list? What's the process for syncing changes?
- Does Pauperwave publish their taxonomy in a structured format, or does it need to be manually extracted?
- Should we credit Pauperwave in the UI (e.g., "Archetype names from Pauperwave")?
- How to handle decks that Pauperwave hasn't classified (new brews, rogue decks)?
- Should the naming convention be configurable per community, or is Pauperwave the single source of truth?
