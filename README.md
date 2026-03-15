# AI Exposure of the US Job Market

This repository started from code released by Andrej Karpathy on AI exposure at
the occupation level, and it was later forked from Josh Kale's repository. This
version removes the website, rebuilds the occupational exposures, computes
industry AI exposures from those occupation-level exposures, and organizes the
project into clearer script/source/export directories.

There is no live website in this repo. The focus here is the data pipeline, the
occupation-level scores, and the derived industry-level outputs.

## Repo layout

```text
README.md
pyproject.toml
scripts/
data/
  source/
    occupational_outlook_handbook.html
    html/
  pages/
  exports/
```

- `scripts/` contains the runnable pipeline scripts.
- `data/source/` contains the raw BLS source material.
- `data/pages/` contains parsed markdown pages generated from the raw HTML.
- `data/exports/` contains the JSON and CSV outputs used for analysis.

## Pipeline

1. `scripts/scrape.py` downloads raw BLS occupation pages into `data/source/html/`.
2. `scripts/process.py` converts raw HTML into markdown files in `data/pages/`.
3. `scripts/make_csv.py` extracts structured occupation fields into `data/exports/occupations.csv`.
4. `scripts/score.py` rebuilds occupation-level AI exposure scores into `data/exports/scores.json`.
5. `scripts/build_industry_exposure.py` computes industry AI exposure from the occupational exposures.

## Main data files

- `data/exports/occupations.json`: master occupation list with title, URL, category, and slug.
- `data/exports/occupations.csv`: structured occupation summary fields extracted from the BLS pages.
- `data/exports/scores_org.json`: archived original occupation-level score baseline.
- `data/exports/scores.json`: current rebuilt occupation-level AI exposure scores.
- `data/exports/industry_exposure.json`: employment-weighted AI exposure by NAICS code across all available levels.
- `data/exports/industry_exposure.csv`: flat CSV export of the mixed-level industry exposure dataset.
- `data/exports/industry_exposure_4digit.json`: employment-weighted AI exposure filtered to 4-digit NAICS codes.
- `data/exports/industry_exposure_4digit.csv`: flat CSV export of the 4-digit industry exposure dataset.

## Occupational AI exposure

Each occupation receives a single `AI Exposure` score from `0` to `10`. The
score is meant to capture how much AI is likely to reshape that occupation,
combining direct automation effects with indirect productivity effects.

`data/exports/scores.json` is the canonical rebuilt occupation dataset.
`data/exports/scores_org.json` preserves the earlier baseline for comparison.

## Industry AI exposure

Industry AI exposure is derived from the occupation scores. For a given NAICS
industry, the metric is:

```text
industry exposure =
  sum(occupation exposure * occupation jobs in industry)
  / sum(occupation jobs in industry)
```

Industry exposure is therefore not independently scored by an LLM. It is
computed from the occupation-level scores using occupation employment within
each industry as the weight.

The industry outputs are based on the occupations covered by this repository's
BLS-derived dataset, so `covered_employment_2024` reflects covered occupations
rather than a full census of every job in the industry.


## Comparison scripts

The repository includes a comparison/benchmarking layer for aligning internal Karpathy-style scores with external occupation and industry AI exposure datasets.

- `scripts/download_comparison_data.py` downloads comparison workbooks/CSVs into `data/source/comparison/`.
- `scripts/compare_occupation_exposure.py` harmonizes occupation-level metrics, writes cleaned datasets to `data/exports/comparisons/cleaned/`, summary/disagreement tables to `data/exports/comparisons/tables/`, and scatter plots to `data/exports/comparisons/figures/`.
- `scripts/compare_industry_exposure.py` compares 4-digit industry exposures and writes overlap tables/figures to `data/exports/comparisons/`.
- `scripts/build_industry_exposure.py` now accepts `--scores-path` for alternate score files while preserving defaults.

If present, `data/local/scores_gpt54.json` is treated as an optional additional internal variant.

```bash
uv run python scripts/download_comparison_data.py
uv run python scripts/compare_occupation_exposure.py
uv run python scripts/build_industry_exposure.py --scores-path data/local/scores_gpt54.json --naics-level 4 --output-prefix data/exports/comparisons/tables/custom_industry_exposure_local_gpt54_4digit
uv run python scripts/compare_industry_exposure.py
```

## Setup

```bash
uv sync
uv run playwright install chromium
```

Requires an OpenAI API key in `.env`:

```bash
OPENAI_API_KEY=your_key_here
```

## Usage

```bash
# Scrape BLS pages (results are cached in data/source/html/)
uv run python scripts/scrape.py

# Generate Markdown from HTML
uv run python scripts/process.py

# Generate CSV summary data
uv run python scripts/make_csv.py

# Rebuild occupation-level AI exposure scores
uv run python scripts/score.py

# Build mixed-level NAICS industry exposure outputs
uv run python scripts/build_industry_exposure.py

# Build 4-digit NAICS industry exposure outputs
uv run python scripts/build_industry_exposure.py --naics-level 4 --output-prefix data/exports/industry_exposure_4digit
```
