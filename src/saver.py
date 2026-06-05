import json
from pathlib import Path


def save_json_locally(file_path: Path | str, data: dict):
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
