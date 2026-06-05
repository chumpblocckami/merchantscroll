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
        decklists.append(minified_deck)

    minified["decklists"] = decklists
    return minified


def enrich_deck_colors(
    tournament_data: dict, color_lookup: dict[str, list[str]]
) -> dict:
    """Add a ``colors`` array to each decklist in a tournament.

    Color identity is the union of all non-land card color identities.
    Lands are excluded. A deck with no colored non-land cards gets ``["C"]``.
    Mutates and returns *tournament_data*.
    """
    for deck in tournament_data.get("decklists", []):
        colors: set[str] = set()
        for card in deck.get("main_deck", []) + deck.get("sideboard_deck", []):
            card_type = (card.get("card_attributes", {}).get("card_type", "")).strip()
            if card_type == "LAND":
                continue
            card_name = card.get("card_attributes", {}).get("card_name", "")
            identity = color_lookup.get(card_name, [])
            colors.update(identity)

        deck["colors"] = sorted(colors) if colors else ["C"]

    return tournament_data
