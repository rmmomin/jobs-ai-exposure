"""Compare internal 4-digit industry exposure outputs against external AIIE benchmarks."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from comparison_utils import (
    add_distribution_columns,
    build_overlap_summary,
    comparison_download_path,
    default_comparison_paths,
    disagreement_table,
    ensure_comparison_dirs,
    ensure_downloads,
    find_column_by_tokens,
    first_present_column,
    metric_output_stem,
    norm_naics,
    read_csv_flexible,
    save_scatter_plot,
    select_workbook_sheet,
    to_numeric,
    write_table,
)
from paths import COMPARISON_TABLES_DIR, INDUSTRY_EXPOSURE_4DIGIT_CSV


REQUIRED_DOWNLOADS = [
    "felten_base",
    "felten_language_modeling",
    "felten_image_generation",
]
CUSTOM_VARIANT_RE = re.compile(r"^custom_industry_exposure_(?P<variant>.+)_4digit\.csv$")


def naics4_key(value) -> str | None:
    """Normalize a NAICS code to a four-digit comparison key."""
    code = norm_naics(value)
    if code is None or len(code) < 4:
        return None
    return code[:4]


def aggregate_internal_variant_rows(frame: pd.DataFrame, variant: str, source_path: Path) -> pd.DataFrame:
    """Normalize one internal 4-digit industry exposure table."""
    rows = frame.copy()
    required = ["naics_code", "title", "weighted_exposure"]
    missing = [column for column in required if column not in rows.columns]
    if missing:
        raise ValueError(f"{source_path} is missing required columns: {', '.join(missing)}")

    rows["karpathy_score"] = to_numeric(rows["weighted_exposure"])
    if "covered_employment_2024" not in rows.columns:
        rows["covered_employment_2024"] = pd.NA
    if "occupation_count" not in rows.columns:
        rows["occupation_count"] = pd.NA
    rows["covered_employment_2024"] = to_numeric(rows["covered_employment_2024"])
    rows["occupation_count"] = to_numeric(rows["occupation_count"])
    rows["comparison_key"] = rows["naics_code"].map(naics4_key)
    rows = rows[rows["comparison_key"].notna() & rows["karpathy_score"].notna()].copy()

    if rows.empty:
        return pd.DataFrame(
            columns=[
                "variant",
                "comparison_key",
                "comparison_title",
                "karpathy_score",
                "karpathy_zscore",
                "karpathy_percentile",
            ]
        )

    grouped = rows.groupby("comparison_key", dropna=False).agg(
        raw_naics_examples=("naics_code", lambda values: " | ".join(pd.unique(values.dropna().astype(str))[:5])),
        source_row_count=("comparison_key", "size"),
        comparison_title=("title", lambda values: values.dropna().astype(str).iloc[0] if not values.dropna().empty else ""),
        covered_employment_2024=("covered_employment_2024", "sum"),
        occupation_count=("occupation_count", "sum"),
        karpathy_score=("karpathy_score", "mean"),
    ).reset_index()
    grouped["variant"] = variant
    grouped["comparison_level"] = "naics4"
    grouped["source_file"] = source_path.name
    return add_distribution_columns(grouped, "karpathy_score", "karpathy")


def discover_internal_variant_paths(search_dirs: list[Path]) -> dict[str, Path]:
    """Discover canonical and custom 4-digit industry exposure CSVs."""
    variant_paths = {"repo_current": INDUSTRY_EXPOSURE_4DIGIT_CSV}
    seen: set[Path] = set()
    for directory in search_dirs:
        if not directory.exists():
            continue
        for path in directory.glob("custom_industry_exposure_*_4digit.csv"):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            match = CUSTOM_VARIANT_RE.match(path.name)
            if not match:
                continue
            variant = match.group("variant")
            if variant == "repo_current":
                continue
            variant_paths[variant] = path
    return variant_paths


def load_current_title_lookup() -> dict[str, str]:
    """Load canonical repo-current industry titles for label harmonization."""
    frame = aggregate_internal_variant_rows(read_csv_flexible(INDUSTRY_EXPOSURE_4DIGIT_CSV), "repo_current", INDUSTRY_EXPOSURE_4DIGIT_CSV)
    return frame.set_index("comparison_key")["comparison_title"].to_dict()


def load_internal_variants(search_dirs: list[Path], selected_variants: list[str] | None = None) -> dict[str, pd.DataFrame]:
    """Load canonical and any present custom 4-digit industry exposure variants."""
    variant_paths = discover_internal_variant_paths(search_dirs)
    if selected_variants:
        requested = set(selected_variants)
        missing = sorted(requested - set(variant_paths))
        if missing:
            raise ValueError(
                "Requested industry variants are unavailable. "
                "Build the custom 4-digit output first or remove: "
                + ", ".join(missing)
            )
        variant_paths = {name: path for name, path in variant_paths.items() if name in requested}

    variants = {}
    for variant, path in sorted(variant_paths.items()):
        variants[variant] = aggregate_internal_variant_rows(read_csv_flexible(path), variant, path)
    return variants


def aggregate_external_metric_rows(
    frame: pd.DataFrame,
    metric_name: str,
    title_lookup: dict[str, str],
    source_path: Path,
    sheet_name: str,
) -> pd.DataFrame:
    """Aggregate one external industry metric to normalized 4-digit NAICS rows."""
    rows = frame.copy()
    rows["metric_value"] = to_numeric(rows["metric_value"])
    rows["comparison_key"] = rows["comparison_key"].map(naics4_key)
    rows = rows[rows["comparison_key"].notna() & rows["metric_value"].notna()].copy()

    if rows.empty:
        return pd.DataFrame(
            columns=[
                "comparison_key",
                "comparison_title",
                "metric_value",
                "metric_zscore",
                "metric_percentile",
            ]
        )

    grouped = rows.groupby("comparison_key", dropna=False).agg(
        raw_naics_examples=("raw_naics", lambda values: " | ".join(pd.unique(values.dropna().astype(str))[:5])),
        raw_title_examples=("raw_title", lambda values: " | ".join(pd.unique(values.dropna().astype(str))[:5])),
        source_row_count=("comparison_key", "size"),
        metric_value=("metric_value", "mean"),
    ).reset_index()
    grouped["comparison_title"] = grouped["comparison_key"].map(title_lookup).fillna(grouped["raw_title_examples"])
    grouped["metric_name"] = metric_name
    grouped["comparison_level"] = "naics4"
    grouped["source_file"] = source_path.name
    grouped["sheet_name"] = sheet_name
    return add_distribution_columns(grouped, "metric_value", "metric")


def load_felten_industry_metric(download_name: str, metric_name: str, include_tokens: tuple[str, ...]) -> pd.DataFrame:
    """Load one Felten 4-digit industry AIIE workbook dynamically."""
    path = comparison_download_path(download_name)
    sheet_name, _, df = select_workbook_sheet(path, include_tokens=include_tokens)
    code_column = first_present_column(df, "naics") or find_column_by_tokens(df, ("naics",))
    title_column = (
        first_present_column(df, "industry_title", "naics_description")
        or find_column_by_tokens(df, ("industry",), optional_tokens=("title", "description"))
        or find_column_by_tokens(df, ("naics",), optional_tokens=("description",))
    )
    value_column = find_column_by_tokens(df, ("aiie",), exclude_tokens=("rank",))
    if code_column is None or title_column is None or value_column is None:
        raise ValueError(f"Could not identify NAICS/AIIE columns in {path}")

    rows = df.copy()
    rows["raw_naics"] = rows[code_column].astype(str)
    rows["raw_title"] = rows[title_column].astype(str)
    rows["comparison_key"] = rows[code_column]
    rows["metric_value"] = rows[value_column]
    return aggregate_external_metric_rows(rows, metric_name, {}, path, sheet_name)


def compare_variant_to_metric(
    internal_frame: pd.DataFrame,
    metric_frame: pd.DataFrame,
    variant_name: str,
    metric_name: str,
    tables_dir: Path,
    figures_dir: Path,
) -> dict:
    """Compare one internal industry variant against one external metric."""
    merged = internal_frame.merge(metric_frame, on="comparison_key", how="inner", suffixes=("_left", "_right"))
    if merged.empty:
        return {
            "left": variant_name,
            "right": metric_name,
            "overlap_count": 0,
            "pearson_correlation": None,
            "pearson_pvalue": None,
            "spearman_correlation": None,
            "spearman_pvalue": None,
            "top_decile_intersection_count": 0,
            "top_decile_union_count": 0,
            "top_decile_overlap": None,
            "bottom_decile_intersection_count": 0,
            "bottom_decile_union_count": 0,
            "bottom_decile_overlap": None,
            "comparison_level": "naics4",
        }

    merged["comparison_title"] = merged["comparison_title_left"].fillna(merged["comparison_title_right"])
    merged = merged.drop(columns=["comparison_title_left", "comparison_title_right"])
    stem = f"{metric_output_stem(variant_name)}_{metric_output_stem(metric_name)}"
    write_table(merged, tables_dir / f"industry_overlap_{stem}.csv")

    summary = build_overlap_summary(
        merged,
        left_label=variant_name,
        right_label=metric_name,
        left_z_column="karpathy_zscore",
        right_z_column="metric_zscore",
        left_percentile_column="karpathy_percentile",
        right_percentile_column="metric_percentile",
    )
    summary["comparison_level"] = "naics4"

    disagreements = disagreement_table(
        merged,
        left_label=variant_name,
        right_label=metric_name,
        left_value_column="karpathy_score",
        right_value_column="metric_value",
        left_percentile_column="karpathy_percentile",
        right_percentile_column="metric_percentile",
    )
    write_table(disagreements, tables_dir / f"industry_disagreements_{stem}.csv")
    save_scatter_plot(
        merged,
        x_column="karpathy_zscore",
        y_column="metric_zscore",
        output_path=figures_dir / f"industry_scatter_{stem}.png",
        title=f"{variant_name} vs {metric_name}",
        x_label=f"{variant_name} z-score",
        y_label=f"{metric_name} z-score",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", nargs="*", default=None, help="Only compare selected internal industry variants.")
    parser.add_argument("--force", action="store_true", help="Redownload benchmark workbooks before comparing.")
    parser.add_argument("--skip-download", action="store_true", help="Fail if benchmark workbooks are missing instead of downloading them.")
    parser.add_argument("--output-dir", default=None, help="Base directory for comparison outputs. Defaults to data/exports/comparisons/.")
    args = parser.parse_args()

    ensure_comparison_dirs()
    cleaned_dir, tables_dir, figures_dir = default_comparison_paths(args.output_dir)
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    missing = ensure_downloads(REQUIRED_DOWNLOADS, force=args.force, skip_download=args.skip_download)
    if missing:
        raise FileNotFoundError(f"Missing required comparison sources: {', '.join(missing)}")

    search_dirs = [COMPARISON_TABLES_DIR]
    if tables_dir.resolve() != COMPARISON_TABLES_DIR.resolve():
        search_dirs.append(tables_dir)

    internal_variants = load_internal_variants(search_dirs, args.variant)
    if not internal_variants:
        raise ValueError("No internal industry variants available for comparison.")

    current_titles = load_current_title_lookup()

    metrics = {
        "felten_base_aiie": load_felten_industry_metric(
            "felten_base",
            "felten_base_aiie",
            ("naics", "industry", "aiie"),
        ),
        "felten_language_modeling_aiie": load_felten_industry_metric(
            "felten_language_modeling",
            "felten_language_modeling_aiie",
            ("naics", "language", "aiie"),
        ),
        "felten_image_generation_aiie": load_felten_industry_metric(
            "felten_image_generation",
            "felten_image_generation_aiie",
            ("naics", "image", "aiie"),
        ),
    }

    for metric_name, frame in metrics.items():
        frame["comparison_title"] = frame["comparison_key"].map(current_titles).fillna(frame["comparison_title"])
        write_table(frame, cleaned_dir / f"industry_metric_{metric_name}.csv")

    for variant_name, frame in internal_variants.items():
        write_table(frame, cleaned_dir / f"industry_internal_{variant_name}_4digit.csv")

    summary_rows = []
    for variant_name, variant_frame in internal_variants.items():
        for metric_name, metric_frame in metrics.items():
            summary_rows.append(
                compare_variant_to_metric(
                    variant_frame,
                    metric_frame,
                    variant_name,
                    metric_name,
                    tables_dir,
                    figures_dir,
                )
            )

    summary = pd.DataFrame(summary_rows)
    write_table(summary, tables_dir / "industry_comparison_summary.csv")

    print(f"Wrote industry comparison outputs to {tables_dir.parent}")
    print("Loaded internal variants:")
    for variant_name, frame in internal_variants.items():
        print(f"  {variant_name}: {len(frame)} rows")
    print("Loaded external metrics:")
    for metric_name, frame in metrics.items():
        print(f"  {metric_name}: {len(frame)} rows")


if __name__ == "__main__":
    main()
