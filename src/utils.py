import re
from datetime import datetime


def normalize_date(date_str) -> str:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.date().isoformat()


def extract_date(url):
    match = re.search(r"(\d{4}-\d{2}-\d{2})", url)
    return match.group(1) if match else "0000-00-00"


def canonical_starttime(site_name: str, starttime: str) -> str:
    """Return the canonical calendar date for a tournament.

    MTGO league pages report *starttime* as the last publish date, which
    drifts as new decks are submitted.  The league week is encoded in
    *site_name* (e.g. ``pauper-league-2026-06-1710636``), so we prefer
    that date for leagues.
    """
    if "-league-" in site_name:
        url_date = extract_date(site_name)
        if url_date != "0000-00-00":
            return url_date
    return starttime or ""


def enrich_challenge_results(tournament_data: dict) -> dict:
    """Attach win/loss record and final rank to each challenge decklist.

    Uses the top-level ``winloss`` and ``final_rank`` arrays (keyed by
    ``loginid``) to populate per-deck ``wins`` and ``final_rank`` fields.
    Decklists are then sorted by final rank ascending (best placement first).
    Mutates and returns *tournament_data*.
    """
    winloss = tournament_data.get("winloss")
    final_rank = tournament_data.get("final_rank")

    if not winloss and not final_rank:
        return tournament_data

    wl_map: dict[str, dict] = {}
    for entry in (winloss or []):
        wl_map[str(entry["loginid"])] = {
            "wins": str(entry["wins"]),
            "losses": str(entry["losses"]),
        }

    rank_map: dict[str, int] = {}
    for entry in (final_rank or []):
        rank_map[str(entry["loginid"])] = int(entry["rank"])

    for deck in tournament_data.get("decklists", []):
        lid = str(deck.get("loginid", ""))
        if lid in wl_map:
            deck["wins"] = wl_map[lid]
        if lid in rank_map:
            deck["final_rank"] = rank_map[lid]

    if "decklists" in tournament_data:
        tournament_data["decklists"].sort(
            key=lambda d: d.get("final_rank", 9999)
        )

    return tournament_data


def minify_tournament_data(data: dict) -> dict:
    """Strip tournament data to only the fields the frontend needs.

    Keeps card names, quantities, and card types (for creature/spell/land
    categorization). Removes IDs, rarity, color, set, and other metadata.
    """
    minified: dict = {
        "description": data.get("description", data.get("name", "")),
        "starttime": data.get("starttime", data.get("publish_date", "")),
        "site_name": data.get("site_name", ""),
        "player_count": data.get("player_count", {}),
    }

    decklists = []
    for deck in data.get("decklists", []):
        minified_deck: dict = {
            "player": deck.get("player", ""),
            "main_deck": [
                {
                    "qty": card["qty"],
                    "card_attributes": {
                        "card_name": card["card_attributes"]["card_name"],
                        "card_type": card["card_attributes"].get("card_type", ""),
                    },
                }
                for card in deck.get("main_deck", [])
            ],
            "sideboard_deck": [
                {
                    "qty": card["qty"],
                    "card_attributes": {
                        "card_name": card["card_attributes"]["card_name"],
                        "card_type": card["card_attributes"].get("card_type", ""),
                    },
                }
                for card in deck.get("sideboard_deck", [])
            ],
        }
        if "wins" in deck:
            minified_deck["wins"] = deck["wins"]
        if "final_rank" in deck:
            minified_deck["final_rank"] = deck["final_rank"]
        if deck.get("archetype"):
            minified_deck["archetype"] = deck["archetype"]
        decklists.append(minified_deck)

    minified["decklists"] = decklists
    if minified["site_name"]:
        minified["starttime"] = canonical_starttime(
            minified["site_name"], minified["starttime"]
        )
    return minified


MTGO_COLOR_LETTERS = {
    "COLOR_WHITE": "W",
    "COLOR_BLUE": "U",
    "COLOR_BLACK": "B",
    "COLOR_RED": "R",
    "COLOR_GREEN": "G",
}


def _mtgo_colors(attributes: dict) -> list[str]:
    """Read colors off MTGO's own card attributes."""
    return [
        MTGO_COLOR_LETTERS[color]
        for color in attributes.get("colors") or []
        if color in MTGO_COLOR_LETTERS
    ]


def enrich_deck_colors(
    tournament_data: dict, color_lookup: dict[str, list[str]]
) -> dict:
    """Add a ``colors`` array to each decklist in a tournament.

    A deck's colors are the colors its main deck has to be able to produce.
    Lands are excluded, and so is the sideboard: those cards come in against
    specific matchups, and one of them should not recolor the whole deck the
    way a single sideboard Gut Shot used to make Mono Blue Terror blue-red.
    A deck with no colored main-deck cards gets ``["C"]``.
    Mutates and returns *tournament_data*.
    """
    for deck in tournament_data.get("decklists", []):
        colors: set[str] = set()
        for card in deck.get("main_deck", []):
            attributes = card.get("card_attributes", {})
            if attributes.get("card_type", "").strip() == "LAND":
                continue
            # A card Scryfall has no entry for falls back to MTGO's own colors;
            # a known card that needs no colored mana maps to [] and must not.
            required = color_lookup.get(attributes.get("card_name", ""))
            colors.update(_mtgo_colors(attributes) if required is None else required)

        deck["colors"] = sorted(colors) if colors else ["C"]

    return tournament_data
