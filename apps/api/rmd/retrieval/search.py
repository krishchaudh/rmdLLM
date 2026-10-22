"""Unified retrieval over book + lecture chunks: dense (pgvector), lexical (tsvector), hybrid RRF."""

from __future__ import annotations

import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from rmd.providers.base import Usage
from rmd.providers.factory import get_embedding_provider
from rmd.retrieval.language import detect_language
from rmd.retrieval.terminology import expand_query_terms, fold
from rmd.retrieval.translate import bridge_query


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
    rerank_rank: int | None = None
    youtube_id: str | None = None


@dataclass
class RetrievalResult:
    hits: list[Hit]
    mode: str
    latency_ms: dict = field(default_factory=dict)
    usage: Usage = field(default_factory=Usage)
    expanded_terms: list[str] = field(default_factory=list)
    translated_query: str | None = None
    translation_usage: Usage = field(default_factory=Usage)
    reranked: bool = False
    rerank_usage: Usage = field(default_factory=Usage)


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
    return rrf_fuse_many([dense], [lexical], k, c)


def rrf_fuse_many(
    dense_lists: list[list[Hit]], lexical_lists: list[list[Hit]], k: int, c: int = 60
) -> list[Hit]:
    """Reciprocal-rank fusion over several ranked lists (e.g. original + translated query).

    A chunk's dense_rank / lexical_rank is the best rank it achieved in any list of that kind.
    """
    merged: dict[uuid.UUID, Hit] = {}
    for kind, lists in (("dense", dense_lists), ("lexical", lexical_lists)):
        for ranked in lists:
            for rank, h in enumerate(ranked, start=1):
                m = merged.setdefault(h.chunk_id, Hit(**{**h.__dict__, "score": 0.0}))
                prev = getattr(m, f"{kind}_rank")
                setattr(m, f"{kind}_rank", rank if prev is None else min(prev, rank))
                m.score += 1.0 / (c + rank)
    return sorted(merged.values(), key=lambda h: h.score, reverse=True)[:k]


DIVERSITY_SLOT = 2


def ensure_kind_floor(
    hits: list[Hit], per_kind: dict[str, list[Hit]], k: int, floor: int
) -> list[Hit]:
    """Guarantee every source kind at least `floor` candidates in the fused top-k.

    Fusion runs over the whole corpus so scores stay comparable, but a large English book
    (hundreds of chunks) will push a small Hindi lecture out of the candidate list entirely.
    Each kind is therefore also searched on its own and its best hits are back-filled into the
    tail of the list — the reranker decides whether they actually answer the question.
    """
    out = list(hits)
    present = {h.chunk_id for h in out}
    protected: set[uuid.UUID] = set()
    for kind, ranked in per_kind.items():
        have = sum(1 for h in out if h.kind == kind)
        for h in ranked:
            if have >= floor:
                break
            if h.chunk_id in present:
                continue
            out.append(h)
            present.add(h.chunk_id)
            protected.add(h.chunk_id)
            have += 1
    while len(out) > k:
        victim = next(
            (i for i in range(len(out) - 1, -1, -1) if out[i].chunk_id not in protected), None
        )
        if victim is None:
            break
        out.pop(victim)
    return out


def ensure_kind_diversity(hits: list[Hit], ranked: list[Hit], k: int) -> list[Hit]:
    """Keep the best passage of each kind the reranker judged relevant inside the final top-k.

    The listwise reranker tends to prefer clean English prose over colloquial Hindi speech, so a
    relevant lecture passage can be ranked just below the cut even though it was deemed relevant.
    The rescued passage takes the third slot: the top two stay pure relevance, then the reader
    gets the other source's take on the same question.
    """
    kept = {h.chunk_id for h in hits}
    out = list(hits)
    for kind in sorted({h.kind for h in ranked}):
        best = next((h for h in ranked if h.kind == kind and h.rerank_rank is not None), None)
        if best is None or best.chunk_id in kept:
            continue
        if len(out) >= k:
            out.pop()
        out.insert(min(DIVERSITY_SLOT, len(out)), best)
        kept.add(best.chunk_id)
    return out[:k]


