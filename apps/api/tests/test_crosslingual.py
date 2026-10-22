import uuid

from rmd.providers.mock_provider import MockLLM
from rmd.retrieval.search import Hit, rrf_fuse_many
from rmd.retrieval.translate import bridge_query


def _hit(cid, text="x"):
    return Hit(
        chunk_id=cid,
        source_id=uuid.uuid4(),
        kind="book",
        title="t",
        language="en",
        text=text,
        locator={},
        score=1.0,
    )


def test_rrf_fuse_many_prefers_chunks_found_by_both_queries():
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    dense_orig = [_hit(a), _hit(b)]
    dense_translated = [_hit(c), _hit(a)]
    lexical_translated = [_hit(a), _hit(c)]
    fused = rrf_fuse_many([dense_orig, dense_translated], [lexical_translated], k=3)
    assert [h.chunk_id for h in fused] == [a, c, b]
    best = fused[0]
    assert best.dense_rank == 1 and best.lexical_rank == 1


def test_bridge_query_skips_english_to_english_noop_and_mock_output(monkeypatch):
    llm = MockLLM()
    monkeypatch.setattr("rmd.retrieval.translate.get_llm_provider", lambda: llm)
    text, _ = bridge_query("भौतिक धन से सुख क्यों नहीं मिलता?", "hi")
    assert text is None  # "[mock answer]" is rejected
    llm.scripted = ["Why does material wealth not give happiness?"]
    text, usage = bridge_query("bhautik dhan se sukh kyun nahi milta", "hi-Latn")
    assert text == "Why does material wealth not give happiness?"
    assert usage.total_tokens > 0
    assert llm.calls[-1][1]["content"].startswith("bhautik dhan")
    assert "English" in llm.calls[-1][0]["content"]
    assert bridge_query("anything", "fr") == (None, bridge_query("anything", "fr")[1])


def test_parse_ranking_handles_json_and_garbage():
    from rmd.retrieval.rerank import _parse_ranking

    assert _parse_ranking('{"ranking": [3, 1, 3, 9, "2"]}', 4) == [3, 1, 2]
    assert _parse_ranking("passages 2 and 4", 4) == [2, 4]
    assert _parse_ranking("{}", 4) == []


def test_rerank_reorders_and_backfills(monkeypatch):
    from rmd.retrieval.rerank import rerank

    llm = MockLLM()
    llm.scripted = ['{"ranking": [3, 1]}']
    monkeypatch.setattr("rmd.retrieval.rerank.get_llm_provider", lambda: llm)
    ids = [uuid.uuid4() for _ in range(4)]
    hits = [_hit(i, text=f"passage {n}") for n, i in enumerate(ids)]
    out, usage = rerank("q", hits, keep=3)
    assert [h.chunk_id for h in out] == [ids[2], ids[0], ids[1]]
    assert out[0].rerank_rank == 1 and out[2].rerank_rank is None
    assert usage.total_tokens > 0
    assert "<passage n=1" in llm.calls[-1][1]["content"]


def test_ensure_kind_diversity_restores_top_fused_hit_of_dropped_kind():
    from rmd.retrieval.search import ensure_kind_diversity

    lec = _hit(uuid.uuid4(), "lecture")
    lec.kind = "lecture"
    books = [_hit(uuid.uuid4(), f"b{i}") for i in range(5)]
    fused = [lec] + books
    reranked = books[:3]
    out = ensure_kind_diversity(reranked, fused, k=3)
    assert [h.chunk_id for h in out] == [books[0].chunk_id, books[1].chunk_id, lec.chunk_id]
    # nothing to do when already present
    assert ensure_kind_diversity([lec] + books[:2], fused, k=3) == [lec] + books[:2]
