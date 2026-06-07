# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
# ]
# ///
"""Enrich existing tournament JSON files with deck color data.

Downloads Scryfall oracle-cards bulk data (cached locally), then adds
a ``colors`` array to every decklist in the specified directory.

Usage:
    uv run examples/enrich_colors.py
    uv run examples/enrich_colors.py --dir assets/pauper/raw
    uv run examples/enrich_colors.py --refresh-cache
"""

import argparse
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.scryfall import build_color_lookup, download_oracle_cards, DEFAULT_CACHE_PATH
from src.utils import enrich_challenge_results, enrich_deck_colors


def main():
    parser = argparse.ArgumentParser(description="Enrich tournament data with deck colors")
    parser.add_argument(
        "--dir", "-d",
        default="assets/pauper/raw",
        help="Directory containing tournament JSON files (default: assets/pauper/raw)",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Force re-download of Scryfall oracle data",
    )
    args = parser.parse_args()

    raw_dir = Path(args.dir)
    if not raw_dir.exists():
        print(f"Directory not found: {raw_dir}")
        sys.exit(1)

    if args.refresh_cache and DEFAULT_CACHE_PATH.exists():
        DEFAULT_CACHE_PATH.unlink()
        print("Cache cleared.")

    download_oracle_cards()
    print("Building color lookup...")
    lookup = build_color_lookup()
    print(f"Loaded {len(lookup)} card entries.")

    json_files = sorted(raw_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {raw_dir}")
        sys.exit(1)

    enriched = 0
    for path in json_files:
        data = json.loads(path.read_text())
        enrich_challenge_results(data)
        enrich_deck_colors(data, lookup)
        path.write_text(json.dumps(data, indent=2))
        enriched += 1

    print(f"Enriched {enriched} tournament file(s).")


if __name__ == "__main__":
    main()
