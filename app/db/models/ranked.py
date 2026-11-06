from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class MatchStatus(str, enum.Enum):
    lobby = "lobby"
    banning = "banning"
    ready_check = "ready_check"
    in_progress = "in_progress"
    finished = "finished"
    cancelled = "cancelled"


class RoundStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    closed = "closed"


def _uuid() -> str:
    return str(uuid.uuid4())


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, name="match_status_enum"),
        nullable=False,
        default=MatchStatus.lobby,
    )
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="ru")
    round_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    current_round: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    round_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    banned_topics: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    invite_code: Mapped[str] = mapped_column(String(12), unique=True, nullable=False, index=True)
    host_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    players: Mapped[list[MatchPlayer]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="MatchPlayer.slot",
    )
    rounds: Mapped[list[Round]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="Round.round_index",
    )


class MatchPlayer(Base):
    __tablename__ = "match_players"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    match_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slot: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 or 2
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    banned_topics: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    match: Mapped[Match] = relationship(back_populates="players")
    user: Mapped[User] = relationship()
    answers: Mapped[list[RoundAnswer]] = relationship(back_populates="player")


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    match_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    round_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RoundStatus] = mapped_column(
        Enum(RoundStatus, name="round_status_enum"),
        nullable=False,
        default=RoundStatus.pending,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSON, nullable=False)
    correct_index: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    match: Mapped[Match] = relationship(back_populates="rounds")
    answers: Mapped[list[RoundAnswer]] = relationship(
        back_populates="round",
        cascade="all, delete-orphan",
    )


class RoundAnswer(Base):
    __tablename__ = "round_answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    round_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    player_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("match_players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selected_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    round: Mapped[Round] = relationship(back_populates="answers")
    player: Mapped[MatchPlayer] = relationship(back_populates="answers")
