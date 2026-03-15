"""
Aggregate occupation AI exposure scores into industry-level exposure measures.

Outputs are written into `data/exports/`.

Usage:
    uv run python scripts/build_industry_exposure.py
    uv run python scripts/build_industry_exposure.py --naics-level 4
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from paths import INDUSTRY_EXPOSURE_JSON, ROOT_DIR, SCORES_JSON, resolve_project_path


TOP_OCCUPATIONS_LIMIT = 10


def load_scores(path: Path) -> list[dict]:
    """Load an occupation score export from disk."""
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def merge_scores_with_canonical_industries(
    canonical_scores: list[dict],
    override_scores: list[dict],
) -> tuple[list[dict], int, int]:
    """Overlay alternate scores onto canonical occupations while preserving industry lists."""
    canonical_by_slug = {
        row.get("slug"): row
        for row in canonical_scores
        if row.get("slug")
    }
    merged = []
    matched_slugs = 0
    ignored_slugs = []

    for override in override_scores:
        slug = override.get("slug")
        if not slug:
            continue

        canonical = canonical_by_slug.get(slug)
        if canonical is None:
            ignored_slugs.append(slug)
            continue

        row = dict(canonical)
        row.update(override)
        row["industries"] = canonical.get("industries", [])
        row["naics_industry_codes"] = canonical.get("naics_industry_codes", [])
        merged.append(row)
        matched_slugs += 1

    if ignored_slugs:
        preview = ", ".join(sorted(set(ignored_slugs))[:10])
        print(
            "Warning: ignored override occupations without canonical industry data: "
            f"{preview}"
        )

    return merged, matched_slugs, len(ignored_slugs)


def naics_level(code: str) -> int:
    """Infer the effective NAICS grain from a six-digit code with trailing zeros."""
    if code.endswith("0000"):
        return 2
    if code.endswith("000"):
        return 3
    if code.endswith("00"):
        return 4
    if code.endswith("0"):
        return 5
    return 6


def sort_rows(rows: list[dict]) -> list[dict]:
    """Sort output rows from coarse to fine, then by exposure and size."""
    return sorted(
        rows,
        key=lambda row: (
            row["naics_level"],
            -row["weighted_exposure"],
            -row["covered_employment_2024"],
            row["naics_code"],
        ),
    )


def keep_row(row: dict, exact_naics_level: int | None) -> bool:
    """Return whether one aggregated row should be kept in the final output."""
    if exact_naics_level is None:
        return True
    return row["naics_level"] == exact_naics_level


def aggregate_industries(scores: list[dict], exact_naics_level: int | None = None) -> list[dict]:
    """Aggregate occupation exposures into employment-weighted industry exposures."""
    industries = {}
    contributors = defaultdict(list)

    for occupation in scores:
        exposure = occupation.get("exposure")
        if exposure is None:
            continue

        for industry in occupation.get("industries", []):
            code = industry.get("naics_code")
            title = industry.get("title")
            employment = industry.get("employment_2024")
            if not code or not title or not employment:
                continue

            if code not in industries:
                industries[code] = {
                    "naics_code": code,
                    "title": title,
                    "industry_type": industry.get("industry_type"),
                    "covered_employment_2024": 0,
                    "occupation_count": 0,
                    "weighted_exposure_numerator": 0.0,
                }

            record = industries[code]
            record["covered_employment_2024"] += employment
            record["occupation_count"] += 1
            record["weighted_exposure_numerator"] += employment * exposure

            contributors[code].append({
                "slug": occupation["slug"],
                "title": occupation["title"],
                "exposure": exposure,
                "industry_employment_2024": employment,
            })

    rows = []
    for code, record in industries.items():
        numerator = record.pop("weighted_exposure_numerator")
        total_jobs = record["covered_employment_2024"]
        record["weighted_exposure"] = round(numerator / total_jobs, 4)
        record["naics_level"] = naics_level(code)
        record["is_sector"] = record["naics_level"] == 2
        if not keep_row(record, exact_naics_level):
            continue

        top_occupations = sorted(
            contributors[code],
            key=lambda row: (
                -row["industry_employment_2024"],
                -row["exposure"],
                row["title"],
            ),
        )
        for occupation in top_occupations:
            occupation["covered_industry_share_pct"] = round(
                100 * occupation["industry_employment_2024"] / total_jobs,
                2,
            )

        record["top_occupations"] = top_occupations[:TOP_OCCUPATIONS_LIMIT]
        rows.append(record)

    return sort_rows(rows)


def write_csv(rows: list[dict], path: Path) -> None:
    """Write the flat CSV export used by the rest of the repo."""
    fieldnames = [
        "naics_code",
        "title",
        "industry_type",
        "naics_level",
        "is_sector",
        "covered_employment_2024",
        "occupation_count",
        "weighted_exposure",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in fieldnames})


def write_json(rows: list[dict], path: Path) -> None:
    """Write the richer JSON export, including top occupation contributors."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scores-path",
        default=str(SCORES_JSON.relative_to(ROOT_DIR)),
        help="Path to occupation scores JSON. Defaults to data/exports/scores.json.",
    )
    parser.add_argument(
        "--naics-level",
        type=int,
        choices=[2, 3, 4, 5, 6],
        default=None,
        help="Only emit industries at a single NAICS level",
    )
    parser.add_argument(
        "--output-prefix",
        default=None,
        help="Write outputs to <prefix>.json and <prefix>.csv",
    )
    args = parser.parse_args()

    default_prefix = str(INDUSTRY_EXPOSURE_JSON.relative_to(ROOT_DIR).with_suffix(""))
    output_prefix = args.output_prefix or default_prefix
    output_base = resolve_project_path(output_prefix)
    output_json = output_base.with_suffix(".json")
    output_csv = output_base.with_suffix(".csv")

    canonical_scores = load_scores(SCORES_JSON)
    scores_path = resolve_project_path(args.scores_path)

    if scores_path.resolve() == SCORES_JSON.resolve():
        scores = canonical_scores
        print(f"Using canonical occupation scores from {scores_path}")
    else:
        override_scores = load_scores(scores_path)
        scores, matched_slugs, ignored_slugs = merge_scores_with_canonical_industries(
            canonical_scores,
            override_scores,
        )
        print(
            f"Using alternate occupation scores from {scores_path} "
            f"merged onto canonical industry lists from {SCORES_JSON}"
        )
        print(
            f"Merged {matched_slugs} occupations; "
            f"ignored {ignored_slugs} unmatched override rows"
        )

    rows = aggregate_industries(scores, args.naics_level)
    write_json(rows, output_json)
    write_csv(rows, output_csv)

    print(f"Wrote {len(rows)} industry rows to {output_json}")
    print(f"Wrote {len(rows)} industry rows to {output_csv}")

    label = f"NAICS level {args.naics_level} industries" if args.naics_level is not None else "sectors"
    printable_rows = rows if args.naics_level is not None else [row for row in rows if row["is_sector"]]

    print(f"\nTop {label} by weighted exposure:")
    for row in sorted(printable_rows, key=lambda row: row["weighted_exposure"], reverse=True)[:10]:
        print(
            f"  {row['naics_code']} {row['title']}: "
            f"{row['weighted_exposure']:.2f} "
            f"({row['covered_employment_2024']:,} covered jobs)"
        )


if __name__ == "__main__":
    main()
