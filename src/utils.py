import re
from datetime import datetime
from functools import reduce


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


def get_league_record(wins_data):
    return f"({wins_data['wins']}-{wins_data['losses']})"


def parse_decklist(decklist: dict, tournament: dict, **kwargs) -> dict:
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
