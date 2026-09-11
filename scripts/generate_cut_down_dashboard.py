"""Generate a shareable Cut Down analysis dashboard for Pauper creatures.

Reads tournament decklists and Scryfall oracle data, then writes a single HTML
file you can open locally or host anywhere.

    uv run python scripts/generate_cut_down_dashboard.py
    uv run python scripts/generate_cut_down_dashboard.py
    uv run python scripts/generate_cut_down_dashboard.py -o cutdown/index.html
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

NUMBER_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.classifier import canonical_archetype, normalize_card_name  # noqa: E402
from src.scryfall import DEFAULT_CACHE_PATH, required_colors  # noqa: E402
from src.utils import canonical_starttime  # noqa: E402

RAW_DIR = Path("assets/pauper/raw")
DEFAULT_OUTPUT = Path("cutdown/index.html")

COLOR_BUCKETS = (
    ("white", "White", "W"),
    ("blue", "Blue", "U"),
    ("black", "Black", "B"),
    ("red", "Red", "R"),
    ("green", "Green", "G"),
    ("colorless", "Colorless", "C"),
    ("multicolor", "Multicolor", "M"),
)


def parse_pt(value: object) -> int | None:
    """Return numeric power or toughness, or None when unknown."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    return None


def is_creature_type(type_line: str) -> bool:
    """Return whether a type line describes a creature."""
    return "creature" in (type_line or "").lower()


def name_variants(name: str) -> set[str]:
    """Return MTGO and Scryfall spellings for one card name."""
    variants = {name}
    if " // " in name:
        variants.add(name.replace(" // ", "/"))
        variants.update(part.strip() for part in name.split(" // "))
    for variant in list(variants):
        if not variant.isascii():
            try:
                variants.add(variant.encode("utf-8").decode("latin-1"))
            except UnicodeError:
                pass
    return variants


def _creature_faces(card: dict) -> list[dict]:
    """Return every creature face on a Scryfall card object."""
    faces = card.get("card_faces") or []
    if faces:
        return [face for face in faces if is_creature_type(face.get("type_line", ""))]
    if is_creature_type(card.get("type_line", "")):
        return [card]
    return []


def _face_total(face: dict) -> int | None:
    """Return total power and toughness for one face when both are numeric."""
    power = parse_pt(face.get("power"))
    toughness = parse_pt(face.get("toughness"))
    if power is None or toughness is None:
        return None
    return power + toughness


def _combined_oracle(card: dict, creature_faces: list[dict]) -> str:
    """Return oracle text from every creature face on a card."""
    chunks = [face.get("oracle_text") or "" for face in creature_faces]
    if not chunks:
        chunks = [card.get("oracle_text") or ""]
    return "\n".join(chunk for chunk in chunks if chunk)


def _face_image_url(face: dict, card: dict) -> str | None:
    """Return a stable Scryfall CDN URL for a creature face image."""
    for source in (face, card):
        uris = source.get("image_uris") or {}
        for key in ("normal", "large", "small"):
            if uris.get(key):
                return uris[key]
    return None


