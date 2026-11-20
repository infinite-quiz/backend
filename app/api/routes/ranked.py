from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user_optional, resolve_user_id
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.ranked import (
    CreateMatchRequest,
    JoinMatchRequest,
    LeaveMatchRequest,
    MatchResponse,
    QueueRequest,
    QueueTicketResponse,
    RankedCurrentResponse,
)
from app.services import queue_service, ranked_service

router = APIRouter()


def _uid(payload_user_id: str | None, user: User | None) -> str:
    if user is not None:
        return user.id
    if payload_user_id:
        return payload_user_id
    from fastapi import HTTPException

    raise HTTPException(status_code=401, detail="user_id or session required")


@router.post("/queue", response_model=QueueTicketResponse, summary="Start ranked matchmaking")
def enqueue(
    payload: QueueRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> QueueTicketResponse:
    user_id = _uid(payload.user_id, user)
    display = payload.display_name or (user.display_name if user else None)
    return queue_service.enqueue(db, user_id, display)


@router.delete("/queue/{ticket_id}", response_model=QueueTicketResponse, summary="Cancel search")
def cancel_queue(
    ticket_id: str,
    user: User | None = Depends(get_current_user_optional),
    user_id: str | None = Query(default=None),
) -> QueueTicketResponse:
    uid = _uid(user_id, user)
    return queue_service.cancel(ticket_id, uid)


@router.get("/current", response_model=RankedCurrentResponse, summary="Restore search or match")
def current(
    db: Session = Depends(get_db),
    uid: str = Depends(resolve_user_id),
) -> RankedCurrentResponse:
    return queue_service.get_current(db, uid)


@router.post("/matches", response_model=MatchResponse, summary="Create ranked match (invite)")
def create_match(
    payload: CreateMatchRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> MatchResponse:
    data = payload.model_copy(update={"user_id": _uid(payload.user_id, user)})
    return ranked_service.create_match(db, data)


@router.post("/matches/join", response_model=MatchResponse, summary="Join by invite_code")
def join_by_code(
    payload: JoinMatchRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> MatchResponse:
    data = payload.model_copy(update={"user_id": _uid(payload.user_id, user)})
    return ranked_service.join_by_code(db, data)


@router.post("/matches/{match_id}/join", response_model=MatchResponse, summary="Join by id")
def join_match(
    match_id: str,
    payload: JoinMatchRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> MatchResponse:
    data = payload.model_copy(update={"user_id": _uid(payload.user_id, user)})
    return ranked_service.join_match(db, match_id, data)


@router.get("/matches/{match_id}", response_model=MatchResponse, summary="Get match snapshot")
def get_match(
    match_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
    user_id: str | None = Query(default=None),
) -> MatchResponse:
    viewer = user.id if user else user_id
    return ranked_service.get_match(db, match_id, viewer_user_id=viewer)


@router.post("/matches/{match_id}/leave", response_model=MatchResponse, summary="Leave / surrender")
async def leave_match(
    match_id: str,
    payload: LeaveMatchRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> MatchResponse:
    uid = _uid(payload.user_id, user)
    return await ranked_service.leave_match(db, match_id, uid)
