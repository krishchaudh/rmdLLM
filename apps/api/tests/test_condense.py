import pytest

from rmd.generation import condense
from rmd.generation.condense import condense_question, needs_context
from rmd.providers.mock_provider import MockLLM

HIST = [
    {"role": "user", "content": "How can a seeker cultivate prema?"},
    {"role": "assistant", "content": "Through satsang and surrender [1]."},
]


@pytest.fixture
def llm(monkeypatch):
    m = MockLLM()
    monkeypatch.setattr(condense, "get_llm_provider", lambda: m)
    return m


def test_needs_context_detects_followups():
    assert needs_context("Summarize this in one sentence.", HIST)
    assert needs_context("why?", HIST)
    assert needs_context("इसका मतलब क्या है", HIST)
    assert not needs_context("What does the book say about the role of the guru in devotion?", HIST)
    assert not needs_context("Summarize this", None)


def test_condense_uses_history_and_returns_standalone(llm):
    llm.scripted.append("Summarize in one sentence how a seeker can cultivate prema.")
    out, usage = condense_question("Summarize this in one sentence.", HIST)
    assert out == "Summarize in one sentence how a seeker can cultivate prema."
    assert usage.prompt_tokens > 0
    sent = llm.calls[-1][1]["content"]
    assert "cultivate prema" in sent and "LATEST MESSAGE: Summarize this" in sent


def test_condense_returns_none_when_unchanged_or_mock(llm):
    llm.scripted.append("why?")
    assert condense_question("why?", HIST)[0] is None
    assert condense_question("why?", HIST)[0] is None  # "[mock answer]" fallback
