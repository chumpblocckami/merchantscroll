"""End-to-end crawl pipeline for Merchant Scroll.

Discovers new Pauper tournaments on MTGO, crawls those not already
stored locally (and re-crawls same-day events whose decklists may still
be updating), enriches with color data, updates the index, and writes
the info.json timestamp.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .classifier import (
    classify_unlabeled_mtgo_decks,
    normalize_archetype_labels,
    enrich_archetypes,
    load_archetype_dictionary,
    rebuild_archetype_dictionary,
)
from .crawler import crawl_decks, crawl_tournaments
from .deck_stats import rebuild_deck_profiles
from .player_stats import rebuild_player_profiles
from .pauperwave_crawler import (
    discover_pauperwave_files,
    fetch_markdown,
    parse_tournament_file,
)
from .scryfall import build_color_lookup, download_oracle_cards
from .utils import canonical_starttime, extract_date


RAW_DIR = Path("assets/pauper/raw")
INDEX_PATH = Path("assets/pauper/index.json")
PLAYERS_PATH = Path("assets/pauper/players.json")
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
    """Crawl new Pauper tournaments and refresh same-day leagues.

    Returns a list of site_names that were crawled or refreshed.
    """
    print("Discovering tournaments from mtgo.com...")
    urls = discover_pauper_urls()
    print(f"Found {len(urls)} Pauper tournament(s) on MTGO.")

    existing = existing_site_names()
    today = datetime.now().date().isoformat()
    to_crawl = [
        (u, site_name_from_url(u))
        for u in urls
        if site_name_from_url(u) not in existing or today in site_name_from_url(u)
    ]

    if not to_crawl:
        print("No new tournaments to crawl.")
        return []

    new_count = sum(1 for _, sn in to_crawl if sn not in existing)
    refresh_count = len(to_crawl) - new_count
    print(
        f"{len(to_crawl)} tournament(s) to crawl"
        f" ({new_count} new, {refresh_count} same-day refresh).\n"
    )
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    crawled = []
    for url, site_name in to_crawl:
        print(f"  Crawling {site_name}...")
        data = crawl_decks(url, color_lookup=color_lookup)
        if data is None:
            print(f"  Skipped (crawl failed).")
            continue

        archetype_map = load_archetype_dictionary()
        if archetype_map:
            enrich_archetypes(data, archetype_map)

        deck_count = len(data.get("decklists", []))
        out_path = RAW_DIR / f"{site_name}.json"
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print(f"  Saved ({deck_count} decks).")
        crawled.append(site_name)

    print(f"\nCrawled {len(crawled)} tournament(s).")
    return crawled


def crawl_pauperwave_tournaments(
    color_lookup: dict[str, list[str]],
    token: str | None = None,
) -> list[str]:
    """Crawl new Pauperwave IRL tournaments.

    Returns a list of site_names that were newly crawled.
    """
    print("Discovering tournaments from Pauperwave...")
    try:
        files = discover_pauperwave_files(token=token)
    except Exception as e:
        print(f"  Failed to list Pauperwave files: {e}")
        return []

    print(f"Found {len(files)} Pauperwave tournament file(s).")

    existing = existing_site_names()
    new_files = []
    for f in files:
        slug = f["name"].replace(".md", "")
        site_name = f"pauperwave-{slug}"
        if site_name not in existing:
            new_files.append((f, site_name))

    if not new_files:
        print("No new Pauperwave tournaments to import.")
        return []

    print(f"{len(new_files)} new Pauperwave tournament(s) to import.\n")
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    crawled = []
    for file_info, site_name in new_files:
        print(f"  Importing {file_info['name']}...")
        try:
            md = fetch_markdown(file_info["download_url"])
            data = parse_tournament_file(
                md, file_info["name"], color_lookup=color_lookup
            )
        except Exception as e:
            print(f"  Skipped (error: {e}).")
            continue

        if data is None:
            print("  Skipped (no decklists or unpublished).")
            continue

        deck_count = len(data.get("decklists", []))
        out_path = RAW_DIR / f"{site_name}.json"
        out_path.write_text(json.dumps(data, indent=2))
        print(f"  Saved ({deck_count} decks).")
        crawled.append(site_name)

    print(f"\nImported {len(crawled)} Pauperwave tournament(s).")
    return crawled


def fix_league_starttimes() -> int:
    """Correct drifted league starttimes in stored raw files.

    MTGO updates a league page's *starttime* when new decks are published,
    but the league week is fixed in the URL slug.  Returns files updated.
    """
    if not RAW_DIR.exists():
        return 0

    fixed = 0
    for path in RAW_DIR.glob("pauper-league-*.json"):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        site_name = data.get("site_name", path.stem)
        canonical = canonical_starttime(site_name, data.get("starttime", ""))
        if canonical != data.get("starttime"):
            data["starttime"] = canonical
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            fixed += 1
    if fixed:
        print(f"Fixed starttime on {fixed} league file(s).")
    return fixed


def rebuild_index():
    """Regenerate index.json from all raw tournament files, sorted by date desc."""
    if not RAW_DIR.exists():
        print("No raw directory found, skipping index generation.")
        return

    fix_league_starttimes()

    index = []
    for path in RAW_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        site_name = data.get("site_name", path.stem)
        index.append({
            "site_name": path.stem,
            "starttime": canonical_starttime(site_name, data.get("starttime", "")),
            "deck_count": len(data.get("decklists", [])),
        })

    index.sort(key=lambda x: x["starttime"], reverse=True)
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, indent=2))
    print(f"Index updated: {len(index)} tournaments.")


def rebuild_players_index():
    """Regenerate players.json mapping player names to their tournament site_names.

    Output format: {"playername": ["site_name_1", "site_name_2", ...], ...}
    Player names are stored lowercase for case-insensitive frontend matching.
    """
    if not RAW_DIR.exists():
        print("No raw directory found, skipping players index.")
        return

    players: dict[str, list[str]] = {}
    for path in RAW_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        site_name = path.stem
        for deck in data.get("decklists", []):
            name = deck.get("player", "").lower()
            if name:
                players.setdefault(name, []).append(site_name)

    PLAYERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAYERS_PATH.write_text(json.dumps(players, separators=(",", ":")))
    total = sum(len(v) for v in players.values())
    print(f"Players index updated: {len(players)} players, {total} entries.")


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

    rebuild_archetype_dictionary()

    token = os.environ.get("TOKEN") or os.environ.get("GITHUB_TOKEN")
    crawled = crawl_new_tournaments(color_lookup)
    pw_crawled = crawl_pauperwave_tournaments(color_lookup, token=token)

    if pw_crawled:
        rebuild_archetype_dictionary()

    archetype_map = load_archetype_dictionary()
    classified = classify_unlabeled_mtgo_decks(archetype_map)
    normalized = normalize_archetype_labels()
    if classified:
        print(f"Classified {classified} MTGO decklist(s).")

    all_crawled = crawled + pw_crawled

    if all_crawled or classified:
        rebuild_index()
        rebuild_players_index()
        rebuild_player_profiles()
        if normalized:
            print(f"Archetype labels normalized: {normalized} decklists.")
        rebuild_deck_profiles()
        write_info()
    else:
        print("Nothing new — index unchanged.")

    return all_crawled
