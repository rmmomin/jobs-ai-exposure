# Codex spec for `rmmomin/jobs-ai-exposure`

This spec assumes you are working **inside the existing `rmmomin/jobs-ai-exposure` repository**.
Do **not** create a brand-new project layout from scratch.
The repo already contains the core Karpathy-style pipeline, the rebuilt occupation scores, and derived industry exposure exports. The new work should extend that repo with a **comparison / benchmarking layer**.

## 1) Respect the current repo

The current repo already has:

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

The existing pipeline is:

1. `scripts/scrape.py`
2. `scripts/process.py`
3. `scripts/make_csv.py`
4. `scripts/score.py`
5. `scripts/build_industry_exposure.py`

The current published exports are:

- `data/exports/occupations.json`
- `data/exports/occupations.csv`
- `data/exports/scores_org.json`
- `data/exports/scores.json`
- `data/exports/industry_exposure.json`
- `data/exports/industry_exposure.csv`
- `data/exports/industry_exposure_4digit.json`
- `data/exports/industry_exposure_4digit.csv`

Use the repo's existing `uv` / `pyproject.toml` workflow. Do **not** replace it with a separate `requirements.txt`-driven layout unless there is a very strong reason.

## 2) Goal

Add code that can:

1. download public comparison datasets,
2. load the repo's existing internal score exports,
3. optionally load a local alternate score file,
4. compare occupation-level Karpathy-style scores with alternative AI exposure measures,
5. compare industry-level Karpathy-style exposure with alternative industry measures, and
6. save clean outputs back into the repo using the repo's existing directory conventions.

## 3) Internal inputs to use

Prefer local repo files first.

### Current canonical repo score inputs

- `data/exports/scores.json` — current rebuilt canonical occupation dataset
- `data/exports/scores_org.json` — archived original baseline
- `data/exports/occupations.csv` — structured occupation metadata
- `data/exports/industry_exposure.csv` — mixed-level NAICS industry exposure output
- `data/exports/industry_exposure_4digit.csv` — 4-digit NAICS industry exposure output

### Optional local override

- `data/local/scores_gpt54.json`

Treat `data/local/scores_gpt54.json` as **optional**. If it exists, compare it alongside the repo's own current and original scores. If it does not exist, the comparison pipeline should still run using the repo's built-in exports.

## 4) Internal schemas to rely on

### `data/exports/occupations.csv`

The current file includes these useful columns:

- `title`
- `category`
- `slug`
- `soc_code`
- `median_pay_annual`
- `median_pay_hourly`
- `entry_education`
- `work_experience`
- `training`
- `num_jobs_2024`
- `projected_employment_2034`
- `outlook_pct`
- `outlook_desc`
- `employment_change`
- `employment_by_industry_url`
- `url`

### `data/exports/scores.json`

The current canonical rebuilt score file includes, per occupation:

- `slug`
- `title`
- `exposure`
- `rationale`
- `soc_code`
- `industry_matrix_url`
- `url`
- `industries` (nested list)
- `naics_industry_codes`

Each item in `industries` includes at least:

- `title`
- `naics_code`
- `industry_type`
- `employment_2024`
- `occupation_share_2024_pct`

This nested `industries` structure is important. It means custom industry aggregations for alternate score files can be built by merging alternate occupation scores onto the repo's canonical `scores.json` by `slug`, then exploding `industries`.

### `data/exports/scores_org.json`

The archived baseline file currently has the simpler schema:

- `slug`
- `title`
- `exposure`
- `rationale`

### `data/exports/industry_exposure_4digit.csv`

The current 4-digit industry export includes:

- `naics_code`
- `title`
- `industry_type`
- `naics_level`
- `is_sector`
- `covered_employment_2024`
- `occupation_count`
- `weighted_exposure`

Any new custom industry aggregation output should preserve a compatible schema where possible.

## 5) New directories to add

Keep the existing repo structure. Add only what is needed.

Recommended additions:

```text
data/
  local/
  source/
    comparison/
  exports/
    comparisons/
      cleaned/
      tables/
      figures/
```

Use:

- `data/source/comparison/` for downloaded external comparison datasets
- `data/exports/comparisons/cleaned/` for harmonized intermediate comparison-ready tables
- `data/exports/comparisons/tables/` for final CSV tables
- `data/exports/comparisons/figures/` for scatter plots and rank-comparison charts

## 6) External datasets to download

Write code to download these public files into `data/source/comparison/`.

### Felten / Raj / Seamans

- `https://raw.githubusercontent.com/AIOE-Data/AIOE/main/AIOE_DataAppendix.xlsx`
- `https://raw.githubusercontent.com/AIOE-Data/AIOE/main/Language%20Modeling%20AIOE%20and%20AIIE.xlsx`
- `https://raw.githubusercontent.com/AIOE-Data/AIOE/main/Image%20Generation%20AIOE%20and%20AIIE.xlsx`

