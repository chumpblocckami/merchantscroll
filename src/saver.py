"""The single writer for stored JSON data artifacts."""

import json
from pathlib import Path


def encode_json(data) -> str:
    """Serialise a data artifact as compact JSON with a trailing newline.

    Indentation cost the stored tournaments more bytes than the decklists it
    wrapped, and nothing reads these files by hand, so they are written dense.
    Curated files that people do edit (the archetype dictionaries, info.json)
    stay indented and deliberately do not come through here.
    """
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n"


def write_json(file_path: Path | str, data) -> None:
    """Write a data artifact, creating parent directories as needed.

    Every writer routes through here so that a re-save, a starttime fix, an
    archetype relabel, or a profile rebuild cannot re-inflate what
    ``scripts/compact_raw.py`` squeezed out.
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encode_json(data), encoding="utf-8")
