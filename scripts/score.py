"""
Score each occupation's AI exposure using the OpenAI Responses API.

Reads Markdown descriptions from `data/pages/`, sends each to an OpenAI model
with a scoring rubric, and caches results in `data/exports/scores.json`.

Usage:
    uv run python scripts/score.py
    uv run python scripts/score.py --model gpt-5.4
    uv run python scripts/score.py --start 0 --end 10
"""

import argparse
import csv
import json
import os
import re
import time

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from paths import OCCUPATIONS_CSV, OCCUPATIONS_JSON, PAGES_DIR, ROOT_DIR, SCORES_JSON, resolve_project_path

load_dotenv(ROOT_DIR / ".env")

DEFAULT_MODEL = "gpt-5.4"
API_URL = "https://api.openai.com/v1/responses"
NUMERIC_CODE_RE = re.compile(r"^\d+$")
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "exposure": {
            "type": "integer",
            "minimum": 0,
            "maximum": 10,
        },
        "rationale": {
            "type": "string",
            "minLength": 1,
        },
    },
    "required": ["exposure", "rationale"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """\
You are an expert analyst evaluating how exposed different occupations are to AI.
You will be given a detailed description of an occupation from the Bureau of
Labor Statistics.

Rate the occupation's overall AI Exposure on a scale from 0 to 10.

AI Exposure measures how much AI will reshape this occupation. Consider both
direct effects (AI automating tasks currently done by humans) and indirect
effects (AI making each worker so productive that fewer are needed).

A key signal is whether the job's work product is fundamentally digital. If
the job can be done entirely from a home office on a computer - writing,
coding, analyzing, communicating - then AI exposure is inherently high (7+),
because AI capabilities in digital domains are advancing rapidly. Even if
today's AI cannot handle every aspect of such a job, the trajectory is steep
and the ceiling is very high. Conversely, jobs requiring physical presence,
manual skill, or real-time human interaction in the physical world have a
natural barrier to AI exposure.

Use these anchors to calibrate your score:

- 0-1: Minimal exposure. The work is almost entirely physical, hands-on, or
  requires real-time human presence in unpredictable environments. AI has
  essentially no impact on daily work. Examples: roofer, landscaper,
  commercial diver.

- 2-3: Low exposure. Mostly physical or interpersonal work. AI might help with
  minor peripheral tasks (scheduling, paperwork) but does not touch the core
  job. Examples: electrician, plumber, firefighter, dental hygienist.

- 4-5: Moderate exposure. A mix of physical/interpersonal work and knowledge
  work. AI can meaningfully assist with the information-processing parts but a
  substantial share of the job still requires human presence. Examples:
  registered nurse, police officer, veterinarian.

- 6-7: High exposure. Predominantly knowledge work with some need for human
  judgment, relationships, or physical presence. AI tools are already useful
  and workers using AI may be substantially more productive. Examples:
  teacher, manager, accountant, journalist.

- 8-9: Very high exposure. The job is almost entirely done on a computer. All
  core tasks - writing, coding, analyzing, designing, communicating - are in
  domains where AI is rapidly improving. The occupation faces major
  restructuring. Examples: software developer, graphic designer, translator,
  data analyst, paralegal, copywriter.

- 10: Maximum exposure. Routine information processing, fully digital, with no
  physical component. AI can already do most of it today. Examples: data entry
  clerk, telemarketer.

Respond with only a JSON object in this exact format, with no other text:
{
  "exposure": <0-10>,
  "rationale": "<2-3 sentences explaining the key factors>"
}\
"""


def clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def extract_output_text(payload):
    """Extract concatenated output_text content from a Responses API payload."""
    texts = []

    if isinstance(payload.get("output_text"), str):
        texts.append(payload["output_text"])

    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                texts.append(content["text"])

    return "\n".join(texts).strip()


def get_api_key():
    """Load the OpenAI API key from env or a bare-key .env file."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return api_key.strip()

    dotenv_path = ROOT_DIR / ".env"
    if dotenv_path.exists():
        raw = dotenv_path.read_text(encoding="utf-8").strip()
        if raw.startswith("sk-") and "=" not in raw:
            return raw

    raise RuntimeError("OPENAI_API_KEY is not set")


def default_reasoning_effort(model):
    """Pick a safe default reasoning effort for the requested model family."""
    if model.startswith("gpt-5.4"):
        return "low"
    if model.startswith("gpt-5"):
        return "minimal"
    return None


def parse_thousands_number(value):
    """Convert BLS matrix employment figures from thousands into whole jobs."""
    cleaned = clean(value).replace(",", "")
    if not cleaned:
        return None
    try:
        return int(round(float(cleaned) * 1000))
    except ValueError:
        return None


def parse_percent(value):
    cleaned = clean(value).replace(",", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def load_occupation_metadata():
    metadata = {}
    with OCCUPATIONS_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            metadata[row["slug"]] = {
                "soc_code": row.get("soc_code", ""),
                "industry_matrix_url": row.get("employment_by_industry_url", ""),
                "url": row.get("url", ""),
            }
    return metadata


def parse_industry_matrix(html):
    """Parse BLS employment-by-industry rows into a compact JSON shape."""
    soup = BeautifulSoup(html, "html.parser")
    table = None
    for candidate in soup.find_all("table"):
        headers = {clean(th.get_text(" ", strip=True)) for th in candidate.find_all("th")}
        if "Industry Title" in headers and "Industry Code" in headers:
            table = candidate
            break

    if table is None:
        return [], []

    industries = []
    naics_codes = []
    seen = set()

    for tr in table.find_all("tr"):
        cells = [clean(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]
        if len(cells) < 2:
            continue

        title, code = cells[0], cells[1]
        if title == "Industry Title" or title.startswith("Filter by Title:"):
            continue
        if not NUMERIC_CODE_RE.match(code):
            continue

        key = (title, code)
        if key in seen:
            continue
        seen.add(key)

        industry = {
            "title": title,
            "naics_code": code,
        }
        if len(cells) > 2 and cells[2]:
            industry["industry_type"] = cells[2]

        employment_2024 = parse_thousands_number(cells[3]) if len(cells) > 3 else None
        if employment_2024 is not None:
            industry["employment_2024"] = employment_2024

        occupation_share = parse_percent(cells[4]) if len(cells) > 4 else None
        if occupation_share is not None:
            industry["occupation_share_2024_pct"] = occupation_share

        industries.append(industry)
        naics_codes.append(code)

    return industries, sorted(set(naics_codes))


def fetch_industry_profile(client, url, cache):
    if not url:
        return [], []
    if url in cache:
        return cache[url]

    response = client.get(
        url,
        headers={"User-Agent": "jobs-ai-exposure/1.0"},
        timeout=60,
    )
    response.raise_for_status()
    parsed = parse_industry_matrix(response.text)
    cache[url] = parsed
    return parsed


def enrich_score_entry(entry, metadata, bls_client, industry_cache):
    changed = False
    if metadata is None:
        return changed

    soc_code = metadata.get("soc_code") or ""
    if entry.get("soc_code") != soc_code:
        entry["soc_code"] = soc_code
        changed = True

    industry_matrix_url = metadata.get("industry_matrix_url") or ""
    if entry.get("industry_matrix_url") != industry_matrix_url:
        entry["industry_matrix_url"] = industry_matrix_url
        changed = True

    url = metadata.get("url") or ""
    if url and entry.get("url") != url:
        entry["url"] = url
        changed = True

    industries, naics_codes = fetch_industry_profile(bls_client, industry_matrix_url, industry_cache)
    if entry.get("industries") != industries:
        entry["industries"] = industries
        changed = True
    if entry.get("naics_industry_codes") != naics_codes:
        entry["naics_industry_codes"] = naics_codes
        changed = True

    return changed


def score_occupation(client, text, model, reasoning_effort=None):
    """Send one occupation to the model and parse the structured response."""
    payload = {
        "model": model,
        "instructions": SYSTEM_PROMPT,
        "input": text,
        "text": {
            "verbosity": "low",
            "format": {
                "type": "json_schema",
                "name": "ai_exposure_score",
                "strict": True,
                "schema": OUTPUT_SCHEMA,
            },
        },
        "max_output_tokens": 800,
        "store": False,
    }
    effort = reasoning_effort or default_reasoning_effort(model)
    if effort is not None:
        payload["reasoning"] = {"effort": effort}

    response = client.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {get_api_key()}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    content = extract_output_text(response.json())
    if not content:
        raise RuntimeError("OpenAI response did not include output text")

    result = json.loads(content)
    result["exposure"] = int(result["exposure"])
    result["rationale"] = result["rationale"].strip()
    return result


def ordered_scores(scores, occupations):
    known_slugs = set()
    ordered = []
    for occ in occupations:
        slug = occ["slug"]
        if slug in scores:
            ordered.append(scores[slug])
            known_slugs.add(slug)

    for slug, entry in scores.items():
        if slug not in known_slugs:
            ordered.append(entry)
    return ordered


def write_scores(path, scores, occupations):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(ordered_scores(scores, occupations), f, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument("--output-file", default=str(SCORES_JSON.relative_to(ROOT_DIR)))
    parser.add_argument("--force", action="store_true", help="Re-score even if already cached")
    args = parser.parse_args()

    output_path = resolve_project_path(args.output_file)

    with OCCUPATIONS_JSON.open(encoding="utf-8") as f:
        occupations = json.load(f)

    subset = occupations[args.start:args.end]
    metadata_by_slug = load_occupation_metadata()

    scores = {}
    if output_path.exists() and not args.force:
        with output_path.open(encoding="utf-8") as f:
            for entry in json.load(f):
                scores[entry["slug"]] = entry

    print(f"Scoring {len(subset)} occupations with {args.model}")
    print(f"Already cached: {len(scores)}")

    errors = []
    openai_client = httpx.Client()
    bls_client = httpx.Client(follow_redirects=True)
    industry_cache = {}
    dirty = False

    for slug, entry in list(scores.items()):
        metadata = metadata_by_slug.get(slug)
        try:
            dirty = enrich_score_entry(entry, metadata, bls_client, industry_cache) or dirty
        except Exception as exc:
            print(f"  WARN {slug}: could not load industry metadata ({exc})")

    for index, occ in enumerate(subset):
        slug = occ["slug"]
        metadata = metadata_by_slug.get(slug)

        if slug in scores:
            continue

        md_path = PAGES_DIR / f"{slug}.md"
        if not md_path.exists():
            print(f"  [{index + 1}] SKIP {slug} (no markdown)")
            continue

        text = md_path.read_text(encoding="utf-8")
        print(f"  [{index + 1}/{len(subset)}] {occ['title']}...", end=" ", flush=True)

        try:
            result = score_occupation(openai_client, text, args.model, args.reasoning_effort)
            entry = {
                "slug": slug,
                "title": occ["title"],
                **result,
            }
            try:
                enrich_score_entry(entry, metadata, bls_client, industry_cache)
            except Exception as exc:
                print(f"WARN industry metadata unavailable ({exc})", end=" ")
            scores[slug] = entry
            dirty = True
            print(f"exposure={result['exposure']}")
        except Exception as exc:
            print(f"ERROR: {exc}")
            errors.append(slug)

        write_scores(output_path, scores, occupations)

        if index < len(subset) - 1:
            time.sleep(args.delay)

    if dirty:
        write_scores(output_path, scores, occupations)

    openai_client.close()
    bls_client.close()

    print(f"\nDone. Scored {len(scores)} occupations, {len(errors)} errors.")
    if errors:
        print(f"Errors: {errors}")

    vals = [entry for entry in scores.values() if "exposure" in entry]
    if vals:
        avg = sum(entry["exposure"] for entry in vals) / len(vals)
        by_score = {}
        for entry in vals:
            bucket = entry["exposure"]
            by_score[bucket] = by_score.get(bucket, 0) + 1
        print(f"\nAverage exposure across {len(vals)} occupations: {avg:.1f}")
        print("Distribution:")
        for bucket in sorted(by_score):
            print(f"  {bucket}: {'#' * by_score[bucket]} ({by_score[bucket]})")


if __name__ == "__main__":
    main()
