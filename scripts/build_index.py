"""Build index.json for each format from raw tournament data.

Generates a lightweight index that the frontend loads instead of parsing
tournaments.txt. Each entry contains only the metadata needed to render
the tournament list and lazy-load individual deck files.
"""

import json
import re
import sys
from pathlib import Path

FORMATS = ["pauper"]
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def extract_date(filename: str) -> str:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    return match.group(1) if match else "0000-00-00"


def build_index(fmt: str) -> list[dict]:
    raw_dir = ASSETS_DIR / fmt / "raw"
    if not raw_dir.exists():
        print(f"No raw directory for {fmt}, skipping.")
        return []

    index = []
    for path in sorted(raw_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"Skipping {path.name}: {e}")
            continue

        decklists = data.get("decklists", [])
        entry = {
            "site_name": data.get("site_name", path.stem),
            "description": data.get("description", data.get("name", "")),
            "starttime": data.get("starttime", data.get("publish_date", "")),
            "deck_count": len(decklists),
        }
        index.append(entry)

    index.sort(key=lambda e: e["starttime"], reverse=True)
    return index


def main():
    for fmt in FORMATS:
        index = build_index(fmt)
        out_path = ASSETS_DIR / fmt / "index.json"
        out_path.write_text(json.dumps(index, separators=(",", ":")))
        print(f"{fmt}: {len(index)} tournaments -> {out_path} ({out_path.stat().st_size // 1024}KB)")


if __name__ == "__main__":
    main()
