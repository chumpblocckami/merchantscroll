"""Crawler for Pauperwave local (IRL) tournament decklists.

Fetches Markdown files from the Pauperwave GitHub repository, parses
the ``::magic-decklist`` component format, and converts them into the
same JSON structure used by the MTGO pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import requests
import yaml

from .constants.crawler import HEADERS, TIMEOUT

GITHUB_API_BASE = (
    "https://api.github.com/repos/Pauperwave/blog/contents/"
    "content/blog/decklists"
)
RAW_BASE = (
    "https://raw.githubusercontent.com/Pauperwave/blog/main/"
    "content/blog/decklists"
)

PLACEMENT_RANK = {
    "winner": 1,
    "finalist": 2,
    "top 4": 3,
    "top 8": 5,
}

GRADIENT_COLORS: dict[str, list[str]] = {
    "monored": ["R"],
    "monoblue": ["U"],
    "monoblack": ["B"],
    "monowhite": ["W"],
    "monogreen": ["G"],
    "dimir": ["B", "U"],
    "golgari": ["B", "G"],
    "simic": ["G", "U"],
    "izzet": ["R", "U"],
    "boros": ["R", "W"],
    "gruul": ["G", "R"],
    "azorius": ["U", "W"],
    "orzhov": ["B", "W"],
    "rakdos": ["B", "R"],
    "selesnya": ["G", "W"],
    "esper": ["B", "U", "W"],
    "grixis": ["B", "R", "U"],
    "jund": ["B", "G", "R"],
    "naya": ["G", "R", "W"],
    "bant": ["G", "U", "W"],
    "abzan": ["B", "G", "W"],
    "jeskai": ["R", "U", "W"],
    "sultai": ["B", "G", "U"],
    "mardu": ["B", "R", "W"],
    "temur": ["G", "R", "U"],
    "5c": ["B", "G", "R", "U", "W"],
    "wubrg": ["B", "G", "R", "U", "W"],
}

CARD_TYPE_LABELS: dict[str, str] = {
    "creatures": "ISCREA",
    "creature": "ISCREA",
    "instants": "INSTNT",
    "instant": "INSTNT",
    "sorceries": "SORCRY",
    "sorcery": "SORCRY",
    "enchantments": "ENCHMN",
    "enchantment": "ENCHMN",
    "artifacts": "ARTFCT",
    "artifact": "ARTFCT",
    "lands": "LAND  ",
    "land": "LAND  ",
    "planeswalkers": "PLNSWK",
    "planeswalker": "PLNSWK",
}

CARD_LINE_RE = re.compile(r"^(\d+)\s+(.+)$")


@dataclass
class ParsedDecklist:
    """A single parsed decklist from a Pauperwave Markdown file."""

    name: str = ""
    player: str = ""
    placement: str = ""
    header_gradient: str = ""
    main_deck: list[dict] = field(default_factory=list)
    sideboard_deck: list[dict] = field(default_factory=list)


def discover_pauperwave_files(token: str | None = None) -> list[dict]:
    """List tournament Markdown files in the Pauperwave decklists directory.

    Returns a list of dicts with ``name`` and ``download_url`` keys,
    excluding template files and non-Markdown files.
    """
    headers = {**HEADERS}
    if token:
        headers["Authorization"] = f"token {token}"

    resp = requests.get(GITHUB_API_BASE, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()

    files = []
    for entry in resp.json():
        name = entry.get("name", "")
        if not name.endswith(".md"):
            continue
        if name.startswith("0000-"):
            continue
        files.append({"name": name, "download_url": f"{RAW_BASE}/{name}"})

    return sorted(files, key=lambda f: f["name"], reverse=True)


def fetch_markdown(url: str) -> str:
    """Download a single Markdown file from GitHub."""
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.text


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter from the body of a Markdown file."""
    if not text.startswith("---"):
        return {}, text

    end = text.find("---", 3)
    if end == -1:
        return {}, text

    fm_text = text[3:end].strip()
    body = text[end + 3 :].strip()
    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        fm = {}
    return fm or {}, body


