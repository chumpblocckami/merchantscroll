# Feature 9: Deck Profile

**Status:** Done

## Summary

Deck profile pages aggregate tournament history and statistics for a specific archetype (e.g. "U Terror"), mirroring the player profile concept.

## Statistics

| Stat | Description |
|------|-------------|
| **Total entries** | All appearances of this archetype across MTGO and IRL |
| **League entries** | Count of league appearances |
| **League trophies** | 5-0 league finishes, ranked among decks yearly and all-time |
| **Challenge appearances** | Number of challenge entries |
| **Challenge record** | Aggregate match W-L and win percentage across all pilots |
| **Top pilot** | Player with the most entries on this deck |
| **IRL top-8s** | Top-8 finishes in Pauperwave events |

## Data Pipeline

`src/deck_stats.py` iterates `assets/pauper/raw/`, groups decklists by `deck.archetype` (fallback: color identity), and writes:

- `assets/pauper/decks/{slug}.json` — per-archetype profile
- `assets/pauper/decks/index.json` — sorted index by entry count

Rebuilt automatically after each crawl via `src/pipeline.py` and `entrypoint.py`.

## Frontend

- Click the **archetype name** in the deck header to open the deck profile modal
- Swipe **right** (or press **←**) for deck/metagame stats; swipe **left** (or **→**) for player profile
- **Favorite decks** in a player profile link to the corresponding deck profile
- Reuses the same modal UI as player profiles
