import re
from dataclasses import asdict, dataclass
from typing import Any, List

import requests
from PIL import Image
from tqdm import tqdm


@dataclass
class Card:
    name: str
    type_line: str
    mana_cost: str
    color_identity: List[str]
    oracle_text: str
    power: int
    toughness: int
    cmc: int = 0
    artwork: str | None = None

    def __post_init__(self):
        self.mana_cost = self.mana_cost.replace("{", "").replace("}", "")
        self.cmc = self.cost_from_string(self.mana_cost)
        self.power = int(self.power) if self.power else self.power
        self.toughness = int(self.toughness) if self.toughness else self.toughness
        if self.artwork:
            self._artwork_image = Image.open(requests.get(self.artwork, stream=True).raw)
        else:
            self._artwork_image = None

    def cost_from_string(self, cost_string: str):
        match = re.match(r"(\d*)", cost_string)
        colorless = int(match.group(1)) if match.group(1) else 0
        symbols = cost_string[match.end() :]
        return colorless + len(symbols)

    def todict(self):
        d = asdict(self)
        d.pop("_artwork_image", None)
        return d


class PileOfCards:
    def __init__(self):
        self.pile = []

    def __len__(self):
        return len(self.pile)

    def __getitem__(self, index):
        return self.pile[index]

    def __iter__(self):
        return iter(self.pile)

    def append(self, item: any):
        self.pile.append(item)

    def extend(self, items: list):
        self.pile.extend(items)

    def __add__(self, other: Any):
        if isinstance(other, PileOfCards):
            return self.pile + other.pile
        return NotImplemented

    def __repr__(self):
        return f"A pile of {len(self.pile)} cards made of {[x.name for x in self.pile[:5]]}..."


def _get_artwork_url(card_data: dict) -> str | None:
    """Extract art_crop URL, handling double-faced cards."""
    image_uris = card_data.get("image_uris")
    if image_uris:
        return image_uris.get("art_crop")
    faces = card_data.get("card_faces", [])
    if faces and faces[0].get("image_uris"):
        return faces[0]["image_uris"].get("art_crop")
    return None


class ScryPyFall:
    url: str = "https://api.scryfall.com/cards/search?q="
    addons: str = (
        " -is:reprint +not:poster+-(set:otj,otp+frame:showcase)+not:extra+-t:stickers -is:meld -is:split -is:flip -is:transform"
    )

    @classmethod
    def get_by_name(cls, card_name: str) -> dict:
        """Search for a card by exact name and return the raw Scryfall dict."""
        response = requests.get(cls.url + card_name.lower() + cls.addons).json()
        card = next(
            iter(
                list(
                    filter(
                        lambda item: item["name"].lower() == card_name.lower(),
                        response["data"],
                    )
                )
            )
        )
        return card

    @classmethod
    def get_by_query(cls, query: str) -> Card:
        """Search by Scryfall query string and return the first result as a Card."""
        url = cls.url + query
        response = requests.get(url)
        raw_card = response.json()["data"][0]
        return Card(
            name=raw_card.get("name"),
            type_line=raw_card.get("type_line"),
            mana_cost=raw_card.get("mana_cost"),
            color_identity=raw_card.get("color_identity"),
            artwork=_get_artwork_url(raw_card),
            oracle_text=raw_card.get("oracle_text"),
            power=raw_card.get("power"),
            toughness=raw_card.get("toughness"),
        )

    @classmethod
    def query(cls, query: str) -> PileOfCards:
        has_more = True
        page = 1
        url = cls.url + query
        pile = PileOfCards()
        while has_more:
            response = requests.get(url)
            has_more = response.json()["has_more"]
            url = response.json()["next_page"] if "next_page" in response.json() else ""
            print(url)
            remaining_pages = int(response.json()["total_cards"] / 175)
            for card in tqdm(
                response.json()["data"],
                desc=f"Downloading {query} {page}/{remaining_pages+1}",
            ):
                # print(card)
                pile.append(
                    Card(
                        name=card.get("name"),
                        type_line=card.get("type_line"),
                        mana_cost=card.get("mana_cost"),
                        color_identity=card.get("color_identity"),
                        artwork=_get_artwork_url(card),
                        oracle_text=card.get("oracle_text"),
                        power=card.get("power"),
                        toughness=card.get("toughness"),
                    )
                )
            page = page + 1
        return pile


if __name__ == "__main__":
    scry = ScryPyFall()
    card = scry.get_by_query("'deep analysis' s:ody")
    print(card)
