"""Unified retrieval over book + lecture chunks: dense (pgvector), lexical (tsvector), hybrid RRF."""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from rmd.providers.base import Usage
from rmd.providers.factory import get_embedding_provider
from rmd.retrieval.terminology import expand_query_terms, fold


@dataclass
class Hit:
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    kind: str
    title: str
    language: str
    text: str
    locator: dict
    score: float
    dense_rank: int | None = None
    lexical_rank: int | None = None
    youtube_id: str | None = None


@dataclass
class RetrievalResult:
    hits: list[Hit]
    mode: str
    latency_ms: dict = field(default_factory=dict)
    usage: Usage = field(default_factory=Usage)
    expanded_terms: list[str] = field(default_factory=list)


_BASE_SELECT = """
SELECT c.id, c.source_id, c.kind, s.title, c.language, c.text, c.locator, l.youtube_id, {score} AS score
FROM chunks c
JOIN sources s ON s.id = c.source_id
LEFT JOIN lectures l ON l.source_id = c.source_id
WHERE s.status = 'ready' {filters}
"""


def _rows_to_hits(rows) -> list[Hit]:
    return [
        Hit(
            chunk_id=r.id,
            source_id=r.source_id,
            kind=r.kind,
            title=r.title,
            language=r.language,
            text=r.text,
            locator=r.locator,
            score=float(r.score),
            youtube_id=r.youtube_id,
        )
        for r in rows
    ]


def _filters(source_ids: list[uuid.UUID] | None, kinds: list[str] | None) -> tuple[str, dict]:
    sql, params = "", {}
    if source_ids:
        sql += " AND c.source_id IN :source_ids"
        params["source_ids"] = list(source_ids)
    if kinds:
        sql += " AND c.kind IN :kinds"
        params["kinds"] = list(kinds)
    return sql, params


def dense_search(
    db: Session, query_vec: list[float], k: int, source_ids=None, kinds=None
) -> list[Hit]:
    f, params = _filters(source_ids, kinds)
    sql = _BASE_SELECT.format(score="1 - (c.embedding <=> CAST(:qv AS vector))", filters=f)
    sql += " AND c.embedding IS NOT NULL ORDER BY c.embedding <=> CAST(:qv AS vector) LIMIT :k"
    stmt = text(sql)
    if source_ids:
        stmt = stmt.bindparams(bindparam("source_ids", expanding=True))
    if kinds:
        stmt = stmt.bindparams(bindparam("kinds", expanding=True))
    rows = db.execute(stmt, {"qv": str(query_vec), "k": k, **params}).fetchall()
    return _rows_to_hits(rows)


def _lexical_query_string(query: str, expansions: list[str]) -> str:
    tokens = re.findall(r"[\w\u0900-\u097F]+", query.lower())
    stop = {
        "the",
        "a",
        "an",
        "of",
        "is",
        "are",
        "to",
        "in",
        "and",
        "or",
        "why",
        "what",
        "how",
        "does",
        "do",
        "not",
        "doesn",
        "t",
        "for",
        "with",
        "on",
        "by",
        "it",
        "be",
        "that",
        "this",
    }
    tokens = [t for t in tokens if t not in stop and len(t) > 1]
    parts = [f"{t}:*" for t in tokens]
    for e in expansions:
        ws = re.findall(r"[\w\u0900-\u097F]+", e.lower())
        if ws:
            parts.append("(" + " & ".join(f"{w}:*" for w in ws) + ")")
    return " | ".join(parts)


def lexical_search(
    db: Session,
    query: str,
    k: int,
    source_ids=None,
    kinds=None,
    expansions: list[str] | None = None,
) -> list[Hit]:
    tsq = _lexical_query_string(query, expansions or [])
    if not tsq:
        return []
    f, params = _filters(source_ids, kinds)
    sql = _BASE_SELECT.format(score="ts_rank_cd(c.text_tsv, to_tsquery('simple', :tsq))", filters=f)
    sql += " AND c.text_tsv @@ to_tsquery('simple', :tsq) ORDER BY score DESC LIMIT :k"
    stmt = text(sql)
    if source_ids:
        stmt = stmt.bindparams(bindparam("source_ids", expanding=True))
    if kinds:
        stmt = stmt.bindparams(bindparam("kinds", expanding=True))
    try:
        rows = db.execute(stmt, {"tsq": tsq, "k": k, **params}).fetchall()
    except Exception:
        db.rollback()
        return []
    return _rows_to_hits(rows)


def rrf_fuse(dense: list[Hit], lexical: list[Hit], k: int, c: int = 60) -> list[Hit]:
    merged: dict[uuid.UUID, Hit] = {}
    for rank, h in enumerate(dense, start=1):
        m = merged.setdefault(h.chunk_id, Hit(**{**h.__dict__, "score": 0.0}))
        m.dense_rank = rank
        m.score += 1.0 / (c + rank)
    for rank, h in enumerate(lexical, start=1):
        m = merged.setdefault(h.chunk_id, Hit(**{**h.__dict__, "score": 0.0}))
        m.lexical_rank = rank
        m.score += 1.0 / (c + rank)
    return sorted(merged.values(), key=lambda h: h.score, reverse=True)[:k]


def retrieve(
    db: Session,
    query: str,
    *,
    k: int = 8,
    mode: str = "hybrid",  # dense | lexical | hybrid
    candidate_k: int = 30,
    source_ids: list[uuid.UUID] | None = None,
    kinds: list[str] | None = None,
) -> RetrievalResult:
    lat: dict[str, float] = {}
    usage = Usage()
    expansions = expand_query_terms(query)
    dense: list[Hit] = []
    lexical: list[Hit] = []
    if mode in ("dense", "hybrid"):
        t = time.perf_counter()
        embedder = get_embedding_provider()
        vecs, usage = embedder.embed([query])
        lat["embed_ms"] = round((time.perf_counter() - t) * 1000, 1)
        t = time.perf_counter()
        dense = dense_search(db, vecs[0], candidate_k, source_ids, kinds)
        lat["dense_ms"] = round((time.perf_counter() - t) * 1000, 1)
    if mode in ("lexical", "hybrid"):
        t = time.perf_counter()
        lexical = lexical_search(db, fold(query), candidate_k, source_ids, kinds, expansions)
        lat["lexical_ms"] = round((time.perf_counter() - t) * 1000, 1)
    if mode == "dense":
        hits = dense[:k]
    elif mode == "lexical":
        hits = lexical[:k]
    else:
        hits = rrf_fuse(dense, lexical, k)
    return RetrievalResult(
        hits=hits, mode=mode, latency_ms=lat, usage=usage, expanded_terms=expansions
    )
