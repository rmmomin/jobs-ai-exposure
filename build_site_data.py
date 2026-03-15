"""
Build a compact JSON for the website by merging CSV stats with AI exposure scores.

Reads occupations.csv, scores_org.json (archived baseline), and scores.json
(latest canonical scores). Writes site/data.json and site/changes.json.

Usage:
    uv run python build_site_data.py
"""

import csv
import json
import os


BASELINE_SCORES_FILE = "scores_org.json"
LATEST_SCORES_FILE = "scores.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    baseline_scores = None
    if os.path.exists(BASELINE_SCORES_FILE):
        baseline_scores = {score["slug"]: score for score in load_json(BASELINE_SCORES_FILE)}

    latest_scores = {score["slug"]: score for score in load_json(LATEST_SCORES_FILE)}

    with open("occupations.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    data = []
    changes = []
    for row in rows:
        slug = row["slug"]
        baseline = baseline_scores.get(slug, {}) if baseline_scores else {}
        latest = latest_scores.get(slug, {})

        data.append({
            "title": row["title"],
            "slug": slug,
            "category": row["category"],
            "pay": int(row["median_pay_annual"]) if row["median_pay_annual"] else None,
            "jobs": int(row["num_jobs_2024"]) if row["num_jobs_2024"] else None,
            "outlook": int(row["outlook_pct"]) if row["outlook_pct"] else None,
            "outlook_desc": row["outlook_desc"],
            "education": row["entry_education"],
            "exposure": latest.get("exposure"),
            "exposure_rationale": latest.get("rationale"),
            "url": row.get("url", ""),
        })

        if not baseline_scores:
            continue

        old_exposure = baseline.get("exposure")
        new_exposure = latest.get("exposure")
        if old_exposure is None or new_exposure is None:
            continue

        changes.append({
            "title": row["title"],
            "slug": slug,
            "category": row["category"],
            "pay": int(row["median_pay_annual"]) if row["median_pay_annual"] else None,
            "jobs": int(row["num_jobs_2024"]) if row["num_jobs_2024"] else None,
            "url": row.get("url", ""),
            "old_exposure": old_exposure,
            "new_exposure": new_exposure,
            "delta": new_exposure - old_exposure,
            "old_rationale": baseline.get("rationale"),
            "new_rationale": latest.get("rationale"),
        })

    os.makedirs("site", exist_ok=True)
    with open("site/data.json", "w", encoding="utf-8") as f:
        json.dump(data, f)

    print(f"Wrote {len(data)} occupations to site/data.json")
    total_jobs = sum(entry["jobs"] for entry in data if entry["jobs"])
    print(f"Total jobs represented: {total_jobs:,}")

    if not baseline_scores:
        print(f"Skipped site/changes.json because {BASELINE_SCORES_FILE} was not found")
        return

    with open("site/changes.json", "w", encoding="utf-8") as f:
        json.dump(changes, f)
    print(f"Wrote {len(changes)} occupations to site/changes.json")


if __name__ == "__main__":
    main()
