"""
Process scraped HTML files into Markdown.

Reads from `data/source/html/` and writes to `data/pages/`.

Usage:
    uv run python scripts/process.py
    uv run python scripts/process.py --force
"""

import argparse
import json

from parse_detail import parse_ooh_page
from paths import HTML_DIR, OCCUPATIONS_JSON, PAGES_DIR, ensure_data_dirs


def main():
    parser = argparse.ArgumentParser(description="Convert HTML to Markdown")
    parser.add_argument("--force", action="store_true", help="Re-process even if .md exists")
    args = parser.parse_args()

    ensure_data_dirs()
    with OCCUPATIONS_JSON.open(encoding="utf-8") as f:
        occupations = json.load(f)

    processed = 0
    skipped = 0
    missing = 0

    for occ in occupations:
        slug = occ["slug"]
        html_path = HTML_DIR / f"{slug}.html"
        md_path = PAGES_DIR / f"{slug}.md"

        if not html_path.exists():
            missing += 1
            continue

        if not args.force and md_path.exists():
            skipped += 1
            continue

        md_path.write_text(parse_ooh_page(html_path), encoding="utf-8")
        processed += 1

    total_html = len(list(HTML_DIR.glob("*.html")))
    total_md = len(list(PAGES_DIR.glob("*.md")))
    print(f"Processed: {processed}, Skipped (cached): {skipped}, Missing HTML: {missing}")
    print(f"Total: {total_html} HTML files, {total_md} Markdown files")


if __name__ == "__main__":
    main()
