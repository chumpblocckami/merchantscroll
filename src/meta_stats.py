"""Generate the metagame timeline artifact from tournament data.

One compact file serves every scope the frontend needs (single tournament,
single day, arbitrary timespan), so the browser never has to fetch the raw
tournament tree to compute archetype shares.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .classifier import canonical_archetype
from .deck_stats import archetype_slug
from .player_stats import _tournament_type
from .utils import canonical_starttime

RAW_DIR = Path("assets/pauper/raw")
TIMELINE_PATH = Path("assets/pauper/meta/timeline.json")

UNCLASSIFIED = "Unclassified"


def _deck_archetype(deck: dict) -> str:
    """Return the canonical archetype label, or ``Unclassified`` when absent.

    Unlike deck profiles, decks without a label are not bucketed by color
    identity: a color string is not an archetype and would rank alongside
    real ones.
    """
    label = (deck.get("archetype") or "").strip()
    return canonical_archetype(label) if label else UNCLASSIFIED


def rebuild_metagame_timeline(
    raw_dir: Path = RAW_DIR,
    out_path: Path = TIMELINE_PATH,
) -> int:
    """Write the per-event archetype count timeline. Returns events written.

    Output format, with counts referencing the shared ``archetypes`` table so
    archetype names are stored once instead of per event::

        {
          "generated": "2026-07-31",
          "archetypes": ["Mono Red Madness", "Elves"],
          "events": [
            {"s": site_name, "d": "2026-07-31", "t": "league",
             "n": "Pauper League", "c": [[0, 3], [1, 1]]}
          ]
        }
    """
    if not raw_dir.exists():
        print("No raw directory found, skipping metagame timeline.")
        return 0

    archetype_ids: dict[str, int] = {}
    events: list[dict] = []

    for path in sorted(raw_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        decklists = data.get("decklists", [])
        if not decklists:
            continue

        site_name = data.get("site_name", path.stem)
        counts: Counter[int] = Counter()
        for deck in decklists:
            archetype = _deck_archetype(deck)
            if archetype not in archetype_ids:
                archetype_ids[archetype] = len(archetype_ids)
            counts[archetype_ids[archetype]] += 1

        events.append({
            "s": path.stem,
            "d": canonical_starttime(site_name, data.get("starttime", ""))[:10],
            "t": _tournament_type(site_name),
            "n": data.get("description", site_name),
            "c": sorted(counts.items(), key=lambda item: (-item[1], item[0])),
        })

    # Date alone is not a total order: a whole league week shares one. Two
    # stable passes so the tie breaks ascending while the date stays
    # descending, matching the profile builders.
    events.sort(key=lambda event: event["s"])
    events.sort(key=lambda event: event["d"], reverse=True)

    names = sorted(archetype_ids, key=lambda name: archetype_ids[name])
    payload = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "archetypes": names,
        "slugs": [archetype_slug(name) for name in names],
        "events": events,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))

    decks = sum(count for event in events for _, count in event["c"])
    print(
        f"Metagame timeline updated: {len(events)} events, "
        f"{len(names)} archetypes, {decks} decks."
    )
    return len(events)
