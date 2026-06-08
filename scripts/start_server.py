# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Start a local HTTP server for development.

Usage:
    uv run scripts/start_server.py
    uv run scripts/start_server.py --port 3000
"""

import argparse
import http.server
import os


def main():
    parser = argparse.ArgumentParser(description="Start a local dev server")
    parser.add_argument("--port", "-p", type=int, default=8000)
    args = parser.parse_args()

    root = os.path.join(os.path.dirname(__file__), "..")
    os.chdir(root)

    handler = http.server.SimpleHTTPRequestHandler
    server = http.server.HTTPServer(("", args.port), handler)
    print(f"Serving at http://localhost:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
