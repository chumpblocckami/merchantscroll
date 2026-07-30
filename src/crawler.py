import re
import time
from ast import literal_eval

import requests
from bs4 import BeautifulSoup

from .constants.crawler import TIMEOUT
from .constants.misc import PATTERN
from .utils import (
    canonical_starttime,
    enrich_challenge_results,
    enrich_deck_colors,
    minify_tournament_data,
)

BASE_URL = "https://www.mtgo.com"
DECKLISTS_URL = f"{BASE_URL}/decklists"

# A bare "Mozilla/5.0" agent gets a stub page with no decklist anchors; the full
# header set of a real browser gets the server-rendered listing.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class EmptyListingError(requests.exceptions.RequestException):
    """The decklists page loaded but held no tournament links.

    Subclasses RequestException so existing callers that already handle
    network trouble treat a stub or bot-challenge page the same way.
    """


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
    site_name = tournament_url.rstrip("/").split("/")[-1]
    if site_name:
        minified["site_name"] = site_name
        minified["starttime"] = canonical_starttime(
            site_name, minified.get("starttime", "")
        )
    if color_lookup:
        enrich_deck_colors(minified, color_lookup)
    return minified


def _decklist_links(html: str) -> list[str]:
    """Extract absolute tournament URLs from the decklists listing HTML."""
    soup = BeautifulSoup(html, "html.parser")
    return sorted(
        {
            BASE_URL + a["href"]
            for a in soup.find_all("a", href=True)
            if "/decklist/" in a["href"]
        }
    )


def crawl_tournaments(attempts: int = 3) -> list[str]:
    """Discover all tournament URLs from the MTGO decklists page.

    Args:
        attempts: How many times to fetch before giving up.

    Returns:
        Absolute tournament URLs, sorted.

    Raises:
        EmptyListingError: If the page loads but yields no decklist links,
            which means a stub or challenge page rather than the listing.
        requests.exceptions.HTTPError: If the page returns a non-200 status.
    """
    detail = ""
    for attempt in range(1, attempts + 1):
        response = requests.get(DECKLISTS_URL, headers=HEADERS, timeout=TIMEOUT)
        if response.status_code != 200:
            raise requests.exceptions.HTTPError(
                f"Error fetching page: {response.status_code}", response=response
            )

        urls = _decklist_links(response.text)
        if urls:
            return urls

        title = BeautifulSoup(response.text, "html.parser").title
        detail = (
            f"{len(response.content)} bytes,"
            f" title={title.string.strip() if title and title.string else None!r}"
        )
        print(f"  Attempt {attempt}/{attempts}: listing had no decklist links ({detail}).")
        # ponytail: a fixed 5s retry only rescues transient stubs; a persistent
        # block needs a headless browser or an off-datacenter egress IP.
        if attempt < attempts:
            time.sleep(5)

    raise EmptyListingError(
        f"{DECKLISTS_URL} returned 200 but no /decklist/ links in {attempts} attempts"
        f" ({detail}). The page normally lists hundreds, so this response was a stub"
        " or bot challenge, not an empty schedule."
    )
