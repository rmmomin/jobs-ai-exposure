"""Helpers for comparison dataset downloads, normalization, and statistics."""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Iterable


SOC_RE = re.compile(r"(\d{2})[- ]?(\d{4})")
NAICS_RE = re.compile(r"\d+")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def norm_soc(code: object) -> str | None:
    if code is None:
        return None
    text = str(code).strip()
    if not text:
        return None
    match = SOC_RE.search(text)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 6:
        return f"{digits[:2]}-{digits[2:6]}"
    return None


def soc4(code: object) -> str | None:
    normalized = norm_soc(code)
    if not normalized:
        return None
    return normalized[:2] + "-" + normalized[3:5]


def soc_major(code: object) -> str | None:
    normalized = norm_soc(code)
    if not normalized:
        return None
    return normalized[:2]


def norm_naics(code: object) -> str | None:
    if code is None:
        return None
    text = str(code).strip()
    if not text:
        return None
    digits_match = NAICS_RE.findall(text)
    if not digits_match:
        return None
    digits = "".join(digits_match)
    return digits


def naics_level(code: object) -> int | None:
    normalized = norm_naics(code)
    if not normalized:
        return None
    return len(normalized)


def z_scores(values: Iterable[float]) -> list[float]:
    vals = list(values)
    if not vals:
        return []
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    std = math.sqrt(var)
    if std == 0:
        return [0.0 for _ in vals]
    return [(v - mean) / std for v in vals]


def percentile_ranks(values: Iterable[float]) -> list[float]:
    vals = list(values)
    if not vals:
        return []
    indexed = sorted(enumerate(vals), key=lambda x: x[1])
    out = [0.0] * len(vals)
    for rank, (idx, _) in enumerate(indexed, start=1):
        out[idx] = rank / len(vals)
    return out


def pearson(xs: list[float], ys: list[float]) -> float:
    if not xs or len(xs) != len(ys):
        return float("nan")
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys))
    if denx == 0 or deny == 0:
        return float("nan")
    return num / (denx * deny)


def spearman(xs: list[float], ys: list[float]) -> float:
    xr = percentile_ranks(xs)
    yr = percentile_ranks(ys)
    return pearson(xr, yr)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fieldnames})


def write_json(path: Path, payload: object) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