def build_creature_lookup(cache_path: Path) -> dict[str, dict]:
    """Build a decklist-name lookup for Pauper creature oracle data."""
    lookup: dict[str, dict] = {}
    with gzip.open(cache_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            card = json.loads(line)
            legalities = card.get("legalities") or {}
            if all(status == "not_legal" for status in legalities.values()):
                continue

            name = card.get("name", "")
            creature_faces = _creature_faces(card)
            if not creature_faces:
                continue

            face_totals = [_face_total(face) for face in creature_faces]
            numeric_totals = [total for total in face_totals if total is not None]
            max_face_total = max(numeric_totals) if numeric_totals else None
            oracle_text = _combined_oracle(card, creature_faces)
            keywords: set[str] = set(card.get("keywords") or [])
            for face in creature_faces:
                keywords.update(face.get("keywords") or [])

            for face in creature_faces:
                type_line = face.get("type_line", "")
                face_name = face.get("name", name)
                colors = face.get("colors") or required_colors(face)
                info = {
                    "name": face_name,
                    "lookup_name": face_name,
                    "full_name": name,
                    "power": parse_pt(face.get("power")),
                    "toughness": parse_pt(face.get("toughness")),
                    "colors": sorted(set(colors)),
                    "type_line": type_line,
                    "oracle_text": oracle_text,
                    "max_face_total": max_face_total,
                    "keywords": sorted(keywords),
                    "image_url": _face_image_url(face, card),
                }
                for variant in name_variants(face_name) | name_variants(name):
                    lookup.setdefault(variant, info)
    return lookup


def resolve_creature(name: str, lookup: dict[str, dict]) -> dict | None:
    """Resolve a decklist creature name to oracle data."""
    for key in (name, name.strip().replace("/", " // ")):
        if key in lookup:
            return lookup[key]
    front = normalize_card_name(name)
    if front in lookup:
        return lookup[front]
    if " // " not in name:
        for info in lookup.values():
            if info["full_name"].startswith(f"{name} //"):
                return info
    return None


def color_bucket(colors: list[str]) -> str:
    """Map a card's colors to one dashboard bucket."""
    if len(colors) >= 2:
        return "multicolor"
    if len(colors) == 1:
        return {"W": "white", "U": "blue", "B": "black", "R": "red", "G": "green"}[colors[0]]
    return "colorless"


def _parse_counter_count(raw: str) -> int:
    """Parse a spelled-out or numeric counter count from oracle text."""
    raw = raw.strip().lower()
    if raw.isdigit():
        return int(raw)
    return NUMBER_WORDS.get(raw, 1)


def is_untargetable(info: dict) -> tuple[bool, str]:
    """Return whether Cut Down cannot target this creature."""
    keywords = {keyword.lower() for keyword in info.get("keywords", [])}
    oracle_text = (info.get("oracle_text") or "").lower()
    if "shroud" in keywords or re.search(r"\bshroud\b", oracle_text):
        return True, "shroud"
    if "hexproof" in keywords or re.search(r"\bhexproof\b", oracle_text):
        return True, "hexproof"
    if "can't be the target of spells or abilities your opponents control" in oracle_text:
        return True, "hexproof"
    return False, ""


def _oracle_for_self_permanent_growth(oracle_text: str) -> str:
    """Keep only oracle lines that can permanently grow this creature."""
    kept: list[str] = []
    for line in oracle_text.split("\n"):
        lowered = line.lower()
        if "until end of turn" in lowered:
            continue
        if "during your turn" in lowered and "gets +" in lowered:
            continue
        if "target creature" in lowered and "this creature" not in lowered and "~" not in lowered:
            continue
        kept.append(line)
    return "\n".join(kept).lower()


def _has_unbounded_growth(oracle_text: str) -> bool:
    """Return whether oracle text can add +1/+1 counters without a fixed cap."""
    oracle_lower = _oracle_for_self_permanent_growth(oracle_text)
    if re.search(r"\bevolve\b", oracle_lower) or re.search(r"\badapt\b", oracle_lower):
        return False
    patterns = (
        r"whenever .* put a \+1/\+1 counter on (?:this creature|~)",
        r"for each .* put a \+1/\+1 counter on (?:this creature|~)",
        r"\{[^}]+\}: put a \+1/\+1 counter on (?:this creature|~)",
        r"sacrifice .*?: .*?put a \+1/\+1 counter on (?:this creature|~)",
    )
    return any(re.search(pattern, oracle_lower) for pattern in patterns)


def _self_stat_oracle(oracle_text: str) -> str:
    """Keep oracle lines where this creature's own power or toughness can change."""
    kept: list[str] = []
    for line in oracle_text.split("\n"):
        lowered = line.lower()
        if "this creature gets +" not in lowered and "~ gets +" not in lowered:
            continue
        if "target creature" in lowered and "this creature gets +" not in lowered:
            continue
        kept.append(line)
    return "\n".join(kept).lower()


def _apply_gets_boosts(power: int, toughness: int, oracle_lower: str) -> int:
    """Return the best total after one self-targeted ``gets +`` line applies."""
    best_total = power + toughness
    for power_bonus, toughness_bonus in re.findall(
        r"(?:this creature|~ ) gets \+(\d+)/\+(\d+)", oracle_lower
    ):
        best_total = max(
            best_total,
            (power + int(power_bonus)) + (toughness + int(toughness_bonus)),
        )
    for power_bonus in re.findall(r"(?:this creature|~ ) gets \+(\d+)/\+0", oracle_lower):
        best_total = max(best_total, (power + int(power_bonus)) + toughness)
    for toughness_bonus in re.findall(r"(?:this creature|~ ) gets \+0/\+(\d+)", oracle_lower):
        best_total = max(best_total, power + (toughness + int(toughness_bonus)))
    for power_bonus, toughness_bonus in re.findall(
        r"gets \+(\d+)/\+(\d+) for each", oracle_lower
    ):
        best_total = max(
            best_total,
            (power + int(power_bonus)) + (toughness + int(toughness_bonus)),
        )
    return best_total


def _has_repeatable_responsive_boost(oracle_text: str) -> bool:
    """Return whether this creature can chain temporary self-boosts."""
    oracle_lower = _self_stat_oracle(oracle_text)
    if not oracle_lower:
        return False
    if "once each turn" in oracle_lower or "activate only once" in oracle_lower:
        return False
    return bool(
        re.search(r"(?:discard|sacrifice)[^.\n]*(?:this creature|~ ) gets \+", oracle_lower)
    )


def _max_permanent_total(info: dict) -> int | None:
    """Estimate the highest permanent total power and toughness."""
    power = info["power"]
    toughness = info["toughness"]
    if power is None or toughness is None:
        return None

    oracle_text = info.get("oracle_text") or ""
    oracle_lower = _oracle_for_self_permanent_growth(oracle_text)
    if _has_unbounded_growth(oracle_text):
        return None

    best_total = power + toughness
    max_face_total = info.get("max_face_total")
    if isinstance(max_face_total, int):
        best_total = max(best_total, max_face_total)

    for power_text, toughness_text in re.findall(
        r"level[^\n]*\n(\d+|\*)/(\d+|\*)", oracle_lower, flags=re.IGNORECASE
    ):
        if power_text.isdigit() and toughness_text.isdigit():
            best_total = max(best_total, int(power_text) + int(toughness_text))

    counter_bonus = 0
    enters_with = re.search(
        r"enters (?:the battlefield )?with ([a-z]+|\d+) \+1/\+1 counters?",
        oracle_lower,
    )
    if enters_with:
        counter_bonus += _parse_counter_count(enters_with.group(1))

    for keyword in ("evolve", "adapt", "renown", "bloodthirst", "modular"):
        if re.search(rf"\b{keyword}\b", oracle_lower):
            counter_bonus += 1

    if "explore" in oracle_lower:
        counter_bonus += 1

    if not re.search(r"\bevolve\b", oracle_lower):
        if re.search(
            r"when (?:this creature|~ ) enters.*?put a \+1/\+1 counter on (?:this creature|~)",
            oracle_lower,
        ) or re.search(r"put a \+1/\+1 counter on (?:this creature|~)", oracle_lower):
            counter_bonus += 1

    if "undying" in oracle_lower or "persist" in oracle_lower:
        counter_bonus = max(counter_bonus, 1)

    best_total = max(best_total, (power + counter_bonus) + (toughness + counter_bonus))
    best_total = max(best_total, _apply_gets_boosts(power, toughness, oracle_lower))

    if re.search(r"power and toughness are each equal to", oracle_lower):
        return None

    return best_total


def _max_responsive_total(info: dict) -> int | None:
    """Estimate the best total this creature can reach with temporary self-boosts."""
    power = info["power"]
    toughness = info["toughness"]
    if power is None or toughness is None:
        return None

    oracle_text = info.get("oracle_text") or ""
    oracle_lower = _self_stat_oracle(oracle_text)
    if not oracle_lower:
        return power + toughness

    if _has_repeatable_responsive_boost(oracle_text):
        return None

    return _apply_gets_boosts(power, toughness, oracle_lower)


def max_potential_total(info: dict) -> int | None:
    """Estimate the highest total this creature can reach before Cut Down resolves."""
    permanent = _max_permanent_total(info)
    responsive = _max_responsive_total(info)
    if permanent is None or responsive is None:
        return None
    return max(permanent, responsive)


def growth_reason(info: dict, max_total: int | None) -> str:
    """Summarize why a creature might grow beyond Cut Down's limit."""
    oracle_text = info.get("oracle_text") or ""
    oracle_lower = oracle_text.lower()
    responsive_lower = _self_stat_oracle(oracle_text)
    reasons: list[str] = []
    if max_total is None:
        if _has_unbounded_growth(oracle_text) or _has_repeatable_responsive_boost(oracle_text):
            reasons.append("repeatable growth")
        else:
            reasons.append("can grow above 5 total")
    max_face_total = info.get("max_face_total")
    base_total = (info["power"] or 0) + (info["toughness"] or 0)
    if isinstance(max_face_total, int) and max_face_total > base_total:
        reasons.append("another form")
    if _has_unbounded_growth(oracle_text):
        reasons.append("+1/+1 counters")
    if responsive_lower and _apply_gets_boosts(
        info["power"] or 0,
        info["toughness"] or 0,
        responsive_lower,
    ) > base_total:
        if "until end of turn" in responsive_lower:
            reasons.append("temporary boost")
        else:
            reasons.append("activated boost")
    if re.search(r"level[^\n]*\n\d+/\d+", oracle_lower, flags=re.IGNORECASE):
        reasons.append("level up")
    if not reasons:
        reasons.append("can grow above 5 total")
    return "; ".join(dict.fromkeys(reasons))


def dies_to_cut_down(info: dict) -> bool | None:
    """Return whether Cut Down destroys this creature, or None if unknown."""
    power = info["power"]
    toughness = info["toughness"]
    if power is None or toughness is None:
        return None
    return power + toughness <= 5


def might_survive_cut_down(info: dict) -> tuple[bool, str]:
    """Return whether a targetable creature can grow above Cut Down's limit."""
    power = info["power"]
    toughness = info["toughness"]
    if power is None or toughness is None:
        return False, ""

    if power + toughness > 5:
        return False, ""

    max_total = max_potential_total(info)
    if max_total is None or max_total > 5:
        return True, growth_reason(info, max_total)
    return False, ""


def _tournament_type(site_name: str) -> str:
    """Return a coarse event label from a tournament site name."""
    if site_name.startswith("pauperwave-"):
        return "irl"
    lower = site_name.lower()
    for kind in ("league", "challenge", "showcase", "preliminary", "premier", "classic"):
        if kind in lower:
            return kind
    return "other"


def _deck_archetype(deck: dict) -> str:
    """Return a readable deck label for archetype breakdowns."""
    archetype = (deck.get("archetype") or "").strip()
    if archetype:
        return canonical_archetype(archetype)
    colors = deck.get("colors") or []
    if colors:
        return "".join(colors)
    return "Unknown"


def _finalize_creature_deck_stats(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert raw counters into the compact deck-context payload."""
    dates = sorted({day[:10] for day in raw["dates"] if day})
    return {
        "decklists": raw["decklists"],
        "copies": raw["copies"],
        "main": raw["main_decks"],
        "side": raw["side_decks"],
        "first": dates[0] if dates else "",
        "last": dates[-1] if dates else "",
        "events": raw["events"].most_common(4),
        "archetypes": raw["archetypes"].most_common(5),
    }


def collect_creature_deck_stats(raw_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Return per-creature deck usage stats and overall analysis metadata."""
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "decklists": 0,
            "copies": 0,
            "main_decks": 0,
            "side_decks": 0,
            "events": Counter(),
            "archetypes": Counter(),
            "dates": [],
        }
    )
    all_dates: list[str] = []
    tournament_count = 0
    decklist_count = 0

    for path in raw_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        tournament_count += 1
        site_name = data.get("site_name", path.stem)
        event_type = _tournament_type(site_name)
        date = canonical_starttime(site_name, data.get("starttime", ""))[:10]
        if date:
            all_dates.append(date)

        for deck in data.get("decklists", []):
            decklist_count += 1
            archetype = _deck_archetype(deck)
            main_creatures: Counter[str] = Counter()
            side_creatures: Counter[str] = Counter()

            for entry in deck.get("main_deck", []):
                attrs = entry.get("card_attributes", {})
                if attrs.get("card_type", "").strip() != "ISCREA":
                    continue
                name = attrs.get("card_name", "").strip()
                if not name:
                    continue
                qty = int(entry.get("qty") or 1)
                main_creatures[name] += qty

            for entry in deck.get("sideboard_deck", []):
                attrs = entry.get("card_attributes", {})
                if attrs.get("card_type", "").strip() != "ISCREA":
                    continue
                name = attrs.get("card_name", "").strip()
                if not name:
                    continue
                qty = int(entry.get("qty") or 1)
                side_creatures[name] += qty

            for name, qty in main_creatures.items():
                stats[name]["copies"] += qty
            for name, qty in side_creatures.items():
                stats[name]["copies"] += qty

            for name in set(main_creatures) | set(side_creatures):
                row = stats[name]
                row["decklists"] += 1
                row["events"][event_type] += 1
                row["archetypes"][archetype] += 1
                if date:
                    row["dates"].append(date)
                if name in main_creatures:
                    row["main_decks"] += 1
                if name in side_creatures:
                    row["side_decks"] += 1

    sorted_dates = sorted({day[:10] for day in all_dates if day})
    analysis = {
        "tournaments": tournament_count,
        "decklists": decklist_count,
        "first_date": sorted_dates[0] if sorted_dates else "",
        "last_date": sorted_dates[-1] if sorted_dates else "",
    }
    return {name: _finalize_creature_deck_stats(raw) for name, raw in stats.items()}, analysis


