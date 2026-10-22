from rmd.retrieval.language import detect_language
from rmd.retrieval.search import Hit, ensure_kind_diversity, ensure_kind_floor, rrf_fuse
from rmd.retrieval.terminology import expand_query_terms, fold


def test_detect_language():
    assert detect_language("भौतिक धन से स्थायी सुख क्यों नहीं मिलता?") == "hi"
    assert detect_language("Why doesn't material wealth provide lasting happiness?") == "en"
    assert detect_language("bhautik dhan se sthayi sukh kyu nahi milta?") == "hi-Latn"


def test_fold_and_expand():
    assert fold("Śrī Kṛṣṇa") == "sri krsna"
    exp = expand_query_terms("What is bhakti and sharanagati?")
    assert "भक्ति" in exp and "शरणागति" in exp


def test_rrf():
    import uuid

    def h(i):
        return Hit(uuid.UUID(int=i), uuid.UUID(int=0), "book", "t", "en", "x", {}, 1.0)

    fused = rrf_fuse([h(1), h(2), h(3)], [h(3), h(4)], k=3)
    assert fused[0].chunk_id == uuid.UUID(int=3)
    assert fused[0].dense_rank == 3 and fused[0].lexical_rank == 1


def _hit(i, kind="book", rerank_rank=None):
    import uuid

    h = Hit(uuid.UUID(int=i), uuid.UUID(int=0), kind, "t", "en", "x", {}, 1.0)
    h.rerank_rank = rerank_rank
    return h


def test_kind_floor_backfills_minority_kind_without_dropping_it():
    fused = [_hit(i) for i in range(1, 9)]  # book crowds out everything
    per_kind = {"book": [_hit(1)], "lecture": [_hit(20, "lecture"), _hit(21, "lecture")]}
    out = ensure_kind_floor(fused, per_kind, k=8, floor=2)
    assert len(out) == 8
    assert [h.chunk_id.int for h in out if h.kind == "lecture"] == [20, 21]
    assert [h.chunk_id.int for h in out[:6]] == [1, 2, 3, 4, 5, 6]


def test_kind_floor_noop_when_kind_already_present():
    fused = [_hit(1), _hit(2, "lecture"), _hit(3, "lecture")]
    out = ensure_kind_floor(fused, {"lecture": [_hit(9, "lecture")]}, k=3, floor=2)
    assert [h.chunk_id.int for h in out] == [1, 2, 3]


def test_kind_diversity_keeps_relevant_minority_hit():
    ranked = [_hit(i, rerank_rank=i) for i in range(1, 6)] + [_hit(7, "lecture", rerank_rank=6)]
    ranked.append(_hit(8, "lecture"))  # not judged relevant → must not be forced in
    out = ensure_kind_diversity(ranked[:5], ranked, k=5)
    assert [h.chunk_id.int for h in out] == [1, 2, 7, 3, 4]
    out = ensure_kind_diversity(ranked[:5], ranked[:5] + [ranked[6]], k=5)
    assert [h.chunk_id.int for h in out] == [1, 2, 3, 4, 5]
