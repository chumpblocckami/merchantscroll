import os
from pathlib import Path
from typing import Union

from git import GitCommandError, InvalidGitRepositoryError, Repo


def git_commit_push(
    file_path: Union[str, Path, list[Union[str, Path]]],
    branch: str,
    commit_message: str = "Update via script",
):
    try:
        # Initialize repo from current directory
        repo = Repo(os.getcwd())
    except InvalidGitRepositoryError:
        print("❌ Not a git repository.")
        return

    # origin = repo.remotes.origin

    # Ensure file_path is a list of Path objects
    if isinstance(file_path, (str, Path)):
        file_paths = [Path(file_path)]
    elif isinstance(file_path, list):
        file_paths = [Path(p) for p in file_path]
    else:
        raise ValueError("file_path must be a string, Path, or list of them")

    # Fetch and checkout/create the branch
    try:
        repo.git.fetch()
        if branch in repo.heads:
            repo.git.checkout(branch)
        else:
            repo.git.checkout("-b", branch)
    except GitCommandError as e:
        print(f"❌ Could not checkout/create branch '{branch}': {e}")
        return

    # Pull latest changes from remote (if it exists)
    try:
        if f"origin/{branch}" in repo.git.branch("-r"):
            repo.git.pull("origin", branch)
        else:
            print(f"ℹ️ Remote branch '{branch}' doesn't exist yet, skipping pull.")
    except GitCommandError as e:
        print(f"❌ Git pull failed: {e}")
        return

    # Add files to staging
    try:
        for path in file_paths:
            repo.git.add(str(path))
    except GitCommandError as e:
        print(f"❌ Error adding files: {e}")
        return

    # Commit and push
    try:
        if repo.is_dirty(index=True, working_tree=False):
            repo.index.commit(commit_message)

            # Push (set upstream if first push)
            tracking = repo.head.reference.tracking_branch()
            if tracking is None:
                repo.git.push("--set-upstream", "origin", branch)
            else:
                repo.git.push("origin", branch)

            print(f"✅ Changes committed and pushed to origin/{branch}.")
        else:
            print("ℹ️ No changes to commit.")
    except GitCommandError as e:
        print(f"❌ Commit or push failed: {e}")
        return
