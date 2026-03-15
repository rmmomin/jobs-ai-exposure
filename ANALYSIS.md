# Comparing AI Exposure Metrics in `jobs-ai-exposure`

This note explains what the repository’s internal and external AI exposure measures are actually measuring, how the current benchmark results compare, and why occupation-level and industry-level exposure often behave differently.

It is written against the repo’s current exported comparison outputs, especially:

- [`data/exports/comparisons/tables/occupation_comparison_summary.csv`](data/exports/comparisons/tables/occupation_comparison_summary.csv)
- [`data/exports/comparisons/tables/internal_variant_comparisons.csv`](data/exports/comparisons/tables/internal_variant_comparisons.csv)
- [`data/exports/comparisons/tables/industry_comparison_summary.csv`](data/exports/comparisons/tables/industry_comparison_summary.csv)
- [`data/exports/comparisons/tables/industry_internal_variant_comparisons.csv`](data/exports/comparisons/tables/industry_internal_variant_comparisons.csv)

## Executive summary

The repo’s canonical `repo_current` score is best interpreted as a **broad “AI will reshape this occupation” measure** rather than a narrow automation-risk score. It is built by scoring BLS Occupational Outlook Handbook pages with a GPT rubric that explicitly combines:

- **direct effects**: AI automates tasks currently done by workers
- **indirect effects**: AI makes each worker more productive, so fewer workers may be needed
- a strong emphasis on whether the occupation’s **core output is digital**

That design choice makes `repo_current` line up most closely with modern **GenAI / LLM exposure measures**, especially OpenAI’s *GPTs are GPTs* and Yale’s composite reference, while still remaining fairly close to Felten’s broader pre-GenAI AIOE framework.

The headline empirical pattern in the current exports is:

1. **Occupation-level agreement is high overall**, especially with OpenAI, Yale, Felten base, and Eisfeldt.
2. **Agreement is much weaker at the very top of the occupation distribution** for some benchmarks, even when overall correlations are high.
3. **Industry exposure is a derived staffing-mix measure**, not a directly scored measure in this repo.
4. **Industry-level agreement is moderately strong with Felten’s AIIE measures**, and stronger at the top of the distribution than at the bottom.
5. **Internal variants are very stable**: `repo_current`, `repo_original`, and `repo_gabriel` preserve most of the same ordering.

## What the internal measures are

### `repo_current`

- File: [`data/exports/scores.json`](data/exports/scores.json)
- Construction: BLS occupation pages are scored with `gpt-5.4` in [`scripts/score.py`](scripts/score.py)
- Scale: integer `0` to `10`
- Interpretation: “How much AI is likely to reshape this occupation?”

The rubric in `scripts/score.py` makes the repo’s stance unusually explicit. It asks the model to rate overall AI exposure from 0 to 10, combining direct automation and indirect productivity effects, and says that occupations whose work can be done “entirely from a home office on a computer” should generally be high exposure. In other words, this is a **digital-work / information-processing reshaping score**.

### `repo_original`

- File: [`data/exports/scores_org.json`](data/exports/scores_org.json)
- Construction: archived earlier baseline preserved for comparison
- Role in the repo: reference point for how much the rebuilt canonical score changed

This is useful as a stability check. The rebuilt score does move some occupations around, but not enough to overturn the broad ranking structure.

### `repo_gabriel`

