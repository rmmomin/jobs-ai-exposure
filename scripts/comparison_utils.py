"""Shared helpers for downloading and comparing benchmark exposure datasets."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import matplotlib.pyplot as plt
import pandas as pd
from scipy import stats

from paths import (
    COMPARISON_CLEANED_DIR,
    COMPARISON_FIGURES_DIR,
    COMPARISON_SOURCE_DIR,
    COMPARISON_TABLES_DIR,
    OCCUPATIONS_CSV,
    SCORES_GABRIEL_JSON,
    SCORES_JSON,
    SCORES_ORG_JSON,
    ensure_data_dirs,
    resolve_project_path,
)


DEFAULT_TIMEOUT = 120.0
MAX_EXCEL_HEADER_ROWS = 8
PLOT_DPI = 180
TOP_DISAGREEMENTS = 30
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

COMPARISON_DOWNLOADS = [
    {
        "name": "felten_base",
        "filename": "AIOE_DataAppendix.xlsx",
        "url": "https://raw.githubusercontent.com/AIOE-Data/AIOE/main/AIOE_DataAppendix.xlsx",
        "kind": "occupation_industry",
    },
    {
        "name": "felten_language_modeling",
        "filename": "Language_Modeling_AIOE_and_AIIE.xlsx",
        "url": "https://raw.githubusercontent.com/AIOE-Data/AIOE/main/Language%20Modeling%20AIOE%20and%20AIIE.xlsx",
        "kind": "occupation_industry",
    },
    {
        "name": "felten_image_generation",
        "filename": "Image_Generation_AIOE_and_AIIE.xlsx",
        "url": "https://raw.githubusercontent.com/AIOE-Data/AIOE/main/Image%20Generation%20AIOE%20and%20AIIE.xlsx",
        "kind": "occupation_industry",
    },
    {
        "name": "openai_gpts_are_gpts",
        "filename": "openai_occ_level.csv",
        "url": "https://raw.githubusercontent.com/openai/GPTs-are-GPTs/main/data/occ_level.csv",
        "kind": "occupation",
    },
    {
        "name": "microsoft_working_with_ai",
        "filename": "microsoft_ai_applicability_scores.csv",
        "url": "https://raw.githubusercontent.com/microsoft/working-with-ai/main/ai_applicability_scores.csv",
        "kind": "occupation",
    },
    {
        "name": "eisfeldt_occupation",
        "filename": "genaiexp_estz_occscores.csv",
        "url": "https://artificialminushuman.com/data/genaiexp_estz_occscores.csv",
        "kind": "occupation",
    },
    {
        "name": "eisfeldt_firm",
        "filename": "genaiexp_estz_firmscores.csv",
        "url": "https://artificialminushuman.com/data/genaiexp_estz_firmscores.csv",
        "kind": "reference",
    },
    {
        "name": "webb_soc4",
        "filename": "webb_exposure_by_soc4.xlsx",
        "url": "https://raw.githubusercontent.com/nandomp/AIlabour/master/labour%20data/scores_webb2020/exposure_by_soc4.xlsx",
        "kind": "occupation",
    },
    {
        "name": "yale_workbook",
        "filename": "TBL_Data_AI_Exposure_What_do_we_know_202602_Updated.xlsx",
        "url": "https://budgetlab.yale.edu/sites/default/files/2026-02/TBL-Data-AI-Exposure-What-do-we-know-202602-Updated.xlsx",
        "kind": "reference",
    },
    {
        "name": "bls_soc_2010_to_2018_crosswalk",
        "filename": "soc_2010_to_2018_crosswalk.xlsx",
        "url": "https://www.bls.gov/soc/2018/soc_2010_to_2018_crosswalk.xlsx",
        "kind": "crosswalk",
    },
    {
        "name": "bls_nem_onet_to_soc_crosswalk",
        "filename": "nem_onet_to_soc_crosswalk.xlsx",
        "url": "https://www.bls.gov/emp/classifications-crosswalks/nem-onet-to-soc-crosswalk.xlsx",
        "kind": "crosswalk",
    },
    {
        "name": "bls_nem_occupational_coverage",
        "filename": "nem_occupational_coverage.xlsx",
        "url": "https://www.bls.gov/emp/classifications-crosswalks/nem-occupational-coverage.xlsx",
        "kind": "crosswalk",
    },
]

DOWNLOADS_BY_NAME = {item["name"]: item for item in COMPARISON_DOWNLOADS}
SOC_DIGITS_RE = re.compile(r"(\d{2})\D?(\d{4})")
SOC4_DIGITS_RE = re.compile(r"(\d{2})\D?(\d{2})")
NON_DIGIT_RE = re.compile(r"\D+")


def ensure_comparison_dirs() -> None:
    """Create the comparison download and export directories."""
    ensure_data_dirs()


def comparison_download_path(name: str) -> Path:
    """Return the local path for a configured comparison source."""
    target = DOWNLOADS_BY_NAME[name]
    return COMPARISON_SOURCE_DIR / target["filename"]


def ensure_downloads(names: list[str], force: bool = False, skip_download: bool = False) -> list[str]:
    """Ensure named comparison sources exist locally, downloading when allowed."""
    missing: list[str] = []
    for name in names:
        path = comparison_download_path(name)
        if path.exists() and not force:
            continue
        if skip_download:
            missing.append(name)
            continue
        target = DOWNLOADS_BY_NAME[name]
        download_file(target["url"], path, force=force)
    return missing


def download_file(url: str, output_path: Path, force: bool = False) -> Path:
    """Download a file unless it already exists locally."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not force:
        return output_path

    with httpx.stream(
        "GET",
        url,
        headers=BROWSER_HEADERS,
        follow_redirects=True,
        timeout=DEFAULT_TIMEOUT,
    ) as response:
        response.raise_for_status()
        with output_path.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
    return output_path




