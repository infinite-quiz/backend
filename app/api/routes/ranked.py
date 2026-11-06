from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ranked import CreateMatchRequest, JoinMatchRequest, MatchResponse
from app.services import ranked_service

router = APIRouter()


@router.post("/matches", response_model=MatchResponse, summary="Create ranked match")
def create_match(payload: CreateMatchRequest, db: Session = Depends(get_db)) -> MatchResponse:
    return ranked_service.create_match(db, payload)


@router.post(
    "/matches/join",
    response_model=MatchResponse,
    summary="Join ranked match by invite_code",
)
def join_by_code(payload: JoinMatchRequest, db: Session = Depends(get_db)) -> MatchResponse:
    return ranked_service.join_by_code(db, payload)


@router.post(
    "/matches/{match_id}/join",
    response_model=MatchResponse,
    summary="Join ranked match by id",
)
def join_match(
    match_id: str,
    payload: JoinMatchRequest,
    db: Session = Depends(get_db),
) -> MatchResponse:
    return ranked_service.join_match(db, match_id, payload)


@router.get("/matches/{match_id}", response_model=MatchResponse, summary="Get match state")
def get_match(match_id: str, db: Session = Depends(get_db)) -> MatchResponse:
    return ranked_service.get_match(db, match_id)
