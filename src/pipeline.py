"""End-to-end crawl pipeline for Merchant Scroll.

Discovers new Pauper tournaments on MTGO, crawls those not already
stored locally, refreshes active leagues and recent empty placeholders,
enriches with color data, updates the index, and writes the info.json
timestamp.
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
from .refresh_policy import (
    prune_empty_raw_files,
    save_tournament_if_nonempty,
    should_crawl_mtgo,
    should_import_pauperwave,
    stored_deck_counts,
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

def site_name_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def crawl_new_tournaments(
    color_lookup: dict[str, list[str]],
) -> tuple[list[str], bool]:
    """Crawl new Pauper tournaments and refresh leagues or empty placeholders.

    Returns ``(saved_site_names, data_changed)``.
    """
    print("Discovering tournaments from mtgo.com...")
    urls = discover_pauper_urls()
    print(f"Found {len(urls)} Pauper tournament(s) on MTGO.")

    counts = stored_deck_counts(RAW_DIR)
    existing = set(counts)
    today = datetime.now().date()
    to_crawl: list[tuple[str, str]] = []
    seen: set[str] = set()
    for url in urls:
        site_name = site_name_from_url(url)
        if site_name in seen:
            continue
        seen.add(site_name)
        if should_crawl_mtgo(
            site_name,
            exists=site_name in existing,
            stored_deck_count=counts.get(site_name),
            today=today,
        ):
            to_crawl.append((url, site_name))

    if not to_crawl:
        print("No new tournaments to crawl.")
        return [], False

    new_count = sum(1 for _, sn in to_crawl if sn not in existing)
    refresh_count = len(to_crawl) - new_count
    print(
        f"{len(to_crawl)} tournament(s) to crawl"
        f" ({new_count} new, {refresh_count} refresh).\n"
    )
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    saved: list[str] = []
    changed = False
    for url, site_name in to_crawl:
        print(f"  Crawling {site_name}...")
        data = crawl_decks(url, color_lookup=color_lookup)
        if data is None:
            print("  Skipped (crawl failed).")
            continue

        archetype_map = load_archetype_dictionary()
        if archetype_map:
            enrich_archetypes(data, archetype_map)

        wrote, deck_count = save_tournament_if_nonempty(
            RAW_DIR, site_name, data, ensure_ascii=False
        )
        if wrote:
            changed = True
        if deck_count > 0:
            saved.append(site_name)

    print(f"\nCrawled {len(saved)} tournament(s) with decklists.")
    return saved, changed


def crawl_pauperwave_tournaments(
    color_lookup: dict[str, list[str]],
    token: str | None = None,
) -> tuple[list[str], bool]:
    """Crawl new Pauperwave IRL tournaments and retry empty placeholders.

    Returns ``(saved_site_names, data_changed)``.
    """
    print("Discovering tournaments from Pauperwave...")
    try:
        files = discover_pauperwave_files(token=token)
    except Exception as e:
        print(f"  Failed to list Pauperwave files: {e}")
        return [], False

    print(f"Found {len(files)} Pauperwave tournament file(s).")

    counts = stored_deck_counts(RAW_DIR)
    to_import: list[tuple[dict, str]] = []
    for file_info in files:
        slug = file_info["name"].replace(".md", "")
        site_name = f"pauperwave-{slug}"
        if should_import_pauperwave(
            site_name,
            exists=site_name in counts,
            stored_deck_count=counts.get(site_name),
        ):
            to_import.append((file_info, site_name))

    if not to_import:
        print("No Pauperwave tournaments to import.")
        return [], False

    new_count = sum(1 for _, sn in to_import if sn not in counts)
    refresh_count = len(to_import) - new_count
    print(
        f"{len(to_import)} Pauperwave tournament(s) to import"
        f" ({new_count} new, {refresh_count} refresh).\n"
    )
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    saved: list[str] = []
    changed = False
    for file_info, site_name in to_import:
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

        wrote, deck_count = save_tournament_if_nonempty(RAW_DIR, site_name, data)
        if wrote:
            changed = True
        if deck_count > 0:
            saved.append(site_name)

    print(f"\nImported {len(saved)} Pauperwave tournament(s) with decklists.")
    return saved, changed


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


def rebuild_index() -> bool:
    """Regenerate index.json from raw tournament files, sorted by date desc.

    Returns whether the index content changed.
    """
    if not RAW_DIR.exists():
        print("No raw directory found, skipping index generation.")
        return False

    fix_league_starttimes()
    prune_empty_raw_files(RAW_DIR)

    index = []
    for path in RAW_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        deck_count = len(data.get("decklists", []))
        if deck_count == 0:
            continue
        site_name = data.get("site_name", path.stem)
        index.append({
            "site_name": path.stem,
            "starttime": canonical_starttime(site_name, data.get("starttime", "")),
            "deck_count": deck_count,
        })

    index.sort(key=lambda x: x["starttime"], reverse=True)
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    new_text = json.dumps(index, indent=2) + "\n"
    previous = INDEX_PATH.read_text() if INDEX_PATH.exists() else ""
    INDEX_PATH.write_text(new_text)
    print(f"Index updated: {len(index)} tournaments.")
    return new_text != previous


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
    crawled, mtgo_changed = crawl_new_tournaments(color_lookup)
    pw_crawled, pw_changed = crawl_pauperwave_tournaments(
        color_lookup, token=token
    )

    if pw_crawled:
        rebuild_archetype_dictionary()

    archetype_map = load_archetype_dictionary()
    classified = classify_unlabeled_mtgo_decks(archetype_map)
    normalized = normalize_archetype_labels()
    if classified:
        print(f"Classified {classified} MTGO decklist(s).")

    all_crawled = crawled + pw_crawled
    data_changed = mtgo_changed or pw_changed or bool(classified)

    if data_changed:
        index_changed = rebuild_index()
        rebuild_players_index()
        rebuild_player_profiles()
        if normalized:
            print(f"Archetype labels normalized: {normalized} decklists.")
        rebuild_deck_profiles()
        if index_changed or all_crawled or classified:
            write_info()
        else:
            print("Data pruned — index rebuilt without new decklists.")
    else:
        pruned = prune_empty_raw_files(RAW_DIR)
        if pruned:
            rebuild_index()
            rebuild_players_index()
            rebuild_player_profiles()
            rebuild_deck_profiles()
            write_info()
        else:
            print("Nothing new — index unchanged.")

    return all_crawled