def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column labels into compact snake_case names."""
    columns = []
    seen: dict[str, int] = {}
    for column in df.columns:
        text = str(column).strip().lower()
        text = re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "column"
        count = seen.get(text, 0)
        seen[text] = count + 1
        columns.append(text if count == 0 else f"{text}_{count + 1}")
    out = df.copy()
    out.columns = columns
    return out


def clean_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Drop empty rows and columns from an imported dataframe."""
    out = df.copy()
    out = out.dropna(axis=0, how="all")
    out = out.dropna(axis=1, how="all")
    return out


def inspect_excel_workbook(path: Path) -> pd.DataFrame:
    """Create a lightweight workbook inventory for downloaded Excel files."""
    workbook = pd.ExcelFile(path)
    rows: list[dict] = []
    for sheet_name in workbook.sheet_names:
        parsed = None
        chosen_header = None
        for header_row in range(MAX_EXCEL_HEADER_ROWS + 1):
            try:
                df = pd.read_excel(path, sheet_name=sheet_name, header=header_row)
            except Exception:
                continue
            df = normalize_columns(clean_frame(df))
            if df.empty:
                continue
            usable_columns = [column for column in df.columns if not column.startswith("unnamed")]
            if not usable_columns:
                continue
            parsed = df
            chosen_header = header_row
            break
        if parsed is None:
            rows.append(
                {
                    "source_path": str(path),
                    "sheet_name": sheet_name,
                    "header_row": None,
                    "row_count": 0,
                    "column_count": 0,
                    "columns": "",
                }
            )
            continue
        rows.append(
            {
                "source_path": str(path),
                "sheet_name": sheet_name,
                "header_row": chosen_header,
                "row_count": len(parsed),
                "column_count": len(parsed.columns),
                "columns": ", ".join(parsed.columns[:15]),
            }
        )
    return pd.DataFrame(rows)