def collect_metagame_creatures(raw_dir: Path) -> set[str]:
    """Return unique creature names from main decks and sideboards."""
    return set(collect_creature_deck_stats(raw_dir)[0].keys())


def build_dashboard_data(raw_dir: Path, cache_path: Path) -> dict:
    """Build the JSON payload embedded in the dashboard HTML."""
    lookup = build_creature_lookup(cache_path)
    deck_stats, analysis = collect_creature_deck_stats(raw_dir)
    metagame_names = set(deck_stats.keys())

    buckets: dict[str, dict[str, Any]] = {
        key: {
            "label": label,
            "symbol": symbol,
            "dies": [],
            "might_die": [],
            "survives": [],
            "unknown": [],
        }
        for key, label, symbol in COLOR_BUCKETS
    }
    unresolved: list[str] = []

    for deck_name in sorted(metagame_names):
        info = resolve_creature(deck_name, lookup)
        if info is None:
            unresolved.append(deck_name)
            continue

        bucket_key = color_bucket(info["colors"])
        power = info["power"]
        toughness = info["toughness"]
        total = power + toughness if power is not None and toughness is not None else None
        untargetable, untargetable_reason = is_untargetable(info)
        dies = dies_to_cut_down(info)
        conditional, reason = might_survive_cut_down(info)
        card = {
            "name": deck_name,
            "lookup_name": info["lookup_name"],
            "image_url": info.get("image_url"),
            "power": power,
            "toughness": toughness,
            "total": total,
            "colors": info["colors"],
            "type_line": info["type_line"],
            "reason": untargetable_reason or reason,
            "decks": deck_stats.get(deck_name, {}),
        }

        if untargetable:
            buckets[bucket_key]["survives"].append(card)
        elif dies is False:
            buckets[bucket_key]["survives"].append(card)
        elif dies is True and conditional:
            buckets[bucket_key]["might_die"].append(card)
        elif dies is True:
            buckets[bucket_key]["dies"].append(card)
        else:
            buckets[bucket_key]["unknown"].append(card)

    summary_rows = []
    overall_dies = overall_might_die = overall_survives = overall_total = 0
    for key, label, symbol in COLOR_BUCKETS:
        bucket_data = buckets[key]
        dies_count = len(bucket_data["dies"])
        might_die_count = len(bucket_data["might_die"])
        survives_count = len(bucket_data["survives"])
        total_count = dies_count + might_die_count + survives_count + len(bucket_data["unknown"])
        overall_dies += dies_count
        overall_might_die += might_die_count
        overall_survives += survives_count
        overall_total += total_count
        summary_rows.append(
            {
                "key": key,
                "label": label,
                "symbol": symbol,
                "dies": dies_count,
                "might_die": might_die_count,
                "survives": survives_count,
                "total": total_count,
                "die_pct": round(100 * dies_count / total_count, 1) if total_count else 0.0,
                "might_die_pct": (
                    round(100 * might_die_count / total_count, 1) if total_count else 0.0
                ),
                "survive_pct": round(100 * survives_count / total_count, 1) if total_count else 0.0,
            }
        )

    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "scope": "Pauper metagame creatures from tournament decklists",
        "analysis": analysis,
        "unique_creatures": len(metagame_names),
        "resolved_creatures": len(metagame_names) - len(unresolved),
        "unresolved_creatures": unresolved,
        "summary": {
            "overall": {
                "dies": overall_dies,
                "might_die": overall_might_die,
                "survives": overall_survives,
                "total": overall_total,
                "die_pct": round(100 * overall_dies / overall_total, 1) if overall_total else 0.0,
                "might_die_pct": (
                    round(100 * overall_might_die / overall_total, 1) if overall_total else 0.0
                ),
                "survive_pct": (
                    round(100 * overall_survives / overall_total, 1) if overall_total else 0.0
                ),
            },
            "by_color": summary_rows,
        },
        "buckets": buckets,
    }


