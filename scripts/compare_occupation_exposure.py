"""Compare internal occupation AI exposure scores against external benchmarks."""

from __future__ import annotations

import argparse
from itertools import combinations

import httpx
import pandas as pd

from comparison_utils import (
    COMPARISON_DOWNLOADS,
    add_distribution_columns,
    aggregate_variant_by_column,
    build_overlap_summary,
    build_slug_crosswalks,
    comparison_download_path,
    default_comparison_paths,
    disagreement_table,
    download_file,
    ensure_comparison_dirs,
    ensure_downloads,
    load_internal_variants,
    load_nem_onet_crosswalk,
    load_nem_occupational_coverage,
    load_occupations_metadata,
    load_soc_2010_to_2018_crosswalk,
    map_soc_codes_to_2018,
    metric_output_stem,
    norm_soc,
    read_csv_flexible,
    save_scatter_plot,
    select_workbook_sheet,
    soc4,
    to_numeric,
    write_table,
)


REQUIRED_DOWNLOADS = [
    "felten_base",
    "felten_language_modeling",
    "felten_image_generation",
    "openai_gpts_are_gpts",
    "microsoft_working_with_ai",
    "eisfeldt_occupation",
    "webb_soc4",
    "bls_soc_2010_to_2018_crosswalk",
    "bls_nem_onet_to_soc_crosswalk",
    "bls_nem_occupational_coverage",
]
OPTIONAL_DOWNLOADS = ["yale_workbook"]