def write_table(df: pd.DataFrame, path: Path) -> None:
    """Write a dataframe to CSV using UTF-8."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def default_comparison_paths(output_dir: str | None = None) -> tuple[Path, Path, Path]:
    """Resolve cleaned, table, and figure directories for comparison outputs."""
    if output_dir is None:
        return COMPARISON_CLEANED_DIR, COMPARISON_TABLES_DIR, COMPARISON_FIGURES_DIR
    base = resolve_project_path(output_dir)
    return base / "cleaned", base / "tables", base / "figures"


def load_json_records(path: Path) -> list[dict]:
    """Load a JSON list from disk."""
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"Expected a list of records in {path}")
    return payload


def read_csv_flexible(path: Path) -> pd.DataFrame:
    """Read a CSV file and normalize its columns."""
    return normalize_columns(clean_frame(pd.read_csv(path)))


def read_excel_sheet_candidates(path: Path, sheet_name: str) -> list[tuple[int, pd.DataFrame]]:
    """Read one sheet with multiple header guesses for schema detection."""
    candidates: list[tuple[int, pd.DataFrame]] = []
    for header_row in range(MAX_EXCEL_HEADER_ROWS + 1):
        try:
            df = pd.read_excel(path, sheet_name=sheet_name, header=header_row)
        except Exception:
            continue
        df = normalize_columns(clean_frame(df))
        if df.empty:
            continue
        usable_columns = [column for column in df.columns if not column.startswith("unnamed")]
        if not usable_columns:
            continue
        candidates.append((header_row, df))
    return candidates


def workbook_sheet_score(df: pd.DataFrame, include_tokens: tuple[str, ...], exclude_tokens: tuple[str, ...]) -> int:
    """Score one parsed workbook sheet candidate against desired tokens."""
    columns = " ".join(df.columns)
    score = min(len(df.columns), 12)
    for token in include_tokens:
        if token in columns:
            score += 3
    for token in exclude_tokens:
        if token in columns:
            score -= 4
    return score


def choose_sheet_candidate(
    candidates: list[tuple[int, pd.DataFrame]],
    include_tokens: tuple[str, ...] = (),
    exclude_tokens: tuple[str, ...] = (),
) -> tuple[int, pd.DataFrame] | None:
    """Pick the parsed sheet candidate whose columns best match the target tokens."""
    best_choice = None
    best_score = -1
    for header_row, df in candidates:
        score = workbook_sheet_score(df, include_tokens, exclude_tokens)
        if score > best_score:
            best_score = score
            best_choice = (header_row, df)
    return best_choice


def select_workbook_sheet(
    path: Path,
    include_tokens: tuple[str, ...],
    exclude_tokens: tuple[str, ...] = (),
) -> tuple[str, int, pd.DataFrame]:
    """Inspect workbook sheets dynamically and return the best matching parse."""
    workbook = pd.ExcelFile(path)
    best_sheet = None
    best_header = None
    best_df = None
    best_score = -1
    for sheet_name in workbook.sheet_names:
        choice = choose_sheet_candidate(
            read_excel_sheet_candidates(path, sheet_name),
            include_tokens=include_tokens,
            exclude_tokens=exclude_tokens,
        )
        if choice is None:
            continue
        header_row, df = choice
        score = workbook_sheet_score(df, include_tokens, exclude_tokens)
        if score > best_score:
            best_score = score
            best_sheet = sheet_name
            best_header = header_row
            best_df = df
    if best_df is None or best_sheet is None or best_header is None:
        raise ValueError(f"Could not locate a matching sheet in {path}")
    return best_sheet, best_header, best_df


def first_present_column(df: pd.DataFrame, *candidates: str) -> str | None:
    """Return the first matching normalized column from a candidate list."""
    for column in candidates:
        if column in df.columns:
            return column
    return None


def find_column_by_tokens(
    df: pd.DataFrame,
    required_tokens: tuple[str, ...],
    optional_tokens: tuple[str, ...] = (),
    exclude_tokens: tuple[str, ...] = (),
) -> str | None:
    """Find a likely column name based on token matches."""
    best_column = None
    best_score = -1
    for column in df.columns:
        text = column.lower()
        if any(token in text for token in exclude_tokens):
            continue
        if not all(token in text for token in required_tokens):
            continue
        score = sum(token in text for token in optional_tokens)
        if score > best_score:
            best_score = score
            best_column = column
    return best_column


def to_numeric(series: pd.Series) -> pd.Series:
    """Convert a series to numeric, coercing malformed values to NaN."""
    return pd.to_numeric(series.astype(str).str.replace(",", ""), errors="coerce")


def norm_soc(value) -> str | None:
    """Normalize detailed SOC values like 15-1252.00 into 15-1252."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    if not text or text in {"—", "-"}:
        return None

    match = SOC_DIGITS_RE.search(text)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    digits = NON_DIGIT_RE.sub("", text)
    if len(digits) >= 6:
        return f"{digits[:2]}-{digits[2:6]}"
    return None


