"""Capture mobile viewport screenshots and run layout checks for visual deck view."""

from __future__ import annotations

import argparse
import http.server
import socket
import threading
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tests" / "screenshots" / "mobile"
DEVICES = {
    "iphone_13": "iPhone 13",
    "pixel_7": "Pixel 7",
}


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_server(port: int) -> http.server.ThreadingHTTPServer:
    handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(  # noqa: E731
        *args,
        directory=str(ROOT),
        **kwargs,
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def wait_for_deck(page, timeout_ms: int = 45_000) -> None:
    page.wait_for_selector(".deck-container", timeout=timeout_ms)
    page.wait_for_function(
        """() => {
          const loader = document.getElementById("loader");
          return !loader || loader.style.display === "none";
        }""",
        timeout=timeout_ms,
    )


def set_view_mode(page, mode: str) -> None:
    page.evaluate("(mode) => localStorage.setItem('ms-deck-view', mode)", mode)
    page.reload(wait_until="domcontentloaded")
    wait_for_deck(page)


def collect_layout_metrics(page) -> dict:
    return page.evaluate(
        """() => {
          const columns = document.querySelector(".decklist-columns.visual-mode");
          const tiles = document.querySelectorAll(".card-tile");
          const imgs = document.querySelectorAll(".card-tile-img[src]");
          const textBtn = document.querySelector(".deck-view-toggle");
          const exportBtn = document.querySelector(".download-btn");
          const btnStyle = (el) => el ? getComputedStyle(el) : null;
          const textStyle = btnStyle(textBtn);
          const exportStyle = btnStyle(exportBtn);
          return {
            tileCount: tiles.length,
            loadedImages: [...imgs].filter((img) => img.complete && img.naturalWidth > 0).length,
            columnsOverflow: columns
              ? columns.scrollHeight - columns.clientHeight
              : null,
            buttonsMatch: textStyle && exportStyle
              ? textStyle.borderRadius === exportStyle.borderRadius
                && textStyle.borderColor === exportStyle.borderColor
                && textStyle.color === exportStyle.color
              : false,
          };
        }"""
    )


def run(device_key: str, headless: bool, wait_images_ms: int) -> int:
    device_name = DEVICES[device_key]
    port = free_port()
    server = start_server(port)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    failures = 0
    try:
        with sync_playwright() as playwright:
            device = playwright.devices[device_name]
            browser = playwright.chromium.launch(headless=headless)
            context = browser.new_context(**device)
            page = context.new_page()

            page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded")
            set_view_mode(page, "text")
            page.screenshot(path=str(OUT_DIR / "01-text-mode.png"), full_page=True)

            set_view_mode(page, "visual")
            page.wait_for_timeout(wait_images_ms)
            page.screenshot(path=str(OUT_DIR / "02-visual-mode.png"), full_page=True)

            metrics = collect_layout_metrics(page)
            print(f"Device: {device_name}")
            print(f"Screenshots: {OUT_DIR}")
            print(f"Tiles: {metrics['tileCount']}")
            print(f"Loaded card images: {metrics['loadedImages']}")
            print(f"Visual columns overflow (px): {metrics['columnsOverflow']}")
            print(f"Action buttons styled consistently: {metrics['buttonsMatch']}")

            if metrics["tileCount"] == 0:
                print("FAIL: no card tiles rendered in visual mode")
                failures += 1
            if metrics["columnsOverflow"] is not None and metrics["columnsOverflow"] > 2:
                print("FAIL: visual deck grid still scrolls internally")
                failures += 1
            if not metrics["buttonsMatch"]:
                print("FAIL: Text and Export buttons have mismatched styles")
                failures += 1

            browser.close()
    except PlaywrightError as err:
        print(f"Playwright error: {err}")
        failures += 1
    finally:
        server.shutdown()

    if failures:
        print(f"\n{failures} check(s) failed.")
        return 1

    print("\nAll mobile visual checks passed.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--device",
        choices=sorted(DEVICES),
        default="iphone_13",
        help="Playwright device profile to emulate",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run with a visible browser window",
    )
    parser.add_argument(
        "--wait-images-ms",
        type=int,
        default=4000,
        help="Extra wait time for Scryfall card images to load",
    )
    args = parser.parse_args()
    raise SystemExit(run(args.device, headless=not args.headed, wait_images_ms=args.wait_images_ms))


if __name__ == "__main__":
    main()
