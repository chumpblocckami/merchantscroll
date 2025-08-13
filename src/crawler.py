import re
from ast import literal_eval
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from src.constants.crawler import HEADERS, TIMEOUT
from src.constants.misc import PATTERN, SAVE_FILE_AS
from src.renderer.html import write_html
from src.renderer.png import write_png

from .constants.paths import (
    OUTPUT_CONTENT_PATH,
    OUTPUT_PATH,
    RAW_TOURNAMENT_PATH,
    REMOTE_DECKLISTS_PATH,
    REMOTE_PATH,
    REMOTE_TOURNAMENTS_PATH,
)
from .domain import Tournament
from .saver import (
    assess_tournament_folder,
    push_to_different_remote,
    push_to_same_remote,
    save_json_locally,
    update_crawled_contents,
    update_crawled_tournaments,
)
from .utils import get_challenge_record, get_league_record, parse_decklist


def crawl_decks(tournament_url: str) -> None:
    # Fetch the deck page
    response = requests.get(tournament_url, headers=HEADERS, timeout=TIMEOUT)
    if response.status_code != 200:
        print(f"Failed to retrieve the deck page. Status code: {response.status_code}")
        exit()

    # Parse the deck page
    soup = BeautifulSoup(response.text, "html.parser")

    match = re.search(PATTERN, str(soup), re.DOTALL)
    if match:
        # Get raw tournament data and generate dataclass
        tournament_data = literal_eval(
            match.group(1).replace("false", "False").replace("true", "True")
        )
        tournament = Tournament(
            site_name=tournament_data.get("site_name"),
            reference_date=tournament_data.get(
                "publish_date",
                tournament_data.get("starttime"),
            ),
            event_id=tournament_data.get("event_id", tournament_data.get("playeventid")),
            is_ranked=True if "final_rank" in tournament_data else False,
        )

        # Save raw tournament data
        raw_tournament_path = str(
            Path(
                RAW_TOURNAMENT_PATH.format(
                    deck_format=tournament.deck_format, tournament_id=tournament.site_name
                )
            ).resolve()
        )
        save_json_locally(raw_tournament_path, tournament_data)

        push_to_same_remote(
            raw_tournament_path,
            branch="main",
            commit_message=f"Updated crawled raw data from {tournament_url}",
        )

        # ---- IMPORTANT: understand if this is useful or not ---
        # Sort by rank (for challenges)
        if tournament.is_ranked:
            rank_map = {
                entry["loginid"]: int(entry["rank"]) for entry in tournament_data["final_rank"]
            }
            decklists = sorted(
                tournament_data.get("decklists", []), key=lambda p: rank_map.get(p["loginid"], 9999)
            )
        else:
            decklists = tournament_data.get("decklists", [])

        # ---- END -----

        # Save tournament content
        assess_tournament_folder(tournament=tournament)
        pbar = tqdm(decklists, desc="Reading decklists")
        for decklist in pbar:
            pbar.set_description(desc=f"Reading {tournament.site_name}-{decklist['player']}")

            # Parse decklist and save content
            player_id = decklist.get("loginid", "playerid_not_found")
            record = (
                get_challenge_record(tournament_data["winloss"], player_id)
                if "winloss" in tournament_data
                else (
                    get_league_record(decklist["wins"])
                    if "wins" in decklist
                    else "(record not available)"
                )
            )
            deck = parse_decklist(decklist, tournament=tournament, record=record)
            deck_name = f"{tournament.name.replace(' ','_').lower()}_{tournament.event_id}_{player_id}"  # noqa

            # Save deck content
            try:
                if SAVE_FILE_AS == "png":
                    write_png(
                        deck,
                        OUTPUT_CONTENT_PATH.format(
                            deck_format=tournament.deck_format,
                            reference_date=tournament.reference_date,
                            deck_name=deck_name,
                        )
                        + ".png",
                    )
                else:
                    write_html(
                        deck,
                        OUTPUT_CONTENT_PATH.format(
                            deck_format=tournament.deck_format,
                            reference_date=tournament.reference_date,
                            deck_name=deck_name,
                        )
                        + ".html",
                    )

            except Exception as e:
                print(f"Error saving deck for {deck['player']}: {e}")
                continue

            # Updated crawled decklistslists
            update_crawled_contents(
                decklist_path=f"./assets/{tournament.deck_format}/decklists.txt",
                remote_path=REMOTE_PATH.format(
                    deck_format=tournament.deck_format,
                    reference_date=tournament.reference_date,
                    deck_name=deck_name,
                ),
            )

    else:
        print("No tournament data found.")
        return

    # Update the decklists file with the new URLs
    push_to_different_remote(
        Path(
            OUTPUT_PATH.format(
                deck_format=tournament.deck_format,
                reference_date=tournament.reference_date,
            )
        ).resolve(),
        branch=tournament.branch_name,
        commit_message=f"Got data for {tournament.branch_name}",
    )

    push_to_same_remote(
        str(Path(REMOTE_DECKLISTS_PATH.format(deck_format=tournament.deck_format)).resolve()),
        branch="main",
        commit_message=f"Updated crawled decklists with {tournament_url}",
    )

    # If the tournament is still in progress, we need to wait for it to finish
    if datetime.now().date().isoformat() not in tournament_url:
        update_crawled_tournaments(
            tournaments_path=REMOTE_TOURNAMENTS_PATH.format(deck_format=tournament.deck_format),
            tournament_url=tournament_url,
        )
        push_to_same_remote(
            str(Path(REMOTE_TOURNAMENTS_PATH.format(deck_format=tournament.deck_format)).resolve()),
            branch="main",
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
    response = requests.get(base_url, headers=headers, timeout=TIMEOUT)
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
