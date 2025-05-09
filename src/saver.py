import os
import pandas as pd
from git import GitCommandError, Repo

from dotenv import load_dotenv

load_dotenv()
class Saver:
    def __init__(self, repo_path: str) -> None:
        self.repo = Repo(repo_path, search_parent_directories=True)
        self.branch = "main"
        self.github_username = os.environ["USER"]
        self.access_token = os.environ["TOKEN"]
        self.remote_repo = os.environ["REPO"]
        self.endpoint = f"https://{self.github_username}:{self.access_token}@github.com/{self.github_username}/{self.remote_repo}.git"
        self.pull_latest()
        
    def init_repo(self):
        try:
            origin = self.repo.remote(name="origin")
            origin.push(refspec=f"{self.branch}:{self.branch}")
        except GitCommandError as e:
            print(f"GitCommandError: {e}")

    def commit_and_push(self, file_path: str, commit_message: str):

        if self.repo.is_dirty():
            print("This repo has uncommited changes")

        self.repo.index.add([file_path])
        self.repo.index.commit(commit_message)
        origin = self.repo.remote(name="origin")
        origin.set_url(self.endpoint)
        origin.push(refspec=f"{self.branch}:{self.branch}")

    def pull_latest(self):
        origin = self.repo.remote(name="origin")
        origin.pull(self.branch)

    def get_path(self, file: str):
        return f"{os.path.dirname(os.path.dirname(os.path.realpath(__file__)))}/{file}"

    def submit_changes(self, file_paths: list[str]):
        for file_path in file_paths:
            self.commit_and_push(file_path, commit_message=f"feat: added {file_path}")
            self.pull_latest()