### OpenAI GPTs are GPTs

- `https://raw.githubusercontent.com/openai/GPTs-are-GPTs/main/data/occ_level.csv`

### Microsoft Working with AI

- `https://raw.githubusercontent.com/microsoft/working-with-ai/main/ai_applicability_scores.csv`

### Eisfeldt et al.

- `https://artificialminushuman.com/data/genaiexp_estz_occscores.csv`
- `https://artificialminushuman.com/data/genaiexp_estz_firmscores.csv`

### Webb public mirror

- `https://raw.githubusercontent.com/nandomp/AIlabour/master/labour%20data/scores_webb2020/exposure_by_soc4.xlsx`

### Yale comparison workbook

- `https://budgetlab.yale.edu/sites/default/files/2026-02/TBL-Data-AI-Exposure-What-do-we-know-202602-Updated.xlsx`

### Official crosswalk/helper files

- `https://www.bls.gov/soc/2018/soc_2010_to_2018_crosswalk.xlsx`
- `https://www.bls.gov/emp/classifications-crosswalks/nem-onet-to-soc-crosswalk.xlsx`
- `https://www.bls.gov/emp/classifications-crosswalks/nem-occupational-coverage.xlsx`

Do **not** redownload the repo's own internal exports from GitHub unless you are explicitly building a fallback mode. Use the local repo files first.

## 7) What code to add or change

Follow the repo's existing `scripts/` convention.

### Add these scripts

- `scripts/download_comparison_data.py`
- `scripts/compare_occupation_exposure.py`
- `scripts/compare_industry_exposure.py`

### Optional shared helper module

If needed, add one lightweight helper module such as:

- `scripts/comparison_utils.py`

Keep it small and reusable.

### Extend an existing script

Modify `scripts/build_industry_exposure.py` to support an optional score input override:

- `--scores-path` with default `data/exports/scores.json`
- optionally `--occupations-csv` with default `data/exports/occupations.csv`

The default behavior must stay backward-compatible with the repo's current workflow.

## 8) Package / dependency requirements

Update `pyproject.toml` only if needed.

Prefer these packages:

- `pandas`
- `numpy`
- `requests`
- `openpyxl`
- `matplotlib`
- `scipy`

If the repo already includes some of them, do not duplicate unnecessary config.

## 9) Build internal score variants

Implement loaders that produce three internal score variants when available:

1. `repo_current` from `data/exports/scores.json`
2. `repo_original` from `data/exports/scores_org.json`
3. `local_gpt54` from `data/local/scores_gpt54.json` if present

For each variant, build a normalized occupation-level table with at least:

- `variant`
- `slug`
- `title`
- `karpathy_score`
- `rationale`
- `soc_code`
- `category`
- `num_jobs_2024`
- `url`

### Merge rules

- `repo_current`: use `data/exports/scores.json` as the main source, merge in missing metadata from `occupations.csv` on `slug`
- `repo_original`: use `scores_org.json`, merge in `soc_code`, `category`, `num_jobs_2024`, and URLs from `occupations.csv`, and merge in `industries` from current `scores.json` on `slug`
- `local_gpt54`: use `data/local/scores_gpt54.json`, merge in `soc_code`, `category`, `num_jobs_2024`, URLs from `occupations.csv`, and merge in `industries` from current `scores.json` on `slug`

Rename `exposure` to `karpathy_score` in all normalized comparison tables.

## 10) SOC and NAICS normalization

Implement robust helpers for:

- normalizing SOC codes like `15-1252.00` to `15-1252`
- deriving SOC4 and major group codes
- normalizing NAICS codes to strings while preserving leading/trailing zeros where meaningful
- detecting malformed occupation codes gracefully

Suggested helper functions:

- `norm_soc(code)`
- `soc4(code)`
- `soc_major(code)`
- `norm_naics(code)`
- `naics_level(code)`

## 11) Occupation-level comparison logic

`compare_occupation_exposure.py` should:

1. load all available internal Karpathy variants,
2. load and harmonize all external occupation-level metrics,
3. compare each internal variant against each external metric on overlapping occupations,
4. compare internal variants against each other, especially:
   - `repo_current` vs `repo_original`
   - `repo_current` vs `local_gpt54` if present
   - `repo_original` vs `local_gpt54` if present

### External occupation-level metrics to harmonize

- Felten base AIOE
- Felten language-modeling occupation exposure
- Felten image-generation occupation exposure
- OpenAI GPTs-are-GPTs occupation exposure
- Microsoft AI applicability
- Eisfeldt occupation GenAI exposure
- Webb SOC4 exposure
- Yale workbook as a validation/reference file, not necessarily as the primary source of truth

