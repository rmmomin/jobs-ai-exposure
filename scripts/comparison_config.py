"""Shared comparison configuration (paths + source URLs) for first-pass tooling."""

from __future__ import annotations

from pathlib import Path

from paths import DATA_DIR, EXPORTS_DIR, SOURCE_DIR

COMPARISON_SOURCE_DIR = SOURCE_DIR / "comparison"
COMPARISON_EXPORTS_DIR = EXPORTS_DIR / "comparisons"
COMPARISON_CLEANED_DIR = COMPARISON_EXPORTS_DIR / "cleaned"
COMPARISON_TABLES_DIR = COMPARISON_EXPORTS_DIR / "tables"
COMPARISON_FIGURES_DIR = COMPARISON_EXPORTS_DIR / "figures"
LOCAL_DATA_DIR = DATA_DIR / "local"

COMPARISON_DOWNLOADS: dict[str, str] = {
    # Felten / Raj / Seamans
    "AIOE_DataAppendix.xlsx": "https://raw.githubusercontent.com/AIOE-Data/AIOE/main/AIOE_DataAppendix.xlsx",
    "Language_Modeling_AIOE_and_AIIE.xlsx": "https://raw.githubusercontent.com/AIOE-Data/AIOE/main/Language%20Modeling%20AIOE%20and%20AIIE.xlsx",
    "Image_Generation_AIOE_and_AIIE.xlsx": "https://raw.githubusercontent.com/AIOE-Data/AIOE/main/Image%20Generation%20AIOE%20and%20AIIE.xlsx",
    # OpenAI GPTs are GPTs
    "openai_occ_level.csv": "https://raw.githubusercontent.com/openai/GPTs-are-GPTs/main/data/occ_level.csv",
    # Microsoft Working with AI
    "microsoft_ai_applicability_scores.csv": "https://raw.githubusercontent.com/microsoft/working-with-ai/main/ai_applicability_scores.csv",
    # Eisfeldt et al.
    "genaiexp_estz_occscores.csv": "https://artificialminushuman.com/data/genaiexp_estz_occscores.csv",
    "genaiexp_estz_firmscores.csv": "https://artificialminushuman.com/data/genaiexp_estz_firmscores.csv",
    # Webb mirror
    "exposure_by_soc4.xlsx": "https://raw.githubusercontent.com/nandomp/AIlabour/master/labour%20data/scores_webb2020/exposure_by_soc4.xlsx",
    # Yale workbook
    "TBL_Data_AI_Exposure_Updated.xlsx": "https://budgetlab.yale.edu/sites/default/files/2026-02/TBL-Data-AI-Exposure-What-do-we-know-202602-Updated.xlsx",
    # Official crosswalk/helper files
    "soc_2010_to_2018_crosswalk.xlsx": "https://www.bls.gov/soc/2018/soc_2010_to_2018_crosswalk.xlsx",
    "nem_onet_to_soc_crosswalk.xlsx": "https://www.bls.gov/emp/classifications-crosswalks/nem-onet-to-soc-crosswalk.xlsx",
    "nem_occupational_coverage.xlsx": "https://www.bls.gov/emp/classifications-crosswalks/nem-occupational-coverage.xlsx",
}


COMPARISON_DIRS: tuple[Path, ...] = (
    LOCAL_DATA_DIR,
    COMPARISON_SOURCE_DIR,
    COMPARISON_EXPORTS_DIR,
    COMPARISON_CLEANED_DIR,
    COMPARISON_TABLES_DIR,
    COMPARISON_FIGURES_DIR,
)


def ensure_comparison_dirs() -> None:
    for path in COMPARISON_DIRS:
        path.mkdir(parents=True, exist_ok=True)
