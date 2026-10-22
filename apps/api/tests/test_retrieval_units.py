from rmd.retrieval.language import detect_language
from rmd.retrieval.search import Hit, rrf_fuse
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
