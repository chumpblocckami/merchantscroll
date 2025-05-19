import os

TIMEOUT = 60

HEADERS = {"User-Agent": "Mozilla/5.0"}
PATTERN = r"window\.MTGO\.decklists\.data\s*=\s*({.*?});"

FORMATS = ["pauper", "modern", "legacy"]

REMOTE_REPO_URL = (
    f"https://x-access-token:{os.getenv('TOKEN_DECKS')}@github.com/chumpblocckami/mtg-decklists.git"
)