### Harmonization rules

- inspect workbook sheets dynamically instead of hardcoding fragile assumptions
- preserve raw source columns where useful for debugging
- create explicit cleaned tables with source labels
- compute raw, z-score, and percentile versions for each metric

### Comparison outputs

For each variant/metric pair, compute at least:

- overlap count
- Pearson correlation on z-scores
- Spearman correlation on percentile ranks
- top-decile overlap
- bottom-decile overlap
- disagreement tables for the largest rank differences

Save outputs such as:

- `data/exports/comparisons/cleaned/occupation_metric_<name>.csv`
- `data/exports/comparisons/tables/occupation_comparison_summary.csv`
- `data/exports/comparisons/tables/occupation_disagreements_<variant>_<metric>.csv`
- `data/exports/comparisons/figures/occupation_scatter_<variant>_<metric>.png`
- `data/exports/comparisons/tables/internal_variant_comparisons.csv`

## 12) Industry aggregation logic

There are two distinct industry use cases.

### A) Use existing repo output for the canonical current score variant

For `repo_current`, prefer the repo's existing:

- `data/exports/industry_exposure.csv`
- `data/exports/industry_exposure_4digit.csv`

Do not recompute those unless you need to validate or refresh them.

### B) Recompute industry exposure for alternate score variants

For `repo_original` and `local_gpt54`, build custom industry outputs using the `industries` lists from the canonical current `scores.json`.

Algorithm:

1. load the alternate score variant by `slug`
2. merge in `industries` from current `scores.json` by `slug`
3. explode `industries`
4. extract per-row:
   - `naics_code`
   - `title`
   - `industry_type`
   - `employment_2024`
5. compute industry weighted exposure as:

```text
weighted_exposure = sum(karpathy_score * employment_2024) / sum(employment_2024)
```

6. compute and keep:
   - `covered_employment_2024`
   - `occupation_count`
   - `weighted_exposure`
   - `naics_level`
   - `is_sector`

For 4-digit comparison work, filter to 4-digit NAICS output and save a CSV compatible with the existing repo schema.

### Important

Because the repo README explicitly states that industry exposure is derived from occupation scores rather than independently scored, the custom industry aggregation should mirror that same formula and preserve backward compatibility with the repo's published schema.

## 13) Industry comparison logic

`compare_industry_exposure.py` should:

1. load the repo's canonical 4-digit industry exposure output,
2. load custom 4-digit industry outputs for other internal variants when available,
3. load external industry metrics,
4. compare each internal industry variant to external industry measures.

### External industry metrics to compare against

- Felten base AIIE
- Felten language-modeling AIIE
- Felten image-generation AIIE

Prefer 4-digit NAICS comparisons.

### Outputs

Save at least:

- `data/exports/comparisons/tables/industry_comparison_summary.csv`
- `data/exports/comparisons/tables/industry_overlap_<variant>_<metric>.csv`
- `data/exports/comparisons/tables/custom_industry_exposure_<variant>_4digit.csv`
- `data/exports/comparisons/figures/industry_scatter_<variant>_<metric>.png`

## 14) CLI behavior

Keep the scripts easy to run with `uv run`.

Recommended usage examples:

```bash
uv run python scripts/download_comparison_data.py
uv run python scripts/compare_occupation_exposure.py
uv run python scripts/build_industry_exposure.py --naics-level 4 --output-prefix data/exports/industry_exposure_4digit
uv run python scripts/build_industry_exposure.py --scores-path data/local/scores_gpt54.json --naics-level 4 --output-prefix data/exports/comparisons/tables/custom_industry_exposure_local_gpt54_4digit
uv run python scripts/compare_industry_exposure.py
```

The compare scripts should accept reasonable flags such as:

- `--variant`
- `--force`
- `--skip-download`
- `--output-dir`

## 15) README updates

Update the repo's top-level `README.md` with a short section describing the new comparison scripts:

- what they do
- where they write outputs
- how to run them
- how to use `data/local/scores_gpt54.json` for an alternate score variant

Do **not** rewrite the entire repo README. Just extend it cleanly.

## 16) Constraints

- Keep backward compatibility with the existing repo pipeline.
- Do not break the current `uv run python scripts/score.py` or `build_industry_exposure.py` workflow.
- Prefer local repo exports over external refetching.
- Keep the code modular and small.
- Log assumptions clearly.
- Fail loudly on missing critical files, but treat `data/local/scores_gpt54.json` as optional.

## 17) Deliverables

When Codex is done, it should summarize:

1. files created or modified,
2. new commands added,
3. assumptions made about workbook schemas or crosswalks,
4. any manual validation steps still recommended.
