from rmd.generation.answer import TokenStreamer
from rmd.providers.mock_provider import MockLLM


def _collect(deltas: list[str]) -> str:
    out: list[str] = []
    st = TokenStreamer(out.append)
    for d in deltas:
        st.push(d)
    return "".join(out)


def test_streamer_hides_followups_even_when_marker_is_split():
    text = _collect(["Love is ", "the goal [1].", "\n\nFOLLOW", "UPS:\n- q1\n- q2"])
    assert text == "Love is the goal [1]."


def test_streamer_never_leaks_abstain_marker():
    assert _collect(["ABST", "AIN: not in sources"]) == ""
    assert _collect(["Abstain"]) == ""


def test_streamer_streams_normal_text_progressively():
    out: list[str] = []
    st = TokenStreamer(out.append)
    st.push("Devotion means surrender and this sentence is long enough to flush.")
    assert out and out[0].startswith("Devotion means")


def test_default_chat_stream_emits_whole_text():
    llm = MockLLM(scripted=["hello world"])
    got: list[str] = []
    res = llm.chat_stream([{"role": "user", "content": "x"}], got.append)
    assert got == ["hello world"] and res.text == "hello world"
