"""Build archetypes/paupergeddon.json from the Paupergeddon Hugging Face dataset.

Offline generator: run it by hand whenever the dataset gains a split, then
commit the regenerated baseline.  The crawl pipeline never calls this, it only
reads the JSON the script writes.

    uv run python scripts/import_paupergeddon.py
"""

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.classifier import (  # noqa: E402
    ARCHETYPE_PATH,
    BASELINE_PATH,
    BASIC_LAND_NAMES,
    MATCH_THRESHOLD,
    build_signature_map,
    load_archetype_aliases,
    match_archetype,
    normalize_card_name,
)

DATASET = "vedalken/paupergeddon-decklists"
SPLITS = ("2026_spring", "2026_summer")
PARQUET_URL = (
    "https://huggingface.co/datasets/{dataset}/resolve/"
    "refs%2Fconvert%2Fparquet/default/{split}/0000.parquet"
)
CACHE_DIR = Path(".cache/paupergeddon")
RAW_DIR = Path("assets/pauper/raw")

# Catch-all buckets: the decks under them share no strategy, so any signature
# mined from them would match on staples alone.
EXCLUDED_LABELS = {"others", "other_gates"}

# Titlecasing the snake_case labels covers all but the handful below, where the
# dataset either compresses a guild name or uses colour shorthand.
LABEL_OVERRIDES = {
    "cawgate": "Cawgate",
    "pili-pala": "Pili-Pala",
    "ug_ramp": "Simic Ramp",
    "ur_affinity": "Izzet Affinity",
    "mono_red_synth": "Mono Red Synth",
    "hot_dogs": "Hot Dogs",
}

HOLDOUT_FRACTION = 0.25
HOLDOUT_SEED = 0


def display_name(label: str) -> str:
    """Turn a dataset label such as ``mono_blue_terror`` into ``Mono Blue Terror``."""
    if label in LABEL_OVERRIDES:
        return LABEL_OVERRIDES[label]
    return " ".join(word.capitalize() for word in label.split("_"))


def download_split(split: str, cache_dir: Path = CACHE_DIR) -> Path:
    """Fetch one parquet split, reusing the local cache when present."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{split}.parquet"
    if path.exists():
        return path

    url = PARQUET_URL.format(dataset=DATASET, split=split)
    print(f"  Downloading {split}...")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return path


def load_decks(splits: tuple[str, ...] = SPLITS) -> list[tuple[str, set[str]]]:
    """Return ``(archetype display name, mainboard card names)`` for every deck."""
    frames = [pd.read_parquet(download_split(split)) for split in splits]
    df = pd.concat(frames, ignore_index=True)

    decks = []
    for label, mainboard in zip(df["archetype"], df["mainboard"]):
        if label in EXCLUDED_LABELS:
            continue
        cards = {normalize_card_name(entry["card"]) for entry in mainboard}
        cards -= BASIC_LAND_NAMES
        if cards:
            decks.append((display_name(label), cards))
    return decks


def evaluate(decks: list[tuple[str, set[str]]]) -> dict[str, float]:
    """Score the signature selection on a held-out slice of the dataset.

    Builds the dictionary from the training slice only, so the reported
    accuracy is not the accuracy of memorised decks.  The tie rate counts decks
    that match two or more archetypes equally well and therefore fall through to
    the prevalence ordering of the dictionary.
    """
    shuffled = list(decks)
    random.Random(HOLDOUT_SEED).shuffle(shuffled)
    cut = int(len(shuffled) * (1 - HOLDOUT_FRACTION))
    train, test = shuffled[:cut], shuffled[cut:]

    arch_decks: dict[str, list[set[str]]] = defaultdict(list)
    for archetype, cards in train:
        arch_decks[archetype].append(cards)
    dictionary = build_signature_map(arch_decks)

    correct = unmatched = tied = 0
    for archetype, cards in test:
        name, score = match_archetype(cards, dictionary)
        if not name or score < MATCH_THRESHOLD:
            unmatched += 1
            continue
        correct += name == archetype
        equal = sum(
            1
            for signatures in dictionary.values()
            if signatures
            and sum(1 for sig in signatures if sig in cards) / len(signatures) == score
        )
        tied += equal > 1

    total = len(test) or 1
    return {
        "train": len(train),
        "test": len(test),
        "archetypes": len(dictionary),
        "accuracy": correct / total,
        "ties": tied / total,
        "unmatched": unmatched / total,
    }


def _stored_archetype_labels() -> set[str]:
    """Collect every archetype string already written into the raw tournament data."""
    labels: set[str] = set()
    for path in RAW_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        for deck in data.get("decklists", []):
            label = (deck.get("archetype") or "").strip()
            if label:
                labels.add(label)

    if ARCHETYPE_PATH.exists():
        try:
            labels.update(json.loads(ARCHETYPE_PATH.read_text()))
        except (json.JSONDecodeError, OSError):
            pass
    return labels


def report_unmapped_labels(canonical: set[str]) -> list[str]:
    """List stored labels that are neither canonical nor covered by the alias map."""
    aliases = load_archetype_aliases()
    unmapped = sorted(
        label
        for label in _stored_archetype_labels()
        if label not in canonical and label not in aliases
    )

    if unmapped:
        print(f"\n{len(unmapped)} stored label(s) with no canonical name and no alias:")
        for label in unmapped:
            print(f"  {label}")
    else:
        print("\nEvery stored label maps to a canonical archetype name.")
    return unmapped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report only, leave archetypes/paupergeddon.json untouched",
    )
    args = parser.parse_args()

    print(f"Loading {DATASET}...")
    decks = load_decks()
    counts = Counter(archetype for archetype, _ in decks)
    print(f"Loaded {len(decks)} decks across {len(counts)} labels.")

    arch_decks: dict[str, list[set[str]]] = defaultdict(list)
    for archetype, cards in decks:
        arch_decks[archetype].append(cards)
    dictionary = build_signature_map(arch_decks)

    dropped = sorted(set(counts) - set(dictionary))
    print(f"Kept {len(dictionary)} archetypes with enough decks and distinct signatures.")
    if dropped:
        print(f"Dropped {len(dropped)}: {', '.join(dropped)}")

    report = evaluate(decks)
    print(
        f"\nHoldout ({report['train']} train / {report['test']} test, "
        f"{report['archetypes']} archetypes): accuracy {report['accuracy']:.1%}, "
        f"ties {report['ties']:.1%}, unmatched {report['unmatched']:.1%}"
    )

    report_unmapped_labels(set(dictionary))

    if args.check:
        print(f"\n--check: {BASELINE_PATH} left untouched.")
        return

    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(dictionary, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {BASELINE_PATH} ({len(dictionary)} archetypes).")


if __name__ == "__main__":
    main()
