"""Build occupation-level comparison tables/figures from internal and external exposure metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from comparison_config import COMPARISON_CLEANED_DIR, COMPARISON_FIGURES_DIR, COMPARISON_SOURCE_DIR, COMPARISON_TABLES_DIR, ensure_comparison_dirs
from comparison_utils import add_standardized_columns, ensure_dir, norm_soc, pearson, soc4, spearman
from paths import OCCUPATIONS_CSV, SCORES_JSON, SCORES_ORG_JSON, resolve_project_path

INTERNAL_VARIANT_COLUMNS = ["variant", "slug", "title", "soc_code", "soc4", "value", "value_z", "value_pct"]
SUMMARY_COLUMNS = [
    "variant",
    "metric",
    "grain",
    "overlap_count",
    "pearson_z",
    "spearman_pct",
    "top_decile_overlap",
    "bottom_decile_overlap",
]


def build_lookup() -> pd.DataFrame:
    """Load occupation lookup used to normalize score variants to SOC/SOC4."""
    occupations = pd.read_csv(OCCUPATIONS_CSV)
    occupations["soc_code"] = occupations["soc_code"].map(norm_soc)
    occupations["soc4"] = occupations["soc_code"].map(soc4)
    return occupations[["slug", "title", "soc_code", "soc4"]].drop_duplicates()


def normalize_internal_variant(label: str, df: pd.DataFrame, lookup: pd.DataFrame) -> pd.DataFrame:
    base = df.copy()

    if "slug" not in base.columns:
        if "title" in base.columns:
            base = base.merge(lookup[["slug", "title"]], on="title", how="left")
        else:
            base["slug"] = None

    if "soc_code" not in base.columns:
        base = base.merge(lookup[["slug", "soc_code", "soc4"]], on="slug", how="left")
    else:
        base["soc_code"] = base["soc_code"].map(norm_soc)
        if "soc4" not in base.columns:
            base["soc4"] = base["soc_code"].map(soc4)

    if "title" not in base.columns:
        base = base.merge(lookup[["slug", "title"]], on="slug", how="left")

    base["value"] = base["exposure"]
    base = add_standardized_columns(base, "value")
    base["variant"] = label

    keep = [c for c in INTERNAL_VARIANT_COLUMNS if c in base.columns]
    return base[keep]


def load_internal_variants(local_scores_path: Path) -> dict[str, pd.DataFrame]:
    lookup = build_lookup()

    current = pd.DataFrame(json.loads(SCORES_JSON.read_text(encoding="utf-8")))
    current_variant = normalize_internal_variant("repo_current", current, lookup)

    original = pd.DataFrame(json.loads(SCORES_ORG_JSON.read_text(encoding="utf-8")))
    original_variant = normalize_internal_variant("repo_original", original, lookup)

    variants = {
        "repo_current": current_variant,
        "repo_original": original_variant,
    }

    if local_scores_path.exists():
        local = pd.DataFrame(json.loads(local_scores_path.read_text(encoding="utf-8")))
        variants["local_gpt54"] = normalize_internal_variant("local_gpt54", local, lookup)

    return variants


def _pick_code_col(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        lc = col.lower()
        if ("soc" in lc and ("code" in lc or lc == "soc")) or "occ_code" in lc or "occupation_code" in lc:
            return col
    for col in df.columns:
        lc = col.lower()
        if "soc" in lc or lc.endswith("occ"):
            return col
    return None


def _pick_title_col(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        lc = col.lower()
        if "title" in lc or "occupation" in lc or "job" in lc:
            return col
    return None


def _pick_metric_col(df: pd.DataFrame) -> str | None:
    priority = [
        "ai_exposure",
        "exposure",
        "aioe",
        "score",
        "predicted_exposure",
        "genaiexp",
        "applicability",
        "value",
    ]
    lower_to_col = {c.lower(): c for c in df.columns}
    for key in priority:
        if key in lower_to_col:
            return lower_to_col[key]

    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if numeric_cols:
        return numeric_cols[-1]
    return None


def _clean_metric_df(df: pd.DataFrame, source_file: str, sheet_name: str | None) -> pd.DataFrame | None:
    code_col = _pick_code_col(df)
    value_col = _pick_metric_col(df)
    if code_col is None or value_col is None:
        return None

    title_col = _pick_title_col(df)
    out = pd.DataFrame()
    out["source_file"] = source_file
    out["sheet_name"] = sheet_name or ""
    out["source_row"] = list(range(1, len(df) + 1))
    out["raw_soc_code"] = df[code_col].astype(str)
    out["raw_title"] = df[title_col].astype(str) if title_col else ""
    out["value_raw"] = df[value_col]
    out["value"] = df[value_col]
    out["soc_code"] = out["raw_soc_code"].map(norm_soc)
    out["soc4"] = out["raw_soc_code"].map(soc4)

    lowered_name = source_file.lower()
    if "webb" in lowered_name or "soc4" in lowered_name:
        out["grain"] = "soc4"
        out["join_code"] = out["soc4"]
    else:
        out["grain"] = "soc_code"
        out["join_code"] = out["soc_code"]

    out = out.dropna(subset=["join_code"]).copy()
    out = add_standardized_columns(out, "value")
    if out.empty:
        return None

    return out


def load_external_metrics() -> tuple[dict[str, pd.DataFrame], list[dict[str, str]]]:
    """Load all external occupation metrics via dynamic CSV/XLSX sheet inspection."""
    metrics: dict[str, pd.DataFrame] = {}
    issues: list[dict[str, str]] = []

    source_dir = COMPARISON_SOURCE_DIR
    csv_paths = sorted(source_dir.glob("*.csv"))
    xlsx_paths = sorted(source_dir.glob("*.xlsx"))

    for path in csv_paths:
        try:
            raw = pd.read_csv(path)
            cleaned = _clean_metric_df(raw, path.name, None)
            if cleaned is None:
                issues.append({"source_file": path.name, "issue": "No SOC/metric columns found"})
                continue
            metric_name = path.stem
            metrics[metric_name] = cleaned
        except Exception as exc:  # pragma: no cover
            issues.append({"source_file": path.name, "issue": str(exc)})

    for path in xlsx_paths:
        try:
            workbook = pd.ExcelFile(path)
        except Exception as exc:  # pragma: no cover
            issues.append({"source_file": path.name, "issue": f"Workbook open failed: {exc}"})
            continue

        for sheet in workbook.sheet_names:
            try:
                raw = workbook.parse(sheet_name=sheet)
                cleaned = _clean_metric_df(raw, path.name, sheet)
                metric_name = f"{path.stem}__{sheet.strip().replace(' ', '_').lower()}"
                if cleaned is None:
                    issues.append({"source_file": f"{path.name}:{sheet}", "issue": "No SOC/metric columns found"})
                    continue
                metrics[metric_name] = cleaned
            except Exception as exc:  # pragma: no cover
                issues.append({"source_file": f"{path.name}:{sheet}", "issue": str(exc)})

    return metrics, issues


def _decile_overlap(left_pct: pd.Series, right_pct: pd.Series, which: str) -> float:
    if which == "top":
        left = set(left_pct[left_pct >= 0.9].index)
        right = set(right_pct[right_pct >= 0.9].index)
    else:
        left = set(left_pct[left_pct <= 0.1].index)
        right = set(right_pct[right_pct <= 0.1].index)

    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def compare_variant_to_metric(variant: pd.DataFrame, metric_name: str, metric_df: pd.DataFrame, tables_dir: Path, figures_dir: Path) -> dict[str, object] | None:
    grain = metric_df["grain"].iloc[0]
    join_col = "soc4" if grain == "soc4" else "soc_code"

    left = variant[["slug", "title", "soc_code", "soc4", "value", "value_z", "value_pct"]].rename(
        columns={"value": "variant_value", "value_z": "variant_z", "value_pct": "variant_pct"}
    )
    right = metric_df[["source_file", "sheet_name", "source_row", "raw_soc_code", "raw_title", "join_code", "value", "value_z", "value_pct"]].rename(
        columns={"value": "metric_value", "value_z": "metric_z", "value_pct": "metric_pct"}
    )

    merged = left.merge(right, left_on=join_col, right_on="join_code", how="inner")
    merged = merged.dropna(subset=["variant_value", "metric_value"]).copy()
    if merged.empty:
        return None

    merged["row_key"] = merged[join_col].astype(str)
    pct_left = merged.groupby("row_key")["variant_pct"].mean()
    pct_right = merged.groupby("row_key")["metric_pct"].mean()
    top_overlap = _decile_overlap(pct_left, pct_right, "top")
    bottom_overlap = _decile_overlap(pct_left, pct_right, "bottom")

    merged["rank_gap_abs"] = (merged["variant_pct"] - merged["metric_pct"]).abs()
    disagreements = merged.sort_values("rank_gap_abs", ascending=False).head(25)
    disagreements.to_csv(
        tables_dir / f"occupation_disagreements_{variant['variant'].iloc[0]}_{metric_name}.csv",
        index=False,
    )

    plt.figure(figsize=(6, 5))
    plt.scatter(merged["variant_z"], merged["metric_z"], alpha=0.5, s=12)
    plt.xlabel(f"{variant['variant'].iloc[0]} z-score")
    plt.ylabel(f"{metric_name} z-score")
    plt.title(f"Occupation exposure: {variant['variant'].iloc[0]} vs {metric_name}")
    plt.tight_layout()
    plt.savefig(figures_dir / f"occupation_scatter_{variant['variant'].iloc[0]}_{metric_name}.png", dpi=150)
    plt.close()

    return {
        "variant": variant["variant"].iloc[0],
        "metric": metric_name,
        "grain": grain,
        "overlap_count": int(len(merged)),
        "pearson_z": round(pearson(merged["variant_z"].tolist(), merged["metric_z"].tolist()), 4),
        "spearman_pct": round(spearman(merged["variant_pct"].tolist(), merged["metric_pct"].tolist()), 4),
        "top_decile_overlap": round(top_overlap, 4),
        "bottom_decile_overlap": round(bottom_overlap, 4),
    }


def write_internal_cleaned(variants: dict[str, pd.DataFrame], cleaned_dir: Path) -> None:
    for name, df in variants.items():
        df.to_csv(cleaned_dir / f"occupation_internal_{name}.csv", index=False)


def write_external_cleaned(metrics: dict[str, pd.DataFrame], cleaned_dir: Path) -> None:
    for metric_name, df in metrics.items():
        df.to_csv(cleaned_dir / f"occupation_metric_{metric_name}.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=None, help="Override output root (default: data/exports/comparisons)")
    parser.add_argument("--variant", default=None, help="Only run one internal variant")
    args = parser.parse_args()

    ensure_comparison_dirs()

    if args.output_dir:
        output_root = resolve_project_path(args.output_dir)
        cleaned_dir = output_root / "cleaned"
        tables_dir = output_root / "tables"
        figures_dir = output_root / "figures"
        for path in (cleaned_dir, tables_dir, figures_dir):
            ensure_dir(path)
    else:
        cleaned_dir = COMPARISON_CLEANED_DIR
        tables_dir = COMPARISON_TABLES_DIR
        figures_dir = COMPARISON_FIGURES_DIR

    local_scores_path = resolve_project_path("data/local/scores_gpt54.json")
    variants = load_internal_variants(local_scores_path)
    if args.variant:
        variants = {k: v for k, v in variants.items() if k == args.variant}

    write_internal_cleaned(variants, cleaned_dir)

    metrics, issues = load_external_metrics()
    write_external_cleaned(metrics, cleaned_dir)

    summary_rows: list[dict[str, object]] = []
    for variant_name, variant_df in variants.items():
        for metric_name, metric_df in metrics.items():
            result = compare_variant_to_metric(variant_df, metric_name, metric_df, tables_dir, figures_dir)
            if result:
                summary_rows.append(result)

    summary_df = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)
    summary_df.to_csv(tables_dir / "occupation_comparison_summary.csv", index=False)

    issues_df = pd.DataFrame(issues, columns=["source_file", "issue"])
    issues_df.to_csv(tables_dir / "occupation_metric_load_issues.csv", index=False)

    loaded_df = pd.DataFrame(
        [
            {
                "metric": name,
                "source_file": df["source_file"].iloc[0],
                "sheet_name": df["sheet_name"].iloc[0],
                "grain": df["grain"].iloc[0],
                "rows": len(df),
            }
            for name, df in metrics.items()
        ]
    )
    loaded_df.to_csv(tables_dir / "occupation_metric_inventory.csv", index=False)

    print(f"Internal variants loaded: {', '.join(sorted(variants.keys()))}")
    print(f"External metrics loaded: {len(metrics)}")
    if issues:
        print(f"External metric load issues: {len(issues)} (see occupation_metric_load_issues.csv)")
    print(f"Wrote comparison outputs to {tables_dir.parent}")


if __name__ == "__main__":
    main()
