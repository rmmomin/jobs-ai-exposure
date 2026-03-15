"""
Render site screenshots to PNG assets in the repo root.

Outputs:
    jobs.png
    exposure_changes.png
"""

from __future__ import annotations

import contextlib
import http.server
import os
import pathlib
import socketserver
import threading

from playwright.sync_api import sync_playwright


ROOT = pathlib.Path(__file__).resolve().parent
SITE_DIR = ROOT / "site"


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE_DIR), **kwargs)

    def log_message(self, format, *args):
        pass


@contextlib.contextmanager
def local_server(port: int = 8123):
    server = ReusableTCPServer(("127.0.0.1", port), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def capture_png(page, url: str, output_path: pathlib.Path, width: int, height: int):
    page.set_viewport_size({"width": width, "height": height})
    page.goto(url, wait_until="networkidle")
    page.screenshot(path=str(output_path), full_page=False)


def main():
    os.chdir(ROOT)
    with local_server() as base_url:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(device_scale_factor=1)
            try:
                capture_png(page, f"{base_url}/index.html", ROOT / "jobs.png", 2048, 1065)
                capture_png(
                    page,
                    f"{base_url}/changes.html",
                    ROOT / "exposure_changes.png",
                    2048,
                    1180,
                )
            finally:
                browser.close()


if __name__ == "__main__":
    main()
