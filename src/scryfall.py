import json
from pathlib import Path

import requests

from .constants.crawler import HEADERS, TIMEOUT

BULK_DATA_API = "https://api.scryfall.com/bulk-data"
DEFAULT_CACHE_PATH = Path(".cache/oracle-cards.json")


def _get_oracle_download_url() -> str:
    """Resolve the current download URL for oracle-cards bulk data."""
    resp = requests.get(BULK_DATA_API, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()

    for entry in resp.json().get("data", []):
        if entry.get("type") == "oracle_cards":
            return entry["download_uri"]

    raise RuntimeError("oracle_cards bulk data entry not found in Scryfall API")


def download_oracle_cards(cache_path: Path = DEFAULT_CACHE_PATH) -> Path:
    """Download Scryfall oracle-cards.json if not already cached.

    Returns the path to the cached file.
    """
    cache_path = Path(cache_path)
    if cache_path.exists():
        return cache_path

    url = _get_oracle_download_url()
    print(f"Downloading oracle-cards.json from Scryfall (~80 MB)...")

    resp = requests.get(url, timeout=300)
    resp.raise_for_status()

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(resp.content)
    print(f"Cached at {cache_path}")
    return cache_path


def build_color_lookup(cache_path: Path = DEFAULT_CACHE_PATH) -> dict[str, list[str]]:
    """Build a card_name → color_identity mapping from cached oracle data.

    Returns a dict like {"Lightning Bolt": ["R"], "Counterspell": ["U"]}.
    """
    cache_path = Path(cache_path)
    if not cache_path.exists():
        raise FileNotFoundError(
            f"Oracle data not found at {cache_path}. Run download_oracle_cards() first."
        )

    cards = json.loads(cache_path.read_text())
    lookup: dict[str, list[str]] = {}
    for card in cards:
        name = card.get("name", "")
        color_identity = card.get("color_identity", [])
        if " // " in name:
            lookup[name] = color_identity
            for face in name.split(" // "):
                lookup.setdefault(face.strip(), color_identity)
        else:
            lookup[name] = color_identity

    return lookup
