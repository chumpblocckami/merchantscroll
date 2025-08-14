import time
from pathlib import Path

import scrython

# --- Configuration ---
cols, rows = 5, 3
img_width_px, img_height_px = 146, 204

# Spacing in pixels
spacing_between_columns_px = 2
spacing_between_rows_px = 10
card_shift_px = 21  # vertical offset for stacked cards in the main grid

stack_size = 4  # cards per main stack


def _fetch_card_urls(deck_section: dict, put_lands_last: bool = False) -> list[str]:
    urls = []
    lands = []
    sorted_part = dict(
        sorted(deck_section.items(), key=lambda item: (-item[1], item[0]), reverse=False)
    )
    for card_name, quantity in sorted_part.items():
        time.sleep(0.5)
        sc = scrython.cards.Named(exact=card_name)
        url = sc.image_uris()["small"]
        if put_lands_last and "Land" in sc.type_line():
            lands.extend([url] * quantity)
        else:
            urls.extend([url] * quantity)
    if put_lands_last:
        urls.extend(lands)
    return urls


def _group(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]  # noqa


def generate_deck_html(deck: dict) -> str:
    main_urls = _fetch_card_urls(deck["main"], put_lands_last=True)
    side_urls = _fetch_card_urls(deck["side"], put_lands_last=False)

    grouped_main = list(_group(main_urls, stack_size))

    fig_width_px = cols * img_width_px + (cols + 1) * spacing_between_columns_px
    inner_width_px = (
        fig_width_px - 2 * spacing_between_columns_px
    )  # same visible width as the mainboard
    # Step between sideboard cards so the first card is flush left, the last card is flush right
    if len(side_urls) <= 1:
        side_step_px = 0
    else:
        side_step_px = (inner_width_px - img_width_px) / (len(side_urls) - 1)

    css = f"""
    :root {{
      --card-w: {img_width_px}px;
      --card-h: {img_height_px}px;
      --col-gap: {spacing_between_columns_px}px;
      --row-gap: {spacing_between_rows_px}px;
      --shift: {card_shift_px}px;
      --fig-w: {fig_width_px}px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
      background: #fff;
      color: #222;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      padding: 24px;
    }}
    .page {{
      width: var(--fig-w);
      max-width: 100%;
    }}
    .header {{
      text-align: center;
      margin-bottom: 12px;
      line-height: 1.2;
    }}
    .header .player {{ font-weight: 700; font-size: 18px; }}
    .header .tourney {{ font-weight: 600; font-size: 14px; }}
    .header .date {{ font-weight: 600; font-size: 14px; }}

    .grid {{
      display: grid;
      grid-template-columns: repeat({cols}, var(--card-w));
      column-gap: var(--col-gap);
      row-gap: var(--row-gap);
      justify-content: start;
      width: var(--fig-w);
      padding-left: var(--col-gap);
      padding-right: var(--col-gap);
      padding-top: var(--row-gap);
      padding-bottom: var(--row-gap);
      background: #fff;
    }}

    .stack {{
      position: relative;
      width: var(--card-w);
      height: calc(var(--card-h) + {stack_size - 1} * var(--shift));
    }}
    .stack img {{
      position: absolute;
      width: var(--card-w);
      height: var(--card-h);
      object-fit: cover;
      border-radius: 6px;
      box-shadow: 0 2px 6px rgba(0,0,0,.25);
      background: #eee;
    }}

    /* Sideboard as one horizontal pile, same inner width as mainboard */
    .sidepile-h {{
      position: relative;
      width: {inner_width_px}px;
      height: var(--card-h);
      margin: 0 auto var(--row-gap) auto;
    }}
    .sidepile-h img {{
      position: absolute;
      width: var(--card-w);
      height: var(--card-h);
      object-fit: cover;
      border-radius: 6px;
      box-shadow: 0 2px 6px rgba(0,0,0,.25);
      background: #eee;
      top: 0;
    }}
    """

    max_stacks = rows * cols
    stack_divs = []
    for i, group in enumerate(grouped_main[:max_stacks]):
        h = img_height_px + max(0, len(group) - 1) * card_shift_px
        imgs = []
        for j, url in enumerate(group):
            top = j * card_shift_px
            imgs.append(f'<img src="{url}" alt="card" loading="lazy" style="top:{top}px;">')
        stack_divs.append(f'<div class="stack" style="height:{h}px;">{"".join(imgs)}</div>')

    # Sideboard single horizontal pile that spans the inner width
    side_imgs = []
    for j, url in enumerate(side_urls):
        left = j * side_step_px
        side_imgs.append(
            f'<img src="{url}" alt="sideboard card" loading="lazy" style="left:{left}px; z-index:{j};">'  # noqa
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{deck.get('player', '')} deck layout</title>
  <style>{css}</style>
</head>
<body>
  <main class="page">
    <header class="header">
      <div class="player">{deck.get('player', '')}</div>
      <div class="tourney">{deck.get('tournament', '')}</div>
      <div class="date">{deck.get('date', '')}</div>
    </header>

    <section class="grid">
      {"".join(stack_divs)}
    </section>

    <section class="sidepile-h">
      {"".join(side_imgs)}
    </section>
  </main>
</body>
</html>
"""
    return html


def write_html(deck: dict, path: str | Path = "index.html") -> Path:
    html = generate_deck_html(deck)
    path = Path(path)
    path.write_text(html, encoding="utf-8")
