"""Deck archetype classification using Pauperwave naming conventions.

Combines a committed signature-card baseline derived from the Paupergeddon
dataset with signatures mined from labeled Pauperwave IRL decklists, then
classifies MTGO decklists by matching against the merged dictionary.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

RAW_DIR = Path("assets/pauper/raw")
ARCHETYPE_PATH = Path("archetypes/pauperwave.json")
BASELINE_PATH = Path("archetypes/paupergeddon.json")
ALIAS_PATH = Path("archetypes/aliases.json")

# Fallback for a missing archetypes/aliases.json; that file carries the full map
# and wins wherever the two overlap.
ARCHETYPE_ALIASES: dict[str, str] = {
    "White Weennie": "White Weenie",
    "R Madness": "Mono Red Madness",
    "Red Madness": "Mono Red Madness",
}

_alias_cache: dict[str, str] | None = None


def _read_alias_file(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def load_archetype_aliases(path: Path = ALIAS_PATH) -> dict[str, str]:
    """Return the alias map, falling back to ``ARCHETYPE_ALIASES`` if unreadable."""
    global _alias_cache
    if path != ALIAS_PATH:
        return {**ARCHETYPE_ALIASES, **_read_alias_file(path)}
    if _alias_cache is None:
        _alias_cache = {**ARCHETYPE_ALIASES, **_read_alias_file(path)}
    return _alias_cache


def canonical_archetype(name: str) -> str:
    """Return the canonical Pauperwave archetype name for aliases and typos."""
    cleaned = name.strip()
    if not cleaned:
        return cleaned
    return load_archetype_aliases().get(cleaned, cleaned)


def normalize_card_name(name: str) -> str:
    """Return the front-face name so MTGO and ``//`` spellings compare equal."""
    return name.split(" // ")[0].strip()


_BASIC_LAND_TYPES = ("Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes")
BASIC_LAND_NAMES = frozenset(
    set(_BASIC_LAND_TYPES) | {f"Snow-Covered {name}" for name in _BASIC_LAND_TYPES}
)

MATCH_THRESHOLD = 0.5
MIN_DECKS_PER_ARCHETYPE = 2
MIN_CARD_PRESENCE_RATE = 0.5
MAX_SIGNATURES = 8
MIN_SIGNATURES = 3


def _main_deck_card_names(deck: dict) -> set[str]:
    """Return the main-deck card names that carry archetype signal.

    Only basics are dropped.  Nonbasic lands stay because Pauper archetypes lean
    on them heavily -- the Tron lands, the Gates, and the artifact lands are the
    most distinctive cards their decks play.
    """
    names: set[str] = set()
    for card in deck.get("main_deck", []):
        name = card.get("card_attributes", {}).get("card_name", "")
        if not name:
            continue
        name = normalize_card_name(name)
        if name not in BASIC_LAND_NAMES:
            names.add(name)
    return names


def build_signature_map(
    arch_decks: dict[str, list[set[str]]],
    *,
    min_decks: int = MIN_DECKS_PER_ARCHETYPE,
    min_rate: float = MIN_CARD_PRESENCE_RATE,
    top_n: int = MAX_SIGNATURES,
    min_sigs: int = MIN_SIGNATURES,
) -> dict[str, list[str]]:
    """Pick the signature cards of each archetype from its labeled card sets.

    A card scores ``presence_in_archetype * (1 - presence_elsewhere)``, so
    staples shared with the rest of the metagame lose to cards that only the
    archetype plays.  Ranking by raw frequency instead leaves a quarter of all
    decks tied between several archetypes at match time.

    Archetypes come out ordered by deck count, most played first, because
    :func:`match_archetype` settles ties on that order.
    """
    total_decks = sum(len(deck_sets) for deck_sets in arch_decks.values())
    corpus_hits: Counter[str] = Counter()
    for deck_sets in arch_decks.values():
        for card_set in deck_sets:
            corpus_hits.update(card_set)

    by_prevalence = sorted(arch_decks.items(), key=lambda item: (-len(item[1]), item[0]))

    result: dict[str, list[str]] = {}
    for archetype, deck_sets in by_prevalence:
        deck_count = len(deck_sets)
        if deck_count < min_decks:
            continue

        hits: Counter[str] = Counter()
        for card_set in deck_sets:
            hits.update(card_set)

        outside_decks = max(1, total_decks - deck_count)
        ranked = []
        for card, count in hits.items():
            rate = count / deck_count
            if rate < min_rate:
                continue
            outside_rate = (corpus_hits[card] - count) / outside_decks
            ranked.append((-rate * (1 - outside_rate), card))

        ranked.sort()
        signatures = [card for _, card in ranked[:top_n]]
        if len(signatures) >= min_sigs:
            result[archetype] = signatures

    return result


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

    return build_signature_map(
        arch_decks,
        min_decks=min_decks,
        min_rate=min_rate,
        top_n=top_n,
        min_sigs=min_sigs,
    )


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


def merge_archetype_dictionaries(
    baseline: dict[str, list[str]],
    derived: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Merge mined signatures under a baseline, keeping baseline entries intact.

    The Paupergeddon baseline rests on far more decks per archetype than the
    Pauperwave sample, so it wins wherever both name the same archetype; the
    mined map only contributes archetypes the baseline has never seen.  Those
    additions land after the baseline entries, which keeps the widely played
    archetypes ahead of the local ones in tie-break order.
    """
    merged = dict(baseline)
    for archetype, signatures in derived.items():
        merged.setdefault(archetype, signatures)
    return merged


def match_archetype(
    card_names: set[str],
    archetype_map: dict[str, list[str]],
) -> tuple[str, float]:
    """Return the best-scoring archetype and its score, ``("", 0.0)`` if none.

    Equal scores are common: roughly one deck in twelve matches two archetypes
    perfectly, usually a popular deck against a fringe one built from a subset
    of the same cards.  Those ties go to whichever archetype comes first in
    ``archetype_map``, which the dictionary orders by how often the archetype is
    played, so the label never depends on which entry happens to be visited
    first.  JavaScript preserves the same key order, keeping the frontend in
    agreement with the pipeline.
    """
    best_name = ""
    best_score = 0.0
    for archetype, signatures in archetype_map.items():
        if not signatures:
            continue
        matched = sum(1 for sig in signatures if normalize_card_name(sig) in card_names)
        score = matched / len(signatures)
        if score > best_score:
            best_score = score
            best_name = archetype

    return best_name, best_score


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

    best_name, best_score = match_archetype(card_names, archetype_map)
    if best_name and best_score >= threshold:
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


def rebuild_archetype_dictionary(
    raw_dir: Path = RAW_DIR,
    *,
    baseline_path: Path = BASELINE_PATH,
    output_path: Path = ARCHETYPE_PATH,
) -> dict[str, list[str]]:
    """Rebuild ``archetypes/pauperwave.json`` from the baseline plus raw Pauperwave data."""
    baseline = load_archetype_dictionary(baseline_path)
    derived = build_archetype_dictionary(raw_dir)
    dictionary = merge_archetype_dictionaries(baseline, derived)
    save_archetype_dictionary(dictionary, output_path)
    added = len(dictionary) - len(baseline)
    print(
        f"Archetype dictionary updated: {len(dictionary)} archetypes "
        f"({len(baseline)} from the Paupergeddon baseline, {added} mined from Pauperwave)."
    )
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
