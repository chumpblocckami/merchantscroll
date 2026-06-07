import re
from ast import literal_eval

import requests
from bs4 import BeautifulSoup

from .constants.crawler import HEADERS, TIMEOUT
from .constants.misc import PATTERN
from .utils import enrich_challenge_results, enrich_deck_colors, minify_tournament_data


def crawl_decks(
    tournament_url: str, color_lookup: dict[str, list[str]] | None = None
) -> dict | None:
    """Fetch and parse a single tournament page from MTGO.

    Returns minified (and optionally color-enriched) tournament data,
    or None on failure.
    """
    response = requests.get(tournament_url, headers=HEADERS, timeout=TIMEOUT)
    if response.status_code != 200:
        print(f"Failed to fetch {tournament_url} (status {response.status_code})")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    match = re.search(PATTERN, str(soup), re.DOTALL)
    if not match:
        print(f"No tournament data found in {tournament_url}")
        return None

    tournament_data = literal_eval(
        match.group(1).replace("false", "False").replace("true", "True")
    )
    enrich_challenge_results(tournament_data)
    minified = minify_tournament_data(tournament_data)
    if color_lookup:
        enrich_deck_colors(minified, color_lookup)
    return minified


def crawl_tournaments() -> list[str]:
    """Discover all tournament URLs from the MTGO decklists page."""
    base_url = "https://www.mtgo.com/decklists"

    response = requests.get(base_url, headers=HEADERS, timeout=TIMEOUT)
    if response.status_code != 200:
        raise requests.exceptions.HTTPError(
            f"Error fetching page: {response.status_code}", response=response
        )

    soup = BeautifulSoup(response.text, "html.parser")

    urls = set()
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/decklist/" in href:
            urls.add("https://www.mtgo.com" + href)

    return list(urls)
