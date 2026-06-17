"""Generate per-archetype deck profile statistics from tournament data."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .player_stats import CURRENT_YEAR, _color_label, _is_league_trophy, _tournament_type
from .utils import canonical_starttime

RAW_DIR = Path("assets/pauper/raw")
DECKS_INDEX_PATH = Path("assets/pauper/decks/index.json")
PROFILES_DIR = Path("assets/pauper/decks")


def archetype_slug(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug or "unknown"


def _deck_name(deck: dict) -> str:
    return deck.get("archetype") or _color_label(deck.get("colors"))


def rebuild_deck_profiles(
    raw_dir: Path = RAW_DIR,
    profiles_dir: Path = PROFILES_DIR,
) -> int:
    """Build profile JSON files for all deck archetypes. Returns profiles written."""
    profiles: dict[str, dict] = {}
    slug_by_name: dict[str, str] = {}
    pilot_counts: dict[str, Counter[str]] = defaultdict(Counter)
    trophy_counts_yearly: Counter[str] = Counter()
    trophy_counts_alltime: Counter[str] = Counter()

    for path in raw_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        site_name = data.get("site_name", path.stem)
        tournament_type = _tournament_type(site_name)
        tournament_name = data.get("description", site_name)
        date = canonical_starttime(site_name, data.get("starttime", ""))[:10]
        year = date[:4] if len(date) >= 4 else ""
        source = data.get(
            "source",
            "pauperwave" if site_name.startswith("pauperwave-") else "mtgo",
        )

        for deck in data.get("decklists", []):
            archetype = _deck_name(deck)
            if not archetype:
                continue

            slug = slug_by_name.setdefault(archetype, archetype_slug(archetype))
            if slug not in profiles:
                profiles[slug] = {
                    "archetype": archetype,
                    "slug": slug,
                    "stats": {
                        "total_entries": 0,
                        "league_entries": 0,
                        "league_trophies": 0,
                        "league_trophies_yearly": 0,
                        "challenge_appearances": 0,
                        "challenge_wins": 0,
                        "challenge_losses": 0,
                        "irl_top8": 0,
                    },
                    "recent_entries": [],
                }

            profile = profiles[slug]
            stats = profile["stats"]
            stats["total_entries"] += 1

            player = deck.get("player", "").strip()
            if player:
                pilot_counts[slug][player] += 1

            wins = deck.get("wins")

            if tournament_type == "league":
                stats["league_entries"] += 1
                if _is_league_trophy(wins):
                    stats["league_trophies"] += 1
                    trophy_counts_alltime[slug] += 1
                    if year == CURRENT_YEAR:
                        stats["league_trophies_yearly"] += 1
                        trophy_counts_yearly[slug] += 1

            if tournament_type == "challenge":
                stats["challenge_appearances"] += 1
                if wins:
                    try:
                        stats["challenge_wins"] += int(wins.get("wins", 0))
                        stats["challenge_losses"] += int(wins.get("losses", 0))
                    except (TypeError, ValueError):
                        pass

            if tournament_type == "irl":
                rank = deck.get("final_rank")
                if isinstance(rank, int) and rank <= 8:
                    stats["irl_top8"] += 1

            record = ""
            if wins and "wins" in wins and "losses" in wins:
                record = f"{wins['wins']}-{wins['losses']}"

            profile["recent_entries"].append({
                "site_name": site_name,
                "tournament": tournament_name,
                "date": date,
                "player": player,
                "colors": deck.get("colors") or [],
                "record": record,
                "final_rank": deck.get("final_rank"),
                "source": source,
                "type": tournament_type,
            })

    def _rank_map(counts: Counter[str]) -> dict[str, int]:
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return {slug: idx + 1 for idx, (slug, _) in enumerate(ranked)}

    yearly_ranks = _rank_map(trophy_counts_yearly)
    alltime_ranks = _rank_map(trophy_counts_alltime)
    yearly_pool = len(trophy_counts_yearly)
    alltime_pool = len(trophy_counts_alltime)

    profiles_dir.mkdir(parents=True, exist_ok=True)
    index = []

    written = 0
    for slug, profile in profiles.items():
        stats = profile["stats"]
        cw = stats["challenge_wins"]
        cl = stats["challenge_losses"]
        total_matches = cw + cl
        stats["challenge_win_pct"] = round(100 * cw / total_matches) if total_matches else None
        stats["league_trophy_rank_yearly"] = yearly_ranks.get(slug)
        stats["league_trophy_rank_alltime"] = alltime_ranks.get(slug)
        stats["league_trophy_decks_yearly"] = yearly_pool
        stats["league_trophy_decks_alltime"] = alltime_pool

        profile["top_pilots"] = [
            {"player": player, "count": count}
            for player, count in pilot_counts[slug].most_common(10)
        ]

        profile["recent_entries"].sort(key=lambda e: e["date"], reverse=True)
        profile["recent_entries"] = profile["recent_entries"][:25]

        out_path = profiles_dir / f"{slug}.json"
        out_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n")
        index.append({
            "slug": slug,
            "archetype": profile["archetype"],
            "entries": stats["total_entries"],
        })
        written += 1

    for path in profiles_dir.glob("*.json"):
        if path.name == "index.json":
            continue
        if path.stem not in profiles:
            path.unlink()

    index.sort(key=lambda item: (-item["entries"], item["archetype"].lower()))
    DECKS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    DECKS_INDEX_PATH.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")

    print(f"Deck profiles updated: {written} archetypes.")
    return written
