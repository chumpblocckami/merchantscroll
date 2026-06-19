"""Rules for when to re-crawl stored tournaments and when to persist them."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from .utils import extract_date

LEAGUE_WEEK_DAYS = 7
RECENT_EVENT_RETRY_DAYS = 3


def event_date(site_name: str) -> date | None:
    """Return the calendar date encoded in a tournament slug, if any."""
    raw = extract_date(site_name)
    if raw == "0000-00-00":
        return None
    return datetime.strptime(raw, "%Y-%m-%d").date()


def is_active_league(site_name: str, *, today: date | None = None) -> bool:
    """Return whether a league file may still receive new deck submissions."""
    if "-league-" not in site_name:
        return False
    start = event_date(site_name)
    if start is None:
        return False
    today = today or datetime.now().date()
    return (today - start).days < LEAGUE_WEEK_DAYS


def is_recent_event(
    site_name: str,
    *,
    days: int = RECENT_EVENT_RETRY_DAYS,
    today: date | None = None,
) -> bool:
    """Return whether a tournament slug is recent enough to retry empty crawls."""
    start = event_date(site_name)
    if start is None:
        return False
    today = today or datetime.now().date()
    return (today - start).days <= days


def stored_deck_counts(raw_dir: Path) -> dict[str, int]:
    """Map each stored tournament slug to its current decklist count."""
    counts: dict[str, int] = {}
    if not raw_dir.exists():
        return counts
    for path in raw_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        counts[path.stem] = len(data.get("decklists", []))
    return counts


def empty_stored_site_names(raw_dir: Path) -> set[str]:
    """Return site names whose stored JSON currently has zero decklists."""
    return {name for name, count in stored_deck_counts(raw_dir).items() if count == 0}


def should_crawl_mtgo(
    site_name: str,
    *,
    exists: bool,
    stored_deck_count: int | None,
    today: date | None = None,
) -> bool:
    """Return whether an MTGO tournament URL should be fetched this run."""
    if not exists:
        return True

    today = today or datetime.now().date()
    if today.isoformat() in site_name:
        return True
    if is_active_league(site_name, today=today):
        return True
    if stored_deck_count == 0 and is_recent_event(site_name, today=today):
        return True
    return False


def should_import_pauperwave(
    site_name: str,
    *,
    exists: bool,
    stored_deck_count: int | None,
) -> bool:
    """Return whether a Pauperwave markdown file should be imported this run."""
    if not exists:
        return True
    return stored_deck_count == 0


def save_tournament_if_nonempty(
    raw_dir: Path,
    site_name: str,
    data: dict,
    *,
    ensure_ascii: bool = False,
) -> tuple[bool, int]:
    """Persist tournament data only when decklists are present.

    Removes a stale empty placeholder file when a re-crawl is still empty.
    Returns ``(changed, deck_count)``.
    """
    deck_count = len(data.get("decklists", []))
    out_path = raw_dir / f"{site_name}.json"
    raw_dir.mkdir(parents=True, exist_ok=True)

    if deck_count == 0:
        if out_path.exists():
            out_path.unlink()
            print(f"  Removed empty placeholder ({site_name}).")
            return True, 0
        print("  Skipped (no decklists yet).")
        return False, 0

    out_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=ensure_ascii) + "\n"
    )
    print(f"  Saved ({deck_count} decks).")
    return True, deck_count


def prune_empty_raw_files(raw_dir: Path) -> int:
    """Delete stored tournament files that still have zero decklists."""
    if not raw_dir.exists():
        return 0

    removed = 0
    for path in raw_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if len(data.get("decklists", [])) == 0:
            path.unlink()
            removed += 1
    if removed:
        print(f"Pruned {removed} empty tournament file(s).")
    return removed