def aggregate_metric_rows(
    frame: pd.DataFrame,
    metric_name: str,
    level: str,
    title_lookup: dict[str, str],
    source_file: str,
    sheet_name: str,
    extra_numeric_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Aggregate a raw metric table to the comparison grain and add rank stats."""
    rows = frame.copy()
    rows["metric_value"] = to_numeric(rows["metric_value"])
    rows = rows[rows["comparison_key"].notna() & rows["metric_value"].notna()].copy()
    if rows.empty:
        return pd.DataFrame(
            columns=[
                "metric_name",
                "comparison_level",
                "comparison_key",
                "comparison_title",
                "metric_value",
                "metric_zscore",
                "metric_percentile",
            ]
        )

    numeric_columns = [column for column in (extra_numeric_columns or []) if column in rows.columns]
    for column in numeric_columns:
        rows[column] = to_numeric(rows[column])

    grouped = rows.groupby("comparison_key", dropna=False).agg(
        raw_code_examples=("raw_code", lambda values: " | ".join(pd.unique(values.dropna().astype(str))[:5])),
        raw_title_examples=("raw_title", lambda values: " | ".join(pd.unique(values.dropna().astype(str))[:5])),
        source_row_count=("comparison_key", "size"),
        metric_value=("metric_value", "mean"),
        **{column: (column, "mean") for column in numeric_columns},
    ).reset_index()
    grouped["comparison_title"] = grouped["comparison_key"].map(title_lookup).fillna(grouped["raw_title_examples"])
    grouped["metric_name"] = metric_name
    grouped["comparison_level"] = level
    grouped["source_file"] = source_file
    grouped["sheet_name"] = sheet_name
    return add_distribution_columns(grouped, "metric_value", "metric")


def prepare_internal_variant_tables(
    variants: dict[str, pd.DataFrame],
    cleaned_dir,
) -> dict[str, dict[str, pd.DataFrame]]:
    """Write cleaned internal tables and return comparison-ready frames."""
    prepared = {}
    for variant_name, frame in variants.items():
        raw = add_distribution_columns(frame.copy(), "karpathy_score", "karpathy")
        raw["comparison_key"] = raw["slug"]
        raw["comparison_title"] = raw["title"]
        raw["comparison_level"] = "slug"
        write_table(raw, cleaned_dir / f"occupation_internal_{variant_name}.csv")

        by_soc4 = aggregate_variant_by_column(frame, "soc4")
        by_soc4 = add_distribution_columns(by_soc4, "karpathy_score", "karpathy")
        by_soc4["comparison_key"] = by_soc4["soc4"]
        by_soc4["comparison_title"] = by_soc4["title"]
        by_soc4["comparison_level"] = "soc4"
        write_table(by_soc4, cleaned_dir / f"occupation_internal_{variant_name}_soc4.csv")

        prepared[variant_name] = {"slug": raw, "soc4": by_soc4}
    return prepared


def load_felten_metric(download_name, metric_name, value_token, soc_crosswalk, slug_by_nem, title_by_slug):
    """Load one Felten occupation workbook and map detailed SOC codes to slugs."""
    path = comparison_download_path(download_name)
    sheet_name, _, df = select_workbook_sheet(path, include_tokens=("soc", value_token, "occupation"))
    code_column = next(column for column in df.columns if "soc" in column and "code" in column)
    title_column = next(column for column in df.columns if "occupation" in column and "title" in column)
    value_column = next(column for column in df.columns if value_token in column)
    rows = df.copy()
    rows["raw_code"] = rows[code_column].astype(str)
    rows["raw_title"] = rows[title_column].astype(str)
    rows["nem_code"] = map_soc_codes_to_2018(rows[code_column], soc_crosswalk)
    rows["comparison_key"] = rows["nem_code"].map(slug_by_nem)
    rows["metric_value"] = rows[value_column]
    return aggregate_metric_rows(rows, metric_name, "slug", title_by_slug, path.name, sheet_name)


def load_openai_metric(slug_by_onet, title_by_slug):
    """Load the GPTs-are-GPTs occupation metric using DV Rating Beta as primary."""
    path = comparison_download_path("openai_gpts_are_gpts")
    df = read_csv_flexible(path)
    rows = df.copy()
    rows["raw_code"] = rows["o_net_soc_code"].astype(str)
    rows["raw_title"] = rows["title"].astype(str)
    rows["comparison_key"] = rows["o_net_soc_code"].map(slug_by_onet).fillna(rows["o_net_soc_code"].map(norm_soc).map(slug_by_onet))
    rows["metric_value"] = rows["dv_rating_beta"]
    return aggregate_metric_rows(
        rows,
        "openai_gpts_are_gpts",
        "slug",
        title_by_slug,
        path.name,
        "",
        extra_numeric_columns=[
            "dv_rating_alpha",
            "dv_rating_beta",
            "dv_rating_gamma",
            "human_rating_alpha",
            "human_rating_beta",
            "human_rating_gamma",
        ],
    )


def load_microsoft_metric(soc_crosswalk, slug_by_nem, title_by_slug):
    """Load Microsoft Working with AI applicability scores."""
    path = comparison_download_path("microsoft_working_with_ai")
    df = read_csv_flexible(path)
    rows = df.copy()
    rows["raw_code"] = rows["soc_code"].astype(str)
    rows["raw_title"] = rows["title"].astype(str)
    rows["nem_code"] = map_soc_codes_to_2018(rows["soc_code"], soc_crosswalk)
    rows["comparison_key"] = rows["nem_code"].map(slug_by_nem)
    rows["metric_value"] = rows["ai_applicability_score"]
    return aggregate_metric_rows(rows, "microsoft_ai_applicability", "slug", title_by_slug, path.name, "")


def load_eisfeldt_metric(soc_crosswalk, slug_by_nem, title_by_slug):
    """Load Eisfeldt occupation GenAI exposure scores."""
    path = comparison_download_path("eisfeldt_occupation")
    df = read_csv_flexible(path)
    rows = df.copy()
    rows["raw_code"] = rows["soc2010"].astype(str)
    rows["raw_title"] = rows["soc2010"].astype(str)
    rows["nem_code"] = map_soc_codes_to_2018(rows["soc2010"], soc_crosswalk)
    rows["comparison_key"] = rows["nem_code"].map(slug_by_nem)
    rows["metric_value"] = rows["genaiexp_estz_total"]
    return aggregate_metric_rows(
        rows,
        "eisfeldt_genaiexp_total",
        "slug",
        title_by_slug,
        path.name,
        "",
        extra_numeric_columns=["genaiexp_estz_total", "genaiexp_estz_core", "genaiexp_estz_supplemental"],
    )


def load_webb_metric(title_by_soc4):
    """Load Webb exposure and aggregate it to SOC4 as requested."""
    path = comparison_download_path("webb_soc4")
    sheet_name, _, df = select_workbook_sheet(path, include_tokens=("occ_code", "ai_score"))
    rows = df.copy()
    rows["raw_code"] = rows["occ_code"].astype(str)
    rows["raw_title"] = rows["index"].astype(str)
    rows["comparison_key"] = rows["occ_code"].map(soc4)
    rows["metric_value"] = rows["ai_score"]
    return aggregate_metric_rows(rows, "webb_soc4_ai_score", "soc4", title_by_soc4, path.name, sheet_name)


def load_yale_reference_metric(soc_crosswalk, slug_by_nem, title_by_slug):
    """Load Yale reference tables and expose PCA standardized as a comparison metric."""
    path = comparison_download_path("yale_workbook")
    if not path.exists():
        return None, None

    sheet_f1, _, f1 = select_workbook_sheet(path, include_tokens=("soc2018", "occupation", "pca", "variance"))
    sheet_fa5, _, fa5 = select_workbook_sheet(path, include_tokens=("soc2018", "aioe", "pca", "applicability"))

    f1_rows = f1.copy().rename(
        columns={
            "soc2018": "soc2018",
            "occupation": "occupation",
            "pca_weighted_score": "pca_weighted_score",
            "z_score_variance": "z_score_variance",
        }
    )
    fa5_rows = fa5.copy().rename(
        columns={
            "soc2018": "soc2018",
            "aioe": "aioe",
            "dv_rating_beta": "dv_rating_beta",
            "human_rating_beta": "human_rating_beta",
            "genai_total": "genai_total",
            "genai_core": "genai_core",
            "ai_applicability_score": "ai_applicability_score",
            "pca_standardized": "pca_standardized",
        }
    )

    merged = f1_rows[["soc2018", "occupation", "pca_weighted_score", "z_score_variance"]].merge(
        fa5_rows[["soc2018", "aioe", "dv_rating_beta", "human_rating_beta", "genai_total", "genai_core", "ai_applicability_score", "pca_standardized"]],
        on="soc2018",
        how="outer",
    )
    merged["raw_code"] = merged["soc2018"].astype(str)
    merged["raw_title"] = merged["occupation"].astype(str)
    merged["nem_code"] = map_soc_codes_to_2018(merged["soc2018"], soc_crosswalk)
    merged["comparison_key"] = merged["nem_code"].map(slug_by_nem)
    merged["metric_value"] = merged["pca_standardized"]

    bundle = aggregate_metric_rows(
        merged,
        "yale_reference_bundle",
        "slug",
        title_by_slug,
        path.name,
        f"{sheet_f1}|{sheet_fa5}",
        extra_numeric_columns=[
            "pca_weighted_score",
            "z_score_variance",
            "aioe",
            "dv_rating_beta",
            "human_rating_beta",
            "genai_total",
            "genai_core",
            "ai_applicability_score",
            "pca_standardized",
        ],
    )

    metric = bundle.copy()
    metric["metric_name"] = "yale_pca_standardized_reference"
    return bundle, metric


def compare_variant_to_metric(left, right, left_label, right_label, tables_dir, figures_dir, prefix):
    """Compute overlap tables, summary stats, disagreements, and a scatter plot."""
    merged = left.merge(right, on="comparison_key", how="inner", suffixes=("_left", "_right"))
    if merged.empty:
        return {
            "left": left_label,
            "right": right_label,
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
        }

    merged["comparison_title"] = merged["comparison_title_left"].fillna(merged["comparison_title_right"])
    merged = merged.drop(columns=["comparison_title_left", "comparison_title_right"])
    write_table(merged, tables_dir / f"occupation_overlap_{prefix}.csv")

    summary = build_overlap_summary(
        merged,
        left_label=left_label,
        right_label=right_label,
        left_z_column="karpathy_zscore",
        right_z_column="metric_zscore",
        left_percentile_column="karpathy_percentile",
        right_percentile_column="metric_percentile",
    )
    disagreements = disagreement_table(
        merged,
        left_label=left_label,
        right_label=right_label,
        left_value_column="karpathy_score",
        right_value_column="metric_value",
        left_percentile_column="karpathy_percentile",
        right_percentile_column="metric_percentile",
    )
    write_table(disagreements, tables_dir / f"occupation_disagreements_{prefix}.csv")
    save_scatter_plot(
        merged,
        x_column="karpathy_zscore",
        y_column="metric_zscore",
        output_path=figures_dir / f"occupation_scatter_{prefix}.png",
        title=f"{left_label} vs {right_label}",
        x_label=f"{left_label} z-score",
        y_label=f"{right_label} z-score",
    )
    return summary


def compare_internal_variants(prepared, tables_dir, figures_dir):
    """Compare internal variants directly on slug overlap."""
    pairs = list(combinations(sorted(prepared), 2))

    rows = []
    for left_name, right_name in pairs:
        merged = prepared[left_name]["slug"].merge(prepared[right_name]["slug"], on="comparison_key", how="inner", suffixes=("_left", "_right"))
        merged["comparison_title"] = merged["comparison_title_left"].fillna(merged["comparison_title_right"])
        write_table(merged, tables_dir / f"occupation_overlap_{left_name}_{right_name}.csv")

        summary = build_overlap_summary(
            merged,
            left_label=left_name,
            right_label=right_name,
            left_z_column="karpathy_zscore_left",
            right_z_column="karpathy_zscore_right",
            left_percentile_column="karpathy_percentile_left",
            right_percentile_column="karpathy_percentile_right",
        )
        summary["comparison_level"] = "slug"
        rows.append(summary)

        disagreements = disagreement_table(
            merged,
            left_label=left_name,
            right_label=right_name,
            left_value_column="karpathy_score_left",
            right_value_column="karpathy_score_right",
            left_percentile_column="karpathy_percentile_left",
            right_percentile_column="karpathy_percentile_right",
        )
        write_table(disagreements, tables_dir / f"occupation_disagreements_{left_name}_{right_name}.csv")
        save_scatter_plot(
            merged,
            x_column="karpathy_zscore_left",
            y_column="karpathy_zscore_right",
            output_path=figures_dir / f"occupation_scatter_{left_name}_{right_name}.png",
            title=f"{left_name} vs {right_name}",
            x_label=f"{left_name} z-score",
            y_label=f"{right_name} z-score",
        )

    result = pd.DataFrame(rows)
    write_table(result, tables_dir / "internal_variant_comparisons.csv")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", nargs="*", default=None, help="Only compare the selected internal variants.")
    parser.add_argument("--force", action="store_true", help="Redownload missing sources and rebuild outputs.")
    parser.add_argument("--skip-download", action="store_true", help="Fail if required source files are missing instead of downloading them.")
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
    if not args.skip_download:
        for name in OPTIONAL_DOWNLOADS:
            path = comparison_download_path(name)
            if not path.exists():
                try:
                    target = next(item for item in COMPARISON_DOWNLOADS if item["name"] == name)
                    download_file(target["url"], path, force=False)
                except httpx.HTTPError:
                    pass

    all_variants = load_internal_variants()
    variants = all_variants
    if args.variant:
        requested = set(args.variant)
        unknown = sorted(requested - set(all_variants))
        if unknown:
            raise ValueError(f"Unknown variants requested: {', '.join(unknown)}")
        variants = {name: frame for name, frame in all_variants.items() if name in requested}

    occupations = load_occupations_metadata()
    soc_crosswalk = load_soc_2010_to_2018_crosswalk()
    nem_onet_crosswalk = load_nem_onet_crosswalk()
    nem_coverage = load_nem_occupational_coverage()
    write_table(soc_crosswalk, cleaned_dir / "crosswalk_soc_2010_to_2018.csv")
    write_table(nem_onet_crosswalk, cleaned_dir / "crosswalk_nem_onet.csv")
    write_table(nem_coverage, cleaned_dir / "crosswalk_nem_occupational_coverage.csv")

    slug_by_nem, title_by_nem, slug_by_onet, _ = build_slug_crosswalks(occupations, nem_onet_crosswalk)
    title_by_slug = dict(zip(occupations["slug"], occupations["title"]))
    current_soc4 = aggregate_variant_by_column(all_variants["repo_current"], "soc4")
    title_by_soc4 = dict(zip(current_soc4["soc4"], current_soc4["title"]))

    prepared = prepare_internal_variant_tables(variants, cleaned_dir)

    metrics = {
        "felten_base_aioe": load_felten_metric("felten_base", "felten_base_aioe", "aioe", soc_crosswalk, slug_by_nem, title_by_slug),
        "felten_language_modeling_aioe": load_felten_metric("felten_language_modeling", "felten_language_modeling_aioe", "language_modeling", soc_crosswalk, slug_by_nem, title_by_slug),
        "felten_image_generation_aioe": load_felten_metric("felten_image_generation", "felten_image_generation_aioe", "image_generation", soc_crosswalk, slug_by_nem, title_by_slug),
        "openai_gpts_are_gpts": load_openai_metric(slug_by_onet, title_by_slug),
        "microsoft_ai_applicability": load_microsoft_metric(soc_crosswalk, slug_by_nem, title_by_slug),
        "eisfeldt_genaiexp_total": load_eisfeldt_metric(soc_crosswalk, slug_by_nem, title_by_slug),
        "webb_soc4_ai_score": load_webb_metric(title_by_soc4),
    }

    yale_bundle, yale_metric = load_yale_reference_metric(soc_crosswalk, slug_by_nem, title_by_slug)
    if yale_bundle is not None and yale_metric is not None:
        write_table(yale_bundle, cleaned_dir / "occupation_metric_yale_reference_bundle.csv")
        metrics["yale_pca_standardized_reference"] = yale_metric

    for metric_name, frame in metrics.items():
        write_table(frame, cleaned_dir / f"occupation_metric_{metric_name}.csv")

    summary_rows = []
    for variant_name, variant_tables in prepared.items():
        for metric_name, metric_frame in metrics.items():
            level = metric_frame["comparison_level"].iloc[0] if not metric_frame.empty else "slug"
            left = variant_tables["soc4"] if level == "soc4" else variant_tables["slug"]
            summary = compare_variant_to_metric(
                left,
                metric_frame,
                variant_name,
                metric_name,
                tables_dir,
                figures_dir,
                prefix=f"{variant_name}_{metric_output_stem(metric_name)}",
            )
            summary["comparison_level"] = level
            summary_rows.append(summary)

    write_table(pd.DataFrame(summary_rows), tables_dir / "occupation_comparison_summary.csv")
    compare_internal_variants(prepared, tables_dir, figures_dir)

    print(f"Wrote occupation comparison outputs to {tables_dir.parent}")
    print("Loaded external metrics:")
    for metric_name, frame in metrics.items():
        level = frame["comparison_level"].iloc[0] if not frame.empty else "unknown"
        print(f"  {metric_name}: {len(frame)} rows at {level}")


if __name__ == "__main__":
    main()
