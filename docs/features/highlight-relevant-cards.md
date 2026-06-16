# Highlight Relevant Cards

**Status:** Cancelled

Visually emphasize the cards that define a specific deck's identity and strategy. The goal is to help users quickly understand what makes a deck tick at a glance, without reading every card name.

## Open Questions

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

## Possible First Iteration

Start with the simplest version: visually emphasize 4-of cards in the main deck using bolder text. This requires zero backend changes and provides immediate value — 4-ofs are almost always the deck's core cards. More sophisticated highlighting (archetype-aware, metagame-aware) can build on top of this foundation.
