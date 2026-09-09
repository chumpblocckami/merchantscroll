"""The single writer for stored tournament files."""

import json
from pathlib import Path


def encode_tournament(data: dict) -> str:
    """Serialise a tournament as compact JSON with a trailing newline.

    Indentation cost the stored corpus more bytes than the decklists it wrapped
    and nothing reads these files by hand, so they are written dense.
    """
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n"


def write_tournament(file_path: Path | str, data: dict) -> None:
    """Write a tournament file, creating parent directories as needed.

    Every writer routes through here so that a re-save, a starttime fix, or an
    archetype relabel cannot re-inflate what ``scripts/compact_raw.py`` squeezed
    out.
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encode_tournament(data), encoding="utf-8")
