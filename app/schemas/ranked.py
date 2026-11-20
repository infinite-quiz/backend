from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Difficulty = Literal["easy", "medium", "hard"]
MatchStatus = Literal[
    "lobby",
    "banning",
    "ready_check",
    "in_progress",
    "finished",
    "cancelled",
]
QueueStatus = Literal["searching", "matched", "cancelled", "expired"]
CurrentStatus = Literal["idle", "searching", "matched"]


class CreateMatchRequest(BaseModel):
    user_id: str | None = Field(default=None, max_length=36)
    display_name: str | None = Field(default=None, max_length=100)
    topic_candidates: list[str] = Field(
        default_factory=lambda: ["Космос", "История", "Наука", "Кино", "Спорт"],
        min_length=2,
        max_length=10,
    )
    difficulty: Difficulty = "medium"
    round_count: int = Field(default=5, ge=1, le=20)
    round_seconds: int = Field(default=20, ge=5, le=120)
    language: str = "ru"


class JoinMatchRequest(BaseModel):
    user_id: str | None = Field(default=None, max_length=36)
    display_name: str | None = Field(default=None, max_length=100)
    invite_code: str | None = Field(default=None, max_length=12)


class QueueRequest(BaseModel):
    user_id: str | None = Field(default=None, max_length=36)
    display_name: str | None = Field(default=None, max_length=100)


class LeaveMatchRequest(BaseModel):
    user_id: str | None = Field(default=None, max_length=36)


class MatchPlayerPublic(BaseModel):
    id: str
    user_id: str
    slot: int
    display_name: str
    is_ready: bool
    is_connected: bool
    score: int
    banned_topics: list[str]
    ban_submitted: bool = False


class CurrentQuestionPublic(BaseModel):
    question_id: str
    round: int
    round_index: int
    text: str
    options: list[str]
    deadline_ts: float
    server_now_ts: float
    round_seconds: int


class OwnAnswerPublic(BaseModel):
    question_id: str
    selected_index: int


class MatchResponse(BaseModel):
    match_id: str
    status: MatchStatus
    invite_code: str
    topic: str | None
    difficulty: Difficulty
    round_count: int
    current_round: int
    round_seconds: int
    banned_topics: list[str]
    topic_candidates: list[str] | None = None
    players: list[MatchPlayerPublic]
    ws_url: str
    created_at: datetime
    max_bans: int = 1
    finish_reason: str | None = None
    # reconnect snapshot (viewer-specific fields filled when known)
    current_question: CurrentQuestionPublic | None = None
    own_answer: OwnAnswerPublic | None = None
    last_round_result: dict[str, Any] | None = None
    rating_delta: int | None = None


class QueueTicketResponse(BaseModel):
    ticket_id: str
    status: QueueStatus
    revision: int = 1
    match_id: str | None = None
    ws_url: str | None = None
    reason: str | None = None


class RankedCurrentResponse(BaseModel):
    status: CurrentStatus
    ticket_id: str | None = None
    match_id: str | None = None
    ws_url: str | None = None
    queue: QueueTicketResponse | None = None
    match: MatchResponse | None = None
