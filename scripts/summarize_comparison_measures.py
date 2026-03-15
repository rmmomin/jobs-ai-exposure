"""Build a unified summary table of occupation and industry comparison measures."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from comparison_config import COMPARISON_TABLES_DIR, ensure_comparison_dirs
from paths import resolve_project_path


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def build_occupation_rows(tables_dir: Path) -> list[dict[str, object]]:
    inventory = _safe_read_csv(tables_dir / "occupation_metric_inventory.csv")
    if inventory.empty:
        return []

    summary = _safe_read_csv(tables_dir / "occupation_comparison_summary.csv")
    overlap = {}
    if not summary.empty:
        overlap = (
            summary.groupby("metric", as_index=False)["overlap_count"]
            .max()
            .set_index("metric")["overlap_count"]
            .to_dict()
        )

    rows: list[dict[str, object]] = []
    for _, row in inventory.iterrows():
        metric = str(row.get("metric", ""))
        rows.append(
            {
                "level": "occupation",
                "measure": metric,
                "source_file": row.get("source_file", ""),
                "source_sheet": row.get("sheet_name", ""),
                "grain": row.get("grain", "soc_code"),
                "rows_loaded": int(row.get("rows", 0) or 0),
                "max_overlap_with_internal": int(overlap.get(metric, 0) or 0),
            }
        )
    return rows


def build_industry_rows(tables_dir: Path) -> list[dict[str, object]]:
    inventory = _safe_read_csv(tables_dir / "industry_metric_inventory.csv")
    if inventory.empty:
        return []

    summary = _safe_read_csv(tables_dir / "industry_comparison_summary.csv")
    overlap = {}
    if not summary.empty:
        overlap = (
            summary.groupby("metric", as_index=False)["overlap_count"]
            .max()
            .set_index("metric")["overlap_count"]
            .to_dict()
        )

    metric_source = {
        "felten_base_aiie": ("AIOE_DataAppendix.xlsx", "Appendix B", "naics4"),
        "felten_language_modeling_aiie": ("Language_Modeling_AIOE_and_AIIE.xlsx", "LM AIIE", "naics4"),
        "felten_image_generation_aiie": ("Image_Generation_AIOE_and_AIIE.xlsx", "IG AIIE", "naics4"),
    }

    rows: list[dict[str, object]] = []
    for _, row in inventory.iterrows():
        metric = str(row.get("metric", ""))
        src_file, src_sheet, grain = metric_source.get(metric, ("", "", "naics4"))
        rows.append(
            {
                "level": "industry",
                "measure": metric,
                "source_file": src_file,
                "source_sheet": src_sheet,
                "grain": grain,
                "rows_loaded": int(row.get("rows", 0) or 0),
                "max_overlap_with_internal": int(overlap.get(metric, 0) or 0),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=None, help="Override comparison output root")
    args = parser.parse_args()

    ensure_comparison_dirs()
    if args.output_dir:
        output_root = resolve_project_path(args.output_dir)
        tables_dir = output_root / "tables"
        tables_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_root = COMPARISON_TABLES_DIR.parent
        tables_dir = COMPARISON_TABLES_DIR

    rows = build_occupation_rows(tables_dir) + build_industry_rows(tables_dir)
    out = pd.DataFrame(
        rows,
        columns=[
            "level",
            "measure",
            "source_file",
            "source_sheet",
            "grain",
            "rows_loaded",
            "max_overlap_with_internal",
        ],
    )
    out = out.sort_values(["level", "measure"]).reset_index(drop=True)
    out_path = tables_dir / "measure_comparison_summary.csv"
    out.to_csv(out_path, index=False)
    print(f"Wrote {len(out)} rows to {out_path}")


if __name__ == "__main__":
    main()
