import gzip
import json
import re
from pathlib import Path

import requests

from .constants.crawler import HEADERS, TIMEOUT

BULK_DATA_API = "https://api.scryfall.com/bulk-data"
DEFAULT_CACHE_PATH = Path(".cache/oracle-cards.jsonl.gz")

MANA_SYMBOL_RE = re.compile(r"\{([^}]+)\}")
COLOR_LETTERS = frozenset("WUBRG")


# Cards a deck plays without ever paying their mana cost, so their colors say
# nothing about the deck's own colors.  There is no field in the Scryfall data
# that marks these, hence the list.  Add a card here only if playing it never
# requires producing its colored mana at all.
FREE_TO_PLAY_CARDS = frozenset(
    {
        # Discarded, then returns itself from the graveyard; mono-red madness
        # decks play it without a single blue or black source.
        "Sneaky Snacker",
    }
)


def _get_oracle_download_url() -> str:
    """Resolve the current download URL for oracle-cards bulk data."""
    resp = requests.get(BULK_DATA_API, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()

    for entry in resp.json().get("data", []):
        if entry.get("type") == "oracle_cards":
            # Scryfall retired the plain-JSON `download_uri`; only gzipped JSONL is served.
            return entry["jsonl_download_uri"]

    raise RuntimeError("oracle_cards bulk data entry not found in Scryfall API")


def download_oracle_cards(cache_path: Path = DEFAULT_CACHE_PATH) -> Path:
    """Download the Scryfall oracle-cards bulk file if not already cached.

    Returns the path to the cached gzipped JSONL file.
    """
    cache_path = Path(cache_path)
    if cache_path.exists():
        return cache_path

    url = _get_oracle_download_url()
    print("Downloading oracle-cards.jsonl.gz from Scryfall (~25 MB)...")

    resp = requests.get(url, timeout=300)
    resp.raise_for_status()

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(resp.content)
    print(f"Cached at {cache_path}")
    return cache_path


def _mana_cost(card: dict) -> str:
    """Return a card's mana cost, joining both faces of a double-faced card."""
    faces = card.get("card_faces") or []
    if faces:
        return " ".join(face.get("mana_cost") or "" for face in faces)
    return card.get("mana_cost") or ""


def required_colors(card: dict) -> list[str]:
    """Return the colors a deck must be able to produce in order to play a card.

    This reads the mana cost rather than Scryfall's ``color_identity``, which
    also counts colored mana appearing in abilities.  Nihil Spellbomb costs
    ``{1}`` and only asks for ``{B}`` in an optional draw trigger, yet its
    identity is black, which used to paint thousands of colorless decks black.

    Symbols that can be paid without their color are skipped: Phyrexian mana
    (``{R/P}`` on Gut Shot) takes 2 life instead, and monocolored hybrid
    (``{2/W}``) takes generic mana instead.
    """
    if card.get("name") in FREE_TO_PLAY_CARDS:
        return []

    colors: set[str] = set()
    for symbol in MANA_SYMBOL_RE.findall(_mana_cost(card)):
        parts = symbol.split("/")
        if "P" in parts or any(part.isdigit() for part in parts):
            continue
        colors.update(part for part in parts if part in COLOR_LETTERS)
    return sorted(colors)


def _is_playable(card: dict) -> bool:
    """Whether a card is legal somewhere, i.e. something a decklist can contain.

    Art series and Mystery Booster playtest cards reuse the names of real cards
    and are legal nowhere, so they must not claim a name in the lookup: the
    "Delver of Secrets // Delver of Secrets" art card made every Delver deck
    read as colorless, and "Start // Fire" made Fire // Ice red-white.
    """
    legalities = card.get("legalities") or {}
    return any(status != "not_legal" for status in legalities.values())


def _name_variants(name: str) -> set[str]:
    """Every spelling MTGO might use for a card name.

    MTGO drops the spaces around a split card's slash ("Fire/Ice"), names a
    double-faced card by its front face alone, and serves some names as UTF-8
    bytes reread as Latin-1 ("Troll of Khazad-dÃ»m").
    """
    variants = {name}
    if " // " in name:
        variants.add(name.replace(" // ", "/"))
        variants.update(face.strip() for face in name.split(" // "))
    for variant in list(variants):
        if not variant.isascii():
            try:
                variants.add(variant.encode("utf-8").decode("latin-1"))
            except UnicodeError:
                pass
    return variants


def build_color_lookup(cache_path: Path = DEFAULT_CACHE_PATH) -> dict[str, list[str]]:
    """Build a card_name → required colors mapping from cached oracle data.

    Returns a dict like {"Lightning Bolt": ["R"], "Gut Shot": []}. Alternate
    spellings are registered as aliases, but a card's own name always wins over
    an alias claimed by a different card.
    """
    cache_path = Path(cache_path)
    if not cache_path.exists():
        raise FileNotFoundError(
            f"Oracle data not found at {cache_path}. Run download_oracle_cards() first."
        )

    exact: dict[str, list[str]] = {}
    aliases: dict[str, list[str]] = {}
    with gzip.open(cache_path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            card = json.loads(line)
            if not _is_playable(card):
                continue
            name = card.get("name", "")
            colors = required_colors(card)
            exact[name] = colors
            for variant in _name_variants(name) - {name}:
                aliases.setdefault(variant, colors)

    return {**aliases, **exact}
