from rmd.ingestion.chunking import chunk_book_pages, chunk_transcript_segments, normalize_text


def test_normalize_keeps_devanagari_and_diacritics():
    s = "श्री  राधा   कृष्ण\n\n\n\nŚrī Rādhā"
    assert normalize_text(s) == "श्री राधा कृष्ण\n\nŚrī Rādhā"


def test_book_chunks_span_pages_and_keep_locator():
    pages = [
        {
            "page_index": 10,
            "printed_page_number": "1",
            "text": "Para one. " * 30 + "\n\n" + "Para two. " * 30,
        },
        {"page_index": 11, "printed_page_number": "2", "text": "Para three. " * 30},
    ]
    chunks = chunk_book_pages(pages, target_tokens=120)
    assert chunks
    assert chunks[0].locator["page_index"] == 10
    assert chunks[0].locator["printed_page_number"] == "1"
    assert chunks[-1].locator["page_index_end"] == 11
    assert all(c.token_count <= 500 for c in chunks)
    joined = " ".join(c.text for c in chunks)
    assert "Para three." in joined and "Para one." in joined


def test_transcript_chunks_group_lines():
    segs = [
        {"idx": i, "start_seconds": i * 10, "end_seconds": i * 10 + 10, "text": f"पंक्ति {i} कुछ शब्द"}
        for i in range(20)
    ]
    chunks = chunk_transcript_segments(
        segs, youtube_id="P4u061hYAXs", target_tokens=60, max_window_seconds=60
    )
    assert len(chunks) > 1
    assert chunks[0].locator["youtube_id"] == "P4u061hYAXs"
    assert chunks[0].locator["start_seconds"] == 0
    for c in chunks:
        assert c.locator["end_seconds"] - c.locator["start_seconds"] <= 70
    assert chunks[-1].locator["segment_idx_end"] == 19
