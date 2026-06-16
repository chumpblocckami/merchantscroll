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
from src.pipeline import crawl_pauperwave_tournaments
from src.classifier import (
    classify_unlabeled_mtgo_decks,
    enrich_archetypes,
    load_archetype_dictionary,
    rebuild_archetype_dictionary,
)
from src.player_stats import rebuild_player_profiles
from src.saver import save_json_locally
from src.scryfall import build_color_lookup, download_oracle_cards
from src.utils import extract_date


def slug_from_url(url: str) -> str:
    """Extract the tournament slug from an MTGO URL (last path segment)."""
    return url.rstrip("/").split("/")[-1]


def discover_new_tournaments(fmt: str) -> list[str]:
    """Return MTGO URLs for tournaments that haven't been crawled yet.

    Uses the filesystem (existing JSON files in assets/{fmt}/raw/) as the
    source of truth instead of a separate tournaments.txt manifest.
    Same-day tournaments are always re-crawled since their data may update.
    """
    raw_dir = Path(f"./assets/{fmt}/raw")
    raw_dir.mkdir(parents=True, exist_ok=True)
    existing = {f.stem for f in raw_dir.glob("*.json")}
    today = datetime.now().date().isoformat()

    all_urls = crawl_tournaments()
    urls = [u for u in all_urls if fmt in u]
    urls = sorted(urls, key=extract_date, reverse=True)

    new_urls = [
        u for u in urls
        if slug_from_url(u) not in existing or today in slug_from_url(u)
    ]
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
            save_json_locally(path, data)
            crawled += 1
            time.sleep(1)

    token = os.environ.get("TOKEN") or os.environ.get("GITHUB_TOKEN")
    pw_crawled = crawl_pauperwave_tournaments(color_lookup, token=token)
    crawled += len(pw_crawled)

    if pw_crawled:
        rebuild_archetype_dictionary()

    archetype_map = load_archetype_dictionary()
    classified = classify_unlabeled_mtgo_decks(archetype_map)
    if classified:
        print(f"Classified {classified} MTGO decklist(s).")
        crawled += classified

    rebuild_player_profiles()

    print(f"Done. Crawled: {crawled}, Skipped: {skipped}")

    git_push_all(
        f"Crawled {crawled} tournament(s)" if crawled else "Update player profiles"
    )


if __name__ == "__main__":
    start_crawler()
