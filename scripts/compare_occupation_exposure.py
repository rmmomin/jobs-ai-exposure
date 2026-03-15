"""Compare internal occupation AI exposure variants against external datasets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from comparison_utils import (
    ensure_dir,
    norm_soc,
    percentile_ranks,
    pearson,
    soc4,
    spearman,
    write_csv,
)
from paths import EXPORTS_DIR, SCORES_JSON, SCORES_ORG_JSON, resolve_project_path


def load_internal_variants(local_path: Path) -> dict[str, pd.DataFrame]:
    variants = {}
    current = pd.DataFrame(json.loads(SCORES_JSON.read_text(encoding="utf-8")))
    current["soc_code"] = current["soc_code"].map(norm_soc)
    variants["repo_current"] = current[["slug", "title", "soc_code", "exposure"]].copy()

    original = pd.DataFrame(json.loads(SCORES_ORG_JSON.read_text(encoding="utf-8")))
    original["soc_code"] = original.get("soc_code", pd.Series(index=original.index)).map(norm_soc)
    if original["soc_code"].isna().all():
        lookup = current[["slug", "soc_code"]]
        original = original.merge(lookup, on="slug", how="left", suffixes=("", "_lookup"))
        if "soc_code_lookup" in original.columns:
            original["soc_code"] = original["soc_code_lookup"]
    variants["repo_original"] = original[["slug", "title", "soc_code", "exposure"]].copy()

    if local_path.exists():
        local = pd.DataFrame(json.loads(local_path.read_text(encoding="utf-8")))
        local["soc_code"] = local.get("soc_code", pd.Series(index=local.index)).map(norm_soc)
        if local["soc_code"].isna().all() and "slug" in local.columns:
            local = local.merge(current[["slug", "soc_code"]], on="slug", how="left", suffixes=("", "_lookup"))
            local["soc_code"] = local.get("soc_code_lookup", local.get("soc_code"))
        variants["local_gpt54"] = local[["slug", "title", "soc_code", "exposure"]].copy()

    return variants


def pick_metric_column(df: pd.DataFrame) -> str | None:
    score_names = [
        "exposure",
        "ai_exposure",
        "aioe",
        "aiie",
        "score",
        "value",
        "predicted_exposure",
        "genaiexp",
    ]
    lower = {c.lower(): c for c in df.columns}
    for name in score_names:
        if name in lower:
            return lower[name]
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if numeric:
        return numeric[-1]
    return None


def pick_soc_column(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        lc = c.lower()
        if "soc" in lc or "occ_code" in lc or "occupation_code" in lc:
            return c
    return None


def load_external_metrics(source_dir: Path) -> dict[str, pd.DataFrame]:
    metrics = {}

    csv_files = list(source_dir.glob("*.csv"))
    xlsx_files = list(source_dir.glob("*.xlsx"))

    for path in csv_files:
        df = pd.read_csv(path)
        soc_col = pick_soc_column(df)
        val_col = pick_metric_column(df)
        if not soc_col or not val_col:
            continue
        metric_name = path.stem
        metric = df[[soc_col, val_col]].copy()
        metric.columns = ["soc_raw", "value"]
        metric["soc_code"] = metric["soc_raw"].map(norm_soc)
        metric["soc4"] = metric["soc_raw"].map(soc4)
        metric = metric.dropna(subset=["value"])
        metrics[metric_name] = metric

    for path in xlsx_files:
        xls = pd.ExcelFile(path)
        for sheet in xls.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet)
            soc_col = pick_soc_column(df)
            val_col = pick_metric_column(df)
            if not soc_col or not val_col:
                continue
            metric_name = f"{path.stem}__{sheet.lower().replace(' ', '_')}"
            metric = df[[soc_col, val_col]].copy()
            metric.columns = ["soc_raw", "value"]
            metric["soc_code"] = metric["soc_raw"].map(norm_soc)
            metric["soc4"] = metric["soc_raw"].map(soc4)
            metric = metric.dropna(subset=["value"])
            metrics[metric_name] = metric

    return metrics


def summarize_pair(variant_name: str, metric_name: str, merged: pd.DataFrame) -> dict:
    merged = merged.dropna(subset=["exposure", "value"]).copy()
    if merged.empty:
        return {
            "variant": variant_name,
            "metric": metric_name,
            "overlap_count": 0,
            "pearson_z": None,
            "spearman_pct": None,
            "top_decile_overlap": None,
            "bottom_decile_overlap": None,
        }

    merged["variant_pct"] = percentile_ranks(merged["exposure"].tolist())
    merged["metric_pct"] = percentile_ranks(merged["value"].tolist())
    merged["variant_z"] = (merged["exposure"] - merged["exposure"].mean()) / merged["exposure"].std(ddof=0)
    merged["metric_z"] = (merged["value"] - merged["value"].mean()) / merged["value"].std(ddof=0)

    top_v = set(merged.loc[merged["variant_pct"] >= 0.9, "soc_code"])
    top_m = set(merged.loc[merged["metric_pct"] >= 0.9, "soc_code"])
    bot_v = set(merged.loc[merged["variant_pct"] <= 0.1, "soc_code"])
    bot_m = set(merged.loc[merged["metric_pct"] <= 0.1, "soc_code"])

    top_overlap = len(top_v & top_m) / max(1, min(len(top_v), len(top_m)))
    bot_overlap = len(bot_v & bot_m) / max(1, min(len(bot_v), len(bot_m)))

    return {
        "variant": variant_name,
        "metric": metric_name,
        "overlap_count": int(len(merged)),
        "pearson_z": round(pearson(merged["variant_z"].tolist(), merged["metric_z"].tolist()), 4),
        "spearman_pct": round(spearman(merged["variant_pct"].tolist(), merged["metric_pct"].tolist()), 4),
        "top_decile_overlap": round(top_overlap, 4),
        "bottom_decile_overlap": round(bot_overlap, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default=None, help="Only compare one internal variant")
    parser.add_argument("--skip-download", action="store_true", help="Reserved flag for workflow compatibility")
    parser.add_argument("--output-dir", default="data/exports/comparisons", help="Comparison output root")
    args = parser.parse_args()

    output_root = resolve_project_path(args.output_dir)
    cleaned_dir = ensure_dir(output_root / "cleaned")
    tables_dir = ensure_dir(output_root / "tables")
    figures_dir = ensure_dir(output_root / "figures")
    source_dir = ensure_dir(EXPORTS_DIR.parent / "source" / "comparison")

    local_scores_path = resolve_project_path("data/local/scores_gpt54.json")
    variants = load_internal_variants(local_scores_path)
    if args.variant:
        variants = {k: v for k, v in variants.items() if k == args.variant}

    metrics = load_external_metrics(source_dir)
    summary_rows = []
    internal_rows = []

    for metric_name, metric_df in metrics.items():
        cleaned_metric = metric_df.copy()
        cleaned_metric["value_z"] = (cleaned_metric["value"] - cleaned_metric["value"].mean()) / cleaned_metric["value"].std(ddof=0)
        cleaned_metric["value_pct"] = percentile_ranks(cleaned_metric["value"].tolist())
        write_csv(
            cleaned_dir / f"occupation_metric_{metric_name}.csv",
            cleaned_metric.to_dict(orient="records"),
            ["soc_raw", "soc_code", "soc4", "value", "value_z", "value_pct"],
        )

        for variant_name, variant_df in variants.items():
            merged = variant_df.merge(metric_df[["soc_code", "value"]], on="soc_code", how="inner")
            merged = merged.dropna(subset=["soc_code"]).copy()
            summary_rows.append(summarize_pair(variant_name, metric_name, merged))
            if merged.empty:
                continue
            merged["variant_pct"] = percentile_ranks(merged["exposure"].tolist())
            merged["metric_pct"] = percentile_ranks(merged["value"].tolist())
            merged["rank_gap_abs"] = (merged["variant_pct"] - merged["metric_pct"]).abs()
            disagreements = merged.sort_values("rank_gap_abs", ascending=False).head(25)
            write_csv(
                tables_dir / f"occupation_disagreements_{variant_name}_{metric_name}.csv",
                disagreements.to_dict(orient="records"),
                ["soc_code", "slug", "title", "exposure", "value", "variant_pct", "metric_pct", "rank_gap_abs"],
            )

            plt.figure(figsize=(6, 5))
            plt.scatter(merged["exposure"], merged["value"], s=10, alpha=0.6)
            plt.xlabel(f"{variant_name} exposure")
            plt.ylabel(f"{metric_name} metric")
            plt.title(f"Occupation exposure comparison\n{variant_name} vs {metric_name}")
            plt.tight_layout()
            plt.savefig(figures_dir / f"occupation_scatter_{variant_name}_{metric_name}.png", dpi=150)
            plt.close()

    variant_names = list(variants)
    for i in range(len(variant_names)):
        for j in range(i + 1, len(variant_names)):
            left = variants[variant_names[i]][["soc_code", "exposure"]].rename(columns={"exposure": "left_exposure"})
            right = variants[variant_names[j]][["soc_code", "exposure"]].rename(columns={"exposure": "right_exposure"})
            merged = left.merge(right, on="soc_code", how="inner").dropna()
            if merged.empty:
                continue
            internal_rows.append(
                {
                    "left_variant": variant_names[i],
                    "right_variant": variant_names[j],
                    "overlap_count": int(len(merged)),
                    "pearson": round(pearson(merged["left_exposure"].tolist(), merged["right_exposure"].tolist()), 4),
                    "spearman": round(spearman(merged["left_exposure"].tolist(), merged["right_exposure"].tolist()), 4),
                }
            )

    write_csv(
        tables_dir / "occupation_comparison_summary.csv",
        summary_rows,
        ["variant", "metric", "overlap_count", "pearson_z", "spearman_pct", "top_decile_overlap", "bottom_decile_overlap"],
    )
    write_csv(
        tables_dir / "internal_variant_comparisons.csv",
        internal_rows,
        ["left_variant", "right_variant", "overlap_count", "pearson", "spearman"],
    )

    print(f"Wrote occupation comparison outputs under {output_root}")


if __name__ == "__main__":
    main()
