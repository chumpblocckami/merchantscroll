import glob
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Score:
    wins: int
    losses: int
    loginplayeventcourseid: int

    def __post_init__(self):
        self.wins = int(self.wins)
        self.losses = int(self.losses)
        self.loginplayeventcourseid = int(self.loginplayeventcourseid)


@dataclass
class CardAttributes:
    digitalobjectcatalogid: str
    card_name: str
    rarity: str
    cardset: str

    cost: Optional[str] = None
    color: Optional[str] = None
    card_type: Optional[str] = None
    colors: Optional[List[str]] = field(default_factory=list)


@dataclass
class Card:
    leaguedeckid: int
    loginplayeventcourseid: str
    docid: int
    qty: int
    sideboard: bool
    card_attributes: CardAttributes

    def __post_init__(self):
        self.leaguedeckid = int(self.leaguedeckid)
        self.loginplayeventcourseid = int(self.loginplayeventcourseid)
        self.qty = int(self.qty)
        self.sideboard = bool(self.sideboard)
        try:
            self.card_attributes = CardAttributes(**self.card_attributes)
        except Exception as e:
            print(e)


@dataclass
class Decklist:
    loginplayeventcourseid: int
    loginid: int
    instance_id: str
    player: str
    main_deck: List[Card]
    sideboard_deck: List[Card]
    wins: Score

    def __post_init__(self):
        self.loginplayeventcourseid = int(self.loginplayeventcourseid)
        self.loginid = int(self.loginid)
        self.main_deck = [Card(**card) for card in self.main_deck]
        self.sideboard_deck = [Card(**card) for card in self.sideboard_deck]
        self.wins = Score(**self.wins)


@dataclass
class League:
    playeventid: int
    name: str
    publish_date: datetime
    instance_id: str
    site_name: str
    decklists: List[Decklist]

    def __post_init__(self):
        self.playeventid = int(self.playeventid)
        self.publish_date = datetime.strptime(self.publish_date, "%Y-%m-%d")
        self.decklists = [Decklist(**decklist) for decklist in self.decklists]


def get_best_matching_key(name_list, name_dict):
    max_overlap = 1
    best_key = "Rogue"

    for key, value_names in name_dict.items():
        overlap = len(set(name_list).intersection(value_names))
        if overlap > max_overlap:
            max_overlap = overlap
            best_key = key
    return best_key


if __name__ == "__main__":
    with open("meta.json", "r") as file:
        meta = json.loads(file.read())

    overrall_data = {}
    for file_path in glob.glob("assets/pauper/pauper-league*.json"):
        with open(file_path, "r") as file:
            test = json.loads(file.read())

        league = League(**test)
        print(f"League: {league.name} on {league.publish_date}")

        for decklist in league.decklists:
            names = sorted([card.card_attributes.card_name for card in decklist.main_deck])

            deck_name = get_best_matching_key(names, meta)

            if decklist.player not in overrall_data:
                overrall_data[decklist.player] = {}
            if deck_name not in overrall_data[decklist.player]:
                overrall_data[decklist.player][deck_name] = 0
            overrall_data[decklist.player][deck_name] += 1

            # for card in decklist.main_deck:
            #    query = (
            #        card.card_attributes.card_name.lower()
            #        + " s:"
            #        + card.card_attributes.cardset.lower()
            #    )
            #    card_data = ScryPyFall().get(query)
            #    print(card_data.oracle_text)
    print(overrall_data)
