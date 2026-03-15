"""Download external occupation/industry comparison datasets into data/source/comparison/."""

from __future__ import annotations

import argparse
from pathlib import Path

import httpx

from comparison_utils import ensure_dir
from paths import SOURCE_DIR


DOWNLOADS = {
    "aioe_data_appendix.xlsx": "https://raw.githubusercontent.com/AIOE-Data/AIOE/main/AIOE_DataAppendix.xlsx",
    "aioe_language_modeling.xlsx": "https://raw.githubusercontent.com/AIOE-Data/AIOE/main/Language%20Modeling%20AIOE%20and%20AIIE.xlsx",
    "aioe_image_generation.xlsx": "https://raw.githubusercontent.com/AIOE-Data/AIOE/main/Image%20Generation%20AIOE%20and%20AIIE.xlsx",
    "openai_gpts_occ_level.csv": "https://raw.githubusercontent.com/openai/GPTs-are-GPTs/main/data/occ_level.csv",
    "microsoft_ai_applicability_scores.csv": "https://raw.githubusercontent.com/microsoft/working-with-ai/main/ai_applicability_scores.csv",
    "eisfeldt_genaiexp_occscores.csv": "https://artificialminushuman.com/data/genaiexp_estz_occscores.csv",
    "eisfeldt_genaiexp_firmscores.csv": "https://artificialminushuman.com/data/genaiexp_estz_firmscores.csv",
    "webb_exposure_by_soc4.xlsx": "https://raw.githubusercontent.com/nandomp/AIlabour/master/labour%20data/scores_webb2020/exposure_by_soc4.xlsx",
    "yale_ai_exposure_workbook.xlsx": "https://budgetlab.yale.edu/sites/default/files/2026-02/TBL-Data-AI-Exposure-What-do-we-know-202602-Updated.xlsx",
    "soc_2010_to_2018_crosswalk.xlsx": "https://www.bls.gov/soc/2018/soc_2010_to_2018_crosswalk.xlsx",
    "onet_to_soc_crosswalk.xlsx": "https://www.bls.gov/emp/classifications-crosswalks/nem-onet-to-soc-crosswalk.xlsx",
    "naics_2017_to_2022.xlsx": "https://www.census.gov/naics/concordances/2017_to_2022_NAICS.xlsx",
    "naics_2012_to_2017.xlsx": "https://www.census.gov/naics/concordances/2012_to_2017_NAICS.xlsx",
}


def download_file(client: httpx.Client, url: str, destination: Path, force: bool) -> str:
    if destination.exists() and not force:
        return "cached"
    try:
        response = client.get(url, timeout=120)
        response.raise_for_status()
    except Exception as exc:
        return f"failed ({exc})"
    destination.write_bytes(response.content)
    return "downloaded"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-download even if file already exists")
    args = parser.parse_args()

    out_dir = ensure_dir(SOURCE_DIR / "comparison")
    with httpx.Client(follow_redirects=True) as client:
        for filename, url in DOWNLOADS.items():
            destination = out_dir / filename
            status = download_file(client, url, destination, args.force)
            print(f"[{status}] {filename} <- {url}")


if __name__ == "__main__":
    main()
