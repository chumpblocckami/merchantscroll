# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Analyze locally stored Pauper tournament data.

Reads the JSON files in assets/pauper/raw/ and prints statistics:
most played cards, most active players, tournament counts by type,
and color distribution across decks.

Usage:
    uv run examples/analyze_local_data.py
    uv run examples/analyze_local_data.py --year 2026
    uv run examples/analyze_local_data.py --top 20
"""

import argparse
import json
from collections import Counter
from pathlib import Path

COLOR_NAMES = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green", "C": "Colorless"}


def load_tournaments(raw_dir: Path, year: str | None = None) -> list[dict]:
    tournaments = []
    for path in sorted(raw_dir.glob("*.json")):
        if year and year not in path.name:
            continue
        try:
            tournaments.append(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return tournaments


def main():
    parser = argparse.ArgumentParser(description="Analyze local Pauper tournament data")
    parser.add_argument("--year", "-y", help="Filter by year (e.g. 2026)")
    parser.add_argument("--top", "-t", type=int, default=10, help="Top N results (default: 10)")
    args = parser.parse_args()

    raw_dir = Path(__file__).resolve().parent.parent / "assets" / "pauper" / "raw"
    if not raw_dir.exists():
        print(f"No data found at {raw_dir}")
        return

    tournaments = load_tournaments(raw_dir, args.year)
    if not tournaments:
        print("No tournaments found.")
        return

    total_decks = sum(len(t.get("decklists", [])) for t in tournaments)
    card_counts = Counter()
    player_counts = Counter()
    type_counts = Counter()
    color_counts = Counter()
    color_combo_counts = Counter()

    for t in tournaments:
        desc = t.get("description", "Unknown")
        type_counts[desc] += 1
        for deck in t.get("decklists", []):
            player_counts[deck.get("player", "?")] += 1
            for card in deck.get("main_deck", []):
                name = card.get("card_attributes", {}).get("card_name", "?")
                qty = int(card.get("qty", 0))
                card_counts[name] += qty
            colors = deck.get("colors", [])
            for c in colors:
                color_counts[c] += 1
            combo = "".join(sorted(colors)) if colors else "?"
            color_combo_counts[combo] += 1

    year_label = f" ({args.year})" if args.year else ""
    print(f"=== Pauper Stats{year_label} ===\n")
    print(f"Tournaments: {len(tournaments)}")
    print(f"Total decklists: {total_decks}")
    print(f"Unique players: {len(player_counts)}")
    print(f"Unique cards: {len(card_counts)}")

    print(f"\n--- Tournament types ---")
    for name, count in type_counts.most_common():
        print(f"  {count:>4}x  {name}")

    if color_counts:
        print(f"\n--- Color frequency (how many decks contain each color) ---")
        for c, count in color_counts.most_common():
            label = COLOR_NAMES.get(c, c)
            pct = count / total_decks * 100 if total_decks else 0
            print(f"  {label:>9} ({c}):  {count:>4} decks  ({pct:.1f}%)")

        print(f"\n--- Top {args.top} color combinations ---")
        for combo, count in color_combo_counts.most_common(args.top):
            pct = count / total_decks * 100 if total_decks else 0
            print(f"  {combo:>5}  {count:>4} decks  ({pct:.1f}%)")

    print(f"\n--- Top {args.top} most played cards (by total copies in maindecks) ---")
    for name, count in card_counts.most_common(args.top):
        print(f"  {count:>5}x  {name}")

    print(f"\n--- Top {args.top} most active players (by decklist count) ---")
    for name, count in player_counts.most_common(args.top):
        print(f"  {count:>4}x  {name}")


if __name__ == "__main__":
    main()
