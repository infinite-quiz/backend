from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.quiz import (
    AnswerRequest,
    AnswerResponse,
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
    QuizSessionResponse,
    StartQuizRequest,
    StartQuizResponse,
)
from app.services import quiz_service
from app.services.generator import generate_questions

router = APIRouter()


@router.post(
    "/generate",
    response_model=GenerateQuestionsResponse,
    summary="Generate quiz questions (stub / ML)",
)
async def generate(payload: GenerateQuestionsRequest) -> GenerateQuestionsResponse:
    """Stub endpoint for question generation.

    Currently returns template questions tagged with topic/difficulty.
    Switch `GENERATOR_MODE=http` to call the ML service.
    """
    return await generate_questions(payload)


@router.post("/start", response_model=StartQuizResponse, summary="Start a quiz session")
async def start(payload: StartQuizRequest, db: Session = Depends(get_db)) -> StartQuizResponse:
    return await quiz_service.start_quiz(db, payload)


@router.get("/{session_id}", response_model=QuizSessionResponse, summary="Get quiz session")
def get_quiz(session_id: str, db: Session = Depends(get_db)) -> QuizSessionResponse:
    return quiz_service.get_session(db, session_id)


@router.post(
    "/{session_id}/answer",
    response_model=AnswerResponse,
    summary="Submit an answer",
)
def answer(
    session_id: str,
    payload: AnswerRequest,
    db: Session = Depends(get_db),
) -> AnswerResponse:
    return quiz_service.answer_question(db, session_id, payload)
