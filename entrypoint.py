import time
from pathlib import Path

import requests
from tqdm import tqdm

from src.constants.misc import FORMATS
from src.crawler import crawl_decks, crawl_tournaments


def start_crawler():

    # Get a list of crawled tournaments for the available formats
    crawled_tournaments = []
    for available_format in FORMATS:
        tournaments_path = str(Path(f"./assets/{available_format}/tournaments.txt").resolve())
        Path(tournaments_path).parent.mkdir(parents=True, exist_ok=True)
        if Path(tournaments_path).exists():
            with open(tournaments_path, "r+") as f:
                format_crawled_tournaments = list(set([x.strip() for x in f.readlines()]))
        else:
            Path(tournaments_path).touch()
            format_crawled_tournaments = []
        crawled_tournaments.extend(format_crawled_tournaments)

    try:
        tournaments = crawl_tournaments()
        tournaments = [
            tournament
            for tournament in tournaments
            if any(tournament_format in tournament for tournament_format in FORMATS)
        ]
        tournaments = sorted(tournaments, key=lambda x: int(x.split("-")[-1][:2]), reverse=True)
        tournaments = [x for x in tournaments if x not in crawled_tournaments]
        pbar = tqdm(tournaments, desc="Crawling tournaments")
        for tournament in pbar:
            pbar.set_description(desc=f"Crawling {tournament}")
            crawl_decks(tournament)
            time.sleep(1)
    except requests.exceptions.RequestException as e:
        print(f"Exception: {e}. Skipping this time and rerunning later.")
    print("Finish crawling tournaments")


if __name__ == "__main__":
    start_crawler()
