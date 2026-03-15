"""
Scrape BLS Occupational Outlook Handbook detail pages (raw HTML).

Saves raw HTML to `data/source/html/<slug>.html`.

Usage:
    uv run python scripts/scrape.py
    uv run python scripts/scrape.py --start 0 --end 5
    uv run python scripts/scrape.py --force
"""

import argparse
import json
import time

from playwright.sync_api import sync_playwright

from paths import HTML_DIR, OCCUPATIONS_JSON, ensure_data_dirs


def main():
    parser = argparse.ArgumentParser(description="Scrape BLS OOH pages")
    parser.add_argument("--start", type=int, default=0, help="Start index (inclusive)")
    parser.add_argument("--end", type=int, default=None, help="End index (exclusive)")
    parser.add_argument("--force", action="store_true", help="Re-scrape even if cached")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between requests")
    args = parser.parse_args()

    ensure_data_dirs()
    with OCCUPATIONS_JSON.open(encoding="utf-8") as f:
        occupations = json.load(f)

    end = args.end if args.end is not None else len(occupations)
    subset = occupations[args.start:end]

    to_scrape = []
    for index, occ in enumerate(subset, start=args.start):
        html_path = HTML_DIR / f"{occ['slug']}.html"
        if not args.force and html_path.exists():
            print(f"  [{index}] CACHED {occ['title']}")
            continue
        to_scrape.append((index, occ))

    if not to_scrape:
        print("Nothing to scrape - all cached.")
        return

    print(f"\nScraping {len(to_scrape)} occupations (non-headless Chromium)...\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        for idx, (index, occ) in enumerate(to_scrape):
            html_path = HTML_DIR / f"{occ['slug']}.html"
            print(f"  [{index}] {occ['title']}...", end=" ", flush=True)

            try:
                resp = page.goto(occ["url"], wait_until="domcontentloaded", timeout=15000)
                if resp.status != 200:
                    print(f"HTTP {resp.status} - SKIPPED")
                    continue

                html = page.content()
                html_path.write_text(html, encoding="utf-8")
                print(f"OK ({len(html):,} bytes)")
            except Exception as exc:
                print(f"ERROR: {exc}")

            if idx < len(to_scrape) - 1:
                time.sleep(args.delay)

        browser.close()

    cached = len(list(HTML_DIR.glob("*.html")))
    print(f"\nDone. {cached}/{len(occupations)} HTML files cached in {HTML_DIR}")


if __name__ == "__main__":
    main()
