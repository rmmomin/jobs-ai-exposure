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
  local/
  source/
    occupational_outlook_handbook.html
    html/
    comparison/
  pages/
  exports/
    comparisons/
```

- `scripts/` contains the runnable pipeline scripts.
- `data/source/` contains the raw BLS source material.
- `data/local/` is for optional local-only score variants such as `scores_gpt54.json`.
- `data/pages/` contains parsed markdown pages generated from the raw HTML.
- `data/exports/` contains the JSON and CSV outputs used for analysis.
- `data/source/comparison/` stores downloaded external benchmark datasets.
- `data/exports/comparisons/` is reserved for cleaned download inventories and later comparison outputs.

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

## Comparison data download

The first comparison step is just downloading the public benchmark files into
`data/source/comparison/`.

- `scripts/download_comparison_data.py` fetches the external CSV/XLSX sources listed in `README_codex.md`.
- It also writes a lightweight download manifest and workbook inventory into `data/exports/comparisons/cleaned/`.

## Benchmark comparisons

The comparison scripts benchmark the repo's occupation and industry exposure
measures against external datasets and write results under
`data/exports/comparisons/`:

- `cleaned/`: harmonized intermediate tables and crosswalk extracts
- `tables/`: overlap summaries, disagreement tables, and custom 4-digit industry outputs
- `figures/`: scatter plots for occupation- and industry-level comparisons

The default comparison flow is:

1. `scripts/download_comparison_data.py`
2. `scripts/compare_occupation_exposure.py`
3. `scripts/build_industry_exposure.py --scores-path ... --naics-level 4 --output-prefix ...` for any alternate score variant
4. `scripts/compare_industry_exposure.py`

If you have an optional local alternate score file at `data/local/scores_gpt54.json`,
you can build a compatible 4-digit industry exposure file for it and then include
it in the industry comparison step. `scripts/compare_industry_exposure.py`
automatically picks up any `custom_industry_exposure_*_4digit.csv` files from
`data/exports/comparisons/tables/`.

## Setup

```bash
uv sync
uv run playwright install chromium
```

The repository now requires Python 3.11 or newer for the comparison tooling.

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

# Download external comparison sources
uv run python scripts/download_comparison_data.py

# Compare occupation scores with external benchmarks
uv run python scripts/compare_occupation_exposure.py

# Build a custom 4-digit industry exposure output for an alternate score file
uv run python scripts/build_industry_exposure.py --scores-path data/local/scores_gpt54.json --naics-level 4 --output-prefix data/exports/comparisons/tables/custom_industry_exposure_local_gpt54_4digit

# Compare industry exposure with external 4-digit AIIE benchmarks
uv run python scripts/compare_industry_exposure.py
```
