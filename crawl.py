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
from src.pipeline import rebuild_derived_artifacts, run


def main():
    """Run the crawl pipeline and fail the process only on unexpected sources."""
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

    if failed_sources:
        print(f"\nSource(s) failed: {', '.join(failed_sources)}")
        # MTGO timeouts from GitHub runners are routine; a red X on those
        # floods the Actions inbox. Fail the job only for unexpected sources.
        unexpected = [name for name in failed_sources if name != "mtgo"]
        if unexpected:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
