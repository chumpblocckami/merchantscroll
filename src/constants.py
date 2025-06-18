import os
from pathlib import Path

TIMEOUT = 60

HEADERS = {"User-Agent": "Mozilla/5.0"}
PATTERN = r"window\.MTGO\.decklists\.data\s*=\s*({.*?});"

FORMATS = ["pauper"]  # ["pauper", "modern", "legacy", "standard","vintage"]

REMOTE_REPO_URL = (
    f"https://x-access-token:{os.getenv('TOKEN_DECKS')}@github.com/chumpblocckami/mtg-decklists.git"
)
TOURNAMENT_FILE_PATH = str(Path("./assets/pauper/tournaments.txt").resolve())
