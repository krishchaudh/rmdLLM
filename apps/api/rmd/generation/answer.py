"""Grounded answer pipeline: retrieve → generate with citations → verify → revise/abstain."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from rmd.config import get_settings
from rmd.generation.condense import condense_question, needs_context
from rmd.generation.prompts import (
    SYSTEM_ANSWER,
    SYSTEM_REVISE,
    SYSTEM_VERIFY,
    format_passages,
)
from rmd.ingestion.youtube import timestamp_url
from rmd.logging import get_logger
from rmd.providers.base import Usage, estimate_cost_usd
from rmd.providers.factory import get_llm_provider
from rmd.retrieval.language import detect_language
from rmd.retrieval.search import Hit, retrieve

log = get_logger("rmd.generation")

_CITE_RE = re.compile(r"\[(\d{1,2})\]")


def _fmt_ts(s: int) -> str:
    return f"{s // 60}:{s % 60:02d}"


def hit_to_citation(n: int, h: Hit) -> dict:
    loc = h.locator
    if h.kind == "lecture":
        start, end = int(loc["start_seconds"]), int(loc.get("end_seconds") or loc["start_seconds"])
        return {
            "n": n,
            "chunk_id": str(h.chunk_id),
            "source_id": str(h.source_id),
            "kind": "lecture",
            "title": h.title,
            "language": h.language,
            "text": h.text,
            "start_seconds": start,
            "end_seconds": end,
            "where": f"{_fmt_ts(start)}–{_fmt_ts(end)}",
            "url": timestamp_url(h.youtube_id, start) if h.youtube_id else None,
            "youtube_id": h.youtube_id,
        }
    page = loc.get("page_index")
    printed = loc.get("printed_page_number")
    where = f"PDF page {page + 1}" + (f" (printed p. {printed})" if printed else "")
    return {
        "n": n,
        "chunk_id": str(h.chunk_id),
        "source_id": str(h.source_id),
        "kind": "book",
        "title": h.title,
        "language": h.language,
        "text": h.text,
        "page_index": page,
        "page_index_end": loc.get("page_index_end"),
        "printed_page_number": printed,
        "where": where,
        "url": f"/sources/{h.source_id}/pdf#page={page + 1}",
    }


@dataclass
class Answer:
    answer: str
    abstained: bool
    citations: list[dict]
    followups: list[str]
    verification: dict
    language: str
    retrieval_mode: str
    latency_ms: dict = field(default_factory=dict)
    usage: dict = field(default_factory=dict)
    estimated_cost_usd: float = 0.0
    model: str = ""
    translated_query: str | None = None
    standalone_query: str | None = None


class TokenStreamer:
    """Forwards generation deltas to a sink while holding back text the user should not see:
    a possible leading ``ABSTAIN`` marker and the trailing ``FOLLOWUPS:`` block.
    """

    _HOLD = 8  # len("ABSTAIN") + 1

    def __init__(self, sink: Callable[[str], None]) -> None:
        self._sink = sink
        self._buf = ""
        self._sent = 0
        self._stopped = False

    def push(self, delta: str) -> None:
        if self._stopped or not delta:
            return
        self._buf += delta
        if self._buf.lstrip().upper().startswith("ABSTAIN") or (
            len(self._buf.strip()) < self._HOLD and "ABSTAIN".startswith(self._buf.strip().upper())
        ):
            return  # abstention text is rendered by the server, not streamed
        cut = self._buf.find("FOLLOWUPS:")
        if cut >= 0:
            self._flush_to(len(self._buf[:cut].rstrip()))
            self._stopped = True
            return
        # keep a small tail so a split "FOLLOW" + "UPS:" marker is never leaked
        safe = len(self._buf) - len("FOLLOWUPS:")
        if safe > self._sent:
            self._flush_to(safe)

    def _flush_to(self, end: int) -> None:
        if end > self._sent:
            self._sink(self._buf[self._sent : end])
            self._sent = end


def _split_followups(text: str) -> tuple[str, list[str]]:
    if "FOLLOWUPS:" not in text:
        return text.strip(), []
    body, _, tail = text.partition("FOLLOWUPS:")
    qs = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", ln).strip() for ln in tail.strip().splitlines()]
    return body.strip(), [q for q in qs if q][:3]


def _accumulate(total: dict, u: Usage, key: str) -> None:
    total[key] = {"prompt": u.prompt_tokens, "completion": u.completion_tokens, "model": u.model}


def answer_question(
    db: Session,
    question: str,
    *,
    k: int = 8,
    mode: str = "hybrid",
    history: list[dict] | None = None,
    verify: bool = True,
    on_event: Callable[[dict], None] | None = None,
) -> Answer:
    """Answer a question. If on_event is given, progress events are emitted:
    {"type":"status","stage":...}, {"type":"token","text":...}, {"type":"citations","citations":[...]}.
    """
    emit = on_event or (lambda _e: None)
    s = get_settings()
    llm = get_llm_provider()
    lat: dict[str, float] = {}
    usage: dict = {}
    lang = detect_language(question)

    emit({"type": "status", "stage": "retrieval"})
    t = time.perf_counter()
    standalone: str | None = None
    if history and needs_context(question, history):
        standalone, cu = condense_question(question, history)
        _accumulate(usage, cu, "condense")
    rr = retrieve(db, standalone or question, k=k, mode=mode)
    lat["retrieval_ms"] = round((time.perf_counter() - t) * 1000, 1)
    _accumulate(usage, rr.usage, "embedding")
    if rr.translated_query:
        _accumulate(usage, rr.translation_usage, "translation")
    if rr.reranked:
        _accumulate(usage, rr.rerank_usage, "rerank")
    citations = [hit_to_citation(i, h) for i, h in enumerate(rr.hits, start=1)]
    emit({"type": "citations", "citations": citations})

    if not citations:
        return Answer(
            answer="I could not find any relevant passages in the available sources for this question.",
            abstained=True,
            citations=[],
            followups=[],
            verification={"skipped": "no_passages"},
            language=lang,
            retrieval_mode=mode,
            translated_query=rr.translated_query,
            standalone_query=standalone,
            latency_ms=lat,
            usage=usage,
            model=s.generation_model,
        )

    passages_block = format_passages(citations)
    convo = ""
    if history:
        convo = (
            "\n\nPREVIOUS CONVERSATION (for context only; cite passages, not this):\n"
            + "\n".join(f"{m['role']}: {m['content'][:500]}" for m in history[-6:])
        )
    lang_rule = _LANG_RULE[lang]
    lecture_ns = [c["n"] for c in citations if c["kind"] == "lecture"]
    lecture_note = ""
    if lecture_ns and len(lecture_ns) < len(citations):
        tags = "".join(f"[{n}]" for n in lecture_ns)
        lecture_note = (
            f"\n\nNOTE: passage(s) {tags} are from the spoken lecture. Where one of them supports a "
            "point you make, cite it together with the book passage (rule 7)."
        )
    user_msg = (
        f"SOURCE PASSAGES:\n{passages_block}{convo}\n\nQUESTION: {question}\n\n"
        f"ANSWER LANGUAGE: {lang_rule} (decided from THIS question, not from earlier turns)"
        f"{lecture_note}"
    )

    emit({"type": "status", "stage": "generation"})
    t = time.perf_counter()
    if on_event:
        streamer = TokenStreamer(lambda txt: emit({"type": "token", "text": txt}))
        gen = llm.chat_stream(
            _msgs(SYSTEM_ANSWER, user_msg), streamer.push, temperature=0.1, max_tokens=900
        )
    else:
        gen = llm.chat(_msgs(SYSTEM_ANSWER, user_msg), temperature=0.1, max_tokens=900)
    lat["generation_ms"] = round((time.perf_counter() - t) * 1000, 1)
    _accumulate(usage, gen.usage, "generation")
    draft = gen.text.strip()

    if draft.upper().startswith("ABSTAIN"):
        rest = draft.split("\n", 1)[1].strip() if "\n" in draft else ""
        if _CITE_RE.search(rest):
            draft = rest  # model abstained on one part but answered the rest with citations
    if draft.upper().startswith("ABSTAIN"):
        reason = _CITE_RE.sub("", rest.split("\n", 1)[0]).strip()[:300]
        return Answer(
            answer=_abstain_text(lang, reason),
            abstained=True,
            citations=citations,
            followups=[],
            verification={"skipped": "model_abstained"},
            language=lang,
            retrieval_mode=mode,
            translated_query=rr.translated_query,
            standalone_query=standalone,
            latency_ms=lat,
            usage=usage,
            estimated_cost_usd=_cost(usage),
            model=s.generation_model,
        )

    body, followups = _split_followups(draft)
    body, invalid = _drop_invalid_citations(body, len(citations))
    verification: dict = {"invalid_citations_removed": invalid}

    if verify:
        emit({"type": "status", "stage": "verification"})
        t = time.perf_counter()
        ver = llm.chat(
            _msgs(SYSTEM_VERIFY, f"SOURCE PASSAGES:\n{passages_block}\n\nDRAFT ANSWER:\n{body}"),
            temperature=0.0,
            max_tokens=900,
            json_mode=True,
            model=s.verification_model,
        )
        lat["verification_ms"] = round((time.perf_counter() - t) * 1000, 1)
        _accumulate(usage, ver.usage, "verification")
        claims = _parse_claims(ver.text)
        unsupported = [c for c in claims if c.get("verdict") == "unsupported"]
        verification.update(
            {
                "claims_total": len(claims),
                "claims_unsupported": len(unsupported),
                "claims": claims,
                "parse_ok": bool(claims) or ver.text.strip() != "",
            }
        )
        if unsupported:
            t = time.perf_counter()
            rev = llm.chat(
                _msgs(
                    SYSTEM_REVISE,
                    f"SOURCE PASSAGES:\n{passages_block}\n\nDRAFT ANSWER:\n{body}\n\nVERDICTS:\n"
                    + json.dumps(claims, ensure_ascii=False),
                ),
                temperature=0.0,
                max_tokens=900,
            )
            lat["revision_ms"] = round((time.perf_counter() - t) * 1000, 1)
            _accumulate(usage, rev.usage, "revision")
            revised = rev.text.strip()
            verification["revised"] = True
            if revised.upper().startswith("ABSTAIN"):
                return Answer(
                    answer=_abstain_text(lang, ""),
                    abstained=True,
                    citations=citations,
                    followups=[],
                    verification=verification,
                    language=lang,
                    retrieval_mode=mode,
                    translated_query=rr.translated_query,
                    standalone_query=standalone,
                    latency_ms=lat,
                    usage=usage,
                    estimated_cost_usd=_cost(usage),
                    model=s.generation_model,
                )
            body, fu2 = _split_followups(revised)
            body, _ = _drop_invalid_citations(body, len(citations))
            followups = fu2 or followups

    used = sorted({int(n) for n in _CITE_RE.findall(body)})
    if not used:
        # An answer with zero citations is not grounded → abstain rather than risk fabrication.
        return Answer(
            answer=_abstain_text(lang, ""),
            abstained=True,
            citations=citations,
            followups=[],
            verification={**verification, "reason": "no_citations_in_answer"},
            language=lang,
            retrieval_mode=mode,
            translated_query=rr.translated_query,
            standalone_query=standalone,
            latency_ms=lat,
            usage=usage,
            estimated_cost_usd=_cost(usage),
            model=s.generation_model,
        )
    cited = [c for c in citations if c["n"] in used]
    return Answer(
        answer=body,
        abstained=False,
        citations=cited,
        followups=followups,
        verification=verification,
        language=lang,
        retrieval_mode=mode,
        translated_query=rr.translated_query,
        standalone_query=standalone,
        latency_ms=lat,
        usage=usage,
        estimated_cost_usd=_cost(usage),
        model=s.generation_model,
    )


def _msgs(system: str, user: str) -> list[dict]:
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _drop_invalid_citations(body: str, n: int) -> tuple[str, list[int]]:
    invalid: list[int] = []

    def repl(m: re.Match) -> str:
        i = int(m.group(1))
        if 1 <= i <= n:
            return m.group(0)
        invalid.append(i)
        return ""

    return _CITE_RE.sub(repl, body).strip(), invalid


def _parse_claims(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
    claims = data.get("claims", []) if isinstance(data, dict) else []
    return [c for c in claims if isinstance(c, dict)]


_LANG_RULE = {
    "en": "English",
    "hi": "Hindi in Devanagari script",
    "hi-Latn": "Romanized Hindi (Hinglish) in Latin letters only, no Devanagari",
}


def _abstain_text(lang: str, reason: str) -> str:
    base = {
        "hi": "उपलब्ध स्रोतों में इस प्रश्न का उत्तर देने के लिए पर्याप्त प्रमाण नहीं मिला, इसलिए मैं उत्तर नहीं दे सकता।",
        "hi-Latn": "Uplabdh srot (book/lecture) me is prashn ka uttar dene ke liye paryapt praman nahi mila, isliye main uttar nahi de sakta.",
        "en": "I can't answer this from the available sources — the book and lecture passages I have don't contain enough evidence for it.",
    }[lang]
    return f"{base} {reason}".strip() if reason else base


def _cost(usage: dict) -> float:
    total = 0.0
    for v in usage.values():
        total += estimate_cost_usd(Usage(v["prompt"], v["completion"], v["model"])) or 0.0
    return round(total, 6)