def render_html(data: dict) -> str:
    """Render a self-contained HTML dashboard."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>dies to cut down</title>
  <style>
    :root {{
      --bg: #111318;
      --panel: #181b22;
      --text: #ece7df;
      --muted: #9aa3b2;
      --line: rgba(255, 255, 255, 0.08);
      --accent: #d4b06a;
      --white: #f8f6d8;
      --blue: #0e68ab;
      --black: #150b0d;
      --red: #d3202a;
      --green: #00733e;
      --colorless: #c8ccd4;
      --multicolor: linear-gradient(135deg, #d4af37, #00733e, #0e68ab, #d3202a);
      --shadow: 0 18px 50px rgba(0, 0, 0, 0.35);
      --font: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
      --mono: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      background:
        radial-gradient(circle at top, rgba(212, 176, 106, 0.12), transparent 28rem),
        linear-gradient(180deg, #0d1015 0%, #111318 100%);
      font-family: var(--font);
    }}

    .wrap {{
      width: min(1400px, calc(100vw - 2rem));
      margin: 0 auto;
      padding: 2rem 0 4rem;
    }}

    header {{
      margin-bottom: 1.5rem;
    }}

    h1 {{
      margin: 0 0 0.35rem;
      font-size: clamp(2rem, 4vw, 3rem);
      letter-spacing: 0.02em;
      font-weight: 600;
    }}

    .subtitle {{
      margin: 0;
      color: var(--muted);
      max-width: 70ch;
      line-height: 1.5;
    }}

    .summary-table {{
      width: 100%;
      border-collapse: collapse;
      margin: 1.5rem 0 2rem;
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid var(--line);
      border-radius: 14px;
      overflow: hidden;
      box-shadow: var(--shadow);
    }}

    .summary-table th,
    .summary-table td {{
      padding: 0.85rem 1rem;
      text-align: left;
      border-bottom: 1px solid var(--line);
    }}

    .summary-table th {{
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      background: rgba(255, 255, 255, 0.03);
    }}

    .summary-table tr:last-child td {{
      border-bottom: none;
      font-weight: 700;
      background: rgba(212, 176, 106, 0.08);
    }}

    .chip {{
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      font-family: var(--mono);
      font-size: 0.82rem;
    }}

    .mana {{
      width: 1.1rem;
      height: 1.1rem;
      border-radius: 999px;
      display: inline-grid;
      place-items: center;
      font-size: 0.72rem;
      font-weight: 700;
      color: #fff;
      border: 1px solid rgba(255, 255, 255, 0.18);
      text-shadow: 0 1px 1px rgba(0, 0, 0, 0.45);
    }}

    .mana-W {{ background: #f0e68c; color: #222; }}
    .mana-U {{ background: var(--blue); }}
    .mana-B {{ background: var(--black); }}
    .mana-R {{ background: var(--red); }}
    .mana-G {{ background: var(--green); }}
    .mana-C {{ background: #5f6673; }}
    .mana-M {{ background: conic-gradient(#f0e68c, #0e68ab, #150b0d, #d3202a, #00733e, #f0e68c); }}

    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
      gap: 1rem;
    }}

    .panel {{
      display: flex;
      flex-direction: column;
      min-height: 18rem;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      overflow: hidden;
      box-shadow: var(--shadow);
    }}

    .panel-head {{
      padding: 1rem 1rem 0.75rem;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.02);
    }}

    .panel-head h2 {{
      margin: 0;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      font-size: 1.1rem;
    }}

    .panel-count {{
      font-family: var(--mono);
      font-size: 0.95rem;
      color: var(--accent);
      white-space: nowrap;
    }}

    .card-list {{
      list-style: none;
      margin: 0;
      padding: 0.75rem;
      overflow: auto;
      max-height: 28rem;
    }}

    .card-list li {{
      display: flex;
      justify-content: space-between;
      gap: 0.75rem;
      padding: 0.42rem 0.55rem;
      border-radius: 8px;
      cursor: default;
    }}

    .card-list li:hover {{
      background: rgba(255, 255, 255, 0.05);
    }}

    .card-name {{
      color: var(--text);
    }}

    .card-stats {{
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.82rem;
      white-space: nowrap;
    }}

    .card-reason {{
      display: block;
      margin-top: 0.15rem;
      color: #c9a96a;
      font-size: 0.78rem;
      line-height: 1.35;
    }}

    .card-deck-meta {{
      display: block;
      margin-top: 0.2rem;
      color: var(--muted);
      font-family: var(--mono);
      font-size: 0.72rem;
      line-height: 1.4;
    }}

    .card-list li.has-reason {{
      flex-direction: column;
      align-items: stretch;
    }}

    .card-list li.has-reason .card-row {{
      display: flex;
      justify-content: space-between;
      gap: 0.75rem;
    }}

    .empty {{
      padding: 1rem;
      color: var(--muted);
      font-style: italic;
    }}

    .view-toggle {{
      display: inline-flex;
      gap: 0.35rem;
      padding: 0.35rem;
      margin: 1rem 0 0.25rem;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.03);
    }}

    .view-toggle button {{
      border: none;
      background: transparent;
      color: var(--muted);
      font: inherit;
      font-size: 0.95rem;
      padding: 0.55rem 1rem;
      border-radius: 999px;
      cursor: pointer;
      transition: background 0.15s ease, color 0.15s ease;
    }}

    .view-toggle button.active {{
      background: rgba(212, 176, 106, 0.18);
      color: var(--text);
    }}

    .view-toggle button:hover:not(.active) {{
      color: var(--text);
      background: rgba(255, 255, 255, 0.05);
    }}

    .footer {{
      margin-top: 1.5rem;
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.5;
    }}

    #card-preview {{
      position: fixed;
      z-index: 20;
      pointer-events: none;
      display: none;
      width: min(320px, calc(100vw - 2rem));
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 24px 60px rgba(0, 0, 0, 0.55);
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: #0b0d11;
    }}

    #card-preview img {{
      display: block;
      width: 100%;
      height: auto;
    }}

    #card-context {{
      padding: 0.8rem 0.9rem 0.95rem;
      border-top: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.02);
    }}

    #card-context h3 {{
      margin: 0 0 0.45rem;
      font-size: 0.95rem;
      font-weight: 600;
      color: var(--text);
    }}

    #card-context dl {{
      margin: 0;
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 0.2rem 0.75rem;
      font-size: 0.78rem;
      line-height: 1.45;
      color: var(--muted);
    }}

    #card-context dt {{
      color: #7f8794;
      font-family: var(--mono);
      text-transform: uppercase;
      letter-spacing: 0.04em;
      font-size: 0.68rem;
    }}

    #card-context dd {{
      margin: 0;
      color: var(--text);
    }}

    @media (max-width: 720px) {{
      .wrap {{ width: min(100vw - 1rem, 1400px); }}
      .card-list {{ max-height: 20rem; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1 id="page-title">dies to cut down</h1>
      <p class="subtitle" id="subtitle"></p>
      <div class="view-toggle" role="tablist" aria-label="Cut Down analysis view">
        <button type="button" id="view-dies" class="active" role="tab" aria-selected="true">
          Dies to Cut Down
        </button>
        <button type="button" id="view-might-die" role="tab" aria-selected="false">
          Might Die to Cut Down
        </button>
        <button type="button" id="view-survives" role="tab" aria-selected="false">
          Survives Cut Down
        </button>
      </div>
    </header>

    <table class="summary-table" id="summary-table">
      <thead>
        <tr>
          <th>Color</th>
          <th>Always Dies</th>
          <th>Might Die</th>
          <th>Survives</th>
          <th>Total</th>
          <th>Always Die %</th>
          <th>Might Die %</th>
          <th>Survive %</th>
        </tr>
      </thead>
      <tbody id="summary-body"></tbody>
    </table>

    <div class="grid" id="grid"></div>

    <p class="footer" id="footer"></p>
  </div>

  <div id="card-preview">
    <img id="card-preview-img" alt="" />
    <div id="card-context"></div>
  </div>

  <script>
    const DATA = {payload};

    const preview = document.getElementById("card-preview");
    const previewImg = document.getElementById("card-preview-img");
    const cardContext = document.getElementById("card-context");
    const imageCache = new Map();
    const cardByName = new Map();
    let currentView = "dies";

    for (const bucket of Object.values(DATA.buckets)) {{
      for (const cards of Object.values(bucket)) {{
        if (!Array.isArray(cards)) continue;
        for (const card of cards) {{
          cardByName.set(card.name, card);
          cardByName.set(card.lookup_name, card);
        }}
      }}
    }}

    function escapeAttr(value) {{
      return String(value)
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;")
        .replace(/</g, "&lt;");
    }}

    function formatDateRange(first, last) {{
      if (!first && !last) return "unknown dates";
      if (first === last) return first;
      return `${{first}} to ${{last}}`;
    }}

    function formatDeckMeta(decks) {{
      if (!decks || !decks.decklists) return "";
      const range = formatDateRange(decks.first, decks.last);
      const tops = (decks.archetypes || [])
        .slice(0, 2)
        .map(([name]) => name)
        .join(", ");
      const suffix = tops ? ` · ${{tops}}` : "";
      return `${{decks.decklists.toLocaleString()}} decks · ${{range}}${{suffix}}`;
    }}

    function formatEventList(events) {{
      if (!events || !events.length) return "—";
      return events.map(([name, count]) => `${{name}} (${{count}})`).join(", ");
    }}

    function formatArchetypeList(archetypes) {{
      if (!archetypes || !archetypes.length) return "—";
      return archetypes.map(([name, count]) => `${{name}} (${{count}})`).join(", ");
    }}

    function renderCardContext(card) {{
      if (!card || !card.decks || !card.decks.decklists) {{
        cardContext.innerHTML = "";
        return;
      }}
      const decks = card.decks;
      cardContext.innerHTML = `
        <h3>${{card.name}}</h3>
        <dl>
          <dt>Decks</dt><dd>${{decks.decklists.toLocaleString()}} lists · ${{decks.copies.toLocaleString()}} copies</dd>
          <dt>Window</dt><dd>${{formatDateRange(decks.first, decks.last)}}</dd>
          <dt>Events</dt><dd>${{formatEventList(decks.events)}}</dd>
          <dt>Archetypes</dt><dd>${{formatArchetypeList(decks.archetypes)}}</dd>
          <dt>Zones</dt><dd>Main ${{decks.main.toLocaleString()}} · Side ${{decks.side.toLocaleString()}}</dd>
        </dl>`;
    }}

    const VIEWS = {{
      dies: {{
        title: "dies to cut down",
        bucketKey: "dies",
        emptyText: "No creatures in this slice always die to Cut Down.",
        panelCount(row) {{
          return `${{row.dies}} / ${{row.total}}`;
        }},
        showReason: true,
      }},
      might_die: {{
        title: "might die to cut down",
        bucketKey: "might_die",
        emptyText: "No conditional creatures in this slice.",
        panelCount(row) {{
          return `${{row.might_die}} / ${{row.total}}`;
        }},
        showReason: true,
      }},
      survives: {{
        title: "survives cut down",
        bucketKey: "survives",
        emptyText: "No creatures in this slice survive Cut Down.",
        panelCount(row) {{
          return `${{row.survives}} / ${{row.total}}`;
        }},
        showReason: true,
      }},
    }};

    function manaChip(symbol, label) {{
      const letter = symbol === "C" ? "◯" : symbol === "M" ? "★" : symbol;
      return (
        `<span class="chip"><span class="mana mana-${{symbol}}">${{letter}}</span>`
        + `${{label}}</span>`
      );
    }}

    function scryfallImageUrl(name) {{
      const base = "https://api.scryfall.com/cards/named";
      const query = `exact=${{encodeURIComponent(name)}}&format=image&version=normal`;
      return `${{base}}?${{query}}`;
    }}

    function previewImageUrl(card) {{
      if (card.image_url) return card.image_url;
      const cached = imageCache.get(card.lookup_name);
      if (cached) return cached;
      const fallback = scryfallImageUrl(card.lookup_name);
      imageCache.set(card.lookup_name, fallback);
      return fallback;
    }}

    function showPreview(cardKey, event) {{
      const card = cardByName.get(cardKey);
      if (!card) return;
      renderCardContext(card);
      previewImg.alt = card.name;
      previewImg.src = previewImageUrl(card);
      preview.style.display = "block";
      movePreview(event);
    }}

    function movePreview(event) {{
      const offset = 18;
      const width = preview.offsetWidth || 320;
      const height = preview.offsetHeight || 420;
      let x = event.clientX + offset;
      let y = event.clientY + offset;
      if (x + width > window.innerWidth) x = event.clientX - width - offset;
      if (y + height > window.innerHeight) y = event.clientY - height - offset;
      preview.style.left = `${{x}}px`;
      preview.style.top = `${{y}}px`;
    }}

    function hidePreview() {{
      preview.style.display = "none";
      cardContext.innerHTML = "";
    }}

    function renderSummary() {{
      const body = document.getElementById("summary-body");
      body.innerHTML = DATA.summary.by_color.map((row) => `
        <tr>
          <td>${{manaChip(row.symbol, row.label)}}</td>
          <td>${{row.dies}}</td>
          <td>${{row.might_die}}</td>
          <td>${{row.survives}}</td>
          <td>${{row.total}}</td>
          <td>${{row.die_pct}}%</td>
          <td>${{row.might_die_pct}}%</td>
          <td>${{row.survive_pct}}%</td>
        </tr>
      `).join("") + `
        <tr>
          <td><strong>Overall</strong></td>
          <td>${{DATA.summary.overall.dies}}</td>
          <td>${{DATA.summary.overall.might_die}}</td>
          <td>${{DATA.summary.overall.survives}}</td>
          <td>${{DATA.summary.overall.total}}</td>
          <td>${{DATA.summary.overall.die_pct}}%</td>
          <td>${{DATA.summary.overall.might_die_pct}}%</td>
          <td>${{DATA.summary.overall.survive_pct}}%</td>
        </tr>`;
    }}

    function renderPanels() {{
      const view = VIEWS[currentView];
      const grid = document.getElementById("grid");
      grid.innerHTML = DATA.summary.by_color.map((row) => {{
        const bucket = DATA.buckets[row.key];
        const cards = bucket[view.bucketKey].slice().sort((a, b) => {{
          const deckDiff = (b.decks?.decklists || 0) - (a.decks?.decklists || 0);
          return deckDiff !== 0 ? deckDiff : a.name.localeCompare(b.name);
        }});
        const list = cards.length
          ? cards.map((card) => {{
              const reason = view.showReason && card.reason
                ? `<span class="card-reason">${{card.reason}}</span>`
                : "";
              const deckMeta = formatDeckMeta(card.decks);
              const deckLine = deckMeta
                ? `<span class="card-deck-meta">${{deckMeta}}</span>`
                : "";
              const rowClass = reason || deckMeta ? "has-reason" : "";
              return `
              <li class="${{rowClass}}"
                  data-card="${{escapeAttr(card.name)}}">
                <div class="card-row">
                  <span class="card-name">${{card.name}}</span>
                  <span class="card-stats">${{card.power}}/${{card.toughness}}</span>
                </div>
                ${{deckLine}}
                ${{reason}}
              </li>`;
            }}).join("")
          : `<li class="empty">${{view.emptyText}}</li>`;
        return `
          <section class="panel">
            <div class="panel-head">
              <h2>
                ${{manaChip(row.symbol, row.label)}}
                <span class="panel-count">${{view.panelCount(row)}}</span>
              </h2>
            </div>
            <ul class="card-list">${{list}}</ul>
          </section>`;
      }}).join("");

      grid.querySelectorAll(".card-list li[data-card]").forEach((item) => {{
        item.addEventListener("mouseenter", (event) => {{
          showPreview(item.dataset.card, event);
        }});
        item.addEventListener("mousemove", movePreview);
        item.addEventListener("mouseleave", hidePreview);
      }});
    }}

    function setView(viewName) {{
      currentView = viewName;
      const view = VIEWS[viewName];
      document.getElementById("page-title").textContent = view.title;
      for (const name of ["dies", "might_die", "survives"]) {{
        const active = viewName === name;
        const button = document.getElementById(`view-${{name.replace("_", "-")}}`);
        button.classList.toggle("active", active);
        button.setAttribute("aria-selected", active ? "true" : "false");
      }}
      renderPanels();
    }}

    function renderMeta() {{
      const overall = DATA.summary.overall;
      const subtitle = document.getElementById("subtitle");
      const analysis = DATA.analysis || {{}};
      const analysisWindow = formatDateRange(analysis.first_date, analysis.last_date);
      subtitle.textContent =
        `${{DATA.unique_creatures}} Pauper creatures from `
        + `${{analysis.tournaments?.toLocaleString() || "?"}} tournaments, `
        + `${{analysis.decklists?.toLocaleString() || "?"}} decklists `
        + `(${{analysisWindow}}). Hover a card for deck context.`;
      const footer = document.getElementById("footer");
      footer.textContent =
        `Generated ${{new Date(DATA.generated_at).toLocaleString()}} · `
        + `${{overall.dies}} always die (${{overall.die_pct}}%), `
        + `${{overall.might_die}} might die (${{overall.might_die_pct}}%), `
        + `${{overall.survives}} survive (${{overall.survive_pct}}%) out of `
        + `${{overall.total}} resolved metagame creatures. `
        + `${{DATA.unresolved_creatures.length}} creature names could not be matched `
        + "to oracle stats and are excluded.";
    }}

    document.getElementById("view-dies").addEventListener("click", () => setView("dies"));
    document.getElementById("view-might-die").addEventListener("click", () => setView("might_die"));
    document.getElementById("view-survives").addEventListener("click", () => setView("survives"));

    renderSummary();
    renderPanels();
    renderMeta();
  </script>
</body>
</html>
"""


