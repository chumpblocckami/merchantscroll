import re
import time
from functools import reduce
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from drawer import display_deck
import os 
import json 
from saver import commit_and_push

    
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
        tournament_data = eval(match.group(1).replace("false", "False").replace("true", "True"))

        # Save raw tournament data to file
        deck_format = tournament_data["site_name"].split("-")[0]
        tournament_name = tournament_data["site_name"]
        reference_date = (
                    tournament_data["publish_date"]
                    if "publish_date" in tournament_data
                    else tournament_data["starttime"].split(" ")[0]
                )
        tournament_id = tournament_data["event_id"] if "event_id" in tournament_data else tournament_data["playeventid"]
        Path(f"./assets/{reference_date}").mkdir(parents=True, exist_ok=True)
        with open(f"./assets/{reference_date}/{tournament_name}.json", "w") as f:
            json.dump(tournament_data,f, indent=2)
        commit_and_push(Path(f"./assets/{reference_date}/{tournament_name}.json").resolve(), 
                            target_branch=deck_format,
                            commit_message=f"Added {reference_date} raw tournament data")
        
        # Save decklist images
        pbar = tqdm(tournament_data["decklists"], desc="Reading decklists")
        for decklist in pbar:
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
                "date": reference_date,
                "tournament": tournament_name,
            }
            pbar.set_description(desc=f"Reading {deck['tournament']}-{deck['player']}")
            fig = display_deck(deck=deck)
            deck_name = f"{deck_format}_{tournament_id}_{decklist['player'].replace(' ', '_').lower()}"
            fig.savefig(
                Path(f"./assets/{reference_date}/{deck_name}.png").resolve(),
                dpi=100,
                bbox_inches="tight",
            )
            plt.close()

            with open("./assets/decklists.txt", "a") as f:
                f.write(
                    f"https://raw.githubusercontent.com/chumpblocckami/merchantscroll/{deck_format}/assets/{reference_date}/{deck_name}.png\n"  # noqa
                )
            commit_and_push(Path(f"./assets/{reference_date}/{deck_name}.png").resolve(), 
                            target_branch=deck_format,
                            commit_message=f"Added {deck_name} to {deck_format}")
            commit_and_push(Path("./assets/decklists.txt").resolve(), 
                            target_branch=deck_format,
                            commit_message=f"Updated available decklists with {deck_name}")
            #os.remove(Path(f"./assets/{deck_format}/{deck_name}.png"))
    else:
        return
    with open("./assets/tournaments.txt", "a") as f:
        f.write(tournament_url + "\n")
    commit_and_push(Path("./assets/tournaments.txt").resolve(), 
                    target_branch="main", 
                    commit_message=f"Updated crawled tournaments with {tournament_url}")

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

if __name__ == "__main__":
    with open("./assets/tournaments.txt", "r") as f:
        crawled_tournaments = f.readlines()

    try:
        tournaments = crawl_tournaments()
        # TODO: Filter tournaments for Pauper (extend to other formats later)
        tournaments = [x for x in tournaments if "pauper" in x.lower()]
        pbar= tqdm(tournaments, desc="Crawling tournaments")
        for tournament in pbar:
            pbar.set_description(desc=f"Crawling {tournament}")
            if tournament in crawled_tournaments:
                print("Already crawled tournament:", tournament)
                continue
            deck = crawl_decks(tournament)

            time.sleep(1)
    except Exception as e:
        print(f"Exception: {e}. Rerunning later.")
