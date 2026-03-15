"""Parse the BLS OOH A-Z index to extract all occupations."""

import json
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from paths import OCCUPATIONS_JSON, OOH_INDEX_HTML, ensure_data_dirs


def parse_category_and_slug(url):
    parts = [part for part in urlparse(url).path.split("/") if part]
    if len(parts) < 3:
        return "", ""
    return parts[-2], parts[-1].replace(".htm", "")


def main():
    ensure_data_dirs()
    with OOH_INDEX_HTML.open("r", encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    az_list = soup.find("div", class_="a-z-list")
    occupations = {}
    aliases = []

    for li in az_list.find_all("li"):
        links = li.find_all("a")
        text = li.get_text()

        if ", see:" in text or ", see " in text:
            if len(links) >= 2:
                alias_name = links[0].get_text(strip=True)
                canonical_name = links[1].get_text(strip=True)
                url = links[1]["href"]
                aliases.append((alias_name, canonical_name, url))
                if url not in occupations:
                    occupations[url] = canonical_name
        elif links:
            name = links[0].get_text(strip=True)
            url = links[0]["href"]
            if url not in occupations:
                occupations[url] = name

    sorted_occupations = sorted(occupations.items(), key=lambda item: item[1].lower())

    print(f"Total unique occupations: {len(sorted_occupations)}")
    print(f"Total aliases (redirects): {len(aliases)}")
    print()
    print("--- First 20 occupations ---")
    for url, name in sorted_occupations[:20]:
        print(f"  {name}")
        print(f"    {url}")
    print("...")
    print()
    print("--- Last 10 occupations ---")
    for url, name in sorted_occupations[-10:]:
        print(f"  {name}")
        print(f"    {url}")

    output = []
    for url, name in sorted_occupations:
        category, slug = parse_category_and_slug(url)
        output.append({
            "title": name,
            "url": url,
            "category": category,
            "slug": slug,
        })
    with OCCUPATIONS_JSON.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved {len(output)} occupations to {OCCUPATIONS_JSON}")


if __name__ == "__main__":
    main()
