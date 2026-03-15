"""
Build a CSV summary of all occupations from the scraped HTML files.

Reads from `data/source/html/` and writes to `data/exports/occupations.csv`.

Usage:
    uv run python scripts/make_csv.py
"""

import csv
import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from paths import HTML_DIR, OCCUPATIONS_CSV, OCCUPATIONS_JSON


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def parse_pay(value):
    """Parse pay text into (annual, hourly)."""
    annual = ""
    hourly = ""
    amounts = re.findall(r"\$([\d,]+(?:\.\d+)?)", value)
    if "per year" in value and "per hour" in value and len(amounts) >= 2:
        annual = amounts[0].replace(",", "")
        hourly = amounts[1].replace(",", "")
    elif "per year" in value and amounts:
        annual = amounts[0].replace(",", "")
    elif "per hour" in value and amounts:
        hourly = amounts[0].replace(",", "")
    return annual, hourly


def parse_outlook(value):
    """Parse outlook text into (pct, description)."""
    match = re.match(r"(-?\d+)%\s*\((.+)\)", value)
    if match:
        return match.group(1), match.group(2)
    match = re.match(r"(-?\d+)%", value)
    if match:
        return match.group(1), ""
    return "", value


def parse_number(value):
    """Strip commas and return a clean number string."""
    cleaned = value.replace(",", "").strip()
    if re.match(r"^-?\d+$", cleaned):
        return cleaned
    return value.strip()


def extract_industry_matrix_url(soup, occupation_title):
    """Find the BLS industry-matrix URL for this occupation."""
    outlook_table = soup.find("table", id="outlook-table")
    if not outlook_table:
        return ""

    tbody = outlook_table.find("tbody")
    if not tbody:
        return ""

    fallback_url = ""
    for tr in tbody.find_all("tr"):
        link = tr.find("a", href=re.compile(r"nationalMatrix"))
        if not link:
            continue

        full_url = urljoin("https://data.bls.gov/", link.get("href", ""))
        if not fallback_url:
            fallback_url = full_url

        title_cell = tr.find(["th", "td"])
        if title_cell and clean(title_cell.get_text()) == occupation_title:
            return full_url

    return fallback_url


def extract_occupation(html_path, occ_meta):
    """Extract one row of data from an HTML file."""
    with html_path.open(encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    row = {
        "title": occ_meta["title"],
        "category": occ_meta["category"],
        "slug": occ_meta["slug"],
        "url": occ_meta["url"],
        "soc_code": "",
        "median_pay_annual": "",
        "median_pay_hourly": "",
        "entry_education": "",
        "work_experience": "",
        "training": "",
        "num_jobs_2024": "",
        "outlook_pct": "",
        "outlook_desc": "",
        "employment_change": "",
        "projected_employment_2034": "",
        "employment_by_industry_url": extract_industry_matrix_url(soup, occ_meta["title"]),
    }

    qf_table = soup.find("table", id="quickfacts")
    if qf_table:
        tbody = qf_table.find("tbody")
        if tbody:
            for tr in tbody.find_all("tr"):
                th = tr.find("th")
                td = tr.find("td")
                if not th or not td:
                    continue
                field = clean(th.get_text()).lower()
                value = clean(td.get_text())

                if "median pay" in field:
                    row["median_pay_annual"], row["median_pay_hourly"] = parse_pay(value)
                elif "entry-level education" in field:
                    row["entry_education"] = value
                elif "work experience" in field:
                    row["work_experience"] = value
                elif "on-the-job training" in field:
                    row["training"] = value
                elif "number of jobs" in field:
                    row["num_jobs_2024"] = parse_number(value)
                elif "job outlook" in field:
                    row["outlook_pct"], row["outlook_desc"] = parse_outlook(value)
                elif "employment change" in field:
                    row["employment_change"] = parse_number(value)

    outlook_table = soup.find("table", id="outlook-table")
    if outlook_table:
        tbody = outlook_table.find("tbody")
        if tbody:
            tr = tbody.find("tr")
            if tr:
                cells = [clean(cell.get_text()) for cell in tr.find_all(["td", "th"])]
                if len(cells) >= 4:
                    soc = cells[1]
                    if soc != "-":
                        row["soc_code"] = soc
                    row["projected_employment_2034"] = parse_number(cells[3])

    if row["median_pay_annual"] and not row["median_pay_hourly"]:
        row["median_pay_hourly"] = f"{float(row['median_pay_annual']) / 2080:.2f}"
    elif row["median_pay_hourly"] and not row["median_pay_annual"]:
        row["median_pay_annual"] = str(round(float(row["median_pay_hourly"]) * 2080))

    return row


def main():
    with OCCUPATIONS_JSON.open(encoding="utf-8") as f:
        occupations = json.load(f)

    fieldnames = [
        "title",
        "category",
        "slug",
        "soc_code",
        "median_pay_annual",
        "median_pay_hourly",
        "entry_education",
        "work_experience",
        "training",
        "num_jobs_2024",
        "projected_employment_2034",
        "outlook_pct",
        "outlook_desc",
        "employment_change",
        "employment_by_industry_url",
        "url",
    ]

    rows = []
    missing = 0
    for occ in occupations:
        html_path = HTML_DIR / f"{occ['slug']}.html"
        if not html_path.exists():
            missing += 1
            continue
        rows.append(extract_occupation(html_path, occ))

    with OCCUPATIONS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OCCUPATIONS_CSV} (missing HTML: {missing})")
    print("\nSample rows:")
    for row in rows[:3]:
        print(
            f"  {row['title']}: ${row['median_pay_annual']}/yr, "
            f"{row['num_jobs_2024']} jobs, {row['outlook_pct']}% outlook"
        )


if __name__ == "__main__":
    main()