def _parse_decklist_block(block: str) -> ParsedDecklist:
    """Parse a single ``::magic-decklist`` block into a ParsedDecklist."""
    result = ParsedDecklist()

    yaml_match = re.match(r"---\s*\n(.*?)\n---", block, re.DOTALL)
    if yaml_match:
        try:
            meta = yaml.safe_load(yaml_match.group(1))
        except yaml.YAMLError:
            meta = {}
        if meta:
            result.name = meta.get("name", "")
            result.player = meta.get("player", "")
            result.placement = meta.get("placement", "")
            result.header_gradient = meta.get("headerGradient", "")
        block = block[yaml_match.end() :].strip()

    current_type = "INSTNT"
    in_sideboard = False

    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue

        lower = line.lower()
        if lower == "sideboard":
            in_sideboard = True
            current_type = "INSTNT"
            continue

        if lower in CARD_TYPE_LABELS:
            current_type = CARD_TYPE_LABELS[lower]
            continue

        m = CARD_LINE_RE.match(line)
        if not m:
            continue

        qty = m.group(1)
        card_name = m.group(2).strip()
        card_entry = {
            "qty": qty,
            "card_attributes": {
                "card_name": card_name,
                "card_type": current_type,
            },
        }

        if in_sideboard:
            result.sideboard_deck.append(card_entry)
        else:
            result.main_deck.append(card_entry)

    return result


def _placement_to_rank(placement: str) -> int | None:
    """Convert a placement string to a numeric rank."""
    return PLACEMENT_RANK.get(placement.strip().lower())


def _colors_from_gradient(gradient: str) -> list[str]:
    """Derive deck colors from the headerGradient field."""
    return sorted(GRADIENT_COLORS.get(gradient.strip().lower(), []))


def parse_tournament_file(
    markdown: str,
    filename: str,
    color_lookup: dict[str, list[str]] | None = None,
) -> dict | None:
    """Parse a full Pauperwave Markdown tournament file.

    Returns a tournament dict in the same format as MTGO data, or None
    if parsing fails or the file is not published.
    """
    fm, body = _parse_frontmatter(markdown)

    if fm.get("published") is False:
        return None

    title = fm.get("title", filename.replace(".md", "").replace("-", " "))
    date_val = fm.get("date", "")
    if hasattr(date_val, "isoformat"):
        date_str = date_val.isoformat()
    else:
        date_str = str(date_val)
    location = fm.get("location", "")

    slug = filename.replace(".md", "")
    site_name = f"pauperwave-{slug}"

    blocks = re.split(r"::magic-decklist\b", body)
    decklists = []

    for raw_block in blocks[1:]:
        end = raw_block.find("\n::")
        if end != -1:
            raw_block = raw_block[:end]

        parsed = _parse_decklist_block(raw_block.strip())
        if not parsed.main_deck:
            continue

        deck: dict = {
            "player": parsed.player,
            "main_deck": parsed.main_deck,
            "sideboard_deck": parsed.sideboard_deck,
        }

        if parsed.name:
            deck["archetype"] = parsed.name

        rank = _placement_to_rank(parsed.placement)
        if rank is not None:
            deck["final_rank"] = rank

        if color_lookup:
            colors: set[str] = set()
            for card in parsed.main_deck + parsed.sideboard_deck:
                ct = card["card_attributes"].get("card_type", "").strip()
                if ct == "LAND":
                    continue
                cn = card["card_attributes"]["card_name"]
                colors.update(color_lookup.get(cn, []))
            deck["colors"] = sorted(colors) if colors else ["C"]
        elif parsed.header_gradient:
            deck["colors"] = _colors_from_gradient(parsed.header_gradient)
        else:
            deck["colors"] = ["C"]

        decklists.append(deck)

    if rank is not None:
        decklists.sort(key=lambda d: d.get("final_rank", 9999))

    if not decklists:
        return None

    description = title
    if location:
        description = f"{title} — {location}"

    return {
        "description": description,
        "starttime": date_str,
        "site_name": site_name,
        "source": "pauperwave",
        "format": "pauper",
        "player_count": {},
        "decklists": decklists,
    }
