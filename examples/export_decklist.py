# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Export a decklist from local data in a readable or importable format.

Reads a stored tournament JSON and prints a specific player's decklist
in MTGO-compatible text format (pasteable into MTGO or Moxfield).

Usage:
    uv run examples/export_decklist.py TOURNAMENT_FILE PLAYER
    uv run examples/export_decklist.py assets/pauper/raw/pauper-league-2026-06-0510636.json __forge__
"""

import argparse
import json
import sys
from pathlib import Path


def export_deck(deck: dict) -> str:
    lines = []
    for card in sorted(deck.get("main_deck", []), key=lambda c: c["card_attributes"]["card_name"]):
        lines.append(f"{card['qty']} {card['card_attributes']['card_name']}")
    lines.append("")
    lines.append("Sideboard")
    for card in sorted(
        deck.get("sideboard_deck", []), key=lambda c: c["card_attributes"]["card_name"]
    ):
        lines.append(f"{card['qty']} {card['card_attributes']['card_name']}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Export a decklist as text")
    parser.add_argument("file", help="Path to a tournament JSON file")
    parser.add_argument("player", nargs="?", help="Player name (omit to list all players)")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    data = json.loads(path.read_text())
    decklists = data.get("decklists", [])

    if not args.player:
        print(f"{data.get('description', '?')} — {data.get('starttime', '?')}")
        print(f"{len(decklists)} players:\n")
        for d in decklists:
            record = ""
            if "wins" in d:
                record = f"  ({d['wins'].get('wins', '?')}-{d['wins'].get('losses', '?')})"
            print(f"  {d['player']}{record}")
        return

    match = [d for d in decklists if d["player"].lower() == args.player.lower()]
    if not match:
        print(f"Player '{args.player}' not found. Available players:")
        for d in decklists:
            print(f"  {d['player']}")
        sys.exit(1)

    deck = match[0]
    print(f"// {deck['player']} — {data.get('description', '?')} — {data.get('starttime', '?')}")
    if "wins" in deck:
        print(f"// Record: {deck['wins'].get('wins', '?')}-{deck['wins'].get('losses', '?')}")
    print()
    print(export_deck(deck))


if __name__ == "__main__":
    main()
