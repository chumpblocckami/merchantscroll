import re
from datetime import datetime
from functools import reduce
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain import Tournament


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


def get_challenge_record(winloss_data, player_id):
    for data in winloss_data:
        if data["loginid"] == player_id:
            return f"({data['wins']}-{data['losses']})"
    return "(record not available)"


def get_league_record(wins_data):
    return f"({wins_data['wins']}-{wins_data['losses']})"


def minify_tournament_data(data: dict) -> dict:
    """Strip tournament data to only the fields the frontend needs.

    Removes per-card metadata (IDs, rarity, color, set, etc.) that the
    index.html renderer never reads, keeping only card names and quantities.

    Args:
        data: Full tournament data dict from the MTGO crawler.

    Returns:
        A slimmed-down copy suitable for storage and frontend consumption.
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
                    "card_attributes": {"card_name": card["card_attributes"]["card_name"]},
                }
                for card in deck.get("main_deck", [])
            ],
            "sideboard_deck": [
                {
                    "qty": card["qty"],
                    "card_attributes": {"card_name": card["card_attributes"]["card_name"]},
                }
                for card in deck.get("sideboard_deck", [])
            ],
        }
        if "wins" in deck:
            minified_deck["wins"] = deck["wins"]
        decklists.append(minified_deck)

    minified["decklists"] = decklists
    return minified


def parse_decklist(decklist: dict, tournament: "Tournament", **kwargs) -> dict:
    return {
        "player": decklist["player"],
        "main": reduce(
            lambda acc, x: acc.update(
                {
                    x["card_attributes"]["card_name"]: acc.get(x["card_attributes"]["card_name"], 0)
                    + int(x["qty"])
                }
            )
            or acc,
            decklist["main_deck"],
            {},
        ),
        "side": reduce(
            lambda acc, x: acc.update(
                {
                    x["card_attributes"]["card_name"]: acc.get(x["card_attributes"]["card_name"], 0)
                    + int(x["qty"])
                }
            )
            or acc,
            decklist["sideboard_deck"],
            {},
        ),
        "date": tournament.reference_date,
        "tournament": tournament.name + " " + kwargs.get("record", "record unavailable"),
    }
