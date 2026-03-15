"""
Score occupation AI exposure with the GABRIEL measurement toolkit.

This builds `data/exports/scores_gabriel.json` as an alternate occupation-level
score variant. The file preserves the repo's canonical industry metadata by
overlaying the new Gabriel scores onto the current `scores.json` records.

Usage:
    uv run python scripts/score_gabriel.py
    uv run python scripts/score_gabriel.py --model gpt-5.4 --n-runs 1
    uv run python scripts/score_gabriel.py --start 0 --end 25
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import gabriel
import pandas as pd
from dotenv import load_dotenv

from paths import (
    GABRIEL_RUNS_DIR,
    OCCUPATIONS_JSON,
    PAGES_DIR,
    ROOT_DIR,
    SCORES_GABRIEL_JSON,
    SCORES_JSON,
    resolve_project_path,
)
from score import ordered_scores


load_dotenv(ROOT_DIR / ".env")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_MODEL = "gpt-5.4"
DEFAULT_SAVE_DIR = GABRIEL_RUNS_DIR / "occupation_ai_exposure"
ATTRIBUTE_NAME = "gabriel_ai_exposure_100"
ATTRIBUTE_DESCRIPTION = (
    "How much advances in AI are likely to reshape this occupation over roughly "
    "the next decade, combining direct task automation with indirect "
    "productivity effects. High scores mean the occupation's core output is "
    "digital, information-processing, or highly legible to current and likely "
    "future AI systems. Low scores mean the occupation depends on physical "
    "presence, manual dexterity, embodied skill, or real-time in-person "
    "interaction in unpredictable environments."
)
RATING_SCALE = """\
Use integers from 0 to 100.

Interpret the scale as a finer-grained version of the repo's 0-10 occupation
AI exposure measure:

- 0-9: minimal exposure, equivalent to roughly 0-1 on the 0-10 scale
- 10-29: low exposure, equivalent to roughly 1-3
- 30-49: modest to moderate exposure, equivalent to roughly 3-5
- 50-69: moderate to high exposure, equivalent to roughly 5-7
- 70-89: high to very high exposure, equivalent to roughly 7-9
- 90-100: extreme exposure, equivalent to roughly 9-10

Use the full range. Occupations with almost entirely digital, on-computer work
should usually be high. Occupations whose core work is physical, embodied, or
requires live in-person interaction should usually be low.
"""
ADDITIONAL_INSTRUCTIONS = """\
You are evaluating an occupation described in a Bureau of Labor Statistics page.
Score the occupation overall, not just one task. Consider both:

1. direct effects, where AI performs tasks currently done by workers, and
2. indirect effects, where AI makes workers much more productive so fewer are
   needed for the same output.

A key signal is whether the occupation's core work product is fundamentally
digital and can be produced from a computer. Those occupations should generally
score high. Jobs centered on physical manipulation, field work, equipment,
hands-on care, or real-time embodied presence should generally score low.

Base the rating on the occupation description itself, not on prestige,
education, or wages.
"""


def load_occupations() -> list[dict]:
    """Load the canonical ordered occupation list."""
    with OCCUPATIONS_JSON.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_existing_scores(path: Path) -> dict[str, dict]:
    """Load an existing alternate score file if present."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return {row["slug"]: row for row in json.load(handle)}


def load_canonical_scores() -> dict[str, dict]:
    """Load canonical score rows so the Gabriel variant inherits metadata."""
    with SCORES_JSON.open(encoding="utf-8") as handle:
        return {row["slug"]: row for row in json.load(handle)}


def build_input_frame(occupations: list[dict]) -> pd.DataFrame:
    """Build the subset of occupations that have parsed markdown pages."""
    rows = []
    for occupation in occupations:
        slug = occupation["slug"]
        page_path = PAGES_DIR / f"{slug}.md"
        if not page_path.exists():
            continue
        rows.append(
            {
                "slug": slug,
                "title": occupation["title"],
                "page_markdown": page_path.read_text(encoding="utf-8"),
            }
        )
    return pd.DataFrame(rows)


