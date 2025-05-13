import os
from pathlib import Path

from src.saver import Saver

if __name__ == "__main__":
    repo = Path(os.path.dirname(os.path.realpath(__file__))).parent
    saver = Saver(str(repo))
    saver.submit_changes(["./assets/pauper/9081_fszlaien.png"])
