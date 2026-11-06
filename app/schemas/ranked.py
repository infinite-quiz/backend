from datetime import datetime
from typing import Literal

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


class CreateMatchRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=36)
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
    user_id: str = Field(..., min_length=1, max_length=36)
    display_name: str | None = Field(default=None, max_length=100)
    invite_code: str | None = Field(default=None, max_length=12)


class MatchPlayerPublic(BaseModel):
    id: str
    user_id: str
    slot: int
    display_name: str
    is_ready: bool
    is_connected: bool
    score: int
    banned_topics: list[str]


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
