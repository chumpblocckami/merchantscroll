# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Analyze locally stored tournament data.

Reads the JSON files in assets/pauper/raw/ and prints statistics:
most played cards, most active players, tournament counts by type, etc.

Usage:
    uv run examples/analyze_local_data.py
    uv run examples/analyze_local_data.py --year 2026
    uv run examples/analyze_local_data.py --top 20
"""

import argparse
import json
from collections import Counter
from pathlib import Path


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
    parser = argparse.ArgumentParser(description="Analyze local tournament data")
    parser.add_argument("--year", "-y", help="Filter by year (e.g. 2026)")
    parser.add_argument("--top", "-t", type=int, default=10, help="Top N results (default: 10)")
    parser.add_argument(
        "--format", "-f", default="pauper", help="Format directory (default: pauper)"
    )
    args = parser.parse_args()

    raw_dir = Path(__file__).resolve().parent.parent / "assets" / args.format / "raw"
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

    for t in tournaments:
        desc = t.get("description", "Unknown")
        type_counts[desc] += 1
        for deck in t.get("decklists", []):
            player_counts[deck.get("player", "?")] += 1
            for card in deck.get("main_deck", []):
                name = card.get("card_attributes", {}).get("card_name", "?")
                qty = int(card.get("qty", 0))
                card_counts[name] += qty

    year_label = f" ({args.year})" if args.year else ""
    print(f"=== {args.format.title()} Stats{year_label} ===\n")
    print(f"Tournaments: {len(tournaments)}")
    print(f"Total decklists: {total_decks}")
    print(f"Unique players: {len(player_counts)}")
    print(f"Unique cards: {len(card_counts)}")

    print(f"\n--- Tournament types ---")
    for name, count in type_counts.most_common():
        print(f"  {count:>4}x  {name}")

    print(f"\n--- Top {args.top} most played cards (by total copies in maindecks) ---")
    for name, count in card_counts.most_common(args.top):
        print(f"  {count:>5}x  {name}")

    print(f"\n--- Top {args.top} most active players (by decklist count) ---")
    for name, count in player_counts.most_common(args.top):
        print(f"  {count:>4}x  {name}")


if __name__ == "__main__":
    main()
