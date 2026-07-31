"""Check mobile deck swiping, tapping and banner pass-through in emulated Chrome.

Headless Chrome will not natively scroll an inner container from a synthesized
touch gesture, so the touch sequence is dispatched directly and scrollTop is
moved mid-gesture exactly as a real browser would, isolating the app's decision.
"""

from __future__ import annotations

import http.server
import socket
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
results: list[tuple[bool, str, str, str]] = []


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_server(port: int):
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(  # noqa: E731
        *a, directory=str(ROOT), **k
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def record(name, expected, actual):
    results.append((expected == actual, name, expected, actual))


def player(page):
    return page.evaluate(
        "() => document.querySelector('.player-name')?.textContent?.trim() || null"
    )


def modal_open(page):
    return page.evaluate("() => !document.getElementById('player-modal').hidden")


def swipe(page, y_from, y_to, scroll_during=0, x=200):
    cdp = page.context.new_cdp_session(page)
    cdp.send("Input.dispatchTouchEvent",
             {"type": "touchStart", "touchPoints": [{"x": x, "y": y_from}]})
    if scroll_during:
        page.evaluate("(px) => { document.querySelector('.decklist-columns').scrollTop += px; }",
                      scroll_during)
    for i in range(1, 6):
        y = y_from + (y_to - y_from) * i / 5
        cdp.send("Input.dispatchTouchEvent",
                 {"type": "touchMove", "touchPoints": [{"x": x, "y": round(y)}]})
        page.wait_for_timeout(30)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    page.wait_for_timeout(700)


def setup(page, mode="text", height=730, keep_banner=False):
    page.set_viewport_size({"width": 412, "height": height})
    page.evaluate("""([mode, keep]) => {
      localStorage.setItem('ms-deck-view', mode);
      if (!keep) localStorage.setItem('ms-install-banner-dismissed', '1');
    }""", [mode, keep_banner])
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector(".deck-container", timeout=45_000)
    page.wait_for_timeout(2000)
    return page.evaluate("""() => {
      const c = document.querySelector('.decklist-columns');
      const r = c.getBoundingClientRect();
      const h = document.querySelector('.deck-header').getBoundingClientRect();
      return {
        colsMid: Math.round((r.top + r.bottom) / 2),
        hdrMid: Math.round((h.top + h.bottom) / 2),
        canScroll: c.scrollHeight - c.clientHeight,
      };
    }""")


def main() -> None:
    port = free_port()
    server = start_server(port)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 412, "height": 730},
                device_scale_factor=3, is_mobile=True, has_touch=True,
                user_agent=("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
            )
            page = context.new_page()
            page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded")

            s = setup(page)
            b = player(page)
            swipe(page, s["colsMid"] + 70, s["colsMid"] - 70)
            record("swipe over decklist changes deck", "changed",
                   "changed" if player(page) != b else "nothing")

            s = setup(page)
            b = player(page)
            swipe(page, s["hdrMid"] + 70, s["hdrMid"] - 70)
            record("swipe over header changes deck", "changed",
                   "changed" if player(page) != b else "nothing")
            record("swipe over header does not open profile", "closed",
                   "open" if modal_open(page) else "closed")

            s = setup(page, height=380)
            b = player(page)
            swipe(page, s["colsMid"] + 50, s["colsMid"] - 50, scroll_during=40)
            record("swipe that scrolls the list keeps the deck", "same",
                   "same" if player(page) == b else "changed")

            s = setup(page)
            page.evaluate("() => document.querySelector('.player-link')?.click()")
            page.wait_for_timeout(500)
            record("tapping the player link still opens the profile", "open",
                   "open" if modal_open(page) else "closed")

            # Banner pass-through: the element under a finger mid-list must be the
            # deck view, while the banner's own buttons stay hittable.
            setup(page, height=380, keep_banner=True)
            page.evaluate("""() => {
              const b = document.getElementById('install-banner');
              b.hidden = false; b.classList.add('visible');
            }""")
            page.wait_for_timeout(400)
            probe = page.evaluate("""() => {
              const b = document.getElementById('install-banner');
              const r = b.getBoundingClientRect();
              const midX = Math.round(r.left + r.width * 0.25);
              const midY = Math.round((r.top + r.bottom) / 2);
              const btn = document.getElementById('install-banner-action');
              const br = btn.getBoundingClientRect();
              const overText = document.elementFromPoint(midX, midY);
              const overBtn = document.elementFromPoint(
                Math.round((br.left + br.right) / 2), Math.round((br.top + br.bottom) / 2));
              return {
                overText: overText ? (overText.className || overText.tagName) : null,
                overBtn: overBtn ? (overBtn.id || overBtn.className || overBtn.tagName) : null,
              };
            }""")
            record("banner text does not intercept touches", True,
                   "install-banner" not in str(probe["overText"]))
            record("banner Install button is still hittable", "install-banner-action",
                   probe["overBtn"])

            browser.close()
    finally:
        server.shutdown()

    print()
    for ok, name, expected, actual in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if not ok:
            print(f"           expected {expected!r}, got {actual!r}")
    failed = sum(1 for ok, *_ in results if not ok)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