def soc4(value) -> str | None:
    """Collapse a detailed SOC code to SOC4/minor-group grain."""
    normalized = norm_soc(value)
    if normalized is not None:
        return f"{normalized[:2]}-{normalized[3:5]}"

    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    match = SOC4_DIGITS_RE.search(text)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    digits = NON_DIGIT_RE.sub("", text)
    if len(digits) >= 4:
        return f"{digits[:2]}-{digits[2:4]}"
    return None


def soc_major(value) -> str | None:
    """Return the two-digit SOC major group code."""
    normalized = norm_soc(value)
    if normalized is not None:
        return normalized[:2]
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    digits = NON_DIGIT_RE.sub("", str(value))
    return digits[:2] if len(digits) >= 2 else None


def norm_naics(value) -> str | None:
    """Normalize NAICS codes while preserving meaningful trailing zeros."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    digits = NON_DIGIT_RE.sub("", text.replace(".0", ""))
    return digits or None


def naics_level(value) -> int | None:
    """Infer the NAICS grain from a normalized code."""
    code = norm_naics(value)
    if code is None:
        return None
    if len(code) < 6:
        return len(code)
    if code.endswith("0000"):
        return 2
    if code.endswith("000"):
        return 3
    if code.endswith("00"):
        return 4
    if code.endswith("0"):
        return 5
    return 6


def extract_soc_from_matrix_url(value) -> str | None:
    """Pull the NEM/SOC occupation code out of a BLS matrix URL."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    query = parse_qs(urlparse(text).query)
    values = query.get("queryParams") or query.get("queryparams")
    if not values:
        return None
    return norm_soc(values[0])


def add_distribution_columns(df: pd.DataFrame, value_column: str, prefix: str) -> pd.DataFrame:
    """Append z-score and percentile columns for a numeric metric."""
    out = df.copy()
    out[value_column] = to_numeric(out[value_column])
    valid = out[value_column].dropna()
    if valid.empty:
        out[f"{prefix}_zscore"] = pd.NA
        out[f"{prefix}_percentile"] = pd.NA
        return out

    std = valid.std(ddof=0)
    mean = valid.mean()
    if std == 0 or math.isnan(std):
        out[f"{prefix}_zscore"] = 0.0
    else:
        out[f"{prefix}_zscore"] = (out[value_column] - mean) / std
    out[f"{prefix}_percentile"] = out[value_column].rank(method="average", pct=True)
    return out


def employment_weighted_average(values: pd.Series, weights: pd.Series) -> float | None:
    """Return an employment-weighted mean where weights are available."""
    valid = values.notna() & weights.notna()
    if not valid.any():
        return None
    total_weight = weights[valid].sum()
    if total_weight == 0:
        return None
    return float((values[valid] * weights[valid]).sum() / total_weight)


def load_occupations_metadata() -> pd.DataFrame:
    """Load the canonical occupation metadata export with normalized SOC helpers."""
    occupations = pd.read_csv(OCCUPATIONS_CSV, keep_default_na=False)
    occupations = normalize_columns(occupations)
    occupations["num_jobs_2024"] = to_numeric(occupations["num_jobs_2024"])
    occupations["soc_code"] = occupations["soc_code"].map(norm_soc)
    fallback_soc = occupations["employment_by_industry_url"].map(extract_soc_from_matrix_url)
    occupations["soc_code"] = occupations["soc_code"].fillna(fallback_soc)
    occupations["soc4"] = occupations["soc_code"].map(soc4)
    occupations["soc_major"] = occupations["soc_code"].map(soc_major)
    return occupations


