"""Quiz session lifecycle (start / answer / get)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.db.models.quiz import Answer, Difficulty, Question, QuizSession, SessionStatus
from app.schemas.quiz import (
    AnswerRequest,
    AnswerResponse,
    GenerateQuestionsRequest,
    QuestionPublic,
    QuizSessionResponse,
    StartQuizRequest,
    StartQuizResponse,
)
from app.services.generator import generate_questions


def _public_questions(session: QuizSession) -> list[QuestionPublic]:
    return [
        QuestionPublic(
            id=q.id,
            order_index=q.order_index,
            text=q.text,
            options=list(q.options),
        )
        for q in session.questions
    ]


async def start_quiz(db: Session, payload: StartQuizRequest) -> StartQuizResponse:
    settings = get_settings()
    generated = await generate_questions(
        GenerateQuestionsRequest(
            topic=payload.topic,
            count=payload.count,
            difficulty=payload.difficulty,
            language=payload.language,
        ),
        settings=settings,
    )

    session = QuizSession(
        topic=payload.topic,
        difficulty=Difficulty(payload.difficulty),
        requested_count=payload.count,
        lives_total=settings.default_lives,
        lives_left=settings.default_lives,
        score=0,
        status=SessionStatus.active,
        player_name=payload.player_name,
    )
    db.add(session)
    db.flush()

    for idx, item in enumerate(generated.questions):
        db.add(
            Question(
                session_id=session.id,
                order_index=idx,
                text=item.text,
                options=item.options,
                correct_index=item.correct_index,
                explanation=item.explanation,
            )
        )

    db.commit()
    db.refresh(session)
    session = (
        db.query(QuizSession)
        .options(joinedload(QuizSession.questions))
        .filter(QuizSession.id == session.id)
        .one()
    )

    return StartQuizResponse(
        session_id=session.id,
        topic=session.topic,
        difficulty=session.difficulty.value,
        lives_total=session.lives_total,
        lives_left=session.lives_left,
        score=session.score,
        status=session.status.value,
        questions=_public_questions(session),
    )


def get_session(db: Session, session_id: str) -> QuizSessionResponse:
    session = (
        db.query(QuizSession)
        .options(joinedload(QuizSession.questions))
        .filter(QuizSession.id == session_id)
        .one_or_none()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    return QuizSessionResponse(
        id=session.id,
        topic=session.topic,
        difficulty=session.difficulty.value,
        requested_count=session.requested_count,
        lives_total=session.lives_total,
        lives_left=session.lives_left,
        score=session.score,
        status=session.status.value,
        player_name=session.player_name,
        created_at=session.created_at,
        finished_at=session.finished_at,
        questions=_public_questions(session),
    )


def answer_question(db: Session, session_id: str, payload: AnswerRequest) -> AnswerResponse:
    session = (
        db.query(QuizSession)
        .options(joinedload(QuizSession.questions))
        .filter(QuizSession.id == session_id)
        .one_or_none()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.status != SessionStatus.active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is not active")

    question = next((q for q in session.questions if q.id == payload.question_id), None)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    already = (
        db.query(Answer)
        .filter(Answer.session_id == session_id, Answer.question_id == payload.question_id)
        .first()
    )
    if already:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Question already answered")

    if payload.selected_index >= len(question.options):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid option")

    is_correct = payload.selected_index == question.correct_index
    if is_correct:
        session.score += 1
    else:
        session.lives_left -= 1
        if session.lives_left <= 0:
            session.status = SessionStatus.finished
            session.finished_at = datetime.now(timezone.utc)

    answered_count = (
        db.query(Answer).filter(Answer.session_id == session_id).count() + 1
    )
    if session.status == SessionStatus.active and answered_count >= len(session.questions):
        session.status = SessionStatus.finished
        session.finished_at = datetime.now(timezone.utc)

    db.add(
        Answer(
            session_id=session.id,
            question_id=question.id,
            selected_index=payload.selected_index,
            is_correct=is_correct,
        )
    )
    db.commit()
    db.refresh(session)

    return AnswerResponse(
        session_id=session.id,
        question_id=question.id,
        is_correct=is_correct,
        correct_index=question.correct_index,
        lives_left=session.lives_left,
        score=session.score,
        status=session.status.value,
        explanation=question.explanation,
    )
