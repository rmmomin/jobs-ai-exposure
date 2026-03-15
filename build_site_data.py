"""
Build a compact JSON for the website by merging CSV stats with AI exposure scores.

Reads occupations.csv (for stats), scores.json (baseline scores), and
scores_gpt54.json (latest comparison scores).
Writes site/data.json and site/changes.json.

Usage:
    uv run python build_site_data.py
"""

import csv
import json
import os


BASELINE_SCORES_FILE = "scores.json"
LATEST_SCORES_FILE = "scores_gpt54.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    baseline_scores = {s["slug"]: s for s in load_json(BASELINE_SCORES_FILE)}
    latest_scores = None
    if os.path.exists(LATEST_SCORES_FILE):
        latest_scores = {
            s["slug"]: s for s in load_json(LATEST_SCORES_FILE)
        }
    display_scores = latest_scores or baseline_scores

    # Load CSV stats
    with open("occupations.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Build treemap data from the latest scores when available.
    data = []
    changes = []
    for row in rows:
        slug = row["slug"]
        baseline = baseline_scores.get(slug, {})
        display = display_scores.get(slug, {})
        data.append({
            "title": row["title"],
            "slug": slug,
            "category": row["category"],
            "pay": int(row["median_pay_annual"]) if row["median_pay_annual"] else None,
            "jobs": int(row["num_jobs_2024"]) if row["num_jobs_2024"] else None,
            "outlook": int(row["outlook_pct"]) if row["outlook_pct"] else None,
            "outlook_desc": row["outlook_desc"],
            "education": row["entry_education"],
            "exposure": display.get("exposure"),
            "exposure_rationale": display.get("rationale"),
            "url": row.get("url", ""),
        })

        if latest_scores is None:
            continue

        comparison = latest_scores.get(slug, {})
        old_exposure = baseline.get("exposure")
        new_exposure = comparison.get("exposure")
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
            "new_rationale": comparison.get("rationale"),
        })

    os.makedirs("site", exist_ok=True)
    with open("site/data.json", "w", encoding="utf-8") as f:
        json.dump(data, f)

    print(f"Wrote {len(data)} occupations to site/data.json")
    total_jobs = sum(d["jobs"] for d in data if d["jobs"])
    print(f"Total jobs represented: {total_jobs:,}")

    if latest_scores is None:
        print(f"Skipped site/changes.json because {LATEST_SCORES_FILE} was not found")
        return

    with open("site/changes.json", "w", encoding="utf-8") as f:
        json.dump(changes, f)
    print(f"Wrote {len(changes)} occupations to site/changes.json")


if __name__ == "__main__":
    main()
