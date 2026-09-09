"""Compact stored raw tournament files down to the fields anything actually reads.

Two things inflated the corpus to 210 MiB. Every writer emits ``indent=2``, and
515 of the 940 stored files never passed through :func:`minify_tournament_data`,
so they still carry the MTGO bookkeeping the crawler received: per-card
``docid``, ``ptc``, ``sideboard``, ``decktournamentid``, and a ``card_attributes``
block with ``rarity``, ``cardset``, ``cost``, and colours the site never opens.

Rewriting them compact leaves every observable value identical, which
``--verify`` checks file by file before anything is written.

    uv run python scripts/compact_raw.py              # measure, write nothing
    uv run python scripts/compact_raw.py --apply
    uv run python scripts/compact_raw.py --apply --backfill-types
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.saver import encode_json, write_json  # noqa: E402
from src.scryfall import build_type_lookup  # noqa: E402

RAW_DIR = Path("assets/pauper/raw")

# Deck keys worth keeping: player and the decks themselves, the colour identity
# the pips render from, plus the archetype and record the profiles group by.
DECK_KEEP = ("colors", "archetype", "wins", "final_rank")


def compact_tournament(data: dict, types: dict[str, str] | None = None) -> dict:
    """Return the tournament with only the fields the site and pipeline read."""
    out = {
        "description": data.get("description", data.get("name", "")),
        "starttime": data.get("starttime", data.get("publish_date", "")),
        "site_name": data.get("site_name", ""),
    }
    if data.get("player_count"):
        out["player_count"] = data["player_count"]

    decks = []
    for deck in data.get("decklists", []):
        slim: dict = {"player": deck.get("player", "")}
        for key in DECK_KEEP:
            if deck.get(key) not in (None, "", [], {}):
                slim[key] = deck[key]

        for section in ("main_deck", "sideboard_deck"):
            slim[section] = [_compact_card(c, types) for c in deck.get(section, [])]
        decks.append(slim)

    out["decklists"] = decks
    return out


def _compact_card(card: dict, types: dict[str, str] | None) -> dict:
    attrs = card.get("card_attributes", {})
    name = attrs.get("card_name", "")
    # Every reader already strips this, so the padding MTGO sends is dead weight.
    card_type = attrs.get("card_type", "").strip()
    if not card_type and types:
        card_type = types.get(name, "")
    return {
        "qty": card["qty"],
        "card_attributes": {"card_name": name, "card_type": card_type},
    }


def observable(data: dict) -> list:
    """Project a tournament down to everything a consumer can distinguish.

    Applies the same ``name``/``publish_date`` fallbacks and ``card_type``
    stripping the readers apply, so two files comparing equal here are
    interchangeable to the site, the classifier, and the stats modules.
    """
    header = [
        data.get("description", data.get("name", "")),
        data.get("starttime", data.get("publish_date", "")),
        data.get("site_name", ""),
        data.get("player_count") or None,
    ]
    decks = []
    for deck in data.get("decklists", []):
        decks.append(
            [
                deck.get("player", ""),
                [deck.get(k) or None for k in DECK_KEEP],
                [
                    [
                        (
                            c.get("card_attributes", {}).get("card_name", ""),
                            c["qty"],
                            c.get("card_attributes", {}).get("card_type", "").strip(),
                        )
                        for c in deck.get(section, [])
                    ]
                    for section in ("main_deck", "sideboard_deck")
                ],
            ]
        )
    return [header, decks]


def differences(before: list, after: list) -> list[str]:
    """Report observable changes, allowing a blank card_type to gain a value."""
    problems = []
    if before[0] != after[0]:
        problems.append(f"header {before[0]} -> {after[0]}")
    if len(before[1]) != len(after[1]):
        return problems + [f"deck count {len(before[1])} -> {len(after[1])}"]

    for old, new in zip(before[1], after[1]):
        if old[0] != new[0] or old[1] != new[1]:
            problems.append(f"deck {old[0]}: {old[1]} -> {new[1]}")
        for old_section, new_section in zip(old[2], new[2]):
            if len(old_section) != len(new_section):
                problems.append(f"deck {old[0]}: card count changed")
                continue
            for (on, oq, ot), (nn, nq, nt) in zip(old_section, new_section):
                if (on, oq) != (nn, nq) or (ot and ot != nt):
                    problems.append(f"deck {old[0]}: {on} {oq} {ot!r} -> {nn} {nq} {nt!r}")
    return problems


def self_check() -> None:
    """Assert the compaction drops the dead weight and keeps everything else."""
    fat = {
        "event_id": "1",
        "name": "Pauper Challenge",
        "publish_date": "2026-01-01 10:00:00.0",
        "site_name": "pauper-challenge-2026-01-01",
        "inplayoffs": "1",
        "winloss": [{"loginid": "7", "wins": 5}],
        "standings": [1, 2, 3],
        "decklists": [
            {
                "loginid": "7",
                "tournamentid": "1",
                "colors": ["R"],
                "archetype": "Burn",
                "wins": {"wins": 5, "losses": 0},
                "player": "alice",
                "main_deck": [
                    {
                        "docid": "68072",
                        "ptc": "0",
                        "qty": "14",
                        "sideboard": "False",
                        "card_attributes": {
                            "digitalobjectcatalogid": "68072",
                            "card_name": "Mountain",
                            "cost": "0",
                            "rarity": "BASIC_LAND",
                            "cardset": "UST",
                            "card_type": "LAND  ",
                            "colors": ["COLOR_COLORLESS"],
                        },
                    },
                    {
                        "qty": "4",
                        "card_attributes": {"card_name": "Nameless Type", "card_type": ""},
                    },
                ],
                "sideboard_deck": [],
            }
        ],
    }

    slim = compact_tournament(fat)
    assert differences(observable(fat), observable(slim)) == [], "compaction lost data"
    assert set(slim) == {"description", "starttime", "site_name", "decklists"}
    deck = slim["decklists"][0]
    assert set(deck) == {
        "player",
        "colors",
        "archetype",
        "wins",
        "main_deck",
        "sideboard_deck",
    }, deck.keys()
    card = deck["main_deck"][0]
    assert set(card) == {"qty", "card_attributes"}
    assert card["card_attributes"] == {"card_name": "Mountain", "card_type": "LAND"}
    assert slim["description"] == "Pauper Challenge"
    assert slim["starttime"] == "2026-01-01 10:00:00.0"

    typed = compact_tournament(fat, {"Nameless Type": "INSTNT"})
    filled = typed["decklists"][0]["main_deck"][1]["card_attributes"]["card_type"]
    assert filled == "INSTNT", filled
    assert differences(observable(fat), observable(typed)) == [], "backfill broke a card"

    print("self-check passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the files")
    parser.add_argument(
        "--backfill-types",
        action="store_true",
        help="fill blank card_type from the cached Scryfall oracle data",
    )
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()

    if args.self_check:
        self_check()
        return 0

    types = build_type_lookup() if args.backfill_types else None
    files = sorted(args.raw_dir.glob("*.json"))
    if not files:
        print(f"no tournament files under {args.raw_dir}")
        return 1

    before_bytes = after_bytes = 0
    rewritten = filled = 0
    broken: list[str] = []

    for path in files:
        blob = path.read_bytes()
        data = json.loads(blob)
        slim = compact_tournament(data, types)

        problems = differences(observable(data), observable(slim))
        if problems:
            broken.append(f"{path.name}: {problems[0]}")
            continue

        filled += sum(
            1
            for deck in slim["decklists"]
            for section in ("main_deck", "sideboard_deck")
            for card in deck[section]
            if card["card_attributes"]["card_type"]
        ) - sum(
            1
            for deck in data.get("decklists", [])
            for section in ("main_deck", "sideboard_deck")
            for card in deck.get(section, [])
            if card.get("card_attributes", {}).get("card_type", "").strip()
        )

        encoded = encode_json(slim).encode()
        before_bytes += len(blob)
        after_bytes += len(encoded)
        if encoded != blob:
            rewritten += 1
            if args.apply:
                write_json(path, slim)

    mib = 1048576
    verb = "rewrote" if args.apply else "would rewrite"
    print(f"{len(files)} files checked, {verb} {rewritten}")
    print(f"  before {before_bytes / mib:8.1f} MiB")
    print(f"  after  {after_bytes / mib:8.1f} MiB", end="  ")
    if before_bytes:
        print(f"({100 * (1 - after_bytes / before_bytes):.0f}% smaller)")
    if types:
        print(f"  card_type backfilled on {filled} cards")
    if broken:
        print(f"\nSKIPPED {len(broken)} file(s) that would lose data:")
        for line in broken[:10]:
            print(f"  {line}")
        return 1
    if not args.apply:
        print("\ndry run, nothing written. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
