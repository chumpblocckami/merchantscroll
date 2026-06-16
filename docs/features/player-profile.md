# Feature 4: Player Profile Page

**Status:** Done

## Summary

Create player profile pages that aggregate a player's tournament history and statistics across both MTGO and IRL events. Each player gets a dedicated page at a URL like `merchantscroll.com/player/{username}` that shows their overall performance, deck preferences, and tournament history.

## Motivation

Merchant Scroll currently has no concept of a player beyond a name on a decklist. The `players.json` index already maps player names to their tournament appearances, but this data isn't exposed anywhere. A player profile page transforms Merchant Scroll from a deck browser into a player-aware platform, enabling:

- Players to track their own results over time
- Community members to look up opponents and see their deck preferences
- A natural landing page for sharing ("check out my Merchant Scroll profile")

## Example Profile

```
Player
Online: chumpblocckami | IRL: Matteo Mazzola

Overall Score
Leagues: 5 trophies (ranked x/513 yearly — x/overall trophies)
Challenges: 67/102 (win% 85)
IRL tournaments: 5 top-8
Other: ...

Favorite Decks
1. Altar Tron: 56 entries
2. Pizza Druid: 2 entries
3. UG Arcane: 6 entries
```

## Proposed Behavior

### Profile URL

Each player is accessible at:

```
merchantscroll.com/player={username}
```

Where `{username}` is the MTGO login name (lowercased). Example: `merchantscroll.com/player=chumpblocckami`

### Player Identity

- **Online name**: The MTGO username as it appears in tournament data
- **IRL name**: An optional real name, linked when the same person plays both MTGO and Pauperwave local events
- The online-to-IRL name mapping is maintained manually (e.g., a `players/identities.json` file) since there's no automated way to link the two

### Statistics

The profile computes and displays:

| Stat | Description |
|------|-------------|
| **League trophies** | Count of 5-0 league finishes. Ranked against all players yearly and all-time |
| **Challenge record** | Matches won/lost across all challenges, with overall win percentage |
| **IRL top-8s** | Count of top-8 finishes in Pauperwave local tournaments (requires Feature 3) |
| **Favorite decks** | Archetype breakdown by number of entries, sorted descending (requires Feature 2 for naming) |
| **Total entries** | Total number of tournament appearances across all event types |

### Favorite Decks

The "Favorite Decks" section lists the archetypes the player has registered most frequently, with entry counts. Each archetype name links to the corresponding decklist entries. This section depends on:

- **Feature 2** (Pauperwave naming) for archetype classification
- Without classification, this section can fall back to showing deck color identities instead (e.g., "UB: 23 entries, R: 15 entries")

## Data Pipeline

### Player Stats Generation

A new pipeline step computes player statistics from the existing tournament data:

1. Iterate over all tournaments in `assets/pauper/raw/`
2. For each player appearance, extract:
   - Tournament type (league, challenge, etc.)
   - Win/loss record (if available)
   - Final rank (if available)
   - Deck archetype (if classified)
   - Deck colors
3. Aggregate into per-player stats objects
4. Write to `assets/pauper/players/{username}.json`

### Identity Mapping

A manually maintained file maps MTGO usernames to IRL names:

```json
// players/identities.json
{
  "chumpblocckami": {
    "irl_name": "Matteo Mazzola",
    "pauperwave_name": "Matteo Mazzola"
  }
}
```

This allows the profile to show both the online handle and real name, and to merge IRL tournament data (Feature 3) with MTGO results.

### League Trophy Ranking

"Ranked x/513 yearly" requires:

1. Counting 5-0 finishes per player per year
2. Sorting all players by trophy count descending
3. Recording the player's position in that ranking

This is computed during the player stats generation step and updated on each pipeline run.

## Frontend

### Profile Page

The player profile is a new page (or route within the single-page app) that:

- Loads the player's stats JSON (`assets/pauper/players/{username}.json`)
- Renders the stats layout as shown in the example above
- Links each tournament entry back to the corresponding decklist in the carousel
- Uses the same dark theme and visual language as the main site

### Navigation to Profiles

- Player names in the decklist header become clickable links to the player's profile
- A search bar or player lookup (leveraging the existing `players.json` index) could be added in a future iteration

## Dependencies

| Dependency | Required for |
|------------|-------------|
| Feature 2 (Pauperwave naming) | Archetype names in "Favorite Decks" section |
| Feature 3 (Pauperwave decklists) | IRL tournament data and top-8 stats |
| `players.json` index | Already exists — maps player names to tournaments |

## Open Questions

- Should profiles be statically generated (one HTML/JSON per player) or dynamically rendered client-side from `players.json` data?
- How to handle player name changes on MTGO? Should there be an alias system?
- Privacy: should players be able to opt out of having a profile page?
- How to handle the online-to-IRL identity mapping at scale? Manual curation works for a small community but doesn't scale
- Should the profile show individual tournament results (a full history table), or just aggregate stats?
- What's the URL scheme — `player={username}` vs `player/{username}` vs something else?
- How to compute "ranked x/513" — is 513 the total number of unique players with at least one 5-0, or all players who entered a league?
