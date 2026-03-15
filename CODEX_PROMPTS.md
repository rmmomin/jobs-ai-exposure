# Codex prompt bundle for `rmmomin/jobs-ai-exposure`

Use these prompts in order. They assume the repo already exists and should be **extended**, not rebuilt.

## Prompt 1: full extension pass

```text
Read README_codex.md and extend the existing `jobs-ai-exposure` repository exactly as specified.

Important constraints:
- Work inside the current repo layout.
- Keep the existing `scripts/` + `data/source/` + `data/pages/` + `data/exports/` structure.
- Keep the existing `uv` / `pyproject.toml` workflow.
- Do not create a separate `src/` project layout.
- Do not replace the repo's current pipeline.

Requirements:
- Add the comparison download script.
- Add occupation-level comparison scripts.
- Add industry-level comparison scripts.
- Extend `scripts/build_industry_exposure.py` with an optional `--scores-path` override while preserving current defaults.
- Use local repo exports first.
- Treat `data/local/scores_gpt54.json` as optional.
- Save comparison outputs under `data/exports/comparisons/`.
- Update the top-level README with a short section for the comparison scripts.

When finished, summarize:
1. files created or modified,
2. commands to run,
3. assumptions made,
4. any workbook/crosswalk ambiguities that still need manual checking.
```

## Prompt 2: safer first pass

```text
Read README_codex.md and only do the first pass.

Tasks:
- create any missing comparison directories,
- implement `scripts/download_comparison_data.py`,
- add any minimal shared helper module needed for loading paths/config,
- update `pyproject.toml` only if additional dependencies are required,
- add a short README section describing the comparison data download step.

Do not implement the comparison logic yet.

When finished, summarize files changed and any assumptions.
```

## Prompt 3: occupation comparison layer

```text
Continue from the existing repo.

Read README_codex.md and implement the occupation-level comparison layer.

Tasks:
- load `data/exports/scores.json`, `data/exports/scores_org.json`, and `data/exports/occupations.csv`,
- load `data/local/scores_gpt54.json` if present,
- normalize internal score variants,
- load and harmonize the external occupation-level metrics,
- compute overlap tables, correlations, decile overlap, and disagreement tables,
- write cleaned intermediate tables and final outputs to `data/exports/comparisons/`.

Important:
- inspect workbook sheets dynamically,
- preserve raw source columns where useful,
- keep Webb handling at the appropriate SOC4 grain,
- write plots to `data/exports/comparisons/figures/`.

When finished, summarize which metrics were successfully loaded and any unresolved schema issues.
```

## Prompt 4: extend industry builder for alternate score files

```text
Continue from the existing repo.

Read README_codex.md and extend `scripts/build_industry_exposure.py` so it can build industry exposure from an alternate occupation score file.

Requirements:
- add `--scores-path` with default `data/exports/scores.json`,
- preserve backward compatibility with the existing behavior,
- support alternate score files like `data/local/scores_gpt54.json` by merging them onto the canonical `scores.json` industry lists using `slug`,
- preserve output schema compatibility with the repo's current `industry_exposure*.csv` files.

When finished, summarize the CLI changes and any backward-compatibility notes.
```

## Prompt 5: industry comparison layer

```text
Continue from the existing repo.

Read README_codex.md and implement `scripts/compare_industry_exposure.py`.

Requirements:
- use `data/exports/industry_exposure_4digit.csv` for the canonical repo-current variant,
- load custom 4-digit industry outputs for alternate variants when present,
- load Felten base AIIE, language-modeling AIIE, and image-generation AIIE,
- compute overlap tables, correlations, and disagreement tables,
- save tables and figures under `data/exports/comparisons/`.

When finished, summarize:
1. what industry variants were compared,
2. output files created,
3. any NAICS harmonization caveats.
```

## Prompt 6: cleanup and audit

```text
Audit the repository against README_codex.md and fix gaps.

Tasks:
- verify the new scripts run from the repo root with `uv run python ...`,
- verify output paths are consistent,
- simplify duplicated code,
- improve docstrings and comments,
- make sure the top-level README instructions are correct,
- note any remaining manual validation steps.

Then provide a concise repo-audit summary.
```
