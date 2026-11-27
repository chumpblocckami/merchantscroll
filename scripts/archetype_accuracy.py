"""Measure how often the classifier reproduces the hand-written Pauperwave labels.

Each Pauperwave event is held out in turn: the dictionary is mined from the
other events, merged with the Paupergeddon baseline, and used to label the
held-out decks. The confusion list shows which names to alias next.

    uv run python -m src.hub pull
    uv run python scripts/archetype_accuracy.py
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.classifier import (  # noqa: E402
    BASELINE_PATH,
    MATCH_THRESHOLD,
    RAW_DIR,
    _main_deck_card_names,
    build_signature_map,
    canonical_archetype,
    load_archetype_dictionary,
    match_archetype,
    merge_archetype_dictionaries,
)


def main() -> None:
    baseline = load_archetype_dictionary(BASELINE_PATH)
    events: dict[str, list[tuple[str, set[str]]]] = {}
    for path in sorted(RAW_DIR.glob("pauperwave-*.json")):
        decks = []
        for deck in json.loads(path.read_text()).get("decklists", []):
            label = canonical_archetype(deck.get("archetype", "").strip())
            cards = _main_deck_card_names(deck)
            if label and cards:
                decks.append((label, cards))
        if decks:
            events[path.stem] = decks

    outcome: Counter[str] = Counter()
    confusions: Counter[tuple[str, str]] = Counter()
    for held_out, decks in events.items():
        mined: dict[str, list[set[str]]] = defaultdict(list)
        for name, labeled in events.items():
            if name != held_out:
                for label, cards in labeled:
                    mined[label].append(cards)
        dictionary = merge_archetype_dictionaries(baseline, build_signature_map(mined))
        for label, cards in decks:
            best, score = match_archetype(cards, dictionary)
            guess = canonical_archetype(best) if best and score >= MATCH_THRESHOLD else None
            if guess is None:
                outcome["unlabeled"] += 1
            elif guess == label:
                outcome["correct"] += 1
            else:
                outcome["wrong"] += 1
                confusions[(label, guess)] += 1

    total = sum(outcome.values())
    if not total:
        sys.exit(f"No labeled Pauperwave decks in {RAW_DIR}; run `python -m src.hub pull`.")
    print(f"{total} labeled decks in {len(events)} Pauperwave events")
    for key in ("correct", "wrong", "unlabeled"):
        print(f"  {key:9s} {outcome[key] / total:.1%}")
    print("Most common (true label -> guessed):")
    for (true, guess), count in confusions.most_common(20):
        print(f"  {count:4d}  {true} -> {guess}")


if __name__ == "__main__":
    main()
