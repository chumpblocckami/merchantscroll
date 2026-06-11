# New Features

Planned features for future iterations. Each item needs further design and scoping before implementation.

## Highlight Relevant Cards

**Status:** Proposed

Visually emphasize the cards that define a specific deck's identity and strategy. The goal is to help users quickly understand what makes a deck tick at a glance, without reading every card name.

### Open questions

- **What defines "relevant"?** Options include:
  - Cards played as 4-ofs (statistical signal — the pilot considers them essential)
  - Cards unique to this archetype compared to other decks in the same color combination
  - Cards that are new or unusual relative to historical data for the same archetype
  - Key engine/combo pieces identified by card interaction analysis
- **How should highlighting look?** Options include:
  - Bold or brighter text weight for highlighted card names
  - A subtle background tint on the card row
  - A small icon or marker next to the card name
  - A separate "Key Cards" section at the top of the decklist
- **Should it be computed at crawl time or at render time?**
  - Crawl-time: requires archetype classification or cross-deck comparison in the pipeline
  - Render-time: simpler (e.g., just bold 4-ofs) but limits what "relevant" can mean
- **Does this need archetype classification first?** Highlighting "unusual" cards only makes sense if we know what "usual" looks like for a given archetype

### Possible first iteration

Start with the simplest version: visually emphasize 4-of cards in the main deck using bolder text. This requires zero backend changes and provides immediate value — 4-ofs are almost always the deck's core cards. More sophisticated highlighting (archetype-aware, metagame-aware) can build on top of this foundation.

---

## Deck Classification

**Status:** Proposed

Classify each decklist with a human-readable archetype name (e.g., "Mono Red Kuldotha", "Dimir Faeries", "Bogles") so users immediately understand what strategy a deck represents without inspecting every card.

### How it works

Classification is driven by a **user-maintained dictionary** that maps archetype names to signature card lists. The pipeline matches each decklist against the dictionary and assigns the best-fitting archetype.

```
archetypes/pauper.json
```

```json
{
  "Mono Red Kuldotha": ["Kuldotha Rebirth", "Experimental Synthesizer", "Goblin Blast-Runner"],
  "Dimir Faeries": ["Spellstutter Sprite", "Faerie Seer", "Snuff Out"],
  "Bogles": ["Slippery Bogle", "Ethereal Armor", "Ancestral Mask"],
  "Affinity": ["Myr Enforcer", "Frogmite", "Thoughtcast"],
  "Caw-Gates": ["Sacred Cat", "Basilisk Gate", "Brainstorm"],
  "Mono Blue Terror": ["Tolarian Terror", "Counterspell", "Thought Scour"]
}
```

Each key is the archetype display name. Each value is an array of **signature cards** — the cards that, taken together, uniquely identify the archetype.

### Matching algorithm

For each decklist:

1. Collect all card names in the main deck
2. For each archetype in the dictionary, count how many of its signature cards appear in the deck
3. Compute a match score: `matched_signatures / total_signatures`
4. Assign the archetype with the highest score, provided it exceeds a configurable threshold (e.g., ≥ 0.5)
5. If no archetype meets the threshold, label the deck as "Unknown" or leave it unclassified

### Open questions

- **When does classification run?** Options:
  - At crawl time: the pipeline reads the dictionary, classifies each deck, and stores the archetype name in the JSON alongside the decklist. Simplest for the frontend (just render a string)
  - At render time: the frontend loads the dictionary and classifies on the fly. More flexible (users see updates without re-crawling) but adds client-side complexity
- **How is the dictionary maintained?** Options:
  - A JSON file checked into the repo — anyone can submit a PR to add/rename archetypes
  - An admin UI or simple form (future iteration)
- **How to handle overlapping signatures?** Some cards appear in multiple archetypes (e.g., "Counterspell" in both Faeries and Terror). The scoring approach handles this naturally — the archetype with the most unique matches wins — but edge cases may need tie-breaking rules
- **Should it support color-gated matching?** e.g., only consider "Bogles" if the deck's color identity includes W and G. This would reduce false positives but adds complexity to the dictionary format
- **Where does the archetype name appear in the UI?** Options:
  - Below the player name in the deck header
  - As a tag/pill next to the tournament badge
  - In the breadcrumb deck dropdown alongside the player name

### Possible first iteration

1. Create `archetypes/pauper.json` with the 10–15 most common Pauper archetypes and their 3–5 signature cards each
2. Add a classification step in the crawl pipeline (after color enrichment, before minification) that writes an `archetype` field to each decklist
3. Display the archetype name in the deck header at the frontend, below the player name
4. Fallback: decks that don't match any archetype show no label (graceful degradation)
