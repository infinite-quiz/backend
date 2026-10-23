from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Difficulty = Literal["easy", "medium", "hard"]
SessionStatus = Literal["active", "finished", "abandoned"]


class GenerateQuestionsRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=255, examples=["Космос"])
    count: int = Field(..., ge=1, le=20, examples=[5])
    difficulty: Difficulty = Field(default="medium", examples=["medium"])
    language: str = Field(default="ru", min_length=2, max_length=5)


class GeneratedQuestion(BaseModel):
    text: str
    options: list[str] = Field(..., min_length=2, max_length=6)
    correct_index: int = Field(..., ge=0)
    explanation: str | None = None

    @field_validator("options")
    @classmethod
    def options_non_empty(cls, value: list[str]) -> list[str]:
        if any(not opt.strip() for opt in value):
            raise ValueError("options must be non-empty strings")
        return value

    @field_validator("correct_index")
    @classmethod
    def correct_in_range(cls, value: int, info) -> int:
        options = info.data.get("options")
        if options is not None and not (0 <= value < len(options)):
            raise ValueError("correct_index out of options range")
        return value


class GenerateQuestionsResponse(BaseModel):
    topic: str
    difficulty: Difficulty
    count: int
    questions: list[GeneratedQuestion]
    source: Literal["stub", "ml"] = "stub"


class StartQuizRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=255)
    count: int = Field(default=5, ge=1, le=20)
    difficulty: Difficulty = "medium"
    player_name: str | None = Field(default=None, max_length=100)
    user_id: str | None = Field(default=None, max_length=36)
    language: str = "ru"


class QuestionPublic(BaseModel):
    id: str
    order_index: int
    text: str
    options: list[str]


class StartQuizResponse(BaseModel):
    session_id: str
    topic: str
    difficulty: Difficulty
    lives_total: int
    lives_left: int
    score: int
    status: SessionStatus
    user_id: str | None = None
    questions: list[QuestionPublic]


class AnswerRequest(BaseModel):
    question_id: str
    selected_index: int = Field(..., ge=0)


class AnswerResponse(BaseModel):
    session_id: str
    question_id: str
    is_correct: bool
    correct_index: int
    lives_left: int
    score: int
    status: SessionStatus
    explanation: str | None = None


class QuizSessionResponse(BaseModel):
    id: str
    topic: str
    difficulty: Difficulty
    requested_count: int
    lives_total: int
    lives_left: int
    score: int
    status: SessionStatus
    player_name: str | None
    user_id: str | None = None
    created_at: datetime
    finished_at: datetime | None
    questions: list[QuestionPublic]
