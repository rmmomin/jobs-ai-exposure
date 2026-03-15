"""
Create Pearson-correlation column charts from the comparison summary tables.

This reads the existing occupation- and industry-level comparison summaries and
writes a single two-panel figure under `data/exports/comparisons/figures/`.

Usage:
    uv run python scripts/plot_comparison_correlations.py
"""

from __future__ import annotations

import argparse

import matplotlib.pyplot as plt
import pandas as pd

from paths import COMPARISON_FIGURES_DIR, COMPARISON_TABLES_DIR, ROOT_DIR, resolve_project_path


VARIANT_LABELS = {
    "repo_current": "Current",
    "repo_original": "Original",
    "repo_gabriel": "GABRIEL",
}

METRIC_LABELS = {
    "felten_base_aioe": "Felten Base",
    "felten_language_modeling_aioe": "Felten LM",
    "felten_image_generation_aioe": "Felten Image",
    "openai_gpts_are_gpts": "OpenAI GPTs-are-GPTs",
    "microsoft_ai_applicability": "Microsoft",
    "eisfeldt_genaiexp_total": "Eisfeldt",
    "webb_soc4_ai_score": "Webb SOC4",
    "yale_pca_standardized_reference": "Yale PCA",
    "felten_base_aiie": "Felten Base",
    "felten_language_modeling_aiie": "Felten LM",
    "felten_image_generation_aiie": "Felten Image",
}

VARIANT_COLORS = {
    "repo_current": "#1f5aa6",
    "repo_original": "#8f99a8",
    "repo_gabriel": "#d97a29",
}


def prettify_variant(name: str) -> str:
    """Return a compact label for one internal variant."""
    return VARIANT_LABELS.get(name, name.replace("_", " ").title())


def prettify_metric(name: str) -> str:
    """Return a compact label for one comparison metric."""
    return METRIC_LABELS.get(name, name.replace("_", " ").title())


def load_summary(path) -> pd.DataFrame:
    """Load one comparison summary CSV and drop rows without Pearson values."""
    frame = pd.read_csv(path)
    frame = frame[frame["pearson_correlation"].notna()].copy()
    return frame


def sort_metrics(frame: pd.DataFrame, preferred_variant: str) -> list[str]:
    """Order benchmark metrics by the preferred variant's Pearson correlation."""
    subset = frame[frame["left"] == preferred_variant].copy()
    if subset.empty:
        subset = frame.copy()
    subset = subset.sort_values("pearson_correlation", ascending=False)
    return subset["right"].drop_duplicates().tolist()


def plot_grouped_columns(
    ax: plt.Axes,
    frame: pd.DataFrame,
    title: str,
    metric_order: list[str],
) -> None:
    """Draw one grouped Pearson-correlation column chart."""
    pivot = frame.pivot(index="right", columns="left", values="pearson_correlation")
    pivot = pivot.reindex(metric_order)
    variants = [name for name in VARIANT_LABELS if name in pivot.columns]
    if not variants:
        variants = list(pivot.columns)

    x = list(range(len(pivot.index)))
    width = 0.24 if len(variants) >= 3 else 0.32
    offsets = [(idx - (len(variants) - 1) / 2) * width for idx in range(len(variants))]

    for offset, variant in zip(offsets, variants):
        values = pivot[variant].tolist()
        ax.bar(
            [value + offset for value in x],
            values,
            width=width * 0.92,
            label=prettify_variant(variant),
            color=VARIANT_COLORS.get(variant, "#4c72b0"),
            edgecolor="white",
            linewidth=0.7,
        )

    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_ylabel("Pearson Correlation")
    ax.set_xticks(x)
    ax.set_xticklabels([prettify_metric(name) for name in pivot.index], rotation=35, ha="right")
    ax.set_ylim(0, 1.0)
    ax.grid(axis="y", alpha=0.25, linewidth=0.8)
    ax.set_axisbelow(True)


def main() -> None:
    """CLI entry point for building the Pearson summary chart."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str((COMPARISON_FIGURES_DIR / "pearson_correlation_summary.png").relative_to(ROOT_DIR)),
        help="Output PNG path. Defaults to data/exports/comparisons/figures/pearson_correlation_summary.png.",
    )
    args = parser.parse_args()

    occupation_summary = load_summary(COMPARISON_TABLES_DIR / "occupation_comparison_summary.csv")
    industry_summary = load_summary(COMPARISON_TABLES_DIR / "industry_comparison_summary.csv")

    output_path = resolve_project_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 1, figsize=(13, 11), constrained_layout=True)
    plot_grouped_columns(
        axes[0],
        occupation_summary,
        "Occupation Benchmarks",
        sort_metrics(occupation_summary, "repo_current"),
    )
    plot_grouped_columns(
        axes[1],
        industry_summary,
        "Industry Benchmarks (4-digit NAICS)",
        sort_metrics(industry_summary, "repo_current"),
    )
    axes[0].legend(ncol=3, frameon=False, loc="upper right")
    fig.suptitle("Pearson Correlations with External AI Exposure Benchmarks", fontsize=14, fontweight="bold")
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)

    print(f"Wrote Pearson correlation chart to {output_path}")


if __name__ == "__main__":
    main()
