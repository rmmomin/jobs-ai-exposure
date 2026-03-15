"""Shared filesystem paths for the repository."""

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
SOURCE_DIR = DATA_DIR / "source"
HTML_DIR = SOURCE_DIR / "html"
PAGES_DIR = DATA_DIR / "pages"
EXPORTS_DIR = DATA_DIR / "exports"

OOH_INDEX_HTML = SOURCE_DIR / "occupational_outlook_handbook.html"
OCCUPATIONS_JSON = EXPORTS_DIR / "occupations.json"
OCCUPATIONS_CSV = EXPORTS_DIR / "occupations.csv"
SCORES_JSON = EXPORTS_DIR / "scores.json"
SCORES_ORG_JSON = EXPORTS_DIR / "scores_org.json"
INDUSTRY_EXPOSURE_JSON = EXPORTS_DIR / "industry_exposure.json"
INDUSTRY_EXPOSURE_CSV = EXPORTS_DIR / "industry_exposure.csv"
INDUSTRY_EXPOSURE_4DIGIT_JSON = EXPORTS_DIR / "industry_exposure_4digit.json"
INDUSTRY_EXPOSURE_4DIGIT_CSV = EXPORTS_DIR / "industry_exposure_4digit.csv"


def ensure_data_dirs():
    """Create the standard data directories if they do not already exist."""
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def resolve_project_path(path_str: str) -> Path:
    """Resolve a user-provided path relative to the repository root."""
    path = Path(path_str)
    if path.is_absolute():
        return path
    return ROOT_DIR / path
