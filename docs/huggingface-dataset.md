---
pretty_name: Merchant Scroll — Pauper Tournament Decklists
tags:
  - magic-the-gathering
  - pauper
  - decklists
configs:
  - config_name: tournaments
    data_files: raw/*.json
---

# Merchant Scroll — Pauper Tournament Decklists

Every Magic: The Gathering Pauper decklist collected by
[Merchant Scroll](https://github.com/chumpblocckami/merchantscroll): MTGO
Leagues, Challenges, Showcases and RC qualifiers from
[mtgo.com](https://www.mtgo.com/decklists), plus paper events from
[Pauperwave](https://github.com/Pauperwave). The crawler updates it several
times an hour.

## Files

| Path | Contents |
|------|----------|
| `raw/<site_name>.json` | One tournament per file, named after its mtgo.com slug (`pauperwave-<slug>` for paper events) |
| `card-art.json` | Card name → first-printing Scryfall image URLs (`_unresolved` lists names Scryfall does not know) |
| `info.json` | Time of the last crawl that changed the data |

## Tournament record

```json
{
  "description": "Pauper Challenge 32 Special",
  "starttime": "2025-11-12 23:30:00.0",
  "site_name": "pauper-challenge-32-special-2025-11-1212824383",
  "player_count": {"tournamentid": "12824383", "players": "32", "queued_players": "32"},
  "decklists": [
    {
      "player": "Paul16",
      "archetype": "Jund Gardens",
      "colors": ["B"],
      "wins": {"wins": "7", "losses": "1"},
      "final_rank": 1,
      "main_deck": [{"qty": "1", "card_attributes": {"card_name": "Mountain", "card_type": "LAND"}}],
      "sideboard_deck": [{"qty": "3", "card_attributes": {"card_name": "Red Elemental Blast", "card_type": "INSTNT"}}]
    }
  ]
}
```

- `qty`, `wins` and `player_count` values are strings, as mtgo.com publishes them.
- `archetype` is assigned by Merchant Scroll's classifier, not by the player.
- `wins` and `final_rank` appear only for events with published results;
  Leagues publish 5-0 lists without standings.
- `source` and `format` appear on paper (Pauperwave) events only.

## Loading

```python
from huggingface_hub import snapshot_download

path = snapshot_download("vedalken/merchantscroll", repo_type="dataset", allow_patterns="raw/*")
```

Decklists are published by Wizards of the Coast on mtgo.com and by the
Pauperwave community; Merchant Scroll only collects and labels them.
