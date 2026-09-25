import gzip
import json
import re
from pathlib import Path

import requests

from .constants.crawler import HEADERS, TIMEOUT

BULK_DATA_API = "https://api.scryfall.com/bulk-data"
DEFAULT_CACHE_PATH = Path(".cache/oracle-cards.jsonl.gz")
DEFAULT_CARDS_CACHE_PATH = Path(".cache/default-cards.jsonl.gz")

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


def _bulk_download_url(bulk_type: str) -> str:
    """Resolve the current gzipped JSONL URL for a Scryfall bulk-data type."""
    resp = requests.get(BULK_DATA_API, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()

    for entry in resp.json().get("data", []):
        if entry.get("type") == bulk_type:
            # Scryfall retired the plain-JSON `download_uri`; only gzipped JSONL is served.
            return entry["jsonl_download_uri"]

    raise RuntimeError(f"{bulk_type} bulk data entry not found in Scryfall API")


def _download_bulk(
    bulk_type: str, cache_path: Path, label: str, *, refresh: bool = False
) -> Path:
    """Download a Scryfall bulk file if missing, or if ``refresh`` is set."""
    cache_path = Path(cache_path)
    if refresh and cache_path.exists():
        cache_path.unlink()
    if cache_path.exists():
        return cache_path

    url = _bulk_download_url(bulk_type)
    print(f"Downloading {label} from Scryfall...")

    resp = requests.get(url, timeout=300)
    resp.raise_for_status()

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(resp.content)
    print(f"Cached at {cache_path}")
    return cache_path


def download_oracle_cards(cache_path: Path = DEFAULT_CACHE_PATH) -> Path:
    """Download the Scryfall oracle-cards bulk file if not already cached.

    Returns the path to the cached gzipped JSONL file.
    """
    return _download_bulk(
        "oracle_cards", cache_path, "oracle-cards.jsonl.gz (~25 MB)"
    )


def download_default_cards(
    cache_path: Path = DEFAULT_CARDS_CACHE_PATH, *, refresh: bool = False
) -> Path:
    """Download every English printing Scryfall knows about, if not cached.

    oracle-cards keeps one preferred (usually latest) printing per card. First
    artwork needs every printing so this file is the larger default-cards dump.
    """
    return _download_bulk(
        "default_cards",
        cache_path,
        "default-cards.jsonl.gz (~80 MB)",
        refresh=refresh,
    )


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


# MTGO abbreviates the type line to a six-character code. Creature is tested
# before land so artifact lands (Seat of the Synod) stay LAND while a land
# creature stays a creature, matching how the deck view buckets them.
_TYPE_CODES = (
    ("creature", "ISCREA"),
    ("land", "LAND"),
    ("instant", "INSTNT"),
    ("sorcery", "SORCRY"),
    ("artifact", "ARTFCT"),
    ("enchantment", "ENCHMT"),
    ("planeswalker", "PLNSWK"),
)


def mtgo_type_code(type_line: str) -> str:
    """Reduce a Scryfall type line to the MTGO card_type code, or "" if unknown."""
    lowered = type_line.lower()
    for needle, code in _TYPE_CODES:
        if needle in lowered:
            return code
    return ""


def build_type_lookup(cache_path: Path = DEFAULT_CACHE_PATH) -> dict[str, str]:
    """Build a card_name → MTGO card_type code mapping from cached oracle data.

    Returns a dict like {"Lightning Bolt": "INSTNT", "Mountain": "LAND"}.
    Alternate spellings are registered as aliases, but a card's own name always
    wins over an alias claimed by a different card.
    """
    cache_path = Path(cache_path)
    if not cache_path.exists():
        raise FileNotFoundError(
            f"Oracle data not found at {cache_path}. Run download_oracle_cards() first."
        )

    exact: dict[str, str] = {}
    aliases: dict[str, str] = {}
    with gzip.open(cache_path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            card = json.loads(line)
            if not _is_playable(card):
                continue
            code = mtgo_type_code(card.get("type_line", ""))
            if not code:
                continue
            name = card.get("name", "")
            exact[name] = code
            for variant in _name_variants(name) - {name}:
                aliases.setdefault(variant, code)

    return {**aliases, **exact}


# Printings that are not a real first appearance of the card: gold-bordered
# championship decks, art cards, tokens. They can predate or outnumber the
# actual expansion printing and would steal the artwork if left unranked.
_SKIP_SET_TYPES = frozenset(
    {"memorabilia", "token", "minigame", "art_series", "funny"}
)

# Literal first printings that nobody treats as the card. Ice Age Brainstorm
# exists, but the DiTerlizzi Mercadian Masques painting is the one later
# decklists should keep.
CANONICAL_ART_SETS = {
    "Brainstorm": "mmq",
}


def card_image_uris(card: dict) -> dict[str, str] | None:
    """Return small/normal image URLs, using the front face of a split card."""
    uris = card.get("image_uris") or (card.get("card_faces") or [{}])[0].get(
        "image_uris"
    )
    if not uris:
        return None
    small = uris.get("small") or uris.get("normal")
    normal = uris.get("normal") or uris.get("small")
    if not small:
        return None
    return {"s": small, "n": normal}


def first_print_rank(card: dict) -> tuple:
    """Sort key that prefers the earliest real paper printing.

    Paper beats digital, a regular printing beats a promo, and an expansion
    beats a gold-bordered or art-series card. Ties break on release date, then
    set code, so the choice is stable across rebuilds.
    """
    pinned_set = CANONICAL_ART_SETS.get(card.get("name", ""))
    pinned = 0 if pinned_set and card.get("set") == pinned_set else 1
    extra = 1 if (card.get("set_type") or "") in _SKIP_SET_TYPES else 0
    if card.get("oversized") or card.get("layout") == "art_series":
        extra = 1
    paper = 0 if "paper" in (card.get("games") or []) else 1
    promo = 1 if card.get("promo") else 0
    digital = 1 if card.get("digital") else 0
    released = card.get("released_at") or "9999-99-99"
    return (
        pinned,
        extra,
        paper,
        promo,
        digital,
        released,
        card.get("set") or "",
        card.get("collector_number") or "",
    )


def build_first_art_lookup(
    cache_path: Path = DEFAULT_CARDS_CACHE_PATH,
) -> dict[str, dict[str, str]]:
    """Build a card_name → first-printing image URLs mapping.

    Each name points at the earliest paper (or only-digital) printing of that
    card, except for the few names in ``CANONICAL_ART_SETS`` whose familiar
    painting is not the literal first printing (Brainstorm → Mercadian Masques).
    """
    cache_path = Path(cache_path)
    if not cache_path.exists():
        raise FileNotFoundError(
            f"Default cards not found at {cache_path}. Run download_default_cards() first."
        )

    best: dict[str, tuple[tuple, dict[str, str], str]] = {}
    with gzip.open(cache_path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            card = json.loads(line)
            if not _is_playable(card):
                continue
            uris = card_image_uris(card)
            if not uris:
                continue
            oracle_id = card.get("oracle_id") or card.get("id") or ""
            if not oracle_id:
                continue
            rank = first_print_rank(card)
            prev = best.get(oracle_id)
            if prev is None or rank < prev[0]:
                best[oracle_id] = (rank, uris, card.get("name", ""))

    exact: dict[str, dict[str, str]] = {}
    aliases: dict[str, dict[str, str]] = {}
    for _, uris, name in best.values():
        if not name:
            continue
        exact[name] = uris
        for variant in _name_variants(name) - {name}:
            aliases.setdefault(variant, uris)
    return {**aliases, **exact}
