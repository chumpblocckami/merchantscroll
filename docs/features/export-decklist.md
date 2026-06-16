# Feature 1: Export Decklist as .txt

**Status:** Done

## Summary

Add a download button to each decklist in the frontend that exports the deck as a `.txt` file in MTGO-compatible format. This lets users quickly copy a list into MTGO, Moxfield, or any other tool that accepts text-based decklists.

## Motivation

Currently users can only read decklists on the site. To import a deck into MTGO or a deckbuilder, they must manually copy card names and quantities. A one-click `.txt` download removes this friction and makes Merchant Scroll a practical tool, not just a browsing experience.

## Existing Work

The `examples/export_decklist.py` script already implements the export format:

```
4 Lightning Bolt
4 Chain Lightning
4 Monastery Swiftspear
...

Sideboard
2 Pyroblast
2 Red Elemental Blast
...
```

The frontend needs to replicate this logic client-side.

## Proposed Behavior

1. Each deck view shows a small **download button** (e.g., a downward-arrow icon) in the deck header area, next to the player name
2. Clicking the button generates a `.txt` file in-browser from the currently displayed decklist and triggers a browser download
3. The filename follows the pattern: `{player}_{tournament-type}_{date}.txt` (e.g., `chumpblocckami_league_2026-06-05.txt`)

## Export Format

The `.txt` file uses the standard MTGO-compatible format:

```
// Player: {player_name} — {tournament_description} — {date}
// Record: {wins}-{losses}

{qty} {card_name}
{qty} {card_name}
...

Sideboard
{qty} {card_name}
{qty} {card_name}
...
```

- Main deck cards are sorted alphabetically by card name
- A blank line separates the main deck from the sideboard
- The `Sideboard` header precedes sideboard cards
- Comment lines (`//`) at the top include player name, tournament info, and record (if available)

## Technical Approach

- **No backend changes required** — the decklist data is already loaded in the browser when viewing a deck
- Use the [Blob API](https://developer.mozilla.org/en-US/docs/Web/API/Blob) and `URL.createObjectURL` to create a downloadable file client-side
- Trigger download via a dynamically created `<a>` element with the `download` attribute

## Open Questions

- Should the button also offer a "copy to clipboard" option alongside download?
- Should the export include the comment header lines, or just the bare card list for maximum compatibility?
- Placement and styling of the button — should it be an icon-only button, or include a text label like "Export"?
