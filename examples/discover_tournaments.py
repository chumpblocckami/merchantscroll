# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "beautifulsoup4",
# ]
# ///
"""Discover available MTGO tournament URLs.

Lists all tournament decklists currently published on mtgo.com,
optionally filtering by format.

Usage:
    uv run examples/discover_tournaments.py
    uv run examples/discover_tournaments.py --format pauper
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.crawler import crawl_tournaments
from src.utils import extract_date


def main():
    parser = argparse.ArgumentParser(description="Discover MTGO tournaments")
    parser.add_argument("--format", "-f", help="Filter by format (e.g. pauper, modern)")
    args = parser.parse_args()

    print("Fetching tournament list from mtgo.com...")
    urls = crawl_tournaments()
    urls = sorted(urls, key=extract_date, reverse=True)

    if args.format:
        urls = [u for u in urls if args.format.lower() in u.lower()]

    print(f"\nFound {len(urls)} tournament(s):\n")
    for url in urls:
        slug = url.rstrip("/").split("/")[-1]
        date = extract_date(url)
        print(f"  {date}  {slug}")
        print(f"          {url}")


if __name__ == "__main__":
    main()
