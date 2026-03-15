"""Download public comparison datasets into data/source/comparison/."""

from __future__ import annotations

import argparse
from typing import Any

import pandas as pd
import httpx

from comparison_utils import (
    COMPARISON_DOWNLOADS,
    comparison_download_path,
    download_file,
    ensure_comparison_dirs,
    inspect_excel_workbook,
    write_table,
)
from paths import COMPARISON_CLEANED_DIR


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload files even when they already exist locally.",
    )
    args = parser.parse_args()

    ensure_comparison_dirs()

    rows: list[dict[str, Any]] = []
    inventories: list[pd.DataFrame] = []
    for target in COMPARISON_DOWNLOADS:
        output_path = comparison_download_path(target["name"])
        existed = output_path.exists()
        row = {
            "name": target["name"],
            "kind": target["kind"],
            "path": str(output_path),
            "downloaded": False,
            "status": "ok",
            "error": "",
        }
        try:
            download_file(target["url"], output_path, force=args.force)
            row["downloaded"] = not existed or args.force
            if output_path.suffix.lower() == ".xlsx":
                try:
                    inventories.append(inspect_excel_workbook(output_path))
                except Exception as exc:
                    inventories.append(
                        pd.DataFrame(
                            [
                                {
                                    "source_path": str(output_path),
                                    "sheet_name": "",
                                    "header_row": None,
                                    "row_count": 0,
                                    "column_count": 0,
                                    "columns": f"ERROR: {exc}",
                                }
                            ]
                        )
                    )
            print(f"{'Updated' if not existed or args.force else 'Kept'} {output_path}")
        except httpx.HTTPError as exc:
            row["status"] = "error"
            row["error"] = str(exc)
            print(f"WARN could not download {target['name']}: {exc}")
        rows.append(row)

    write_table(pd.DataFrame(rows), COMPARISON_CLEANED_DIR / "download_manifest.csv")
    if inventories:
        write_table(
            pd.concat(inventories, ignore_index=True),
            COMPARISON_CLEANED_DIR / "comparison_workbook_inventory.csv",
        )

    print(f"Wrote download manifest to {COMPARISON_CLEANED_DIR / 'download_manifest.csv'}")


if __name__ == "__main__":
    main()
