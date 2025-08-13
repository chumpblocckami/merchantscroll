from pathlib import Path

TOURNAMENT_FILE_PATH = str(Path("./assets/pauper/tournaments.txt").resolve())
RAW_TOURNAMENT_PATH = "./assets/{deck_format}/{tournament_id}.json"
OUTPUT_PATH = "./{deck_format}/{reference_date}"
OUTPUT_CONTENT_PATH = "./{deck_format}/{reference_date}/{deck_name}"
REMOTE_PATH = "https://raw.githubusercontent.com/chumpblocckami/mtg-decklists/main/{deck_format}/{reference_date}/{deck_name}.png"  # noqa
REMOTE_DECKLISTS_PATH = "./assets/{deck_format}/decklists.txt"
REMOTE_TOURNAMENTS_PATH = "./assets/{deck_format}/tournaments.txt"