def retrieve(
    db: Session,
    query: str,
    *,
    k: int = 8,
    mode: str = "hybrid",  # dense | lexical | hybrid
    candidate_k: int = 20,
    source_ids: list[uuid.UUID] | None = None,
    kinds: list[str] | None = None,
    bridge_languages: bool = True,
    rerank: bool | None = None,
    pooled: bool = True,
) -> RetrievalResult:
    """Hybrid retrieval with language bridging, per-kind candidate floors and optional reranking.

    Candidates are fused over the whole corpus (comparable scores), then every source kind is
    guaranteed a minimum number of candidates from its own search so a large English book cannot
    crowd out the much smaller Hindi lecture before the reranker sees it. Query translation runs
    concurrently with the original-language search.
    """
    from rmd.config import get_settings

    settings = get_settings()
    if rerank is None:
        rerank = settings.rerank_enabled
    lat: dict[str, float] = {}
    usage = Usage()
    translation_usage = Usage()
    translated: str | None = None
    all_kinds = list(kinds or ("book", "lecture"))
    pools: list[list[str]] = [[kd] for kd in all_kinds] if pooled and len(all_kinds) > 1 else []
    dense_lists: list[list[Hit]] = []
    lexical_lists: list[list[Hit]] = []
    kind_dense: dict[str, list[list[Hit]]] = {p[0]: [] for p in pools}
    kind_lexical: dict[str, list[list[Hit]]] = {p[0]: [] for p in pools}
    embedder = get_embedding_provider() if mode in ("dense", "hybrid") else None
    t0 = time.perf_counter()

    def run_queries(queries: list[str]) -> None:
        nonlocal usage
        expansions = expand_query_terms(" ".join(queries))
        if embedder is not None:
            t = time.perf_counter()
            vecs, u = embedder.embed(queries)
            usage = Usage(
                prompt_tokens=usage.prompt_tokens + u.prompt_tokens,
                completion_tokens=usage.completion_tokens + u.completion_tokens,
                model=u.model or usage.model,
            )
            lat["embed_ms"] = round(lat.get("embed_ms", 0.0) + (time.perf_counter() - t) * 1000, 1)
            t = time.perf_counter()
            for v in vecs:
                dense_lists.append(dense_search(db, v, candidate_k, source_ids, all_kinds))
                for pool in pools:
                    kind_dense[pool[0]].append(dense_search(db, v, candidate_k, source_ids, pool))
            lat["dense_ms"] = round(lat.get("dense_ms", 0.0) + (time.perf_counter() - t) * 1000, 1)
        if mode in ("lexical", "hybrid"):
            t = time.perf_counter()
            for q in queries:
                lexical_lists.append(
                    lexical_search(db, fold(q), candidate_k, source_ids, all_kinds, expansions)
                )
                for pool in pools:
                    kind_lexical[pool[0]].append(
                        lexical_search(db, fold(q), candidate_k, source_ids, pool, expansions)
                    )
            lat["lexical_ms"] = round(
                lat.get("lexical_ms", 0.0) + (time.perf_counter() - t) * 1000, 1
            )

    if bridge_languages:
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(bridge_query, query, detect_language(query))
            run_queries([query])
            translated, translation_usage = fut.result()
        lat["translate_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        if translated:
            run_queries([translated])
    else:
        run_queries([query])
    expansions = expand_query_terms(" ".join([query] + ([translated] if translated else [])))

    fuse_k = max(k, settings.rerank_candidates) if rerank else k
    hits = rrf_fuse_many(dense_lists, lexical_lists, fuse_k)
    if pools:
        per_kind = {
            kd: rrf_fuse_many(kind_dense[kd], kind_lexical[kd], settings.kind_floor)
            for kd in kind_dense
        }
        hits = ensure_kind_floor(hits, per_kind, fuse_k, settings.kind_floor)
    rerank_usage = Usage()
    reranked = False
    if rerank and hits:
        from rmd.retrieval.rerank import rerank as _rerank

        t = time.perf_counter()
        ranked, rerank_usage = _rerank(query, hits, keep=len(hits), translated=translated)
        lat["rerank_ms"] = round((time.perf_counter() - t) * 1000, 1)
        hits = ensure_kind_diversity(ranked[:k], ranked, k)
        reranked = True
    return RetrievalResult(
        hits=hits,
        mode=mode,
        latency_ms=lat,
        usage=usage,
        expanded_terms=expansions,
        translated_query=translated,
        translation_usage=translation_usage,
        reranked=reranked,
        rerank_usage=rerank_usage,
    )
