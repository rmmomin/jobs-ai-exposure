"""Compare internal 4-digit industry exposure variants against external AIIE metrics."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from comparison_config import COMPARISON_FIGURES_DIR, COMPARISON_SOURCE_DIR, COMPARISON_TABLES_DIR, ensure_comparison_dirs
from comparison_utils import ensure_dir, naics4, pearson, percentile, spearman, zscore
from paths import INDUSTRY_EXPOSURE_4DIGIT_CSV, resolve_project_path

SUMMARY_COLUMNS = [
    "variant",
    "metric",
    "overlap_count",
    "pearson_z",
    "spearman_pct",
]


def _as_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def load_internal_variants(output_root: Path) -> tuple[dict[str, pd.DataFrame], list[str]]:
    variants: dict[str, pd.DataFrame] = {}
    issues: list[str] = []

    current = pd.read_csv(INDUSTRY_EXPOSURE_4DIGIT_CSV)
    current["naics4"] = current["naics_code"].map(naics4)
    current["value"] = _as_numeric(current["weighted_exposure"])
    current = current.dropna(subset=["naics4", "value"]).copy()
    current["value_z"] = zscore(current["value"].tolist())
    current["value_pct"] = percentile(current["value"].tolist())
    current["variant"] = "repo_current"
    variants["repo_current"] = current

    candidate_files = {
        "repo_original": output_root / "tables" / "custom_industry_exposure_repo_original_4digit.csv",
        "local_gpt54": output_root / "tables" / "custom_industry_exposure_local_gpt54_4digit.csv",
    }

    for variant, path in candidate_files.items():
        if not path.exists():
            issues.append(f"Missing custom variant file for {variant}: {path}")
            continue
        try:
            df = pd.read_csv(path)
            df["naics4"] = df["naics_code"].map(naics4)
            value_col = "weighted_exposure" if "weighted_exposure" in df.columns else "value"
            df["value"] = _as_numeric(df[value_col])
            df = df.dropna(subset=["naics4", "value"]).copy()
            df["value_z"] = zscore(df["value"].tolist())
            df["value_pct"] = percentile(df["value"].tolist())
            df["variant"] = variant
            variants[variant] = df
        except Exception as exc:  # pragma: no cover
            issues.append(f"Failed loading {path}: {exc}")

    return variants, issues


def _clean_aiie_sheet(df: pd.DataFrame, source_file: str, sheet_name: str) -> pd.DataFrame | None:
    naics_col = None
    metric_col = None

    for col in df.columns:
        lc = str(col).lower()
        if naics_col is None and "naics" in lc:
            naics_col = col
        if metric_col is None and "aiie" in lc:
            metric_col = col

    if naics_col is None or metric_col is None:
        return None

    out = pd.DataFrame()
    out["source_file"] = source_file
    out["sheet_name"] = sheet_name
    out["raw_naics"] = df[naics_col].astype(str)
    out["value_raw"] = df[metric_col]
    out["value"] = _as_numeric(df[metric_col])
    out["naics4"] = out["raw_naics"].map(naics4)
    out = out.dropna(subset=["naics4", "value"]).copy()
    if out.empty:
        return None
    out["value_z"] = zscore(out["value"].tolist())
    out["value_pct"] = percentile(out["value"].tolist())
    return out


def load_external_aiie_metrics() -> tuple[dict[str, pd.DataFrame], list[str]]:
    metrics: dict[str, pd.DataFrame] = {}
    issues: list[str] = []

    targets = {
        "felten_base_aiie": ("AIOE_DataAppendix.xlsx", "Appendix B"),
        "felten_language_modeling_aiie": ("Language_Modeling_AIOE_and_AIIE.xlsx", "LM AIIE"),
        "felten_image_generation_aiie": ("Image_Generation_AIOE_and_AIIE.xlsx", "IG AIIE"),
    }

    for metric_name, (filename, sheet_name) in targets.items():
        workbook_path = COMPARISON_SOURCE_DIR / filename
        if not workbook_path.exists():
            issues.append(f"Missing workbook for {metric_name}: {workbook_path}")
            continue
        try:
            df = pd.read_excel(workbook_path, sheet_name=sheet_name)
            cleaned = _clean_aiie_sheet(df, filename, sheet_name)
            if cleaned is None:
                issues.append(f"No NAICS/AIIE columns parsed for {metric_name} ({filename}:{sheet_name})")
                continue
            metrics[metric_name] = cleaned
        except Exception as exc:  # pragma: no cover
            issues.append(f"Failed loading {filename}:{sheet_name} -> {exc}")

    return metrics, issues


def compare_variant_to_metric(variant_df: pd.DataFrame, metric_name: str, metric_df: pd.DataFrame, tables_dir: Path, figures_dir: Path) -> dict[str, object] | None:
    variant_name = variant_df["variant"].iloc[0]

    left = variant_df[["naics4", "value", "value_z", "value_pct"]].rename(
        columns={"value": "variant_value", "value_z": "variant_z", "value_pct": "variant_pct"}
    )
    right = metric_df[["source_file", "sheet_name", "raw_naics", "value", "value_z", "value_pct", "naics4"]].rename(
        columns={"value": "metric_value", "value_z": "metric_z", "value_pct": "metric_pct"}
    )

    merged = left.merge(right, on="naics4", how="inner").dropna(subset=["variant_value", "metric_value"]).copy()
    if merged.empty:
        return None

    merged["rank_gap_abs"] = (merged["variant_pct"] - merged["metric_pct"]).abs()
    disagreements = merged.sort_values("rank_gap_abs", ascending=False).head(25)
    disagreements.to_csv(tables_dir / f"industry_disagreements_{variant_name}_{metric_name}.csv", index=False)

    merged.to_csv(tables_dir / f"industry_overlap_{variant_name}_{metric_name}.csv", index=False)

    plt.figure(figsize=(6, 5))
    plt.scatter(merged["variant_z"], merged["metric_z"], alpha=0.6, s=14)
    plt.xlabel(f"{variant_name} z-score")
    plt.ylabel(f"{metric_name} z-score")
    plt.title(f"Industry exposure: {variant_name} vs {metric_name}")
    plt.tight_layout()
    plt.savefig(figures_dir / f"industry_scatter_{variant_name}_{metric_name}.png", dpi=150)
    plt.close()

    return {
        "variant": variant_name,
        "metric": metric_name,
        "overlap_count": int(len(merged)),
        "pearson_z": round(pearson(merged["variant_z"].tolist(), merged["metric_z"].tolist()), 4),
        "spearman_pct": round(spearman(merged["variant_pct"].tolist(), merged["metric_pct"].tolist()), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=None, help="Override output root (default: data/exports/comparisons)")
    parser.add_argument("--variant", default=None, help="Only run one internal variant")
    args = parser.parse_args()

    ensure_comparison_dirs()

    if args.output_dir:
        output_root = resolve_project_path(args.output_dir)
        tables_dir = output_root / "tables"
        figures_dir = output_root / "figures"
        ensure_dir(tables_dir)
        ensure_dir(figures_dir)
    else:
        output_root = COMPARISON_TABLES_DIR.parent
        tables_dir = COMPARISON_TABLES_DIR
        figures_dir = COMPARISON_FIGURES_DIR

    variants, variant_issues = load_internal_variants(output_root)
    if args.variant:
        variants = {k: v for k, v in variants.items() if k == args.variant}

    metrics, metric_issues = load_external_aiie_metrics()

    summary_rows: list[dict[str, object]] = []
    for _, variant_df in variants.items():
        for metric_name, metric_df in metrics.items():
            result = compare_variant_to_metric(variant_df, metric_name, metric_df, tables_dir, figures_dir)
            if result:
                summary_rows.append(result)

    pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS).to_csv(tables_dir / "industry_comparison_summary.csv", index=False)

    pd.DataFrame(
        [{"variant": k, "rows": len(v)} for k, v in variants.items()],
        columns=["variant", "rows"],
    ).to_csv(tables_dir / "industry_variant_inventory.csv", index=False)

    pd.DataFrame(
        [{"metric": k, "rows": len(v)} for k, v in metrics.items()],
        columns=["metric", "rows"],
    ).to_csv(tables_dir / "industry_metric_inventory.csv", index=False)

    all_issues = [{"issue": msg} for msg in (variant_issues + metric_issues)]
    pd.DataFrame(all_issues, columns=["issue"]).to_csv(tables_dir / "industry_compare_issues.csv", index=False)

    print(f"Industry variants loaded: {', '.join(sorted(variants.keys()))}")
    print(f"External AIIE metrics loaded: {', '.join(sorted(metrics.keys()))}")
    if all_issues:
        print(f"Logged {len(all_issues)} non-fatal issues to industry_compare_issues.csv")
    print(f"Wrote industry comparison outputs to {output_root}")


if __name__ == "__main__":
    main()
