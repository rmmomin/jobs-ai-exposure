"""
Score each occupation's AI exposure using the OpenAI Responses API.

Reads Markdown descriptions from pages/, sends each to an OpenAI model with a
scoring rubric, and collects structured scores. Results are cached
incrementally to scores.json so the script can be resumed if interrupted.

Usage:
    uv run python score.py
    uv run python score.py --model gpt-5-mini
    uv run python score.py --start 0 --end 10   # test on first 10
"""

import argparse
import json
import os
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "gpt-5-mini"
OUTPUT_FILE = "scores.json"
API_URL = "https://api.openai.com/v1/responses"
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
You are an expert analyst evaluating how exposed different occupations are to \
AI. You will be given a detailed description of an occupation from the Bureau \
of Labor Statistics.

Rate the occupation's overall **AI Exposure** on a scale from 0 to 10.

AI Exposure measures: how much will AI reshape this occupation? Consider both \
direct effects (AI automating tasks currently done by humans) and indirect \
effects (AI making each worker so productive that fewer are needed).

A key signal is whether the job's work product is fundamentally digital. If \
the job can be done entirely from a home office on a computer — writing, \
coding, analyzing, communicating — then AI exposure is inherently high (7+), \
because AI capabilities in digital domains are advancing rapidly. Even if \
today's AI can't handle every aspect of such a job, the trajectory is steep \
and the ceiling is very high. Conversely, jobs requiring physical presence, \
manual skill, or real-time human interaction in the physical world have a \
natural barrier to AI exposure.

Use these anchors to calibrate your score:

- **0–1: Minimal exposure.** The work is almost entirely physical, hands-on, \
or requires real-time human presence in unpredictable environments. AI has \
essentially no impact on daily work. \
Examples: roofer, landscaper, commercial diver.

- **2–3: Low exposure.** Mostly physical or interpersonal work. AI might help \
with minor peripheral tasks (scheduling, paperwork) but doesn't touch the \
core job. \
Examples: electrician, plumber, firefighter, dental hygienist.

- **4–5: Moderate exposure.** A mix of physical/interpersonal work and \
knowledge work. AI can meaningfully assist with the information-processing \
parts but a substantial share of the job still requires human presence. \
Examples: registered nurse, police officer, veterinarian.

- **6–7: High exposure.** Predominantly knowledge work with some need for \
human judgment, relationships, or physical presence. AI tools are already \
useful and workers using AI may be substantially more productive. \
Examples: teacher, manager, accountant, journalist.

- **8–9: Very high exposure.** The job is almost entirely done on a computer. \
All core tasks — writing, coding, analyzing, designing, communicating — are \
in domains where AI is rapidly improving. The occupation faces major \
restructuring. \
Examples: software developer, graphic designer, translator, data analyst, \
paralegal, copywriter.

- **10: Maximum exposure.** Routine information processing, fully digital, \
with no physical component. AI can already do most of it today. \
Examples: data entry clerk, telemarketer.

Respond with ONLY a JSON object in this exact format, no other text:
{
  "exposure": <0-10>,
  "rationale": "<2-3 sentences explaining the key factors>"
}\
"""


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

    dotenv_path = ".env"
    if os.path.exists(dotenv_path):
        with open(dotenv_path, encoding="utf-8") as f:
            raw = f.read().strip()
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
            }
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument("--output-file", default=OUTPUT_FILE)
    parser.add_argument("--force", action="store_true",
                        help="Re-score even if already cached")
    args = parser.parse_args()

    with open("occupations.json") as f:
        occupations = json.load(f)

    subset = occupations[args.start:args.end]

    # Load existing scores
    scores = {}
    if os.path.exists(args.output_file) and not args.force:
        with open(args.output_file) as f:
            for entry in json.load(f):
                scores[entry["slug"]] = entry

    print(f"Scoring {len(subset)} occupations with {args.model}")
    print(f"Already cached: {len(scores)}")

    errors = []
    client = httpx.Client()

    for i, occ in enumerate(subset):
        slug = occ["slug"]

        if slug in scores:
            continue

        md_path = f"pages/{slug}.md"
        if not os.path.exists(md_path):
            print(f"  [{i+1}] SKIP {slug} (no markdown)")
            continue

        with open(md_path, encoding="utf-8") as f:
            text = f.read()

        print(f"  [{i+1}/{len(subset)}] {occ['title']}...", end=" ", flush=True)

        try:
            result = score_occupation(client, text, args.model, args.reasoning_effort)
            scores[slug] = {
                "slug": slug,
                "title": occ["title"],
                **result,
            }
            print(f"exposure={result['exposure']}")
        except Exception as e:
            print(f"ERROR: {e}")
            errors.append(slug)

        # Save after each one (incremental checkpoint)
        with open(args.output_file, "w") as f:
            json.dump(list(scores.values()), f, indent=2)

        if i < len(subset) - 1:
            time.sleep(args.delay)

    client.close()

    print(f"\nDone. Scored {len(scores)} occupations, {len(errors)} errors.")
    if errors:
        print(f"Errors: {errors}")

    # Summary stats
    vals = [s for s in scores.values() if "exposure" in s]
    if vals:
        avg = sum(s["exposure"] for s in vals) / len(vals)
        by_score = {}
        for s in vals:
            bucket = s["exposure"]
            by_score[bucket] = by_score.get(bucket, 0) + 1
        print(f"\nAverage exposure across {len(vals)} occupations: {avg:.1f}")
        print("Distribution:")
        for k in sorted(by_score):
            print(f"  {k}: {'█' * by_score[k]} ({by_score[k]})")


if __name__ == "__main__":
    main()
