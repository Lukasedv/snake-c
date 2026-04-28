#!/usr/bin/env python3
"""
Minimal static-file server for the Matopeli web app.

Usage:
    python serve.py          # serves web/ on http://localhost:8000
    python serve.py 9000     # custom port
"""

import http.server
import os
import sys


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    web_dir = os.path.join(os.path.dirname(__file__), "web")
    os.chdir(web_dir)

    handler = http.server.SimpleHTTPRequestHandler
    with http.server.HTTPServer(("", port), handler) as httpd:
        print(f"Serving Matopeli at http://localhost:{port}/")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    main()
