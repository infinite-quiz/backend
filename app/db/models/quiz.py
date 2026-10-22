from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base


class Difficulty(str, enum.Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class SessionStatus(str, enum.Enum):
    active = "active"
    finished = "finished"
    abandoned = "abandoned"


def _uuid() -> str:
    return str(uuid.uuid4())


class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    difficulty: Mapped[Difficulty] = mapped_column(
        Enum(Difficulty, name="difficulty_enum"),
        nullable=False,
        default=Difficulty.medium,
    )
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False)
    lives_total: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    lives_left: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status_enum"),
        nullable=False,
        default=SessionStatus.active,
    )
    player_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    questions: Mapped[list[Question]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Question.order_index",
    )
    answers: Mapped[list[Answer]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSON, nullable=False)
    correct_index: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped[QuizSession] = relationship(back_populates="questions")
    answers: Mapped[list[Answer]] = relationship(back_populates="question")


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selected_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[QuizSession] = relationship(back_populates="answers")
    question: Mapped[Question] = relationship(back_populates="answers")
