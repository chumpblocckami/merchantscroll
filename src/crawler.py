import json
import re
import time
from functools import reduce
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
import glob 
from drawer import display_deck
from saver import Saver
import os 

def crawl_decks(tournament_url: str) -> None:
    # Headers to mimic a browser visit
    headers = {"User-Agent": "Mozilla/5.0"}

    # Fetch the deck page
    response = requests.get(tournament_url, headers=headers, timeout=20)
    if response.status_code != 200:
        print(f"Failed to retrieve the deck page. Status code: {response.status_code}")
        exit()

    # Parse the deck page
    soup = BeautifulSoup(response.text, "html.parser")

    pattern = r"window\.MTGO\.decklists\.data\s*=\s*({.*?});"
    match = re.search(pattern, str(soup), re.DOTALL)
    if match:
        data = match.group(1)
        data = eval(data.replace("false", "False").replace("true", "True"))
        for decklist in tqdm(data["decklists"], desc="Generating decklists"):
            deck = {
                "player": decklist["player"],
                "main": reduce(
                    lambda acc, x: acc.update(
                        {
                            x["card_attributes"]["card_name"]: acc.get(
                                x["card_attributes"]["card_name"], 0
                            )
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
                            x["card_attributes"]["card_name"]: acc.get(
                                x["card_attributes"]["card_name"], 0
                            )
                            + int(x["qty"])
                        }
                    )
                    or acc,
                    decklist["sideboard_deck"],
                    {},
                ),
                "date": (
                    data["publish_date"]
                    if "publish_date" in data
                    else data["starttime"].split(" ")[0]
                ),
                "tournament": data["name"] if "name" in data else data["description"],
            }
            fig = display_deck(deck=deck)
            deck_format = data["site_name"].split("-")[0]
            Path(f"./assets/{deck_format}").mkdir(parents=True, exist_ok=True)
            event_id = data["eventid"] if "eventid" in data else data["playeventid"]
            deck_name = f"{event_id}_{decklist['player'].replace(' ', '_').lower()}"
            fig.savefig(
                f"./assets/{deck_format}/{deck_name}.png",  # noqa
                dpi=100,
                bbox_inches="tight",
            )
            plt.close()

            with open("./assets/decklists.txt", "a") as f:
                f.write(
                    f"https://raw.githubusercontent.com/chumpblocckami/merchantscroll/main/assets/{deck_format}/{deck_name}.png\n"  # noqa
                )
            # REMOVE THIS
            return

    else:
        return
    with open("./assets/tournaments.txt", "a") as f:
        f.write(tournament_url + "\n")


def crawl_tournaments() -> pd.DataFrame:
    base_url = "https://www.mtgo.com/decklists"
    headers = {"User-Agent": "Mozilla/5.0"}

    # Fetch the page
    response = requests.get(base_url, headers=headers, timeout=20)
    if response.status_code != 200:
        print(f"Error fetching page: {response.status_code}")
        exit()

    # Parse the HTML content
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract tournament links
    tournament_links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/decklist/" in href:
            full_url = "https://www.mtgo.com" + href
            tournament_links.append(full_url)

    # Deduplicate and print
    tournament_links = list(set(tournament_links))

    return tournament_links

saver = Saver(os.path.dirname(os.path.realpath(__file__)))

if __name__ == "__main__":
    with open("./assets/tournaments.txt", "r") as f:
        crawled_tournaments = f.readlines()
    tournaments = crawl_tournaments()
    # TODO: Filter tournaments for Pauper (extend to other formats later)
    tournaments = [x for x in tournaments if "pauper" in x.lower()]
    for tournament in tqdm(tournaments, desc="Crawling tournaments"):
        if tournament in crawled_tournaments:
            print("Already crawled tournament:", tournament)
            continue
        deck = crawl_decks(tournament)
        saver.submit_changes(glob.glob("./assets/*/*.png"))

        time.sleep(1)
