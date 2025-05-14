import glob
import os
import shutil
import tempfile
from pathlib import Path, PosixPath

from git import Repo

from .constants import REMOTE_REPO_URL


def push_to_different_remote(
    source_folder: list[str, PosixPath] | str | PosixPath,
    branch: str,
    remote_repo_url=REMOTE_REPO_URL,
    commit_message="Updated files",
):
    # Create a temp directory for isolated git work
    temp_dir = tempfile.mkdtemp()

    # Copy the folder's content to the temp directory
    dest_path = os.path.join(
        temp_dir,
        os.path.basename(source_folder.parent),
        os.path.basename(source_folder),
    )
    shutil.copytree(source_folder, dest_path)

    # Init a new Git repo in the copied folder
    repo = Repo.init(temp_dir)

    # Stage and commit all files
    for file_path in glob.glob(os.path.join(dest_path, "*.png"), recursive=True):
        if os.path.isfile(file_path):
            repo.git.add(file_path)
    repo.index.commit(commit_message)

    # Create and checkout branch
    if branch not in repo.heads:
        repo.git.checkout(b=branch)

    # Add remote
    if "origin" not in [remote.name for remote in repo.remotes]:
        repo.create_remote("origin", remote_repo_url)
    else:
        repo.remotes.origin.set_url(remote_repo_url)

    # Push to remote (force can be dangerous if overwriting)
    repo.remotes.origin.push(refspec=f"{branch}:{branch}", force=True)
    shutil.rmtree(temp_dir)


def push_to_same_remote(
    file_path: str | PosixPath,
    branch: str = "main",
    commit_message: str = "Updated files",
) -> None:
    repo = Repo(Path.cwd())
    git = repo.git
    repo.remotes.origin.pull(branch)

    repo.git.add(file_path)
    if repo.is_dirty(untracked_files=True):
        repo.index.commit(commit_message)
        git.push("origin", branch)
    else:
        print("No changes to commit.")
