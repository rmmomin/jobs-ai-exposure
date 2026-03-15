"""Parse a BLS OOH detail page into a clean Markdown document."""

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from paths import HTML_DIR, PAGES_DIR, resolve_project_path


def clean(text):
    """Clean up whitespace from extracted text."""
    return re.sub(r"\s+", " ", text).strip()


def parse_ooh_page(html_path):
    html_path = Path(html_path)
    with html_path.open("r", encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    md = []

    h1 = soup.find("h1")
    title = clean(h1.get_text()) if h1 else "Unknown Occupation"
    md.append(f"# {title}")
    md.append("")

    canonical = soup.find("link", rel="canonical")
    if canonical:
        md.append(f"**Source:** {canonical['href']}")
        md.append("")

    qf_table = soup.find("table", id="quickfacts")
    if qf_table:
        md.append("## Quick Facts")
        md.append("")
        md.append("| Field | Value |")
        md.append("|-------|-------|")
        for row in qf_table.find("tbody").find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if th and td:
                md.append(f"| {clean(th.get_text())} | {clean(td.get_text())} |")
        md.append("")

    panes = soup.find("div", id="panes")
    if not panes:
        return "\n".join(md)

    tab_ids = ["tab-1", "tab-2", "tab-3", "tab-4", "tab-5", "tab-6", "tab-7", "tab-8", "tab-9"]

    for tab_id in tab_ids:
        tab_div = panes.find("div", id=tab_id)
        if not tab_div:
            continue

        article = tab_div.find("article") or tab_div
        h2 = article.find("h2")
        if not h2:
            continue

        section_title = clean(h2.find("span").get_text()) if h2.find("span") else clean(h2.get_text())
        if tab_id in ("tab-1", "tab-7", "tab-8", "tab-9"):
            continue

        md.append(f"## {section_title}")
        md.append("")

        chart_div = article.find("div", class_="ooh-chart")
        if chart_div:
            chart_subtitle = chart_div.find("p")
            dts = chart_div.find("dl")
            if dts:
                items = []
                for dt, dd in zip(dts.find_all("dt"), dts.find_all("dd")):
                    label = clean(dt.get_text())
                    for span in dd.find_all("span"):
                        value = clean(span.get_text())
                        if value and (value.startswith("$") or value.endswith("%")):
                            items.append((label, value))
                            break
                if items:
                    subtitle = clean(chart_subtitle.get_text()) if chart_subtitle else ""
                    if subtitle:
                        md.append(f"*{subtitle}*")
                        md.append("")
                    for label, value in items:
                        md.append(f"- **{label}**: {value}")
                    md.append("")

        for elem in article.children:
            if not hasattr(elem, "name"):
                continue
            if elem.name == "h2":
                continue
            if elem.name == "div" and "ooh-chart" in elem.get("class", []):
                continue
            if elem.name == "div" and "ooh_right_img" in elem.get("class", []):
                continue
            if elem.name == "h3":
                md.append(f"### {clean(elem.get_text())}")
                md.append("")
            elif elem.name == "p":
                text = clean(elem.get_text())
                if text:
                    md.append(text)
                    md.append("")
            elif elem.name == "ul":
                for li in elem.find_all("li"):
                    md.append(f"- {clean(li.get_text())}")
                md.append("")
            elif elem.name == "table":
                if elem.get("id") == "outlook-table":
                    continue
                rows = elem.find_all("tr")
                if rows:
                    table_data = []
                    for row in rows:
                        row_data = [clean(cell.get_text()) for cell in row.find_all(["td", "th"])]
                        if row_data and any(row_data):
                            table_data.append(row_data)
                    if table_data:
                        max_cols = max(len(row) for row in table_data)
                        for row in table_data:
                            while len(row) < max_cols:
                                row.append("")
                        md.append("| " + " | ".join(["---"] * max_cols) + " |")
                        for row in table_data:
                            md.append("| " + " | ".join(row) + " |")
                        md.append("")

        if tab_id == "tab-6":
            outlook_table = article.find("table", id="outlook-table")
            if outlook_table:
                md.append("### Employment Projections")
                md.append("")
                tbody = outlook_table.find("tbody")
                if tbody:
                    labels = [
                        "Occupational Title",
                        "SOC Code",
                        "Employment 2024",
                        "Projected Employment 2034",
                        "Change % 2024-34",
                        "Change Numeric 2024-34",
                    ]
                    for row in tbody.find_all("tr"):
                        values = [clean(cell.get_text()) for cell in row.find_all(["td", "th"])]
                        if values:
                            for label, value in zip(labels, values):
                                if value and value != "Get data":
                                    md.append(f"- **{label}:** {value}")
                            md.append("")

    update_p = soup.find("p", class_="update")
    if update_p:
        md.append("---")
        md.append(f"*{clean(update_p.get_text())}*")
        md.append("")

    return "\n".join(md)


if __name__ == "__main__":
    html_path = resolve_project_path(sys.argv[1]) if len(sys.argv) > 1 else HTML_DIR / "electrician.html"
    result = parse_ooh_page(html_path)

    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PAGES_DIR / f"{Path(html_path).stem}.md"
    out_path.write_text(result, encoding="utf-8")
    print(f"Written to {out_path}")
    print()
    print(result)
