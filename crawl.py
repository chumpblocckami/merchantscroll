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

The tournament data lives on Hugging Face (see ``src/hub.py``): it is pulled
first and every changed file is pushed back at the end.

Usage:
    uv run crawl.py
    uv run crawl.py --refresh-scryfall
    uv run crawl.py --build-only
"""

import argparse
import os

from src import hub
from src.pipeline import RAW_DIR, rebuild_derived_artifacts, run
from src.refresh_policy import STALE_AFTER_DAYS, days_since_newest_mtgo_event


def main():
    """Run the crawl pipeline; fail on unexpected sources or stale MTGO data."""
    parser = argparse.ArgumentParser(description="Crawl new Pauper tournaments from MTGO")
    parser.add_argument(
        "--refresh-scryfall",
        action="store_true",
        help="Force re-download of Scryfall oracle data",
    )
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Skip crawling; only rebuild the derived files from the dataset",
    )
    args = parser.parse_args()

    hub.pull()
    before = hub.fingerprint()
    if args.build_only:
        crawled, failed_sources = [], []
    else:
        crawled, failed_sources = run(refresh_scryfall=args.refresh_scryfall)

    # Scheduled runs redeploy only on new data; pushes and manual runs always
    # do, and the derived files are not in git, so they must be rebuilt here
    # when the crawl itself did not.
    always_deploy = os.environ.get("GITHUB_EVENT_NAME") != "schedule"
    if args.build_only or (always_deploy and hub.fingerprint() == before):
        rebuild_derived_artifacts(write_timestamp=False)

    changed = hub.push(before) if os.environ.get("HF_TOKEN") else hub.fingerprint() != before
    deploy = changed or always_deploy
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a") as f:
            f.write(f"deploy={str(deploy).lower()}\n")

    if crawled:
        print(f"\nDone. {len(crawled)} new tournament(s) added:")
        for name in crawled:
            print(f"  {name}")
    else:
        print("\nDone. No new data.")

    fail = False
    if failed_sources:
        print(f"\nSource(s) failed: {', '.join(failed_sources)}")
        # MTGO timeouts from GitHub runners are routine; a red X on those
        # floods the Actions inbox. Fail the job only for unexpected sources.
        fail = any(name != "mtgo" for name in failed_sources)

    # Tolerated MTGO failures must not hide a crawl that has stopped working.
    age = None if args.build_only else days_since_newest_mtgo_event(RAW_DIR)
    if age is not None and age > STALE_AFTER_DAYS:
        print(f"\nNewest MTGO tournament is {age} days old; MTGO crawling is broken.")
        fail = True

    if fail:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
