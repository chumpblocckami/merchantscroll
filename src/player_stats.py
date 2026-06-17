"""Generate per-player profile statistics from tournament data."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from .utils import canonical_starttime

RAW_DIR = Path("assets/pauper/raw")
PLAYERS_INDEX_PATH = Path("assets/pauper/players.json")
PROFILES_DIR = Path("assets/pauper/players")
IDENTITIES_PATH = Path("players/identities.json")

CURRENT_YEAR = "2026"


def load_identities() -> dict[str, dict]:
    if not IDENTITIES_PATH.exists():
        return {}
    try:
        raw = json.loads(IDENTITIES_PATH.read_text())
        return {k.strip().lower(): v for k, v in raw.items()}
    except (json.JSONDecodeError, OSError):
        return {}


def _tournament_type(site_name: str) -> str:
    if site_name.startswith("pauperwave-"):
        return "irl"
    lower = site_name.lower()
    for kind in ("league", "challenge", "showcase", "preliminary", "premier", "classic"):
        if kind in lower:
            return kind
    return "other"


def _is_league_trophy(wins: dict | None) -> bool:
    if not wins:
        return False
    return str(wins.get("wins", "")) == "5" and str(wins.get("losses", "")) == "0"


def _color_label(colors: list[str] | None) -> str:
    if not colors:
        return "Unknown"
    return "".join(colors) if colors != ["C"] else "Colorless"


def _identity_keys(username: str, identities: dict[str, dict]) -> set[str]:
    keys = {username.lower()}
    identity = identities.get(username.lower(), {})
    pw_name = identity.get("pauperwave_name", "").strip().lower()
    if pw_name:
        keys.add(pw_name)
    irl_name = identity.get("irl_name", "").strip().lower()
    if irl_name:
        keys.add(irl_name)
    return keys


def _match_player(player_name: str, keys: set[str]) -> bool:
    return player_name.strip().lower() in keys


def rebuild_player_profiles(
    raw_dir: Path = RAW_DIR,
    profiles_dir: Path = PROFILES_DIR,
) -> int:
    """Build profile JSON files for all players. Returns number of profiles written."""
    identities = load_identities()

    # username -> aggregate data
    profiles: dict[str, dict] = {}
    display_names: dict[str, str] = {}
    identity_by_key: dict[str, str] = {}

    for mtgo_user, identity in identities.items():
        canonical = mtgo_user.lower()
        for key in _identity_keys(canonical, identities):
            identity_by_key[key] = canonical

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
        date = canonical_starttime(
            site_name, data.get("starttime", "")
        )[:10]
        year = date[:4] if len(date) >= 4 else ""
        source = data.get("source", "pauperwave" if site_name.startswith("pauperwave-") else "mtgo")

        for deck in data.get("decklists", []):
            player = deck.get("player", "").strip()
            if not player:
                continue

            player_key = player.lower()
            username = identity_by_key.get(player_key, player_key)
            if username not in profiles:
                profiles[username] = {
                    "username": username,
                    "display_name": player if player_key == username else player,
                    "irl_name": identities.get(username, {}).get("irl_name"),
                    "stats": {
                        "total_entries": 0,
                        "league_trophies": 0,
                        "league_trophies_yearly": 0,
                        "challenge_wins": 0,
                        "challenge_losses": 0,
                        "irl_top8": 0,
                    },
                    "favorite_decks": Counter(),
                    "recent_entries": [],
                }
                display_names[username] = player

            if player_key == username:
                display_names[username] = player

            profile = profiles[username]
            stats = profile["stats"]
            stats["total_entries"] += 1

            wins = deck.get("wins")
            if tournament_type == "league" and _is_league_trophy(wins):
                stats["league_trophies"] += 1
                trophy_counts_alltime[username] += 1
                if year == CURRENT_YEAR:
                    stats["league_trophies_yearly"] += 1
                    trophy_counts_yearly[username] += 1

            if tournament_type == "challenge" and wins:
                try:
                    stats["challenge_wins"] += int(wins.get("wins", 0))
                    stats["challenge_losses"] += int(wins.get("losses", 0))
                except (TypeError, ValueError):
                    pass

            if tournament_type == "irl":
                rank = deck.get("final_rank")
                if isinstance(rank, int) and rank <= 8:
                    stats["irl_top8"] += 1

            archetype = deck.get("archetype") or _color_label(deck.get("colors"))
            profile["favorite_decks"][archetype] += 1

            record = ""
            if wins and "wins" in wins and "losses" in wins:
                record = f"{wins['wins']}-{wins['losses']}"

            profile["recent_entries"].append({
                "site_name": site_name,
                "tournament": tournament_name,
                "date": date,
                "player": player,
                "archetype": deck.get("archetype") or "",
                "colors": deck.get("colors") or [],
                "record": record,
                "final_rank": deck.get("final_rank"),
                "source": source,
                "type": tournament_type,
            })

    def _rank_map(counts: Counter[str]) -> dict[str, int]:
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return {user: idx + 1 for idx, (user, _) in enumerate(ranked)}

    yearly_ranks = _rank_map(trophy_counts_yearly)
    alltime_ranks = _rank_map(trophy_counts_alltime)
    yearly_pool = len(trophy_counts_yearly)
    alltime_pool = len(trophy_counts_alltime)

    profiles_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for username, profile in profiles.items():
        stats = profile["stats"]
        cw = stats["challenge_wins"]
        cl = stats["challenge_losses"]
        total_matches = cw + cl
        stats["challenge_win_pct"] = round(100 * cw / total_matches) if total_matches else None
        stats["league_trophy_rank_yearly"] = yearly_ranks.get(username)
        stats["league_trophy_rank_alltime"] = alltime_ranks.get(username)
        stats["league_trophy_players_yearly"] = yearly_pool
        stats["league_trophy_players_alltime"] = alltime_pool

        profile["display_name"] = display_names.get(username, username)
        profile["irl_name"] = identities.get(username, {}).get("irl_name")
        profile["favorite_decks"] = [
            {"archetype": name, "count": count}
            for name, count in profile["favorite_decks"].most_common(10)
        ]
        profile["recent_entries"].sort(key=lambda e: e["date"], reverse=True)
        profile["recent_entries"] = profile["recent_entries"][:25]

        out_path = profiles_dir / f"{username}.json"
        out_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n")
        written += 1

    for path in profiles_dir.glob("*.json"):
        if path.stem not in profiles:
            path.unlink()

    print(f"Player profiles updated: {written} players.")
    return written
