"""Solo result sync for frontend outbox."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.api.deps_auth import get_current_user_optional
from app.db.models.quiz import Answer, QuizSession
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter()

_SAVED: set[str] = set()


class SoloAnswerItem(BaseModel):
    question_id: str
    selected_index: int
    answered_at: datetime | None = None


class SoloResultRequest(BaseModel):
    version: int = 1
    user_id: str | None = None
    session_id: str
    completed_at: datetime | None = None
    answers: list[SoloAnswerItem] = Field(default_factory=list)


@router.post("/results")
def save_solo_results(
    payload: SoloResultRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    key = idempotency_key or f"{payload.session_id}:{payload.user_id or (user.id if user else '')}"
    if key in _SAVED:
        return {"session_id": payload.session_id, "status": "saved"}

    expected = payload.user_id or (user.id if user else None)
    session = (
        db.query(QuizSession)
        .options(joinedload(QuizSession.questions), joinedload(QuizSession.answers))
        .filter(QuizSession.id == payload.session_id)
        .one_or_none()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if expected and session.user_id and session.user_id != expected:
        raise HTTPException(status_code=403, detail="Session belongs to another user")

    # already fully answered — idempotent
    if session.answers:
        _SAVED.add(key)
        return {"session_id": payload.session_id, "status": "saved"}

    by_id = {q.id: q for q in session.questions}
    for item in payload.answers:
        q = by_id.get(item.question_id)
        if q is None:
            continue
        if any(a.question_id == item.question_id for a in session.answers):
            continue
        is_correct = item.selected_index == q.correct_index
        db.add(
            Answer(
                session_id=session.id,
                question_id=q.id,
                selected_index=item.selected_index,
                is_correct=is_correct,
            )
        )
        if is_correct:
            session.score += 1
        else:
            session.lives_left = max(0, session.lives_left - 1)

    db.commit()
    _SAVED.add(key)
    return {"session_id": payload.session_id, "status": "saved"}