- File: [`data/exports/scores_gabriel.json`](data/exports/scores_gabriel.json)
- Construction: alternate variant built with OpenAI’s [GABRIEL](https://github.com/openai/GABRIEL) toolkit in [`scripts/score_gabriel.py`](scripts/score_gabriel.py)
- Scale: raw 0–100 GABRIEL rating, then rescaled to the repo’s 0–10 convention
- Role in the repo: robustness check using a more explicitly measurement-oriented pipeline

Substantively, `repo_gabriel` is a little more conservative on average than `repo_current`, but it still produces very similar occupation and industry rankings.

## What the external benchmarks are measuring

The repo compares its internal scores to several **different kinds of exposure measures**. They are not interchangeable.

| Measure | Unit | Core construction | Best interpretation |
| --- | --- | --- | --- |
| **Felten base AIOE / AIIE** | Occupation / industry | Ability-based exposure using AI application–ability relatedness plus O*NET importance / prevalence weights | Broad AI exposure by occupational ability mix |
| **Felten language-modeling AIOE / AIIE** | Occupation / industry | Felten framework reweighted for language-modeling systems | Exposure to LLM-like language systems |
| **Felten image-generation AIOE / AIIE** | Occupation / industry | Felten framework reweighted for image-generation systems | Exposure to image-generation systems |
| **OpenAI GPTs-are-GPTs** | Occupation | O*NET task exposure to LLMs / LLM+ systems using human and GPT-4 task classifications | Potential LLM task-speedup exposure |
| **Microsoft Working with AI** | Occupation | Occupation applicability inferred from anonymized Bing Copilot conversations | Observed AI applicability in real-world usage |
| **Eisfeldt et al. GenAI** | Occupation (and firm) | Exposure of occupational tasks to GPT-4 capabilities, split into total / core / supplemental | GenAI exposure with substitution vs complementarity signal |
| **Webb** | Occupation (coarser grain) | Patent-text overlap with job-task text | Historical AI / automation exposure via patent-task similarity |
| **Yale PCA reference** | Occupation | Composite reference built from multiple exposure measures | A harmonized “consensus-ish” benchmark |

### A few conceptual differences matter a lot

#### 1. Broad AI vs GenAI / LLM exposure

Felten’s original AIOE was built to capture **AI exposure in a broad sense**, before the current LLM wave. By contrast, OpenAI’s, Microsoft’s, Eisfeldt’s, and the repo’s current rubric are much more tied to **GenAI-era capabilities**, especially language and digital content work.

#### 2. Capability-based vs usage-based

- `repo_current`, Felten, OpenAI, and Eisfeldt are fundamentally **capability / task / exposure** measures.
- Microsoft is closer to an **observed applicability** measure because it is based on actual Copilot conversations.

That means Microsoft should not be read as “the jobs AI will change most in the long run.” It is closer to “the jobs where today’s users are actually using AI in ways that map onto occupational work activities.”

#### 3. Exposure vs substitution vs augmentation

Most of these measures are intentionally **agnostic** about whether AI substitutes for or augments labor. The repo’s canonical score is slightly less agnostic than most, because its rubric explicitly includes productivity-driven reductions in headcount.

Eisfeldt’s core vs supplemental split is especially useful here:

- **core-task exposure** is closer to substitution / labor-saving pressure
- **supplemental-task exposure** is closer to augmentation / assistance

#### 4. Occupation text vs ability / task decomposition

The repo scores the **whole BLS occupation description**. Felten decomposes exposure through **abilities**. OpenAI and Eisfeldt decompose exposure through **tasks**. Microsoft infers applicability from **observed AI-assisted activities**. Webb uses **patent-task overlap**.

Those are related but meaningfully different objects.

## What the repo’s comparison scripts are doing

At the occupation level, [`scripts/compare_occupation_exposure.py`](scripts/compare_occupation_exposure.py) harmonizes multiple benchmark datasets and loads the following external metrics:

- Felten base AIOE
- Felten language-modeling AIOE
- Felten image-generation AIOE
- OpenAI GPTs-are-GPTs
- Microsoft AI applicability
- Eisfeldt GenAI total exposure
- Webb SOC4 AI score
- Yale PCA standardized reference

The script explicitly uses BLS crosswalks and handles comparison at **two different grains**:

- most measures are compared at the repo’s **occupation slug** grain
- Webb is compared at **SOC4** because that is the available public comparison grain

At the industry level, [`scripts/compare_industry_exposure.py`](scripts/compare_industry_exposure.py) normalizes both sides to **4-digit NAICS** and compares internal industry variants to:

- Felten base AIIE
- Felten language-modeling AIIE
- Felten image-generation AIIE

So the repo is already doing the most important harmonization work: aligning occupation codes, collapsing where needed, and comparing like with like as much as the public data allow.

## Occupation-level results: what matches `repo_current` best?

### Overall correlation ranking

For the current canonical score (`repo_current`), the strongest occupation-level matches are:

| External measure | Overlap | Pearson | Spearman | Top-decile overlap | Bottom-decile overlap |
| --- | ---: | ---: | ---: | ---: | ---: |
| OpenAI GPTs-are-GPTs | 341 | 0.885 | 0.893 | 0.415 | 0.519 |
| Yale PCA standardized reference | 334 | 0.878 | 0.888 | 0.273 | 0.540 |
| Felten base AIOE | 329 | 0.851 | 0.850 | 0.038 | 0.434 |
| Eisfeldt GenAI exposure | 329 | 0.834 | 0.851 | 0.350 | 0.407 |
| Felten language-modeling AIOE | 329 | 0.825 | 0.823 | 0.000 | 0.407 |
| Felten image-generation AIOE | 329 | 0.761 | 0.783 | 0.174 | 0.357 |
| Microsoft AI applicability | 341 | 0.661 | 0.680 | 0.184 | 0.339 |
| Webb SOC4 exposure | 84 | 0.002 | 0.066 | 0.000 | 0.000 |

### How to read that pattern

A few things stand out.

#### `repo_current` is closest to OpenAI and Yale

That is exactly what you would expect if the repo’s score is primarily picking up **GenAI-era digital knowledge work exposure**. OpenAI’s measure is explicitly about whether LLMs / LLM+ systems can speed up tasks substantially, while Yale’s PCA is a harmonized summary of multiple modern exposure metrics.

#### Felten is still close — but not the same

The Felten base measure correlates strongly with `repo_current`, but its **top-decile overlap is tiny** even when the overall correlation is high. That tells you the two measures broadly agree on which occupations are more exposed than others, but disagree sharply on **which occupations belong at the very frontier**.

This is one of the most important findings in the repo’s current exports: **high overall agreement does not mean agreement on the most exposed occupations**.

#### Microsoft is meaningfully lower

That makes sense conceptually. Microsoft is measuring **where AI is applicable in real observed use**, not a long-run “how much will this occupation be reshaped” score. The two are related, but they are not the same.

#### Webb is basically orthogonal here

Webb is the least comparable benchmark in this repo because it is:

- older and pre-GenAI
- patent-based rather than LLM / task / usage based
- only compared here at `SOC4` rather than the repo’s occupation slug grain

That does not make Webb “wrong”; it makes it a measure of a **different phenomenon**.

## Internal occupation variants are highly stable

The repo’s own internal variants are much closer to one another than most external benchmarks:

| Comparison | Overlap | Pearson | Spearman | Top-decile overlap | Bottom-decile overlap |
| --- | ---: | ---: | ---: | ---: | ---: |
| `repo_current` vs `repo_original` | 342 | 0.955 | 0.956 | 0.688 | 0.698 |
| `repo_current` vs `repo_gabriel` | 342 | 0.950 | 0.958 | 0.465 | 0.569 |
| `repo_gabriel` vs `repo_original` | 342 | 0.955 | 0.959 | 0.614 | 0.509 |

So the rebuilt canonical score is **not a wholesale rewrite of the ranking structure**. It is better read as a refined version of the same basic map.

The repo README also notes that `repo_gabriel` is somewhat more conservative on average:

- mean occupation exposure: **5.26 → 5.01**
- employment-weighted occupation mean: **5.05 → 4.72**

That is consistent with the Gabriel variant acting more like a disciplined measurement pipeline than a stronger “AI will upend this job” scorer.

## Industry exposure is a different object from occupation exposure

This repo’s industry score is **derived** from occupation scores. It is not independently scored by an LLM.

The formula in [`scripts/build_industry_exposure.py`](scripts/build_industry_exposure.py) is:

```text
industry exposure =
  sum(occupation exposure × occupation employment in industry)
  / sum(occupation employment in industry)
```

That means industry exposure is really a **staffing-mix projection** of occupation exposure.

This distinction matters a lot:

- an occupation score asks: **how exposed is this job’s task bundle?**
- an industry score asks: **how exposed is the weighted average job mix inside this industry?**

A high-exposure occupation does not automatically make an industry highly exposed if that occupation is a small share of industry employment. And an industry can look highly exposed without any single occupation being extreme if it employs **many moderately high-exposure occupations**.

There is also a crucial coverage caveat in this repo: `covered_employment_2024` only counts occupations covered by the repo’s BLS-derived occupation dataset. It is **not** a full census of every occupation in the industry.

## Industry-level results: what matches best?

For `repo_current` at the 4-digit NAICS level, the external matches are:

| External measure | Overlap | Pearson | Spearman | Top-decile overlap | Bottom-decile overlap |
| --- | ---: | ---: | ---: | ---: | ---: |
| Felten base AIIE | 172 | 0.745 | 0.670 | 0.722 | 0.214 |
| Felten image-generation AIIE | 172 | 0.742 | 0.680 | 0.524 | 0.259 |
| Felten language-modeling AIIE | 172 | 0.699 | 0.619 | 0.765 | 0.241 |

And the internal industry variants are even closer:

| Comparison | Overlap | Pearson | Spearman | Top-decile overlap | Bottom-decile overlap |
| --- | ---: | ---: | ---: | ---: | ---: |
| `repo_current` vs `repo_original` | 186 | 0.987 | 0.982 | 0.810 | 0.565 |
| `repo_current` vs `repo_gabriel` | 186 | 0.975 | 0.964 | 0.900 | 0.636 |

### Why industry patterns look different from occupation patterns

At the industry level, agreement at the **top decile** is much stronger than at the bottom. That is almost the opposite of the occupation-level pattern for some external measures.

A plausible explanation is that industry aggregation **smooths away some occupation-level disagreement**. Once you average across many occupations, information-heavy industries tend to float to the top across most methods, even if the methods disagree about which exact occupations are most exposed.

Low-exposure industries are less stable for at least two reasons:

1. they are more sensitive to **coverage gaps** in the occupation dataset
2. they often contain more heterogeneous mixes of physical, administrative, and customer-facing jobs

So the industry score is useful, but it should be treated as a **derived, partially coverage-limited ranking** rather than a ground-truth industry judgment.

## What each measure is “really asking”

This is the most practical way to think about the comparisons.

- **`repo_current`** asks: *How much will AI reshape this occupation, especially if its output is digital and legible to AI systems?*
- **`repo_original`** asks: *What did the earlier Karpathy-style baseline say about the same occupation set?*
- **`repo_gabriel`** asks: *What happens if we score the same BLS occupation descriptions with a measurement-oriented GPT workflow?*
- **Felten base** asks: *How much does this occupation rely on abilities that are related to AI applications?*
- **Felten LM / image** ask: *How exposed is this occupation specifically to language-modeling or image-generation capabilities?*
- **OpenAI GPTs-are-GPTs** asks: *How much of this occupation’s task set could LLMs or LLM+ systems speed up substantially?*
- **Microsoft** asks: *How applicable is AI to the kinds of work people actually bring to a deployed assistant system?*
- **Eisfeldt** asks: *How much of this occupation’s task bundle is exposed to GPT-4, and are those exposed tasks core or supplemental?*
- **Webb** asks: *How similar are this occupation’s tasks to the tasks described in AI-related patents?*
- **Yale PCA** asks: *What is the common signal across several different exposure measures?*

## What this repo is best at

This repo is especially useful for three things.

### 1. Comparing different concepts of AI exposure in one place

The most valuable contribution is not any single score. It is the fact that the repo puts:

- rebuilt Karpathy-style scores
- an alternate GABRIEL variant
- modern GenAI benchmarks
- Felten-style occupation and industry measures
- harmonized occupation and industry comparison tables

into one reproducible pipeline.

### 2. Separating occupation-level and industry-level claims

The repo is careful about the difference between:

- **occupation exposure** as a direct score or benchmarked measure
- **industry exposure** as an aggregation over occupational employment shares

That distinction often gets blurred in public discussions.

### 3. Showing where agreement breaks down

The current exports show that many measures agree on the broad middle of the ranking, but much less on the **most exposed jobs**. That is exactly the part of the distribution people usually care about most.

## Main caveats

1. **Exposure is not the same as job loss.** Most of these measures are about where AI matters, not whether employment falls.
2. **Crosswalks matter.** Some measures start from different occupational coding systems and need harmonization.
3. **Webb is much less apples-to-apples than the GenAI-era measures.**
4. **Industry results depend on occupation coverage.** The repo already flags this through `covered_employment_2024`.
5. **The repo’s canonical score bakes in a substantive prior:** digital, computer-based occupations are inherently more exposed.

That prior is reasonable, but it is not neutral. It helps explain why the repo is so close to OpenAI and Yale.

## Bottom line

The current canonical measure in `jobs-ai-exposure` is best understood as a **broad, digital-work-centered GenAI exposure index**. It is not the same as “probability of automation,” and it is not trying to be.

Its strongest occupation-level peers are:

- **OpenAI GPTs-are-GPTs**
- **Yale’s PCA reference**
- **Felten base AIOE**
- **Eisfeldt GenAI exposure**

Its industry-level outputs are useful, but they should be interpreted as **employment-weighted occupational exposure**, not as independently scored industry measures.

If you want one sentence that captures the repo’s contribution, it is this:

> The repo shows that many AI exposure measures tell a similar broad story, but they diverge meaningfully on what “exposure” means, which occupations sit at the frontier, and how occupational exposure should be translated into industry exposure.

## Sources and further reading

### Repo-internal

- [`README.md`](README.md)
- [`scripts/score.py`](scripts/score.py)
- [`scripts/score_gabriel.py`](scripts/score_gabriel.py)
- [`scripts/build_industry_exposure.py`](scripts/build_industry_exposure.py)
- [`scripts/compare_occupation_exposure.py`](scripts/compare_occupation_exposure.py)
- [`scripts/compare_industry_exposure.py`](scripts/compare_industry_exposure.py)

### External benchmark sources

- Felten, Raj, and Seamans (2021), *Occupational, Industry, and Geographic Exposure to Artificial Intelligence: A Novel Dataset and Its Potential Uses*  
  - Paper: https://doi.org/10.1002/smj.3286  
  - Data repo: https://github.com/AIOE-Data/AIOE
- Felten, Raj, and Seamans (2023), *How will Language Modelers like ChatGPT Affect Occupations and Industries?*  
  - Paper: https://arxiv.org/abs/2303.01157
- OpenAI / Eloundou et al. (2023/2024), *GPTs are GPTs*  
  - Paper page: https://openai.com/index/gpts-are-gpts/  
  - Paper: https://arxiv.org/abs/2303.10130  
  - Data repo: https://github.com/openai/GPTs-are-GPTs
- Microsoft Research (2025), *Working with AI: Measuring the Applicability of Generative AI to Occupations*  
  - Paper page: https://www.microsoft.com/en-us/research/publication/working-with-ai-measuring-the-occupational-implications-of-generative-ai/  
  - Paper: https://arxiv.org/abs/2507.07935  
  - Data repo: https://github.com/microsoft/working-with-ai
- Eisfeldt, Schubert, Taska, and Zhang, *Generative AI and Firm Values*  
  - Data repo: https://artificialminushuman.com/  
  - Working paper: https://www.nber.org/papers/w31222
- Webb (2020), *The Impact of Artificial Intelligence on the Labor Market*  
  - PDF: https://www.michaelwebb.co/webb_ai.pdf
- The Budget Lab at Yale (2026), *Labor Market AI Exposure: What Do We Know?*  
  - Analysis page: https://budgetlab.yale.edu/research/labor-market-ai-exposure-what-do-we-know
- OpenAI GABRIEL toolkit  
  - Repo: https://github.com/openai/GABRIEL
