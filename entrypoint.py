import time

from tqdm import tqdm

from src.constants import TOURNAMENT_FILE_PATH
from src.crawler import crawl_decks, crawl_tournaments


def start_crawler():
    with open(TOURNAMENT_FILE_PATH, "r") as f:
        crawled_tournaments = f.readlines()

    try:
        tournaments = crawl_tournaments()
        # TODO: Filter tournaments for Pauper (extend to other formats later)
        tournaments = set([x for x in tournaments if "pauper" in x.lower()])
        tournaments = sorted(tournaments, key=lambda x: int(x.split("-")[-1][:2]), reverse=True)
        pbar = tqdm(tournaments, desc="Crawling tournaments")
        for tournament in pbar:
            pbar.set_description(desc=f"Crawling {tournament}")
            if tournament in crawled_tournaments:
                print("Already crawled tournament:", tournament)
                continue
            crawl_decks(tournament)
            time.sleep(1)
    except Exception as e:
        print(f"Exception: {e}. Rerunning later.")


if __name__ == "__main__":
    start_crawler()
