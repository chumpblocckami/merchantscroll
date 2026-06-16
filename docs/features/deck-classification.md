# Deck Classification

**Status:** Done

Classify each decklist with a human-readable archetype name (e.g., "Mono Red Kuldotha", "Dimir Faeries", "Bogles") so users immediately understand what strategy a deck represents without inspecting every card.

## How It Works

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

## Matching Algorithm

For each decklist:

1. Collect all card names in the main deck
2. For each archetype in the dictionary, count how many of its signature cards appear in the deck
3. Compute a match score: `matched_signatures / total_signatures`
4. Assign the archetype with the highest score, provided it exceeds a configurable threshold (e.g., ≥ 0.5)
5. If no archetype meets the threshold, label the deck as "Unknown" or leave it unclassified

## Open Questions

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

## Possible First Iteration

1. Create `archetypes/pauper.json` with the 10–15 most common Pauper archetypes and their 3–5 signature cards each
2. Add a classification step in the crawl pipeline (after color enrichment, before minification) that writes an `archetype` field to each decklist
3. Display the archetype name in the deck header at the frontend, below the player name
4. Fallback: decks that don't match any archetype show no label (graceful degradation)
