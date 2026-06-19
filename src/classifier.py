"""Deck archetype classification using Pauperwave naming conventions.

Builds a signature-card dictionary from labeled Pauperwave IRL decklists,
then classifies MTGO decklists by matching against that dictionary.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

RAW_DIR = Path("assets/pauper/raw")
ARCHETYPE_PATH = Path("archetypes/pauperwave.json")

ARCHETYPE_ALIASES: dict[str, str] = {
    "White Weennie": "White Weenie",
    "Rakdos Madness": "BR Madness",
    "Red Madness": "R Madness",
}


def canonical_archetype(name: str) -> str:
    """Return the canonical Pauperwave archetype name for aliases and typos."""
    cleaned = name.strip()
    if not cleaned:
        return cleaned
    return ARCHETYPE_ALIASES.get(cleaned, cleaned)


MATCH_THRESHOLD = 0.5
MIN_DECKS_PER_ARCHETYPE = 2
MIN_CARD_PRESENCE_RATE = 0.5
MAX_SIGNATURES = 6
MIN_SIGNATURES = 3


def _main_deck_card_names(deck: dict) -> set[str]:
    names: set[str] = set()
    for card in deck.get("main_deck", []):
        card_type = card.get("card_attributes", {}).get("card_type", "").strip()
        if card_type == "LAND":
            continue
        name = card.get("card_attributes", {}).get("card_name", "")
        if name:
            names.add(name)
    return names


def build_archetype_dictionary(
    raw_dir: Path = RAW_DIR,
    *,
    min_decks: int = MIN_DECKS_PER_ARCHETYPE,
    min_rate: float = MIN_CARD_PRESENCE_RATE,
    top_n: int = MAX_SIGNATURES,
    min_sigs: int = MIN_SIGNATURES,
) -> dict[str, list[str]]:
    """Derive archetype signature cards from labeled Pauperwave tournaments."""
    arch_decks: dict[str, list[set[str]]] = defaultdict(list)

    for path in raw_dir.glob("pauperwave-*.json"):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        for deck in data.get("decklists", []):
            archetype = canonical_archetype(deck.get("archetype", "").strip())
            if not archetype:
                continue
            cards = _main_deck_card_names(deck)
            if cards:
                arch_decks[archetype].append(cards)

    result: dict[str, list[str]] = {}
    for archetype, deck_sets in sorted(arch_decks.items()):
        if len(deck_sets) < min_decks:
            continue
        hits = Counter()
        for card_set in deck_sets:
            hits.update(card_set)
        deck_count = len(deck_sets)
        signatures = [
            card
            for card, count in hits.most_common()
            if count / deck_count >= min_rate
        ][:top_n]
        if len(signatures) >= min_sigs:
            result[archetype] = signatures

    return result


def save_archetype_dictionary(
    dictionary: dict[str, list[str]],
    path: Path = ARCHETYPE_PATH,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dictionary, indent=2, ensure_ascii=False) + "\n")
    return path


def load_archetype_dictionary(path: Path = ARCHETYPE_PATH) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def classify_deck(
    deck: dict,
    archetype_map: dict[str, list[str]],
    *,
    threshold: float = MATCH_THRESHOLD,
) -> str | None:
    """Return the best-matching Pauperwave archetype name, or None."""
    if deck.get("archetype"):
        return canonical_archetype(deck["archetype"])

    card_names = _main_deck_card_names(deck)
    if not card_names or not archetype_map:
        return None

    best_name = ""
    best_score = 0.0
    for archetype, signatures in archetype_map.items():
        if not signatures:
            continue
        matched = sum(1 for sig in signatures if sig in card_names)
        score = matched / len(signatures)
        if score > best_score:
            best_score = score
            best_name = archetype

    if best_score >= threshold:
        return canonical_archetype(best_name)
    return None


def enrich_archetypes(
    tournament_data: dict,
    archetype_map: dict[str, list[str]],
    *,
    overwrite: bool = False,
) -> dict:
    """Attach ``archetype`` to each decklist that matches the dictionary."""
    for deck in tournament_data.get("decklists", []):
        if deck.get("archetype") and not overwrite:
            continue
        label = classify_deck(deck, archetype_map)
        if label:
            deck["archetype"] = label
    return tournament_data


def rebuild_archetype_dictionary(raw_dir: Path = RAW_DIR) -> dict[str, list[str]]:
    """Rebuild and save ``archetypes/pauperwave.json`` from Pauperwave raw data."""
    dictionary = build_archetype_dictionary(raw_dir)
    save_archetype_dictionary(dictionary)
    print(f"Archetype dictionary updated: {len(dictionary)} archetypes.")
    return dictionary


def classify_unlabeled_mtgo_decks(
    archetype_map: dict[str, list[str]],
    raw_dir: Path = RAW_DIR,
) -> int:
    """Classify MTGO decklists missing an archetype label. Returns decks updated."""
    if not archetype_map:
        return 0

    updated = 0
    for path in raw_dir.glob("pauper-*.json"):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        changed = False
        for deck in data.get("decklists", []):
            if deck.get("archetype"):
                continue
            label = classify_deck(deck, archetype_map)
            if label:
                deck["archetype"] = label
                updated += 1
                changed = True

        if changed:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    return updated


def classify_and_normalize_labels(
    archetype_map: dict[str, list[str]] | None = None,
    raw_dir: Path = RAW_DIR,
) -> tuple[int, int]:
    """Classify unlabeled MTGO decks and normalize archetype aliases.

    Returns ``(classified_count, normalized_count)``.
    """
    archetype_map = archetype_map or load_archetype_dictionary()
    classified = classify_unlabeled_mtgo_decks(archetype_map, raw_dir=raw_dir)
    normalized = normalize_archetype_labels(raw_dir=raw_dir)
    return classified, normalized


def normalize_archetype_labels(raw_dir: Path = RAW_DIR) -> int:
    """Rewrite known archetype aliases in raw tournament data. Returns decks updated."""
    updated = 0
    for path in raw_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        changed = False
        for deck in data.get("decklists", []):
            archetype = deck.get("archetype")
            if not archetype:
                continue
            canonical = canonical_archetype(archetype)
            if canonical != archetype:
                deck["archetype"] = canonical
                updated += 1
                changed = True

        if changed:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    return updated