def _prepare_variant_frame(
    frame: pd.DataFrame,
    variant: str,
    occupations: pd.DataFrame,
    current_extras: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Merge metadata and normalize one internal score variant."""
    out = frame.copy()
    if "exposure" in out.columns and "karpathy_score" not in out.columns:
        out = out.rename(columns={"exposure": "karpathy_score"})
    out["karpathy_score"] = to_numeric(out["karpathy_score"])

    metadata_columns = [
        "slug",
        "title",
        "category",
        "soc_code",
        "soc4",
        "soc_major",
        "num_jobs_2024",
        "url",
    ]
    out = out.merge(occupations[metadata_columns], on="slug", how="left", suffixes=("", "_occ"))

    if "title_occ" in out.columns:
        out["title"] = out["title"].replace("", pd.NA).fillna(out["title_occ"])
        out = out.drop(columns=["title_occ"])
    if "category_occ" in out.columns:
        existing = out["category"] if "category" in out.columns else pd.Series(index=out.index, dtype=object)
        out["category"] = existing.replace("", pd.NA).fillna(out["category_occ"])
        out = out.drop(columns=["category_occ"])
    if "soc_code_occ" in out.columns:
        existing = out["soc_code"] if "soc_code" in out.columns else pd.Series(index=out.index, dtype=object)
        out["soc_code"] = existing.map(norm_soc).fillna(out["soc_code_occ"])
        out = out.drop(columns=["soc_code_occ"])
    if "soc4_occ" in out.columns:
        existing = out["soc4"] if "soc4" in out.columns else pd.Series(index=out.index, dtype=object)
        out["soc4"] = existing.fillna(out["soc4_occ"])
        out = out.drop(columns=["soc4_occ"])
    if "soc_major_occ" in out.columns:
        existing = out["soc_major"] if "soc_major" in out.columns else pd.Series(index=out.index, dtype=object)
        out["soc_major"] = existing.fillna(out["soc_major_occ"])
        out = out.drop(columns=["soc_major_occ"])
    if "num_jobs_2024_occ" in out.columns:
        existing = to_numeric(out["num_jobs_2024"]) if "num_jobs_2024" in out.columns else pd.Series(index=out.index, dtype=float)
        out["num_jobs_2024"] = existing.fillna(to_numeric(out["num_jobs_2024_occ"]))
        out = out.drop(columns=["num_jobs_2024_occ"])
    if "url_occ" in out.columns:
        existing = out["url"] if "url" in out.columns else pd.Series(index=out.index, dtype=object)
        out["url"] = existing.replace("", pd.NA).fillna(out["url_occ"])
        out = out.drop(columns=["url_occ"])

    if current_extras is not None:
        out = out.merge(current_extras, on="slug", how="left", suffixes=("", "_current"))
        for column in ["industry_matrix_url", "industries", "naics_industry_codes"]:
            current_column = f"{column}_current"
            if current_column not in out.columns:
                continue
            if column not in out.columns:
                out[column] = out[current_column]
            else:
                out[column] = out[column].where(out[column].notna(), out[current_column])
            out = out.drop(columns=[current_column])

    out["soc_code"] = out["soc_code"].map(norm_soc)
    out["soc4"] = out["soc4"].fillna(out["soc_code"].map(soc4))
    out["soc_major"] = out["soc_major"].fillna(out["soc_code"].map(soc_major))
    out["variant"] = variant
    return out


def load_internal_variants() -> dict[str, pd.DataFrame]:
    """Load every available internal occupation score variant."""
    occupations = load_occupations_metadata()
    current = pd.DataFrame(load_json_records(SCORES_JSON))
    current_extras = current[["slug", "industry_matrix_url", "industries", "naics_industry_codes"]].copy()

    variants = {
        "repo_current": _prepare_variant_frame(current, "repo_current", occupations),
        "repo_original": _prepare_variant_frame(
            pd.DataFrame(load_json_records(SCORES_ORG_JSON)),
            "repo_original",
            occupations,
            current_extras=current_extras,
        ),
    }
    if SCORES_GABRIEL_JSON.exists():
        variants["repo_gabriel"] = _prepare_variant_frame(
            pd.DataFrame(load_json_records(SCORES_GABRIEL_JSON)),
            "repo_gabriel",
            occupations,
            current_extras=current_extras,
        )
    return variants


def aggregate_variant_by_column(frame: pd.DataFrame, code_column: str) -> pd.DataFrame:
    """Aggregate a normalized internal variant to a shared comparison grain."""
    working = frame.copy()
    working["karpathy_score"] = to_numeric(working["karpathy_score"])
    working["num_jobs_2024"] = to_numeric(working["num_jobs_2024"])
    working = working[working[code_column].notna() & working["karpathy_score"].notna()].copy()
    if working.empty:
        return pd.DataFrame(columns=["variant", code_column, "title", "karpathy_score", "num_jobs_2024"])

    rows = []
    for (variant, group_code), group in working.groupby(["variant", code_column], dropna=False):
        weighted_score = employment_weighted_average(group["karpathy_score"], group["num_jobs_2024"])
        if weighted_score is None:
            weighted_score = float(group["karpathy_score"].mean())
        rows.append(
            {
                "variant": variant,
                code_column: group_code,
                "title": group.sort_values("num_jobs_2024", ascending=False)["title"].iloc[0],
                "karpathy_score": weighted_score,
                "num_jobs_2024": float(group["num_jobs_2024"].fillna(0).sum()),
                "occupation_count": int(group["slug"].nunique()),
            }
        )
    return pd.DataFrame(rows)


def load_soc_2010_to_2018_crosswalk() -> pd.DataFrame:
    """Load the BLS 2010-to-2018 SOC crosswalk."""
    path = comparison_download_path("bls_soc_2010_to_2018_crosswalk")
    _, _, df = select_workbook_sheet(path, include_tokens=("2010", "2018", "soc", "title"))
    columns = {
        "soc_2010_code": find_column_by_tokens(df, ("2010", "soc", "code")),
        "soc_2010_title": find_column_by_tokens(df, ("2010", "soc", "title")),
        "soc_2018_code": find_column_by_tokens(df, ("2018", "soc", "code")),
        "soc_2018_title": find_column_by_tokens(df, ("2018", "soc", "title")),
    }
    out = df[[column for column in columns.values() if column is not None]].copy()
    out = out.rename(columns={value: key for key, value in columns.items() if value is not None})
    out["soc_2010_code"] = out["soc_2010_code"].map(norm_soc)
    out["soc_2018_code"] = out["soc_2018_code"].map(norm_soc)
    return out.dropna(subset=["soc_2010_code", "soc_2018_code"]).drop_duplicates()


def load_nem_onet_crosswalk() -> pd.DataFrame:
    """Load the BLS O*NET/NEM/OOH crosswalk."""
    path = comparison_download_path("bls_nem_onet_to_soc_crosswalk")
    _, _, df = select_workbook_sheet(
        path,
        include_tokens=("o_net", "nem", "ooh", "title"),
        exclude_tokens=("definition",),
    )
    columns = {
        "onet_soc_code": first_present_column(df, "o_net_soc_code"),
        "onet_soc_title": first_present_column(df, "o_net_soc_title"),
        "nem_code": first_present_column(df, "nem_code"),
        "nem_title": first_present_column(df, "nem_title"),
        "ooh_profile_code": first_present_column(df, "ooh_profile_code"),
        "ooh_profile_title": first_present_column(df, "ooh_profile_title"),
        "ooh_profile_website": first_present_column(df, "ooh_profile_website"),
    }
    out = df[[column for column in columns.values() if column is not None]].copy()
    out = out.rename(columns={value: key for key, value in columns.items() if value is not None})
    out["onet_soc_code"] = out["onet_soc_code"].astype(str).str.strip()
    out["onet_soc_norm"] = out["onet_soc_code"].map(norm_soc)
    out["nem_code"] = out["nem_code"].map(norm_soc)
    out["ooh_profile_website"] = out["ooh_profile_website"].replace({"—": pd.NA})
    out["ooh_profile_title"] = out.get("ooh_profile_title", pd.Series(index=out.index, dtype=object)).replace({"—": pd.NA})
    return out.dropna(subset=["onet_soc_norm", "nem_code"]).drop_duplicates()


def load_nem_occupational_coverage() -> pd.DataFrame:
    """Load BLS NEM occupational coverage metadata."""
    path = comparison_download_path("bls_nem_occupational_coverage")
    _, _, df = select_workbook_sheet(
        path,
        include_tokens=("matrix", "occupation", "code", "title"),
        exclude_tokens=("definition",),
    )
    code_column = find_column_by_tokens(df, ("matrix", "code"))
    title_column = find_column_by_tokens(df, ("matrix", "title"))
    occupation_type_column = first_present_column(df, "occupation_type")
    level_column = first_present_column(df, "level")
    out = df[[column for column in [code_column, title_column, occupation_type_column, level_column] if column is not None]].copy()
    out = out.rename(
        columns={
            code_column: "nem_code",
            title_column: "nem_title",
            occupation_type_column: "occupation_type",
            level_column: "level",
        }
    )
    out["nem_code"] = out["nem_code"].map(norm_soc)
    return out.dropna(subset=["nem_code"]).drop_duplicates()


def map_soc_codes_to_2018(series: pd.Series, crosswalk: pd.DataFrame) -> pd.Series:
    """Map 2010 SOC detailed codes to 2018 where the crosswalk provides a match."""
    lookup = dict(zip(crosswalk["soc_2010_code"], crosswalk["soc_2018_code"]))
    normalized = series.map(norm_soc)
    return normalized.map(lambda code: lookup.get(code, code))


def build_slug_crosswalks(
    occupations: pd.DataFrame,
    nem_onet_crosswalk: pd.DataFrame,
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    """Build NEM/O*NET lookup maps into the repo's occupation-page slugs."""
    url_to_slug = dict(zip(occupations["url"], occupations["slug"]))
    url_to_title = dict(zip(occupations["url"], occupations["title"]))

    slug_by_nem = {
        code: slug
        for code, slug in zip(occupations["soc_code"], occupations["slug"])
        if code
    }
    title_by_nem = {
        code: title
        for code, title in zip(occupations["soc_code"], occupations["title"])
        if code
    }
    slug_by_onet: dict[str, str] = {}
    title_by_onet: dict[str, str] = {}

    for _, row in nem_onet_crosswalk.iterrows():
        website = row.get("ooh_profile_website")
        slug = url_to_slug.get(website)
        title = url_to_title.get(website)
        if slug is None:
            continue
        slug_by_nem.setdefault(row["nem_code"], slug)
        title_by_nem.setdefault(row["nem_code"], title)
        slug_by_onet[row["onet_soc_code"]] = slug
        slug_by_onet[row["onet_soc_norm"]] = slug
        title_by_onet[row["onet_soc_code"]] = title
        title_by_onet[row["onet_soc_norm"]] = title

    return slug_by_nem, title_by_nem, slug_by_onet, title_by_onet


def safe_pearson(left: pd.Series, right: pd.Series) -> tuple[float | None, float | None]:
    """Return Pearson correlation and p-value, handling constant series."""
    if len(left) < 2 or left.nunique(dropna=True) < 2 or right.nunique(dropna=True) < 2:
        return None, None
    result = stats.pearsonr(left, right)
    return float(result.statistic), float(result.pvalue)


def safe_spearman(left: pd.Series, right: pd.Series) -> tuple[float | None, float | None]:
    """Return Spearman correlation and p-value, handling constant series."""
    if len(left) < 2 or left.nunique(dropna=True) < 2 or right.nunique(dropna=True) < 2:
        return None, None
    result = stats.spearmanr(left, right, nan_policy="omit")
    return float(result.statistic), float(result.pvalue)


def build_overlap_summary(
    merged: pd.DataFrame,
    left_label: str,
    right_label: str,
    left_z_column: str,
    right_z_column: str,
    left_percentile_column: str,
    right_percentile_column: str,
) -> dict:
    """Compute overlap, correlation, and decile-overlap statistics."""
    overlap_count = int(len(merged))
    pearson_corr, pearson_pvalue = safe_pearson(merged[left_z_column], merged[right_z_column])
    spearman_corr, spearman_pvalue = safe_spearman(
        merged[left_percentile_column],
        merged[right_percentile_column],
    )

    left_top = set(merged.loc[merged[left_percentile_column] >= 0.9, "comparison_key"])
    right_top = set(merged.loc[merged[right_percentile_column] >= 0.9, "comparison_key"])
    left_bottom = set(merged.loc[merged[left_percentile_column] <= 0.1, "comparison_key"])
    right_bottom = set(merged.loc[merged[right_percentile_column] <= 0.1, "comparison_key"])
    top_union = left_top | right_top
    bottom_union = left_bottom | right_bottom

    return {
        "left": left_label,
        "right": right_label,
        "overlap_count": overlap_count,
        "pearson_correlation": pearson_corr,
        "pearson_pvalue": pearson_pvalue,
        "spearman_correlation": spearman_corr,
        "spearman_pvalue": spearman_pvalue,
        "top_decile_intersection_count": len(left_top & right_top),
        "top_decile_union_count": len(top_union),
        "top_decile_overlap": len(left_top & right_top) / len(top_union) if top_union else None,
        "bottom_decile_intersection_count": len(left_bottom & right_bottom),
        "bottom_decile_union_count": len(bottom_union),
        "bottom_decile_overlap": len(left_bottom & right_bottom) / len(bottom_union) if bottom_union else None,
    }


def disagreement_table(
    merged: pd.DataFrame,
    left_label: str,
    right_label: str,
    left_value_column: str,
    right_value_column: str,
    left_percentile_column: str,
    right_percentile_column: str,
    limit: int = TOP_DISAGREEMENTS,
) -> pd.DataFrame:
    """Return the largest percentile disagreements for a comparison pair."""
    disagreements = merged.copy()
    disagreements["left_label"] = left_label
    disagreements["right_label"] = right_label
    disagreements["value_gap"] = disagreements[left_value_column] - disagreements[right_value_column]
    disagreements["percentile_gap"] = disagreements[left_percentile_column] - disagreements[right_percentile_column]
    disagreements["abs_percentile_gap"] = disagreements["percentile_gap"].abs()
    return disagreements.sort_values(
        ["abs_percentile_gap", "comparison_title"],
        ascending=[False, True],
    ).head(limit)


def save_scatter_plot(
    merged: pd.DataFrame,
    x_column: str,
    y_column: str,
    output_path: Path,
    title: str,
    x_label: str,
    y_label: str,
) -> None:
    """Save a simple z-score scatter plot."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.5, 6.0))
    ax.scatter(merged[x_column], merged[y_column], s=18, alpha=0.65, edgecolors="none")
    min_value = min(float(merged[x_column].min()), float(merged[y_column].min()))
    max_value = max(float(merged[x_column].max()), float(merged[y_column].max()))
    ax.plot([min_value, max_value], [min_value, max_value], linestyle="--", linewidth=1.0, color="#666666")
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=PLOT_DPI)
    plt.close(fig)


def metric_output_stem(metric_name: str) -> str:
    """Convert a metric label into a filesystem-safe stem."""
    return re.sub(r"[^a-z0-9]+", "_", metric_name.lower()).strip("_")
