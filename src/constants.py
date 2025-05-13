from pathlib import Path

HEADERS = {"User-Agent": "Mozilla/5.0"}
PATTERN = r"window\.MTGO\.decklists\.data\s*=\s*({.*?});"

DECKLISTS_FILE_PATH = str(Path("./assets/decklists.txt").resolve())
TOURNAMENT_FILE_PATH = str(Path("./assets/tournaments.txt").resolve())
