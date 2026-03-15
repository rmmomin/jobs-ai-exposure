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
    comparison/
  pages/
  exports/
    comparisons/
```

- `scripts/` contains the runnable pipeline scripts.
- `data/source/` contains the raw BLS source material.
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

If you want to compare another score variant, first build a compatible 4-digit
industry exposure file with `scripts/build_industry_exposure.py --scores-path`
and save it under `data/exports/comparisons/tables/`. Then
`scripts/compare_industry_exposure.py` will automatically pick up any
`custom_industry_exposure_*_4digit.csv` files from that directory.

## Current benchmark results

Using the current comparison exports in `data/exports/comparisons/`, the
rebuilt `repo_current` occupation scores are closest to OpenAI GPTs-are-GPTs
and the Yale reference bundle. At the industry level, the closest match is
Felten base AIIE by Pearson correlation and Felten language-modeling AIIE by
top-decile overlap.

### Occupation-level comparison (`repo_current`)

| External measure | Overlap | Pearson | Spearman |
| --- | ---: | ---: | ---: |
| OpenAI GPTs-are-GPTs | 341 | 0.885 | 0.893 |
| Yale PCA standardized reference | 334 | 0.878 | 0.888 |
| Felten base AIOE | 329 | 0.851 | 0.850 |
| Eisfeldt GenAI exposure | 329 | 0.834 | 0.851 |
| Felten language-modeling AIOE | 329 | 0.825 | 0.823 |
| Felten image-generation AIOE | 329 | 0.761 | 0.783 |
| Microsoft AI applicability | 341 | 0.661 | 0.680 |
| Webb SOC4 exposure | 84 | 0.002 | 0.066 |

`repo_current` and `repo_original` are also very close internally at the
occupation level: overlap `342`, Pearson `0.955`, Spearman `0.956`.

### Industry-level comparison (`repo_current`, 4-digit NAICS)

| External measure | Overlap | Pearson | Spearman |
| --- | ---: | ---: | ---: |
| Felten base AIIE | 172 | 0.745 | 0.670 |
| Felten image-generation AIIE | 172 | 0.742 | 0.680 |
| Felten language-modeling AIIE | 172 | 0.699 | 0.619 |

The internal industry variants are even closer to each other than the external
benchmarks: `repo_current` vs `repo_original` has overlap `186`, Pearson
`0.987`, and Spearman `0.982`.

These summary numbers come from:

- `data/exports/comparisons/tables/occupation_comparison_summary.csv`
- `data/exports/comparisons/tables/internal_variant_comparisons.csv`
- `data/exports/comparisons/tables/industry_comparison_summary.csv`

One important caveat: Webb is compared at `SOC4` grain rather than the repo's
occupation `slug` grain, and the industry comparisons normalize both sides to
4-digit NAICS.

## Bibliography

The repo's external benchmark and crosswalk work draws on the following primary
sources:

- Andrej Karpathy, original occupation-exposure code release that this repo extends: [karpathy/AI-jobs](https://github.com/karpathy/AI-jobs)
- BLS Occupational Outlook Handbook, the core occupation source used by this repo: [U.S. Bureau of Labor Statistics](https://www.bls.gov/ooh/)
- BLS crosswalks used for comparison harmonization: [2010 to 2018 SOC crosswalk](https://www.bls.gov/soc/2018/soc_2010_to_2018_crosswalk.xlsx), [NEM O*NET to SOC crosswalk](https://www.bls.gov/emp/classifications-crosswalks/nem-onet-to-soc-crosswalk.xlsx), [NEM occupational coverage](https://www.bls.gov/emp/classifications-crosswalks/nem-occupational-coverage.xlsx)
- Felten, Edward, Manav Raj, and Robert Seamans (2021), "Occupational, Industry, and Geographic Exposure to Artificial Intelligence: A Novel Dataset and Its Potential Uses," *Strategic Management Journal*: [paper](https://doi.org/10.1002/smj.3286), [data repository](https://github.com/AIOE-Data/AIOE)
- Eloundou, Tyna, Sam Manning, Pamela Mishkin, and Daniel Rock (2023), "GPTs are GPTs: An early look at the labor market impact potential of large language models": [paper page](https://openai.com/index/gpts-are-gpts/), [paper](https://arxiv.org/abs/2303.10130), [data repository](https://github.com/openai/GPTs-are-GPTs)
- Tomlinson, Kiran, Sonia Jaffe, Will Wang, Scott Counts, and Siddharth Suri (2025), "Working with AI: Measuring the Applicability of Generative AI to Occupations": [paper](https://arxiv.org/abs/2507.07935), [data repository](https://github.com/microsoft/working-with-ai)
- Eisfeldt, Andrea L., Gregor Schubert, Bledi Taska, and Miao Ben Zhang (2026 forthcoming), "Generative AI and Firm Values": [NBER working paper](https://www.nber.org/papers/w31222), [data repository](https://artificialminushuman.com/)
- Webb, Michael (2020), "The Impact of Artificial Intelligence on the Labor Market": [paper PDF](https://www.michaelwebb.co/webb_ai.pdf)
- The Budget Lab at Yale (2026), "Labor Market AI Exposure: What Do We Know?": [analysis page](https://budgetlab.yale.edu/research/labor-market-ai-exposure-what-do-we-know)

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
uv run python scripts/build_industry_exposure.py --scores-path data/exports/scores_org.json --naics-level 4 --output-prefix data/exports/comparisons/tables/custom_industry_exposure_repo_original_4digit

# Compare industry exposure with external 4-digit AIIE benchmarks
uv run python scripts/compare_industry_exposure.py
```
