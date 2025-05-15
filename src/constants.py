import os
from pathlib import Path

TIMEOUT = 60

HEADERS = {"User-Agent": "Mozilla/5.0"}
PATTERN = r"window\.MTGO\.decklists\.data\s*=\s*({.*?});"

DECKLISTS_FILE_PATH = str(Path("./assets/decklists.txt").resolve())
TOURNAMENT_FILE_PATH = str(Path("./assets/pauper/tournaments.txt").resolve())

REMOTE_REPO_URL = (
    f"https://x-access-token:{os.getenv('TOKEN_DECKS')}@github.com/chumpblocckami/mtg-decklists.git"
)
