"""The Hugging Face dataset that stores every crawled tournament.

Git carries only code: CI pulls the dataset into ``assets/pauper``, crawls,
pushes back the files that changed, and rebuilds the derived profiles from it.

Usage:
    uv run python -m src.hub pull       # fetch the data for local work
    uv run python -m src.hub publish    # one-time upload of local data + card
"""

import hashlib
import os
import sys
from pathlib import Path

from huggingface_hub import (
    CommitOperationAdd,
    CommitOperationDelete,
    HfApi,
    snapshot_download,
)

DATA_DIR = Path("assets/pauper")
DATASET_REPO = os.environ.get("HF_DATASET_REPO", "vedalken/merchantscroll")
SYNCED = ["raw/*.json", "card-art.json", "info.json"]
DATASET_CARD = Path("docs/huggingface-dataset.md")


def fingerprint(data_dir: Path = DATA_DIR) -> dict[str, str]:
    """Map each synced file, relative to ``data_dir``, to its content hash."""
    return {
        path.relative_to(data_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for pattern in SYNCED
        for path in data_dir.glob(pattern)
    }


def diff(before: dict[str, str], after: dict[str, str]) -> tuple[list[str], list[str]]:
    """Return ``(added_or_changed, deleted)`` paths between two fingerprints."""
    upserts = sorted(p for p, digest in after.items() if before.get(p) != digest)
    deletes = sorted(set(before) - set(after))
    return upserts, deletes


def pull(data_dir: Path = DATA_DIR, repo_id: str = DATASET_REPO) -> None:
    """Download the dataset into ``data_dir``.

    Raises if the Hub is unreachable, because rebuilding the site from a
    partial corpus would publish it. ``snapshot_download`` alone does not:
    it falls back to whatever already sits in ``local_dir``.
    """
    revision = HfApi().dataset_info(repo_id).sha
    snapshot_download(
        repo_id,
        repo_type="dataset",
        revision=revision,
        local_dir=data_dir,
        allow_patterns=SYNCED,
    )


def push(
    before: dict[str, str],
    data_dir: Path = DATA_DIR,
    repo_id: str = DATASET_REPO,
    message: str = "Crawler: update tournament data",
) -> bool:
    """Commit every synced file that differs from ``before``.

    Returns whether anything was committed.
    """
    upserts, deletes = diff(before, fingerprint(data_dir))
    if not upserts and not deletes:
        return False
    operations = [
        CommitOperationAdd(path_in_repo=p, path_or_fileobj=str(data_dir / p)) for p in upserts
    ] + [CommitOperationDelete(path_in_repo=p) for p in deletes]
    HfApi().create_commit(repo_id, operations, commit_message=message, repo_type="dataset")
    print(f"Hugging Face: {len(upserts)} file(s) updated, {len(deletes)} deleted.")
    return True


def publish(data_dir: Path = DATA_DIR, repo_id: str = DATASET_REPO) -> None:
    """Create the dataset and upload the whole local corpus plus its card."""
    api = HfApi()
    api.create_repo(repo_id, repo_type="dataset", exist_ok=True)
    push({}, data_dir, repo_id, message="Upload tournament corpus")
    api.upload_file(
        path_or_fileobj=str(DATASET_CARD),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="dataset",
        commit_message="Update dataset card",
    )
    print(f"Published https://huggingface.co/datasets/{repo_id}")


if __name__ == "__main__":
    commands = {"pull": pull, "publish": publish}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        raise SystemExit(f"usage: python -m src.hub {{{'|'.join(commands)}}}")
    commands[sys.argv[1]]()
