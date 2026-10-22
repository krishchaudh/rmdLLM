from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from rmd.db import get_db
from rmd.generation.answer import answer_question
from rmd.limiter import limiter
from rmd.models import Conversation, Feedback, Message

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


@router.post("/ask", response_model=AskResponse)
@limiter.limit("20/minute")
def ask(request: Request, body: AskRequest, db: Session = Depends(get_db)):
    conv = db.get(Conversation, body.conversation_id) if body.conversation_id else None
    if conv is None:
        conv = Conversation(language=None)
        db.add(conv)
        db.flush()
    history_rows = db.scalars(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at)
    ).all()
    history = [{"role": m.role, "content": m.content} for m in history_rows]

    user_msg = Message(conversation_id=conv.id, role="user", content=body.question)
    db.add(user_msg)
    db.flush()

    try:
        ans = answer_question(db, body.question, mode=body.mode, history=history)
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
def get_conversation(conversation_id: uuid.UUID, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    msgs = db.scalars(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at)
    ).all()
    return {
        "id": conv.id,
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
