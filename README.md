# AI Exposure of the US Job Market

This repository started from code released by Andrej Karpathy on AI exposure at
the occupation level, and it was later forked from Josh Kale's repository. This
version removes the website, rebuilds the occupational exposures, and computes
industry AI exposures from those occupation-level exposures.

There is no live website in this repo anymore. The repository is now focused on
the data pipeline, the occupation-level scores, and the derived industry-level
outputs.

## What's here

The BLS Occupational Outlook Handbook covers **342 occupations** across the US
economy, with detailed descriptions of work, pay, training, and employment
projections. This repo scrapes that material, rebuilds occupation-level AI
exposure scores, and then aggregates those scores into industry-level AI
exposure measures.

## Data pipeline

1. **Scrape** (`scrape.py`) - Playwright downloads raw HTML for each BLS occupation page into `html/`.
2. **Parse** (`parse_detail.py`, `process.py`) - BeautifulSoup converts the raw HTML into cleaner structured content in `pages/`.
3. **Tabulate** (`make_csv.py`) - Structured occupation fields are extracted into `occupations.csv`, including each occupation's BLS industry-matrix URL.
4. **Score occupations** (`score.py`) - OpenAI scores each occupation's AI exposure and saves the latest canonical results into `scores.json`.
5. **Aggregate industries** (`build_industry_exposure.py`) - Industry AI exposure is computed from the occupational exposures using employment-weighted averages across NAICS industries.

## Key files

| File | Description |
|------|-------------|
| `occupations.json` | Master list of occupations with title, URL, category, and slug |
| `occupations.csv` | Structured occupation summary data from the BLS pages |
| `scores_org.json` | Archived original occupation-level score baseline |
| `scores.json` | Current rebuilt occupation-level AI exposure scores |
| `industry_exposure.json` | Employment-weighted AI exposure by NAICS code across all available NAICS levels |
| `industry_exposure.csv` | Flat CSV export of the mixed-level industry exposure dataset |
| `industry_exposure_4digit.json` | Employment-weighted AI exposure filtered to 4-digit NAICS codes |
| `industry_exposure_4digit.csv` | Flat CSV export of the 4-digit industry exposure dataset |
| `html/` | Raw BLS HTML pages (source of truth) |
| `pages/` | Parsed occupation pages used for occupation-level scoring |

## Occupational AI exposure

Each occupation receives a single **AI Exposure** score from 0 to 10. The score
is intended to capture how much AI is likely to reshape that occupation,
combining direct automation effects with indirect productivity effects.

The current `scores.json` file is the canonical rebuilt occupation dataset.
`scores_org.json` preserves the earlier baseline for comparison.

## Industry AI exposure

Industry AI exposure is derived from the occupation scores. For a given NAICS
industry, the metric is:

```text
industry exposure =
  sum(occupation exposure * occupation jobs in industry)
  / sum(occupation jobs in industry)
```

That means industry exposure is not independently scored by an LLM. It is
computed from the occupation-level scores using occupation employment within
each industry as the weight.

The industry outputs are based on the occupations covered by this repository's
BLS-derived dataset, so `covered_employment_2024` reflects covered occupations
rather than a full census of every job in the industry.

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
# Scrape BLS pages (results are cached in html/)
uv run python scrape.py

# Generate Markdown from HTML
uv run python process.py

# Generate CSV summary data
uv run python make_csv.py

# Rebuild occupation-level AI exposure scores
uv run python score.py

# Build mixed-level NAICS industry exposure outputs
uv run python build_industry_exposure.py

# Build 4-digit NAICS industry exposure outputs
uv run python build_industry_exposure.py --naics-level 4 --output-prefix industry_exposure_4digit
```
