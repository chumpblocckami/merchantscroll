import os

from git import GitCommandError, Repo


def commit_and_push(
    file_path: str | list[str], target_branch: str, commit_message: str = "Update data", *kwargs
):
    if kwargs.get("debug"):
        return
    repo = Repo(os.getcwd())
    origin = repo.remotes.origin

    # Ensure pull.rebase is true
    repo.git.config("pull.rebase", "true")

    # Checkout or create the target branch
    if target_branch in repo.heads:
        repo.git.checkout(target_branch)
    else:
        repo.git.checkout("-b", target_branch)

    # Stash changes before pulling
    try:
        if repo.is_dirty(untracked_files=True):
            repo.git.stash("save")

        # Try to pull the remote branch
        try:
            origin.pull(target_branch)
        except GitCommandError:
            print(f"Remote branch '{target_branch}' does not exist yet. Skipping pull.")

        # Pop stash (if any)
        if repo.git.stash("list"):
            repo.git.stash("pop")
    except GitCommandError as e:
        print(f"Git error during pull: {e}")
        return

    # Stage and commit changes
    if isinstance(file_path, str):
        repo.git.add(file_path)
    elif isinstance(file_path, list):
        for path in file_path:
            repo.git.add(path)
    else:
        raise ValueError(
            f"file_path must be a string or a list of strings, found {type(file_path)}"
        )
    if repo.is_dirty(untracked_files=True):
        repo.index.commit(commit_message)
        try:
            head = repo.head.reference
            if head.tracking_branch() is None:
                # First push: set upstream
                repo.git.push("--set-upstream", "origin", target_branch)
            else:
                # Normal push
                repo.git.push("origin", target_branch)
            print(f"Pushed changes to origin/{target_branch}.")
        except GitCommandError as e:
            print(f"Git push failed: {e}")
    else:
        print("No changes to commit.")
