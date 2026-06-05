# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "beautifulsoup4",
# ]
# ///
"""Crawl a single MTGO tournament and print its decklists.

Fetches one tournament page, parses the embedded data, and prints
a summary of every decklist. Optionally saves the result to a JSON file.

Usage:
    uv run examples/crawl_single_tournament.py URL
    uv run examples/crawl_single_tournament.py URL --save output.json
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.crawler import crawl_decks


def main():
    parser = argparse.ArgumentParser(description="Crawl a single MTGO tournament")
    parser.add_argument("url", help="Full MTGO tournament URL")
    parser.add_argument("--save", "-s", help="Save result to a JSON file")
    args = parser.parse_args()

    print(f"Crawling {args.url}...")
    data = crawl_decks(args.url)

    if data is None:
        print("Failed to crawl tournament.")
        sys.exit(1)

    print(f"\n{data['description']} — {data['starttime']}")
    print(f"Site name: {data['site_name']}")
    print(f"Decklists: {len(data['decklists'])}\n")

    for i, deck in enumerate(data["decklists"], 1):
        main_count = sum(int(c["qty"]) for c in deck["main_deck"])
        side_count = sum(int(c["qty"]) for c in deck["sideboard_deck"])
        record = ""
        if "wins" in deck:
            record = f" ({deck['wins'].get('wins', '?')}-{deck['wins'].get('losses', '?')})"
        print(f"  {i:>2}. {deck['player']}{record}  —  {main_count} main, {side_count} side")

    if args.save:
        with open(args.save, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\nSaved to {args.save}")


if __name__ == "__main__":
    main()
