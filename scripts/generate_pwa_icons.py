"""Generate PWA icon PNGs from assets/favicon.ico."""

from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "favicon.ico"
OUT_DIR = ROOT / "assets" / "icons"
BG = (15, 15, 15)
WORK_SIZE = 256


def load_largest_icon(path: Path) -> Image.Image:
    with Image.open(path) as img:
        sizes = sorted(img.info.get("sizes", {img.size}), key=max, reverse=True)
        if sizes and sizes[0] != img.size:
            img.size = sizes[0]
            img.load()
        return img.convert("RGBA")


def flood_bbox(
    pixels: np.ndarray,
    seed: tuple[int, int],
    *,
    tolerance: int,
) -> tuple[int, int, int, int] | None:
    height, width = pixels.shape[:2]
    seed_y, seed_x = seed
    target = pixels[seed_y, seed_x, :3].astype(int)
    visited = np.zeros((height, width), dtype=bool)
    queue: deque[tuple[int, int]] = deque([(seed_x, seed_y)])
    min_x = min_y = width
    max_x = max_y = -1

    while queue:
        x, y = queue.popleft()
        if x < 0 or y < 0 or x >= width or y >= height or visited[y, x]:
            continue
        sample = pixels[y, x, :3].astype(int)
        if int(np.max(np.abs(sample - target))) > tolerance:
            continue
        visited[y, x] = True
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)
        queue.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])

    if max_x < 0:
        return None
    return min_x, min_y, max_x, max_y


def centered_scroll_icon(source: Image.Image) -> Image.Image:
    """Crop to the scroll artwork and center it on a square canvas."""
    working = source.resize((WORK_SIZE, WORK_SIZE), Image.Resampling.LANCZOS)
    pixels = np.array(working)

    seeds = [
        ((65, 90), 45),
        ((55, 120), 35),
        ((85, 70), 40),
    ]
    boxes = [flood_bbox(pixels, seed, tolerance=tol) for seed, tol in seeds]
    boxes = [box for box in boxes if box is not None]
    if not boxes:
        return working

    margin = max(4, WORK_SIZE // 24)
    left = max(0, min(box[0] for box in boxes) - margin)
    top = max(0, min(box[1] for box in boxes) - margin)
    right = min(WORK_SIZE - 1, max(box[2] for box in boxes) + margin)
    bottom = min(WORK_SIZE - 1, max(box[3] for box in boxes) + margin)

    cropped = working.crop((left, top, right + 1, bottom + 1))
    side = max(cropped.size)
    canvas = Image.new("RGBA", (side, side), (*BG, 255))
    offset_x = (side - cropped.width) // 2
    offset_y = (side - cropped.height) // 2
    canvas.paste(cropped, (offset_x, offset_y), cropped)
    return canvas


def render_icon(source: Image.Image, size: int, *, padding_ratio: float) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (*BG, 255))
    inner = int(size * (1 - padding_ratio * 2))
    resized = source.resize((inner, inner), Image.Resampling.LANCZOS)
    offset = (size - inner) // 2
    canvas.paste(resized, (offset, offset), resized)
    return canvas.convert("RGB")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = centered_scroll_icon(load_largest_icon(SOURCE))

    render_icon(source, 192, padding_ratio=0.06).save(OUT_DIR / "icon-192.png")
    render_icon(source, 512, padding_ratio=0.06).save(OUT_DIR / "icon-512.png")
    render_icon(source, 512, padding_ratio=0.18).save(OUT_DIR / "icon-512-maskable.png")
    render_icon(source, 180, padding_ratio=0.06).save(OUT_DIR / "apple-touch-icon.png")
    print(f"Wrote icons to {OUT_DIR}")


if __name__ == "__main__":
    main()
