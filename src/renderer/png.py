import time
from io import BytesIO
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import requests
import scrython
from PIL import Image

from src.constants.crawler import TIMEOUT

matplotlib.use("Agg")

# --- Configuration ---
cols, rows = 5, 3
dpi = 100
img_width_px, img_height_px = 146, 204

# Spacing in pixels
spacing_between_columns_px = 5
spacing_between_rows_px = 65
card_shift_px = 21  # vertical offset for stacked cards

# Convert to inches
img_width_in = img_width_px / dpi
img_height_in = img_height_px / dpi
spacing_col_in = spacing_between_columns_px / dpi
spacing_row_in = spacing_between_rows_px / dpi
card_shift_in = card_shift_px / dpi

# Add 1 extra row for the sideboard
extra_row_height = img_height_in + spacing_row_in
fig_height_in = rows * img_height_in + (rows + 1) * spacing_row_in + extra_row_height
fig_width_in = cols * img_width_in + (cols + 1) * spacing_col_in


def display_deck(deck: dict) -> plt.Figure:
    # Load mainboard card images
    cards = []
    lands = []
    sorted_deck = dict(
        sorted(deck["main"].items(), key=lambda item: (-item[1], item[0]), reverse=False)
    )
    for card_name, quantity in sorted_deck.items():
        time.sleep(0.1)
        scrython_card = scrython.cards.Named(exact=card_name)  # set="card_set")
        card_url = scrython_card.image_uris()["small"]
        card_img = Image.open(BytesIO(requests.get(card_url, timeout=TIMEOUT).content))
        if "Land" in scrython_card.type_line():
            lands.extend([card_img] * quantity)
        else:
            cards.extend([card_img] * quantity)
    cards.extend(lands)

    grouped_cards = [cards[i : i + 4] for i in range(0, len(cards), 4)]  # noqa

    # Load sideboard card images
    side_cards = []
    sorted_side = dict(
        sorted(deck["side"].items(), key=lambda item: (-item[1], item[0]), reverse=False)
    )
    for card_name, quantity in sorted_side.items():
        time.sleep(0.1)
        scrython_card = scrython.cards.Named(exact=card_name)
        card_url = scrython_card.image_uris()["small"]
        card_img = Image.open(BytesIO(requests.get(card_url, timeout=TIMEOUT).content))
        side_cards.extend([card_img] * quantity)

    # Create figure
    fig = plt.figure(figsize=(fig_width_in, fig_height_in), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, fig_width_in)
    ax.set_ylim(0, fig_height_in)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    # Draw main card groups (stacked)
    for i, group in enumerate(grouped_cards):
        col = i % cols
        row = i // cols
        if row >= rows:
            break

        x = spacing_col_in + col * (img_width_in + spacing_col_in)
        base_y = (
            spacing_row_in + (rows - 1 - row) * (img_height_in + spacing_row_in) + extra_row_height
        )

        for j, img in enumerate(group):
            y = base_y - j * card_shift_in
            extent = [x, x + img_width_in, y, y + img_height_in]
            ax.imshow(img, extent=extent)

    bottom_y = spacing_row_in / 2  # bottom padding

    usable_width = fig_width_in - spacing_col_in
    total_card_width = len(side_cards) * img_width_in
    h_spacing = (usable_width - total_card_width) / (len(side_cards) - 1)

    for i, card_image in enumerate(side_cards):
        x = spacing_col_in + i * (img_width_in + h_spacing)
        extent = [x, x + img_width_in, bottom_y, bottom_y + img_height_in]

        ax.imshow(card_image, extent=extent)

    # Add player name, tournament and date
    plt.text(
        0.5,
        1,
        f"{deck['player']}",
        ha="center",
        va="top",
        fontsize=15,
        weight="bold",
        color="black",
        transform=ax.transAxes,
    )
    plt.text(
        0.5,
        0.98,
        f"{deck['tournament']}",
        ha="center",
        va="top",
        fontsize=12,
        weight="bold",
        color="black",
        transform=ax.transAxes,
    )
    plt.text(
        0.5,
        0.96,
        f"{deck['date']}",
        ha="center",
        va="top",
        fontsize=12,
        weight="bold",
        color="black",
        transform=ax.transAxes,
    )

    return plt.gcf()


def write_png(deck: dict, path: str | Path = "figure.png"):
    fig = display_deck(deck)
    path = Path(path)
    fig.savefig(
        path.resolve(),
        dpi=100,
        bbox_inches="tight",
    )
    plt.close()
