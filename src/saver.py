from git import GitCommandError, Repo
import os 

def commit_and_push(file_path: str, target_branch:str, commit_message: str = ""):
    repo = Repo(os.getcwd())

    if target_branch in repo.heads:
        repo.git.checkout(target_branch)
    else:
        repo.git.checkout('-b', target_branch)
    
    repo.git.add(file_path)
    if repo.is_dirty(untracked_files=True):
        repo.index.commit(commit_message)
        origin = repo.remote(name='origin')
        origin.push(refspec=f"{target_branch}:{target_branch}")
    else:
        print("No changes to commit.")