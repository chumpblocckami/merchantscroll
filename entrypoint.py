import os
import time
from datetime import datetime
from pathlib import Path

import requests
from git import Repo
from tqdm import tqdm

from src.constants.misc import FORMATS
from src.constants.paths import RAW_TOURNAMENT_PATH
from src.crawler import crawl_decks, crawl_tournaments
from src.pipeline import crawl_pauperwave_tournaments, rebuild_derived_artifacts
from src.classifier import (
    enrich_archetypes,
    load_archetype_dictionary,
    rebuild_archetype_dictionary,
)
from src.scryfall import build_color_lookup, download_oracle_cards
from src.refresh_policy import (
    save_tournament_if_nonempty,
    should_crawl_mtgo,
    stored_deck_counts,
)
from src.utils import extract_date


def slug_from_url(url: str) -> str:
    """Extract the tournament slug from an MTGO URL (last path segment)."""
    return url.rstrip("/").split("/")[-1]


def discover_new_tournaments(fmt: str) -> list[str]:
    """Return MTGO URLs for tournaments that should be crawled this run."""
    raw_dir = Path(f"./assets/{fmt}/raw")
    raw_dir.mkdir(parents=True, exist_ok=True)
    counts = stored_deck_counts(raw_dir)
    today = datetime.now().date()

    all_urls = crawl_tournaments()
    urls = [u for u in all_urls if fmt in u]
    urls = sorted(urls, key=extract_date, reverse=True)

    seen: set[str] = set()
    new_urls: list[str] = []
    for url in urls:
        slug = slug_from_url(url)
        if slug in seen:
            continue
        seen.add(slug)
        if should_crawl_mtgo(
            slug,
            exists=slug in counts,
            stored_deck_count=counts.get(slug),
            today=today,
        ):
            new_urls.append(url)
    return new_urls


def git_push_all(message: str) -> None:
    """Stage everything in assets/ and push in a single commit."""
    repo = Repo(Path.cwd())
    repo.remotes.origin.pull("main")
    repo.git.add("assets/")
    repo.git.add("archetypes/")
    if repo.is_dirty(untracked_files=True):
        repo.index.commit(message)
        repo.git.push("origin", "main")
        print(f"Pushed: {message}")
    else:
        print("No changes to push.")


def start_crawler():
    download_oracle_cards()
    color_lookup = build_color_lookup()
    print(f"Loaded {len(color_lookup)} Scryfall card entries for color enrichment.")

    rebuild_archetype_dictionary()

    crawled = 0
    skipped = 0
    data_changed = False

    for fmt in FORMATS:
        try:
            to_crawl = discover_new_tournaments(fmt)
        except requests.exceptions.RequestException as e:
            print(f"Failed to discover {fmt} tournaments: {e}")
            continue

        if not to_crawl:
            print(f"No new {fmt} tournaments.")
            continue

        print(f"Found {len(to_crawl)} new {fmt} tournament(s).")

        pbar = tqdm(to_crawl, desc=f"Crawling {fmt}")
        for url in pbar:
            pbar.set_description(slug_from_url(url))
            try:
                data = crawl_decks(url, color_lookup=color_lookup)
            except requests.exceptions.RequestException as e:
                print(f"Network error crawling {url}: {e}")
                skipped += 1
                continue

            if data is None:
                skipped += 1
                continue

            archetype_map = load_archetype_dictionary()
            if archetype_map:
                enrich_archetypes(data, archetype_map)

            site_name = data.get("site_name", slug_from_url(url))
            path = RAW_TOURNAMENT_PATH.format(deck_format=fmt, tournament_id=site_name)
            wrote, deck_count = save_tournament_if_nonempty(
                path.parent, site_name, data
            )
            if wrote:
                data_changed = True
            if deck_count > 0:
                crawled += 1
            elif not wrote:
                skipped += 1
            time.sleep(1)

    token = os.environ.get("TOKEN") or os.environ.get("GITHUB_TOKEN")
    pw_crawled, pw_changed = crawl_pauperwave_tournaments(color_lookup, token=token)
    crawled += len(pw_crawled)
    data_changed = data_changed or pw_changed

    if data_changed:
        summary = rebuild_derived_artifacts(refresh_dictionary=True)
        crawled += int(summary["classified"])
    else:
        print("Nothing new — skipping derived artifact rebuild.")

    print(f"Done. Crawled: {crawled}, Skipped: {skipped}")

    git_push_all(
        f"Crawled {crawled} tournament(s)" if crawled else "No tournament changes"
    )


if __name__ == "__main__":
    start_crawler()
