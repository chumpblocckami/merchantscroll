import os 
import sys
sys.path.append('./')
from src.saver import Saver 
from pathlib import Path

if __name__ == "__main__":
    repo = Path(os.path.dirname(os.path.realpath(__file__))).parent
    saver = Saver(str(repo))
    saver.submit_changes(["./assets/pauper/9081_fszlaien.png"])
