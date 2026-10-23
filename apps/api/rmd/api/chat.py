from __future__ import annotations

import json
import queue
import threading
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from rmd.config import get_settings
from rmd.db import get_db
from rmd.generation.answer import answer_question
from rmd.limiter import limiter
from rmd.models import Conversation, Feedback, Message
from rmd.users import (
    UserIdentity,
    ask_rate_key,
    current_user_optional,
    global_key,
    is_guest,
    is_signed_in,
)

router = APIRouter(tags=["chat"])


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    conversation_id: uuid.UUID | None = None
    mode: str = Field(default="hybrid", pattern="^(dense|lexical|hybrid)$")


class AskResponse(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    answer: str
    abstained: bool
    citations: list[dict]
    followups: list[str]
    language: str
    latency_ms: dict
    verification_summary: dict


class FeedbackRequest(BaseModel):
    message_id: uuid.UUID
    rating: int = Field(ge=-1, le=1)
    comment: str | None = Field(default=None, max_length=2000)
    categories: list[str] = Field(default_factory=list)


def _title_from(question: str) -> str:
    q = " ".join(question.split())
    return q if len(q) <= 80 else q[:77].rstrip() + "…"


def _load_conversation(
    db: Session, conversation_id: uuid.UUID | None, user: UserIdentity | None
) -> Conversation | None:
    """A guest conversation is open to whoever holds its id (as before); a saved one only
    to its owner."""
    if conversation_id is None:
        return None
    conv = db.get(Conversation, conversation_id)
    if conv is None:
        return None
    if conv.user_id is not None and (user is None or conv.user_id != user.id):
        raise HTTPException(403, "This conversation belongs to another account")
    return conv


def _answer_and_persist(
    db: Session, body: AskRequest, user: UserIdentity | None = None, on_event=None
) -> AskResponse:
    conv = _load_conversation(db, body.conversation_id, user)
    if conv is None:
        conv = Conversation(language=None)
        db.add(conv)
    if user is not None and conv.user_id is None:
        conv.user_id = user.id  # a guest chat continued after signing in becomes theirs
    if conv.title is None:
        conv.title = _title_from(body.question)
    db.flush()
    history_rows = db.scalars(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at)
    ).all()
    history = [{"role": m.role, "content": m.content} for m in history_rows]

    user_msg = Message(conversation_id=conv.id, role="user", content=body.question)
    db.add(user_msg)
    db.flush()

    try:
        ans = answer_question(db, body.question, mode=body.mode, history=history, on_event=on_event)
    except Exception as exc:
        db.rollback()
        raise HTTPException(503, "Answering service unavailable, please retry") from exc

    ver = ans.verification
    summary = {
        k: ver[k]
        for k in ("claims_total", "claims_unsupported", "revised", "skipped", "reason")
        if k in ver
    }
    msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=ans.answer,
        citations=ans.citations,
        abstained=ans.abstained,
        verification=ver,
        language=ans.language,
        retrieval_trace={
            "mode": ans.retrieval_mode,
            "model": ans.model,
            "followups": ans.followups,
            "translated_query": ans.translated_query,
        },
        latency_ms=ans.latency_ms,
        token_usage=ans.usage,
        estimated_cost_usd=ans.estimated_cost_usd,
    )
    conv.language = conv.language or ans.language
    db.add(msg)
    db.commit()
    return AskResponse(
        conversation_id=conv.id,
        message_id=msg.id,
        answer=ans.answer,
        abstained=ans.abstained,
        citations=ans.citations,
        followups=ans.followups,
        language=ans.language,
        latency_ms=ans.latency_ms,
        verification_summary=summary,
    )


_s = get_settings()


def _ask_limits(fn):
    """Burst limit per identity, daily limits (guests by IP, accounts by id), and a site-wide
    daily cap so a traffic spike can't run up the LLM bill."""
    fn = limiter.limit(_s.rate_limit_ask_global_daily, key_func=global_key)(fn)
    fn = limiter.limit(_s.rate_limit_ask_user_daily, key_func=ask_rate_key, exempt_when=is_guest)(
        fn
    )
    fn = limiter.limit(
        _s.rate_limit_ask_guest_daily, key_func=ask_rate_key, exempt_when=is_signed_in
    )(fn)
    return limiter.limit(_s.rate_limit_ask, key_func=ask_rate_key)(fn)


@router.post("/ask", response_model=AskResponse)
@_ask_limits
def ask(
    request: Request,
    body: AskRequest,
    db: Session = Depends(get_db),
    user: UserIdentity | None = Depends(current_user_optional),
):
    return _answer_and_persist(db, body, user)


@router.post("/ask/stream")
@_ask_limits
def ask_stream(
    request: Request,
    body: AskRequest,
    db: Session = Depends(get_db),
    user: UserIdentity | None = Depends(current_user_optional),
):
    """Server-sent events: status / token / citations events, then a final `done` event
    carrying the same payload as POST /ask (or an `error` event)."""
    q: queue.Queue[dict | None] = queue.Queue()

    def work() -> None:
        try:
            resp = _answer_and_persist(db, body, user, on_event=q.put)
            q.put({"type": "done", "response": json.loads(resp.model_dump_json())})
        except HTTPException as exc:
            q.put({"type": "error", "detail": exc.detail})
        except Exception:
            q.put({"type": "error", "detail": "Answering service unavailable, please retry"})
        finally:
            q.put(None)

    def events():
        threading.Thread(target=work, daemon=True).start()
        while True:
            try:
                ev = q.get(timeout=15)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue
            if ev is None:
                return
            yield f"event: {ev['type']}\ndata: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/feedback", status_code=201)
@limiter.limit("30/minute")
def feedback(request: Request, body: FeedbackRequest, db: Session = Depends(get_db)):
    msg = db.get(Message, body.message_id)
    if msg is None or msg.role != "assistant":
        raise HTTPException(404, "Message not found")
    db.add(
        Feedback(
            message_id=msg.id,
            rating=body.rating,
            comment=body.comment,
            reason=",".join(body.categories) or None,
        )
    )
    db.commit()
    return {"ok": True}


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: UserIdentity | None = Depends(current_user_optional),
):
    conv = _load_conversation(db, conversation_id, user)
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    msgs = db.scalars(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at)
    ).all()
    return {
        "id": conv.id,
        "title": conv.title,
        "owned": conv.user_id is not None,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "citations": m.citations,
                "abstained": m.abstained,
                "followups": (m.retrieval_trace or {}).get("followups", []),
                "created_at": m.created_at,
            }
            for m in msgs
        ],
    }
