# Feature 8: Visual Decklist View

**Status:** Done

## Summary

Add a **visual view** mode that renders each deck as card images instead of a text list. Users can toggle between the current text view and a grid of Scryfall card art, making it easier to recognize decks at a glance and browse lists the way many deckbuilder apps present them.

## Motivation

The default decklist is text-only: quantity plus card name in categorized rows (Creatures, Spells, Lands). Card images appear only on hover or tap via the existing preview tooltip. This works well for copying names and reading quickly on small screens, but it forces users to mentally map names to cards.

A visual view helps when:

- Recognizing an archetype from key art (e.g., Kitchen Imp, Counterspell, Tron lands)
- Comparing two similar lists without reading every line
- Browsing decks in a more immersive, app-like way — especially on tablets

The site already fetches card images from Scryfall for previews; this feature reuses that integration to show the full deck visually.

## Proposed Behavior

### View Toggle

1. Each deck view includes a **view toggle** in the deck header or actions bar (e.g., list icon / grid icon)
2. Tapping the toggle switches between:
   - **Text view** (current default) — categorized text rows with hover/tap preview
   - **Visual view** — card images arranged in a responsive grid
3. The user's preference is saved in `localStorage` and applied to all decks until changed

### Visual Layout

The visual view replaces the text `decklist-columns` content with an image grid:

```
┌─────────────────────────────────────┐
│  Main Deck (60)                     │
│  ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐     │
│  │4 │ │4 │ │4 │ │3 │ │2 │ │1 │ ... │
│  └──┘ └──┘ └──┘ └──┘ └──┘ └──┘     │
│                                     │
│  Sideboard (15)                     │
│  ┌──┐ ┌──┐ ┌──┐                     │
│  │2 │ │2 │ │3 │ ...                 │
│  └──┘ └──┘ └──┘                     │
└─────────────────────────────────────┘
```

- Each unique card is one image tile; a **quantity badge** overlays the corner when `qty > 1`
- Main deck and sideboard remain separate sections with headings
- Cards within each section are sorted by quantity descending, then alphabetically (same order as text view)
- Optional: keep Creatures / Spells / Lands sub-sections in visual mode, or use a single flat grid per section for simplicity

### Card Images

Reuse the existing Scryfall named-card endpoint:

```
https://api.scryfall.com/cards/named?exact={card_name}&format=image&version=small
```

Use `version=small` (~146×204 px) for grid tiles to reduce bandwidth; fall back to `normal` if `small` fails. On tap/click, show the existing full-size preview (already implemented).

### Loading and Placeholders

- Images load lazily as tiles enter the viewport (`loading="lazy"` on `<img>`)
- While loading, show a neutral placeholder (card-shaped skeleton with the card name as `alt` text)
- Failed loads show a fallback tile with the card name in text

### Interaction

- **Tap / click** a card image → open the existing floating preview at full size (same as text view)
- **Scroll** within the deck area when the grid exceeds the viewport (same scroll container as text view)
- Carousel navigation (swipe, wheel, arrow keys) unchanged — only the deck content layout changes

## Technical Approach

### Frontend Only

No pipeline or backend changes. All data is already in the loaded deck JSON (`main_deck`, `sideboard_deck`).

### New Render Path

Add a parallel renderer alongside the existing `cardRow` / `renderCategories` functions:

| Function | Purpose |
|----------|---------|
| `cardTile(name, qty)` | Create a grid cell: `<img>` + optional qty badge |
| `renderVisualCategories(cards)` | Group by creatures/spells/lands, render image grids |
| `renderVisualFlat(cards)` | Flat grid for sideboard |
| `renderDeck(entry, mode)` | Branch on `mode` (`"text"` \| `"visual"`) when building columns |

The view toggle updates `deckViewMode` state and re-renders the current deck (or toggles CSS class on the container without full re-fetch).

### CSS

New classes in `style.css`:

```css
.deck-view-toggle { /* icon button in deck-actions */ }
.deck-visual-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(72px, 1fr)); gap: 6px; }
.card-tile { position: relative; aspect-ratio: 488 / 680; }
.card-tile img { width: 100%; border-radius: 4px; }
.card-tile-qty { /* absolute badge, top-right */ }
```

Grid column count should adapt to viewport width — more columns on desktop, fewer on phone. Respect the existing dark/light theme.

### Performance

A full Pauper deck has ~20–30 unique cards (60 total copies). Loading 30 small Scryfall images per deck is manageable with lazy loading, but users scrolling quickly through the carousel may trigger many requests.

Mitigations:

- Lazy-load images only when the deck slide is active
- Cancel or ignore in-flight image loads when the user scrolls to the next deck
- Optionally cache image URLs in a `Map` keyed by card name (URL is deterministic)
- Do not prefetch images for off-screen decks

### Scryfall Rate Limits

Scryfall asks clients to cache images and avoid burst traffic. Lazy loading plus only rendering the visible deck should stay within reasonable use. If needed, a client-side image cache (`<img>` elements kept in a hidden pool) can reduce duplicate fetches when the same cards appear across decks.

## Example

**Text view (current):**

```
Creatures (12)
4 Kitchen Imp
4 Voldaren Epicure
4 Goblin Tomb Raider
...
```

**Visual view (proposed):**

A grid of card thumbnails with `4` badges on Kitchen Imp, Voldaren Epicure, etc., grouped under "Main Deck" and "Sideboard" headings.

## Dependencies

| Dependency | Required for |
|------------|-------------|
| Scryfall image API | Card art (already used for preview) |
| Existing deck JSON structure | Card names and quantities |
| `flatGroup` / `categorizeCards` helpers | Sorting and grouping logic (reuse) |

No dependency on other feature docs.

## Open Questions

- Should visual view be the default on mobile/tablet and text view on desktop, or one global preference?
- Flat grid per section vs. keeping Creatures / Spells / Lands sub-headings in visual mode?
- How to represent duplicate copies — quantity badge only, or stack offset shadows (e.g., show 4 copies as a fanned stack)?
- Double-faced cards and split cards: Scryfall `named` returns the front face by default — is that sufficient?
- Should the toggle live in the deck header (always visible) or in `deck-actions` next to Export?
- Bandwidth on slow connections: offer a "low bandwidth" fallback that stays on text view, or load visual view on demand only?
- Accessibility: visual mode needs `alt` text per card and keyboard focus for the toggle; should quantity be exposed to screen readers on each tile?
