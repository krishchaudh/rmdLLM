"""Signed-in users: their chat history (list / open / rename / delete / claim)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from rmd.db import get_db
from rmd.logging import get_logger
from rmd.models import Conversation, Message
from rmd.users import UserIdentity, require_user

log = get_logger("rmd.me")
router = APIRouter(prefix="/me", tags=["me"])


class ConversationSummary(BaseModel):
    id: uuid.UUID
    title: str | None
    language: str | None
    message_count: int
    created_at: str
    updated_at: str


class RenameIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)


def _own(db: Session, user: UserIdentity, conversation_id: uuid.UUID) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.get("", response_model=dict)
def me(user: UserIdentity = Depends(require_user)):
    return {"id": user.id, "email": user.email}


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(user: UserIdentity = Depends(require_user), db: Session = Depends(get_db)):
    count = (
        select(Message.conversation_id, func.count().label("n"))
        .group_by(Message.conversation_id)
        .subquery()
    )
    rows = db.execute(
        select(Conversation, func.coalesce(count.c.n, 0))
        .outerjoin(count, count.c.conversation_id == Conversation.id)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(300)
    ).all()
    return [
        ConversationSummary(
            id=c.id,
            title=c.title,
            language=c.language,
            message_count=n,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )
        for c, n in rows
    ]


@router.patch("/conversations/{conversation_id}", response_model=ConversationSummary)
def rename_conversation(
    conversation_id: uuid.UUID,
    body: RenameIn,
    user: UserIdentity = Depends(require_user),
    db: Session = Depends(get_db),
):
    conv = _own(db, user, conversation_id)
    conv.title = body.title.strip()
    db.commit()
    n = db.scalar(select(func.count()).where(Message.conversation_id == conv.id)) or 0
    return ConversationSummary(
        id=conv.id,
        title=conv.title,
        language=conv.language,
        message_count=n,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: uuid.UUID,
    user: UserIdentity = Depends(require_user),
    db: Session = Depends(get_db),
):
    conv = _own(db, user, conversation_id)
    db.delete(conv)
    db.commit()


@router.post("/conversations/{conversation_id}/claim", status_code=204)
def claim_conversation(
    conversation_id: uuid.UUID,
    user: UserIdentity = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Attach a guest conversation (started before signing in) to this account."""
    conv = db.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    if conv.user_id is not None and conv.user_id != user.id:
        raise HTTPException(403, "This conversation belongs to another account")
    conv.user_id = user.id
    db.commit()


@router.delete("/conversations", status_code=204)
def delete_all_conversations(
    user: UserIdentity = Depends(require_user), db: Session = Depends(get_db)
):
    ids = db.scalars(select(Conversation.id).where(Conversation.user_id == user.id)).all()
    if ids:
        db.execute(delete(Message).where(Message.conversation_id.in_(ids)))
        db.execute(delete(Conversation).where(Conversation.id.in_(ids)))
    db.commit()
    log.info("history_deleted", user_id=str(user.id), conversations=len(ids))


@router.delete("", response_model=dict)
def delete_account(user: UserIdentity = Depends(require_user), db: Session = Depends(get_db)):
    """Delete all history, then (best effort) the auth account itself. The API's database
    role may not be allowed to touch auth.users; the client signs out either way."""
    delete_all_conversations(user, db)
    account_deleted = False
    try:
        with db.begin_nested():
            db.execute(text("DELETE FROM auth.users WHERE id = :id"), {"id": str(user.id)})
        db.commit()
        account_deleted = True
    except Exception as exc:
        db.rollback()
        log.warning("auth_user_delete_failed", error=type(exc).__name__)
    return {"history_deleted": True, "account_deleted": account_deleted}
