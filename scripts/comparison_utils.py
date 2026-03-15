"""Shared normalization/statistics helpers for comparison scripts."""

from __future__ import annotations

import math
import re
from pathlib import Path


SOC_RE = re.compile(r"(\d{2})\D?(\d{4})")

NAICS_RE = re.compile(r"\d+")


def norm_naics(code: object) -> str | None:
    if code is None:
        return None
    text = str(code).strip()
    if not text:
        return None
    m = NAICS_RE.findall(text)
    if not m:
        return None
    return "".join(m)


def naics4(code: object) -> str | None:
    normalized = norm_naics(code)
    if not normalized:
        return None
    if len(normalized) < 4:
        return None
    return normalized[:4]


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
    soc = norm_soc(code)
    if not soc:
        return None
    return f"{soc[:2]}-{soc[3:5]}"


def percentile(values: list[float]) -> list[float]:
    if not values:
        return []
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    n = len(values)
    for rank, idx in enumerate(order, start=1):
        out[idx] = rank / n
    return out


def zscore(values: list[float]) -> list[float]:
    if not values:
        return []
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(var)
    if std == 0:
        return [0.0 for _ in values]
    return [(v - mean) / std for v in values]


def pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or not xs:
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
    return pearson(percentile(xs), percentile(ys))


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
