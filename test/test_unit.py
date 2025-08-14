import json
import os
import sys
import unittest
from datetime import datetime
from functools import reduce

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))  # noqa
from src.crawler import crawl_cards  # noqa
from src.renderer.html import write_html  # noqa
from src.renderer.png import write_png  # noqa

DECK_DATA = json.load(open("test/assets/sample_deck.json"))


def prepare_deck(
    decklist: dict,
    reference_date: str = datetime.now().strftime("%Y-%m-%d"),
    tournament_name: str = "Test Tournament",
    record: str = "test_record",
):
    return {
        "player": decklist["player"],
        "main": reduce(
            lambda acc, x: acc.update(
                {
                    x["card_attributes"]["card_name"]: acc.get(x["card_attributes"]["card_name"], 0)
                    + int(x["qty"])
                }
            )
            or acc,
            decklist["main_deck"],
            {},
        ),
        "side": reduce(
            lambda acc, x: acc.update(
                {
                    x["card_attributes"]["card_name"]: acc.get(x["card_attributes"]["card_name"], 0)
                    + int(x["qty"])
                }
            )
            or acc,
            decklist["sideboard_deck"],
            {},
        ),
        "date": reference_date,
        "tournament": tournament_name + " " + record,
    }


class TestRenderer(unittest.TestCase):
    def test_png_deck(self):
        try:
            os.remove("test/assets/figure.png")
        except FileNotFoundError:
            pass

        deck = prepare_deck(DECK_DATA, path="test/assets/figure.png")
        write_png(deck)
        self.assertTrue("figure.png" in os.listdir("test/assets"))

    def test_html_deck(self):
        try:
            os.remove("test/assets/index.html")
        except FileNotFoundError:
            pass

        deck = prepare_deck(DECK_DATA)
        write_html(deck, path="test/assets/index.html")
        self.assertTrue("index.html" in os.listdir("test/assets"))


class TestCrawler(unittest.TestCase):
    def test_crawl_cards(self):
        crawl_cards()


if __name__ == "__main__":
    unittest.main()
