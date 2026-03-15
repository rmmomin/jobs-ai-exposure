"""Download external comparison datasets into data/source/comparison/."""

from __future__ import annotations

import argparse
from pathlib import Path

import httpx

from comparison_config import COMPARISON_DOWNLOADS, COMPARISON_SOURCE_DIR, ensure_comparison_dirs


def download_one(client: httpx.Client, target: Path, url: str, force: bool) -> str:
    if target.exists() and not force:
        return "cached"

    try:
        response = client.get(url, timeout=120)
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover - network/remote-dependent
        return f"failed ({exc})"

    target.write_bytes(response.content)
    return "downloaded"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-download files even if already present")
    args = parser.parse_args()

    ensure_comparison_dirs()

    with httpx.Client(follow_redirects=True) as client:
        for filename, url in COMPARISON_DOWNLOADS.items():
            destination = COMPARISON_SOURCE_DIR / filename
            status = download_one(client, destination, url, force=args.force)
            print(f"[{status}] {filename} <- {url}")


if __name__ == "__main__":
    main()
