from io import BytesIO

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import requests
import scrython
from PIL import Image

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

# 🔺 Add 1 extra row for the 15-card row
extra_row_height = img_height_in + spacing_row_in
fig_height_in = rows * img_height_in + (rows + 1) * spacing_row_in + extra_row_height
fig_width_in = cols * img_width_in + (cols + 1) * spacing_col_in


def display_deck(deck: dict) -> plt.Figure:
    # Load mainboard card images
    cards = []
    last_cards = []
    sorted_deck = dict(sorted(deck["main"].items(), key=lambda item: item[1], reverse=True))
    for card_name, quantity in sorted_deck.items():
        scrython_card = scrython.cards.Named(fuzzy=card_name)
        card_url = scrython_card.image_uris()["small"]
        card_img = Image.open(BytesIO(requests.get(card_url, timeout=10).content))
        if "Land" in scrython_card.type_line():
            last_cards.extend([card_img] * quantity)
        else:
            cards.extend([card_img] * quantity)
    cards.extend(last_cards)
    grouped_cards = [cards[i : i + 4] for i in range(0, len(cards), 4)]  # noqa

    # Load sideboard card images
    side_cards = []
    sorted_side = dict(sorted(deck["side"].items(), key=lambda item: item[1], reverse=True))
    for card_name, quantity in sorted_side.items():
        scrython_card = scrython.cards.Named(fuzzy=card_name)
        card_url = scrython_card.image_uris()["small"]
        card_img = Image.open(BytesIO(requests.get(card_url, timeout=10).content))
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

        #if i == 0:
        #    # Draw red rectangle for deck info
        #    rect = patches.Rectangle(
        #        (x, base_y - (card_shift_in * 3)),
        #        img_width_in,
        #        img_height_in + (card_shift_in * 3),
        #        linewidth=2,
        #        edgecolor="red",
        #        facecolor="none",
        #    )
        #    ax.add_patch(rect)
        #    ax.text(
        #        x + img_width_in / 2,
        #        base_y + img_height_in / 2,
        #        f"{deck['player']}\n{deck['tournament']}\n{deck['date']}",
        #        color="black",
        #        ha="center",
        #        va="center",
        #        fontsize=8,
        #        weight="bold",
        #    )
        #    continue

        for j, img in enumerate(group):
            y = base_y - j * card_shift_in
            extent = [x, x + img_width_in, y, y + img_height_in]
            ax.imshow(img, extent=extent)

    bottom_y = spacing_row_in / 2  # bottom padding

    usable_width = fig_width_in - (cols + 1) * spacing_col_in
    total_card_width = 15 * img_width_in
    h_spacing = (usable_width - total_card_width) / 14

    for i, card_image in enumerate(side_cards):
        x = spacing_col_in + i * (img_width_in + h_spacing)
        extent = [x, x + img_width_in, bottom_y, bottom_y + img_height_in]
        try:
            ax.imshow(card_image, extent=extent)
        except IndexError:
            break  # in case there are fewer than 15 cards

    return plt.gcf()
