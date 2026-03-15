"""
Aggregate occupation AI exposure scores into industry-level exposure measures.

Each industry's score is an employment-weighted average of the occupation
exposure scores observed in that NAICS code:

    weighted_exposure =
        sum(occupation_exposure * occupation_jobs_in_industry)
        / sum(occupation_jobs_in_industry)

The output reflects the occupations covered in this repository's BLS-derived
dataset. It is not a full census of every occupation in the industry.

Outputs:
    industry_exposure.json
    industry_exposure.csv

Usage:
    uv run python build_industry_exposure.py
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict


SCORES_FILE = "scores.json"
OUTPUT_JSON = "industry_exposure.json"
OUTPUT_CSV = "industry_exposure.csv"
TOP_OCCUPATIONS_LIMIT = 10


def load_scores(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def naics_level(code: str) -> int:
    if code.endswith("0000"):
        return 2
    if code.endswith("000"):
        return 3
    if code.endswith("00"):
        return 4
    if code.endswith("0"):
        return 5
    return 6


def sort_rows(rows):
    return sorted(
        rows,
        key=lambda row: (
            row["naics_level"],
            -row["weighted_exposure"],
            -row["covered_employment_2024"],
            row["naics_code"],
        ),
    )


def aggregate_industries(scores):
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
        employment = record.pop("weighted_exposure_numerator")
        total_jobs = record["covered_employment_2024"]
        record["weighted_exposure"] = round(employment / total_jobs, 4)
        record["naics_level"] = naics_level(code)
        record["is_sector"] = record["naics_level"] == 2

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


def write_csv(rows, path: str):
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

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in fieldnames})


def write_json(rows, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


def main():
    scores = load_scores(SCORES_FILE)
    rows = aggregate_industries(scores)
    write_json(rows, OUTPUT_JSON)
    write_csv(rows, OUTPUT_CSV)

    print(f"Wrote {len(rows)} industry rows to {OUTPUT_JSON}")
    print(f"Wrote {len(rows)} industry rows to {OUTPUT_CSV}")

    sectors = [row for row in rows if row["is_sector"]]
    print("\nTop sectors by weighted exposure:")
    for row in sorted(sectors, key=lambda row: row["weighted_exposure"], reverse=True)[:10]:
        print(
            f"  {row['naics_code']} {row['title']}: "
            f"{row['weighted_exposure']:.2f} "
            f"({row['covered_employment_2024']:,} covered jobs)"
        )


if __name__ == "__main__":
    main()
