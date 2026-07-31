# Feature 10: Metagame Overview

**Status:** Done

## Summary

An overlay that answers "what is everyone playing?" — every archetype in a given slice of the data, ranked by presence, with the share of decks each one holds. The slice is switchable: a single tournament, a single day, a rolling timespan, a calendar year, or all time.

Open it with the header button (left of the install icon) or by pressing **M**. Close it with **M**, **Escape**, the close button, or a click on the backdrop.

## What the percentage actually means

MTGO does not publish full metagame data. Leagues publish only 5-0 decks, challenges only the top 32, and Pauperwave IRL events only the top 8. A presence percentage over that data is the **share of winning decks**, not the share of decks people brought.

Mixing those populations blends three different filters, so the overlay lets the user pick one — **All events**, **Leagues**, **Challenges**, **IRL** — and states the caveat in a note under the summary line that changes with the filter. Showcase, preliminary, and other event types are counted only under All events.

## Scopes

| Scope | Range |
|-------|-------|
| **This tournament** | The single event holding the deck currently on screen |
| **This day** | Every event sharing that deck's date |
| **7 / 30 / 90 days** | Rolling window ending on the newest event in the data |
| **Current year** | Jan 1 to Dec 31 |
| **All time** | Everything, currently back to 2019 |

Rolling windows are anchored on the newest event in the timeline rather than the wall clock, so a stalled crawler renders the last week of real data instead of an empty range.

`This tournament` and `This day` need a deck on screen and are disabled without one. Under `This tournament` the event-type filter is disabled too, since a single event has exactly one type.

## Rows

The top 12 archetypes by share, each with a bar scaled against the leader, the share to one decimal, the deck count, and a trend delta. A collapsed row expands the tail: 31 of 88 archetypes have fewer than 5 entries in the whole dataset, so a flat list would bury the signal. Clicking an archetype closes the overlay and opens its existing deck profile.

**Trend delta** is the change in share, in percentage points, against the previous equivalent window — the preceding 30 days for a 30-day view, the previous year for a year view. It is hidden when either window holds fewer than 50 decks: a single league day is about 12 decks, where one extra copy of a deck swings its share 8 points, so the arrow would be pure noise.

Decks the classifier could not label are grouped as **Unclassified** rather than by color identity, and that row does not link anywhere. It covers 47 of 20,707 decks.

## Chart

A stacked area chart of share over time, drawn as inline SVG with no charting dependency. The top 8 archetypes across the window get their own colour, everything else stacks as Other, and the bands always total 100%.

Buckets adapt to the range: days for 7 and 30 days, weeks for 90 days, months for a year and all time. Only buckets that hold events become columns.

Because columns are spaced evenly rather than by date, a sparse bucket would occupy the same width as a dense one and spike to 100% on a single deck — the February 2019 league in the archive holds 8 decks against roughly 600 in a 2026 month. Buckets below 15% of the median bucket size are therefore left out, and the caption says how many were dropped. The ranked rows below always cover the full scope regardless.

Hovering (or tapping) the plot moves a cursor line and rewrites the caption with that bucket's date, deck count, and top three archetypes. The chart is skipped entirely when a scope yields fewer than two buckets, which is every single-tournament view.

## Data Pipeline

`src/meta_stats.py` reads `assets/pauper/raw/` and writes one artifact, `assets/pauper/meta/timeline.json`:

```json
{
  "generated": "2026-07-31",
  "archetypes": ["Mono Red Madness", "Elves"],
  "slugs": ["mono-red-madness", "elves"],
  "events": [
    {"s": "pauper-league-2026-07-3110855", "d": "2026-07-31", "t": "league",
     "n": "Pauper League", "c": [[0, 3], [1, 1]]}
  ]
}
```

Archetype names live in one table and each event references them by index, so the whole history costs **173 KB, 24 KB gzipped** for 851 events and 20,707 decks. That is a single fetch on first open, cached for the session, and it serves every scope — the frontend never touches the 202 MB raw tree to compute a share.

`slugs` is shipped rather than derived in the browser because Python's `\w` matches Unicode letters while JavaScript's does not, so a future accented archetype name would slug differently on each side.

Rebuilt automatically after each crawl by `rebuild_derived_artifacts` in `src/pipeline.py`, after the deck profiles. The service worker already treats everything under `assets/pauper/` as network-first data, so no cache changes were needed.
