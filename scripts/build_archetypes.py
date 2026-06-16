"""Build archetypes/pauperwave.json from labeled Pauperwave tournament data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.classifier import rebuild_archetype_dictionary


def main() -> None:
    dictionary = rebuild_archetype_dictionary()
    for name in sorted(dictionary)[:10]:
        cards = ", ".join(dictionary[name][:4])
        print(f"  {name}: {cards}...")
    if len(dictionary) > 10:
        print(f"  ... and {len(dictionary) - 10} more")


if __name__ == "__main__":
    main()
