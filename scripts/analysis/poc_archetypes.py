import glob
import json
import re
from collections import Counter

import matplotlib.pyplot as plt
import pandas as pd
from tqdm import tqdm

key_cards = {
    "Myr Enforcer": "Affinity",
    "Kitchen Imp": "Madness Pile",
    "Fireblast": "MonoR Pile",
    "Guttersnipe": "MonoR Pile",
    "Chain Lightning": "MonoR Pile",
    "Grab the Prize": "Madness Pile",
    "Basilisk Gate": "Gates Pile",
    "Timberwatch Elf": "Elves",
    "Urza's Tower": "Tron Pile",
    "High Tide": "High Tide",
    "Spellstutter Sprite": "MonoU Faeries",
    "Sunscape Familiar": "UW Familiar",
    "Tolarian Terror": "MonoU Terror",
    "Prismatic Strands": "MonoW",
    "Guardian's Pledge": "MonoW",
    "Nezumi Linkbreaker": "MonoB Aggro",
    "Glistener Elf": "MonoG Infect",
    "Gladecover Scout": "Hexproof",
    "Lotleth Giant": "GY Pile",
    "Stinkweed Imp": "GY Pile",
    "Cleansing Wildfire": "Wildfire Pile",
    "Skred": "Skred Pile",
    "Goblin Tomb Raider": "MonoR Pile",
    "Experimental Synthesizer": "Synth Pile",
    "Boarding Party": "GR Ramp",
    "Eviscerator's Insight": "Deadly Dispute Pile",
    "Axebane Guardian": "Walls",
    "Lagonna-Band Trailblazer": "MonoW Heroic",
    "Persistent Petitioners": "UG Petitioners",
    "Tireless Tribe": "Tribe",
    "Contentious Plan": "Infect Storm",
    "Songs of the Damned": "Cycling Storm",
    "Eldrazi Repurposer": "RG Ramp",
    "Bannerhide Krushok": "RG Ramp",
}


def label_deck(decklist):
    for card in decklist:
        if card in key_cards:
            return key_cards[card]
    return "Other"


# with open("./assets/meta.json", "r") as f:
#    meta = json.load(f)

df = pd.DataFrame()
for file_path in tqdm(
    glob.glob("./assets/pauper/pauper-league-*.json"), desc="Reading league results"
):
    with open(file_path, "r") as f:
        tournament_data = json.load(f)

    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", file_path)
    date = pd.to_datetime(date_match.group(1)) if date_match else pd.NaT

    decks = []
    for decklist in tournament_data.get("decklists"):
        oracles = []
        for card in decklist["main_deck"]:
            # if card["card_attributes"]["card_name"] not in meta:
            #    body = requests.get(
            #        f"https://api.scryfall.com/cards/search?q={card['card_attributes']['card_name']} -is:reprint"
            #    )
            #    card_data = body.json().get("data")[0]
            #    if "card_faces" in card_data:
            #        oracle_text = card_data.get("card_faces")[0].get("oracle_text")
            #    else:
            #        oracle_text = card_data.get("oracle_text")
            #    meta[card["card_attributes"]["card_name"]] = oracle_text
            oracles.append(
                card["card_attributes"]["card_name"]
            )  # meta.get(card["card_attributes"]["card_name"]))

        decks.append(oracles)

    # with open("./assets/meta.json", "w") as f:
    #    json.dump(meta, f)

    archetypes = []
    for deck in decks:
        label = label_deck(deck).upper()
        if label == "OTHER":
            print(label, "-", deck[:5], "...")
        archetypes.append(label)

    data = Counter(archetypes)

    row = pd.DataFrame(data, index=pd.to_datetime([date]))
    df = pd.concat([df, row])

df.fillna(0, inplace=True)
df.sort_index(inplace=True)
df = df.astype(int)

df = df.loc[df.index >= "2025-01-01", :]
ax = df.div(df.sum(axis=1), axis=0).plot(
    kind="area",
    stacked=True,
    cmap="tab20",
    # color=[color_map[label] for label in df.columns],
    figsize=(20, 10),
)
df.to_csv("./assets/pauper-league-archetypes.csv")

ax.set_facecolor("#fafafa")

plt.title("Archetype dominance in pauper leagues")
plt.legend(bbox_to_anchor=(1.0, 1.0))
plt.grid()
fig = plt.gcf()
# fig.tight_layout()
fig.savefig("./assets/pauper-league-archetypes.png", dpi=300, bbox_inches="tight")
