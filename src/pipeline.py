"""End-to-end crawl pipeline for Merchant Scroll.

Discovers new Pauper tournaments on MTGO, crawls only those not already
stored locally, enriches with color data, updates the index, and writes
the info.json timestamp.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from .crawler import crawl_decks, crawl_tournaments
from .scryfall import build_color_lookup, download_oracle_cards
from .utils import extract_date


RAW_DIR = Path("assets/pauper/raw")
INDEX_PATH = Path("assets/pauper/index.json")
INFO_PATH = Path("info.json")


def discover_pauper_urls() -> list[str]:
    """Return tournament URLs filtered to Pauper only, sorted newest first."""
    urls = crawl_tournaments()
    pauper = [u for u in urls if "/pauper-" in u.lower()]
    return sorted(pauper, key=extract_date, reverse=True)


def existing_site_names() -> set[str]:
    """Return the set of site_names already stored locally."""
    if not RAW_DIR.exists():
        return set()
    return {p.stem for p in RAW_DIR.glob("*.json")}


def site_name_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def crawl_new_tournaments(color_lookup: dict[str, list[str]]) -> list[str]:
    """Crawl all new Pauper tournaments.

    Returns a list of site_names that were newly crawled.
    """
    print("Discovering tournaments from mtgo.com...")
    urls = discover_pauper_urls()
    print(f"Found {len(urls)} Pauper tournament(s) on MTGO.")

    existing = existing_site_names()
    new_urls = [(u, site_name_from_url(u)) for u in urls if site_name_from_url(u) not in existing]

    if not new_urls:
        print("No new tournaments to crawl.")
        return []

    print(f"{len(new_urls)} new tournament(s) to crawl.\n")
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    crawled = []
    for url, site_name in new_urls:
        print(f"  Crawling {site_name}...")
        data = crawl_decks(url, color_lookup=color_lookup)
        if data is None:
            print(f"  Skipped (crawl failed).")
            continue

        deck_count = len(data.get("decklists", []))
        out_path = RAW_DIR / f"{site_name}.json"
        out_path.write_text(json.dumps(data, indent=2))
        print(f"  Saved ({deck_count} decks).")
        crawled.append(site_name)

    print(f"\nCrawled {len(crawled)} new tournament(s).")
    return crawled


def rebuild_index():
    """Regenerate index.json from all raw tournament files, sorted by date desc."""
    if not RAW_DIR.exists():
        print("No raw directory found, skipping index generation.")
        return

    index = []
    for path in RAW_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        index.append({
            "site_name": path.stem,
            "starttime": data.get("starttime", ""),
            "deck_count": len(data.get("decklists", [])),
        })

    index.sort(key=lambda x: x["starttime"], reverse=True)
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, indent=2))
    print(f"Index updated: {len(index)} tournaments.")


def write_info():
    """Write info.json with the current UTC timestamp."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    INFO_PATH.write_text(json.dumps({"last_update": now}, indent=2))
    print(f"info.json updated: {now}")


def run(refresh_scryfall: bool = False):
    """Full pipeline: download scryfall data, crawl new tournaments, rebuild index."""
    cache = download_oracle_cards()
    if refresh_scryfall and cache.exists():
        cache.unlink()
        download_oracle_cards()

    print("Building color lookup...")
    color_lookup = build_color_lookup()
    print(f"Loaded {len(color_lookup)} card entries.\n")

    crawled = crawl_new_tournaments(color_lookup)

    if crawled:
        rebuild_index()
        write_info()
    else:
        print("Nothing new — index unchanged.")

    return crawled