def main() -> None:
    """Generate the dashboard HTML from local tournament and oracle data."""
    parser = argparse.ArgumentParser(description="Generate the Cut Down dashboard HTML.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output HTML path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=DEFAULT_CACHE_PATH,
        help="Path to Scryfall oracle-cards.jsonl.gz cache",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=RAW_DIR,
        help="Directory containing tournament JSON files",
    )
    args = parser.parse_args()

    if not args.cache.exists():
        raise FileNotFoundError(
            f"Oracle cache missing at {args.cache}. Run crawl.py --refresh-scryfall first."
        )
    if not args.raw_dir.exists():
        raise FileNotFoundError(f"Tournament data missing at {args.raw_dir}.")

    data = build_dashboard_data(args.raw_dir, args.cache)
    html = render_html(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    overall = data["summary"]["overall"]
    print(f"Wrote {args.output}")
    print(
        f"Metagame creatures: {data['unique_creatures']} unique, "
        f"{overall['dies']} always die ({overall['die_pct']}%), "
        f"{overall['might_die']} might die ({overall['might_die_pct']}%), "
        f"{overall['survives']} survive ({overall['survive_pct']}%)."
    )

    lookup = build_creature_lookup(args.cache)
    chrysalis = resolve_creature("Writhing Chrysalis", lookup)
    assert chrysalis is not None
    assert might_survive_cut_down(chrysalis)[0], "Writhing Chrysalis should be conditional"
    wayfarer = resolve_creature("Ainok Wayfarer", lookup)
    assert wayfarer is not None
    assert not might_survive_cut_down(wayfarer)[0], "Ainok Wayfarer tops out at 2/2"
    tireless = resolve_creature("Tireless Tribe", lookup)
    assert tireless is not None
    assert might_survive_cut_down(tireless)[0], "Tireless Tribe can boost above 5 total"
    delver = resolve_creature("Delver of Secrets", lookup)
    assert delver is not None
    assert not might_survive_cut_down(delver)[0], "Delver back face is still 5 total"
    experiment_one = resolve_creature("Experiment One", lookup)
    assert experiment_one is not None
    assert max_potential_total(experiment_one) == 4, "Experiment One tops out at 2/2"
    bogle = resolve_creature("Slippery Bogle", lookup)
    assert bogle is not None
    assert is_untargetable(bogle)[0], "Slippery Bogle has hexproof"


if __name__ == "__main__":
    main()
