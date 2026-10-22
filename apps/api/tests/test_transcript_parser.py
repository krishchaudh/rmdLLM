import pytest

from rmd.ingestion.transcript_parser import (
    TranscriptParseError,
    parse_transcript,
    parse_youtube_panel_line,
)

SAMPLE = """0:000 secondsदो प्रकार के कर्म होते हैं।
0:055 secondsएक भौतिक, एक आध्यात्मिक
1:231 minute, 23 secondsअर्थात दिव्य कर्म गुणातीत कर्म
"""


@pytest.mark.parametrize(
    "line,start,text",
    [
        ("0:000 secondsदो प्रकार के कर्म होते हैं।", 0, "दो प्रकार के कर्म होते हैं।"),
        ("0:055 secondsएक भौतिक, एक आध्यात्मिक", 5, "एक भौतिक, एक आध्यात्मिक"),
        ("1:231 minute, 23 secondsअर्थात दिव्य कर्म गुणातीत कर्म", 83, "अर्थात दिव्य कर्म गुणातीत कर्म"),
        ("5:165 minutes, 16 secondsअच्छा बताओ जब से तुम पैदा हुए", 316, "अच्छा बताओ जब से तुम पैदा हुए"),
        ("15:4115 minutes, 41 secondsतो प्रहलाद ने कहा", 941, "तो प्रहलाद ने कहा"),
        ("20:0820 minutes, 8 secondsलगाओ लगाओ।", 1208, "लगाओ लगाओ।"),
        ("1:00:001 hour, 0 minutes, 0 secondsनमस्ते", 3600, "नमस्ते"),
        ("1:00 minute test", 60, "minute test"),  # plain "M:SS text"
    ],
)
def test_panel_line(line, start, text):
    assert parse_youtube_panel_line(line) == (start, text)


def test_expected_structured_output():
    result = parse_transcript(SAMPLE)
    assert result.ok
    assert result.format == "youtube_panel"
    assert result.segments[2].to_dict() == {
        "start_seconds": 83,
        "end_seconds": None,
        "text": "अर्थात दिव्य कर्म गुणातीत कर्म",
    }
    assert result.segments[0].end_seconds == 5
    assert result.segments[1].end_seconds == 83


def test_disagreeing_duplicate_is_rejected():
    with pytest.raises(TranscriptParseError):
        parse_youtube_panel_line("1:231 minute, 24 secondsतेक्स्ट")


def test_malformed_lines_reported_not_guessed():
    result = parse_transcript(SAMPLE + "this line has no timestamp\n1:30\n")
    assert len(result.segments) == 3
    reasons = [i.reason for i in result.issues]
    assert any("timestamp" in r for r in reasons)
    assert any("empty caption" in r or "whitespace" in r for r in reasons)
    assert not result.ok


def test_backwards_timestamp_flagged():
    result = parse_transcript("0:100 minutes, 10 secondsक\n0:055 secondsख\n")
    assert any("backwards" in i.reason for i in result.issues)


def test_srt():
    srt = "1\n00:00:01,000 --> 00:00:04,000\nनमस्ते\n\n2\n00:00:04,000 --> 00:00:06,500\nदूसरी पंक्ति\n"
    result = parse_transcript(srt)
    assert result.format == "srt"
    assert [s.start_seconds for s in result.segments] == [1, 4]
    assert result.segments[0].end_seconds == 4


def test_empty():
    assert not parse_transcript("   \n").ok


def test_real_transcript_file():
    import pathlib

    p = pathlib.Path("/home/ubuntu/transcript_P4u061hYAXs.txt")
    if not p.exists():
        pytest.skip("real transcript not available")
    result = parse_transcript(p.read_text(encoding="utf-8"))
    assert result.ok, result.issues[:5]
    assert len(result.segments) == 148
    by_start = {s.start_seconds: s.text for s in result.segments}
    assert by_start[316].startswith("अच्छा बताओ जब से तुम पैदा हुए")
    assert by_start[941].startswith("तो प्रहलाद ने कहा")
