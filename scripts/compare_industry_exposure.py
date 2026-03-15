"""Compare internal industry exposure variants against external industry-level AI metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from comparison_utils import ensure_dir, norm_naics, pearson, percentile_ranks, spearman, write_csv
from paths import (
    EXPORTS_DIR,
    INDUSTRY_EXPOSURE_4DIGIT_CSV,
    SCORES_JSON,
    SCORES_ORG_JSON,
    resolve_project_path,
)


def build_custom_industry(scores_path: Path, canonical_scores_path: Path, variant_name: str, output_tables: Path) -> pd.DataFrame:
    base = pd.DataFrame(json.loads(canonical_scores_path.read_text(encoding="utf-8")))
    alt = pd.DataFrame(json.loads(scores_path.read_text(encoding="utf-8")))
    merged = alt[["slug", "exposure"]].merge(base[["slug", "industries"]], on="slug", how="left")
    exploded = merged.explode("industries").dropna(subset=["industries"]).copy()

    exploded["naics_code"] = exploded["industries"].map(lambda x: str(x.get("naics_code")) if isinstance(x, dict) else None)
    exploded["title"] = exploded["industries"].map(lambda x: x.get("title") if isinstance(x, dict) else None)
    exploded["industry_type"] = exploded["industries"].map(lambda x: x.get("industry_type") if isinstance(x, dict) else None)
    exploded["employment_2024"] = exploded["industries"].map(lambda x: x.get("employment_2024") if isinstance(x, dict) else None)
    exploded = exploded.dropna(subset=["naics_code", "employment_2024", "exposure"])  # type: ignore[arg-type]

    exploded["weighted_component"] = exploded["exposure"] * exploded["employment_2024"]
    grouped = (
        exploded.groupby(["naics_code", "title", "industry_type"], as_index=False)
        .agg(
            covered_employment_2024=("employment_2024", "sum"),
            occupation_count=("slug", "count"),
            weighted_numerator=("weighted_component", "sum"),
        )
    )
    grouped["weighted_exposure"] = grouped["weighted_numerator"] / grouped["covered_employment_2024"]
    grouped = grouped.drop(columns=["weighted_numerator"])
    grouped["naics_level"] = grouped["naics_code"].astype(str).str.len()
    grouped["is_sector"] = grouped["naics_level"] == 2
    grouped = grouped[grouped["naics_level"] == 4].copy()
    grouped["weighted_exposure"] = grouped["weighted_exposure"].round(4)

    out_path = output_tables / f"custom_industry_exposure_{variant_name}_4digit.csv"
    write_csv(
        out_path,
        grouped.to_dict(orient="records"),
        ["naics_code", "title", "industry_type", "naics_level", "is_sector", "covered_employment_2024", "occupation_count", "weighted_exposure"],
    )
    return grouped


def pick_naics_column(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        lc = c.lower()
        if "naics" in lc or "industry_code" in lc:
            return c
    return None


def pick_metric_column(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        lc = c.lower()
        if "aiie" in lc or "aioe" in lc or "exposure" in lc or "score" in lc:
            return c
    nums = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    return nums[-1] if nums else None


def load_external_industry_metrics(source_dir: Path) -> dict[str, pd.DataFrame]:
    metrics = {}
    for path in source_dir.glob("*.xlsx"):
        xls = pd.ExcelFile(path)
        for sheet in xls.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet)
            naics_col = pick_naics_column(df)
            val_col = pick_metric_column(df)
            if not naics_col or not val_col:
                continue
            metric = df[[naics_col, val_col]].copy()
            metric.columns = ["naics_raw", "value"]
            metric["naics_code"] = metric["naics_raw"].map(norm_naics)
            metric = metric.dropna(subset=["naics_code", "value"])  # type: ignore[arg-type]
            metric["naics_code"] = metric["naics_code"].astype(str)
            metric = metric[metric["naics_code"].str.len() == 4]
            if metric.empty:
                continue
            metrics[f"{path.stem}__{sheet.lower().replace(' ', '_')}"] = metric
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default=None)
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--output-dir", default="data/exports/comparisons")
    args = parser.parse_args()

    output_root = resolve_project_path(args.output_dir)
    tables_dir = ensure_dir(output_root / "tables")
    figures_dir = ensure_dir(output_root / "figures")

    variants = {
        "repo_current": pd.read_csv(INDUSTRY_EXPOSURE_4DIGIT_CSV),
    }

    repo_original_custom = build_custom_industry(SCORES_ORG_JSON, SCORES_JSON, "repo_original", tables_dir)
    variants["repo_original"] = repo_original_custom

    local_scores = resolve_project_path("data/local/scores_gpt54.json")
    if local_scores.exists():
        variants["local_gpt54"] = build_custom_industry(local_scores, SCORES_JSON, "local_gpt54", tables_dir)

    if args.variant:
        variants = {k: v for k, v in variants.items() if k == args.variant}

    source_dir = ensure_dir(EXPORTS_DIR.parent / "source" / "comparison")
    external_metrics = load_external_industry_metrics(source_dir)

    summary = []
    for variant_name, variant_df in variants.items():
        variant = variant_df[["naics_code", "weighted_exposure"]].copy()
        variant["naics_code"] = variant["naics_code"].astype(str)
        for metric_name, metric_df in external_metrics.items():
            merged = variant.merge(metric_df[["naics_code", "value"]], on="naics_code", how="inner").dropna()
            if merged.empty:
                continue
            merged["variant_pct"] = percentile_ranks(merged["weighted_exposure"].tolist())
            merged["metric_pct"] = percentile_ranks(merged["value"].tolist())
            write_csv(
                tables_dir / f"industry_overlap_{variant_name}_{metric_name}.csv",
                merged.to_dict(orient="records"),
                ["naics_code", "weighted_exposure", "value", "variant_pct", "metric_pct"],
            )

            plt.figure(figsize=(6, 5))
            plt.scatter(merged["weighted_exposure"], merged["value"], s=12, alpha=0.6)
            plt.xlabel(f"{variant_name} weighted exposure")
            plt.ylabel(f"{metric_name} metric")
            plt.title(f"Industry comparison\n{variant_name} vs {metric_name}")
            plt.tight_layout()
            plt.savefig(figures_dir / f"industry_scatter_{variant_name}_{metric_name}.png", dpi=150)
            plt.close()

            summary.append(
                {
                    "variant": variant_name,
                    "metric": metric_name,
                    "overlap_count": int(len(merged)),
                    "pearson": round(pearson(merged["weighted_exposure"].tolist(), merged["value"].tolist()), 4),
                    "spearman": round(spearman(merged["weighted_exposure"].tolist(), merged["value"].tolist()), 4),
                }
            )

    write_csv(
        tables_dir / "industry_comparison_summary.csv",
        summary,
        ["variant", "metric", "overlap_count", "pearson", "spearman"],
    )
    print(f"Wrote industry comparison outputs under {output_root}")


if __name__ == "__main__":
    main()