async def run_gabriel_rating(frame: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    """Run Gabriel's `rate` helper and return the cleaned result table."""
    return await gabriel.rate(
        frame,
        column_name="page_markdown",
        attributes={ATTRIBUTE_NAME: ATTRIBUTE_DESCRIPTION},
        save_dir=str(resolve_project_path(args.save_dir)),
        file_name="scores_gabriel.csv",
        model=args.model,
        n_parallels=args.n_parallels,
        n_runs=args.n_runs,
        reset_files=args.reset_files,
        modality="text",
        reasoning_effort=args.reasoning_effort,
        rating_scale=RATING_SCALE,
        additional_instructions=ADDITIONAL_INSTRUCTIONS,
    )


def build_score_entry(
    row: pd.Series,
    canonical_by_slug: dict[str, dict],
    model: str,
    n_runs: int,
) -> dict:
    """Convert one Gabriel rating row into the repo's score-export shape."""
    slug = row["slug"]
    score_100 = float(row[ATTRIBUTE_NAME])
    entry = dict(canonical_by_slug.get(slug, {}))
    entry.update(
        {
            "slug": slug,
            "title": row["title"],
            "exposure": round(score_100 / 10.0, 4),
            "rationale": (
                "Generated with the GABRIEL rate workflow from the BLS "
                "occupation description. See `gabriel_score_100` for the raw "
                "0-100 rating."
            ),
            "gabriel_score_100": round(score_100, 4),
            "scoring_method": "gabriel_rate",
            "gabriel_model": model,
            "gabriel_n_runs": n_runs,
        }
    )
    return entry


def summarize_scores(scores: list[dict]) -> None:
    """Print a compact summary of the generated scores."""
    if not scores:
        print("No Gabriel scores were generated.")
        return

    exposures = [float(row["exposure"]) for row in scores if row.get("exposure") is not None]
    average = sum(exposures) / len(exposures)
    buckets: dict[int, int] = {}
    for value in exposures:
        bucket = int(round(value))
        buckets[bucket] = buckets.get(bucket, 0) + 1

    print(f"\nAverage Gabriel exposure across {len(exposures)} occupations: {average:.2f}")
    print("Rounded-score distribution:")
    for bucket in sorted(buckets):
        print(f"  {bucket}: {buckets[bucket]}")


def write_scores(path: Path, scores_by_slug: dict[str, dict], occupations: list[dict]) -> list[dict]:
    """Write ordered Gabriel scores to disk and return the ordered list."""
    ordered = ordered_scores(scores_by_slug, occupations)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(ordered, handle, indent=2)
    return ordered


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the Gabriel scoring workflow."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--n-runs", type=int, default=1)
    parser.add_argument("--n-parallels", type=int, default=24)
    parser.add_argument("--reasoning-effort", default="low")
    parser.add_argument(
        "--save-dir",
        default=str(DEFAULT_SAVE_DIR.relative_to(ROOT_DIR)),
        help="Directory for Gabriel raw responses and cleaned rating tables.",
    )
    parser.add_argument(
        "--output-file",
        default=str(SCORES_GABRIEL_JSON.relative_to(ROOT_DIR)),
        help="Path for the Gabriel score JSON export.",
    )
    parser.add_argument(
        "--reset-files",
        action="store_true",
        help="Force Gabriel to ignore cached raw-response files and rerun requests.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore any existing scores_gabriel.json rows when writing the output.",
    )
    return parser.parse_args()


async def main_async(args: argparse.Namespace) -> None:
    """Run the Gabriel scorer and save the alternate score export."""
    occupations = load_occupations()
    subset = occupations[args.start:args.end]
    frame = build_input_frame(subset)
    if frame.empty:
        raise FileNotFoundError("No occupation markdown files were found for the requested range.")

    print(f"Scoring {len(frame)} occupations with GABRIEL using {args.model}")
    print(f"Save dir: {resolve_project_path(args.save_dir)}")

    rated = await run_gabriel_rating(frame, args)
    if ATTRIBUTE_NAME not in rated.columns:
        raise ValueError(f"GABRIEL output is missing expected column: {ATTRIBUTE_NAME}")

    canonical_by_slug = load_canonical_scores()
    scores_by_slug = {} if args.force else load_existing_scores(resolve_project_path(args.output_file))
    for _, row in rated.iterrows():
        if pd.isna(row[ATTRIBUTE_NAME]):
            continue
        scores_by_slug[row["slug"]] = build_score_entry(row, canonical_by_slug, args.model, args.n_runs)

    ordered = write_scores(resolve_project_path(args.output_file), scores_by_slug, occupations)
    print(f"Wrote {len(ordered)} Gabriel score rows to {resolve_project_path(args.output_file)}")
    summarize_scores(ordered)


def main() -> None:
    """CLI entry point."""
    asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    main()
