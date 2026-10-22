from rmd.eval.metrics import (
    hit_at_k,
    is_relevant,
    mrr,
    ndcg_at_k,
    percentile,
    recall_at_k,
    relevance_vector,
)

LEC = {"kind": "lecture", "youtube_id": "P4u061hYAXs", "start_seconds": 316, "end_seconds": 394}


def _hit(kind, **loc):
    return {"kind": kind, "youtube_id": "P4u061hYAXs", "title": "T", "locator": loc}


def test_lecture_overlap():
    assert is_relevant(_hit("lecture", start_seconds=308, end_seconds=368), LEC)
    assert not is_relevant(_hit("lecture", start_seconds=0, end_seconds=60), LEC)
    assert not is_relevant(_hit("book", page_index=3), LEC)


def test_book_page_overlap_and_printed():
    exp = {"kind": "book", "page_index": 10, "page_index_end": 11}
    assert is_relevant(_hit("book", page_index=11, page_index_end=12), exp)
    assert not is_relevant(_hit("book", page_index=12), exp)
    assert is_relevant(
        _hit("book", page_index=1, printed_page_number="27"),
        {"kind": "book", "printed_page_number": 27},
    )


def test_rank_metrics():
    hits = [
        _hit("lecture", start_seconds=0, end_seconds=60),
        _hit("lecture", start_seconds=300, end_seconds=400),
    ]
    rel = relevance_vector(hits, [LEC])
    assert rel == [0, 1]
    assert mrr(rel) == 0.5
    assert hit_at_k(rel, 1) == 0.0 and hit_at_k(rel, 2) == 1.0
    assert recall_at_k(rel, [LEC], hits, 2) == 1.0
    assert 0 < ndcg_at_k(rel, 2) < 1
    assert ndcg_at_k([1, 0], 2) == 1.0
    assert percentile([5, 1, 3], 50) == 3
