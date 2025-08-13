from dataclasses import dataclass

from .utils import normalize_date


@dataclass
class Tournament:
    site_name: str
    reference_date: str
    event_id: str
    is_ranked: bool

    name: str = ""
    deck_format: str = ""
    branch_name: str = ""

    def __post_init__(self):
        self.deck_format = self.site_name.split("-")[0]
        self.name = " ".join([x.capitalize() for x in self.site_name.split("-")[:2]])
        self.reference_date = self.reference_date.split(" ")[0]
        self.reference_date = normalize_date(self.reference_date)
        self.branch_name = f"{self.name.replace(' ', '_').lower()}-{self.reference_date}"
