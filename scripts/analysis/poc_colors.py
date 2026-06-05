import glob
import json
import re
from collections import Counter

import matplotlib.pyplot as plt
import pandas as pd
from tqdm import tqdm

color_map = {
    "COLORLESS": "lightgray",
    "RED": "red",
    "GREEN": "green",
    "BLACK": "black",
    "BLUE": "blue",
    "WHITE": "yellow",
    "MULTICOLORED": "purple",
}


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
        colors = []
        for card in decklist["main_deck"]:
            try:
                if card["card_attributes"]["card_type"].strip() != "LAND":
                    card_colors = int(card["qty"]) * [card["card_attributes"]["color"]]
                    colors.extend(card_colors)
            except Exception as e:
                print(f"Error processing card {card}: {e}")
                continue

        for card in decklist["sideboard_deck"]:
            try:
                if card["card_attributes"]["card_type"].strip() != "LAND":
                    card_colors = int(card["qty"]) * [card["card_attributes"]["color"]]
                    colors.extend(card_colors)
            except Exception as e:
                print(f"Error processing card {card}: {e}")
                continue

        decks.extend(colors)

    data = Counter(decks)

    row = pd.DataFrame(data, index=pd.to_datetime([date]))
    df = pd.concat([df, row])

df.fillna(0, inplace=True)
df.sort_index(inplace=True)
df = df.astype(int)
df = df.loc[df.index >= "2025-05-01", :]
ax = df.div(df.sum(axis=1), axis=0).plot(
    kind="area",
    stacked=True,
    color=[color_map.get(label, "gray") for label in df.columns],
    figsize=(20, 10),
)
ax.set_facecolor("#fafafa")
plt.title("Color dominance in pauper leagues")
plt.legend(bbox_to_anchor=(1.0, 1.0))
fig = plt.gcf()
# fig.tight_layout()
fig.savefig("pauper-league-stacked-bar.png", dpi=300, bbox_inches="tight")
