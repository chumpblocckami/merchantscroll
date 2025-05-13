import json
import re
from ast import literal_eval
from datetime import datetime
from functools import reduce
from glob import glob
from pathlib import Path

import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from .constants import DECKLISTS_FILE_PATH, HEADERS, PATTERN, TOURNAMENT_FILE_PATH
from .drawer import display_deck
from .saver import commit_and_push
from .utils import normalize_date


def crawl_decks(tournament_url: str) -> None:
    # Fetch the deck page
    response = requests.get(tournament_url, headers=HEADERS, timeout=20)
    if response.status_code != 200:
        print(f"Failed to retrieve the deck page. Status code: {response.status_code}")
        exit()

    # Parse the deck page
    soup = BeautifulSoup(response.text, "html.parser")

    match = re.search(PATTERN, str(soup), re.DOTALL)
    if match:
        tournament_data = literal_eval(
            match.group(1).replace("false", "False").replace("true", "True")
        )

        # Save raw tournament data to file
        deck_format = tournament_data["site_name"].split("-")[0]
        tournament_name = " ".join(
            [x.capitalize() for x in tournament_data["site_name"].split("-")[:2]]
        )
        reference_date = (
            tournament_data["publish_date"]
            if "publish_date" in tournament_data
            else tournament_data["starttime"].split(" ")[0]
        )
        reference_date = normalize_date(reference_date)
        tournament_id = (
            tournament_data["event_id"]
            if "event_id" in tournament_data
            else tournament_data["playeventid"]
        )
        Path(f"./assets/{reference_date}").mkdir(parents=True, exist_ok=True)
        with open(
            str(Path(f"./assets/{reference_date}/{tournament_name}.json").resolve()), "w"
        ) as f:
            json.dump(tournament_data, f, indent=2)
        commit_and_push(
            Path(f"./assets/{reference_date}/{tournament_name}.json").resolve(),
            target_branch=deck_format,
            commit_message=f"Added {reference_date} raw tournament data",
        )

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
            pbar.set_description(desc=f"Reading {tournament_id}-{deck['player']}")
            fig = display_deck(deck=deck)
            deck_name = f"{tournament_name.replace(' ','_').lower()}_{tournament_id}_{decklist['player'].replace(' ', '_').lower()}"  # noqa
            fig.savefig(
                Path(f"./assets/{reference_date}/{deck_name}.png").resolve(),
                dpi=100,
                bbox_inches="tight",
            )
            plt.close()

            # Save decklist URLs
            with open(DECKLISTS_FILE_PATH, "r") as f:
                crawled_decklists = list(set([line.strip() for line in f.readlines()]))
            crawled_decklists.insert(
                0,
                f"https://raw.githubusercontent.com/chumpblocckami/merchantscroll/{deck_format}/assets/{reference_date}/{deck_name}.png",  # noqa
            )
            with open(DECKLISTS_FILE_PATH, "w") as f:
                f.write("\n".join(crawled_decklists) + "\n")

        # os.remove(Path(f"./assets/{deck_format}/{deck_name}.png"))
    else:
        print("No tournament data found.")
        return

    # Push decklist images to the repository
    commit_and_push(
        [Path(file_path).resolve() for file_path in glob(f"./assets/{reference_date}/*.png")],
        target_branch=deck_format,
        commit_message=f"Added {reference_date} to {deck_format}",
    )
    # Update the decklists file with the new URLs
    commit_and_push(
        DECKLISTS_FILE_PATH,
        target_branch=deck_format,
        commit_message=f"Updated available decklists for {reference_date}",
    )

    # If the tournament is still in progress, we need to wait for it to finish
    if datetime.now().date().isoformat() not in tournament_url:
        with open(TOURNAMENT_FILE_PATH, "r") as f:
            crawled_tournaments = list(set([line.strip() for line in f.readlines()]))
        crawled_tournaments.insert(0, tournament_url)
        with open(TOURNAMENT_FILE_PATH, "w") as f:
            f.write("\n".join(crawled_tournaments) + "\n")
        commit_and_push(
            TOURNAMENT_FILE_PATH,
            target_branch="main",
            commit_message=f"Updated crawled tournaments with {tournament_url}",
        )
        return
    else:
        print("The tournament is still in progress, we need to wait for it to finish.")
        return


def crawl_tournaments() -> list[str]:
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
