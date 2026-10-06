# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "beautifulsoup4",
# ]
# ///
"""Main crawl pipeline for Merchant Scroll.

Discovers new Pauper tournaments on MTGO, crawls only those not already
stored, enriches with deck color data via Scryfall, rebuilds the index,
and updates the last-update timestamp.

This is the script that GitHub Actions runs on a cron schedule.

Usage:
    uv run crawl.py
    uv run crawl.py --refresh-scryfall
"""

import argparse

from src.pipeline import run


def main():
    """Run the crawl pipeline and fail the process only on unexpected sources."""
    parser = argparse.ArgumentParser(description="Crawl new Pauper tournaments from MTGO")
    parser.add_argument(
        "--refresh-scryfall",
        action="store_true",
        help="Force re-download of Scryfall oracle data",
    )
    args = parser.parse_args()

    crawled, failed_sources = run(refresh_scryfall=args.refresh_scryfall)
    if crawled:
        print(f"\nDone. {len(crawled)} new tournament(s) added:")
        for name in crawled:
            print(f"  {name}")
    else:
        print("\nDone. No new data.")

    if failed_sources:
        print(f"\nSource(s) failed: {', '.join(failed_sources)}")
        # MTGO timeouts from GitHub runners are routine; a red X on those
        # floods the Actions inbox. Fail the job only for unexpected sources.
        unexpected = [name for name in failed_sources if name != "mtgo"]
        if unexpected:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
