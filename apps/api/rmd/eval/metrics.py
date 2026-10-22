"""Retrieval metrics. A hit is relevant if it overlaps an expected locator.

Expected locators (from the dataset):
  {"kind": "lecture", "youtube_id": "...", "start_seconds": 316, "end_seconds": 394}
  {"kind": "book", "source_title": "...", "page_index": 12, "page_index_end": 13}
  {"kind": "book", "printed_page_number": "27"}
"""

from __future__ import annotations

import math


def _overlap(a0: float, a1: float, b0: float, b1: float) -> bool:
    return max(a0, b0) <= min(a1, b1)


def is_relevant(hit: dict, expected: dict) -> bool:
    if hit.get("kind") != expected.get("kind"):
        return False
    loc = hit.get("locator") or {}
    if expected["kind"] == "lecture":
        if expected.get("youtube_id") and hit.get("youtube_id") != expected["youtube_id"]:
            return False
        hs, he = loc.get("start_seconds"), loc.get("end_seconds", loc.get("start_seconds"))
        if hs is None:
            return False
        return _overlap(
            hs,
            he,
            expected["start_seconds"],
            expected.get("end_seconds", expected["start_seconds"]),
        )
    if expected.get("source_title") and expected["source_title"] != hit.get("title"):
        return False
    if "printed_page_number" in expected:
        return str(loc.get("printed_page_number")) == str(expected["printed_page_number"])
    p0, p1 = loc.get("page_index"), loc.get("page_index_end") or loc.get("page_index")
    if p0 is None:
        return False
    return _overlap(
        p0, p1, expected["page_index"], expected.get("page_index_end", expected["page_index"])
    )


def relevance_vector(hits: list[dict], expected: list[dict]) -> list[int]:
    return [int(any(is_relevant(h, e) for e in expected)) for h in hits]


def recall_at_k(rel: list[int], expected: list[dict], hits: list[dict], k: int) -> float:
    """Fraction of expected locators matched by at least one of the top-k hits."""
    if not expected:
        return 0.0
    top = hits[:k]
    matched = sum(1 for e in expected if any(is_relevant(h, e) for h in top))
    return matched / len(expected)


def hit_at_k(rel: list[int], k: int) -> float:
    return 1.0 if any(rel[:k]) else 0.0


def mrr(rel: list[int]) -> float:
    for i, r in enumerate(rel):
        if r:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(rel: list[int], k: int) -> float:
    gains = rel[:k]
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
    ideal = sorted(rel, reverse=True)[:k]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def percentile(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    idx = min(len(s) - 1, max(0, round((p / 100) * (len(s) - 1))))
    return s[idx]
