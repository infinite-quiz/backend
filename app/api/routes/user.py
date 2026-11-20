from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps_auth import get_current_user
from app.db.models.user import User
from app.services import auth_service

router = APIRouter()


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return auth_service.public_profile(user)


@router.get("/me/statistics")
def statistics(
    period: str = Query(default="all", pattern="^(week|month|all)$"),
    expected_user_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
):
    if expected_user_id and expected_user_id != user.id:
        raise HTTPException(status_code=403, detail="expected_user_id mismatch")
    return {
        "period": period,
        "gamesPlayed": 0,
        "wins": 0,
        "accuracy": 0.0,
        "byTopic": [],
        "activity": [],
    }


@router.get("/me/achievements")
def achievements(
    filter: str = Query(default="all", pattern="^(all|received|progress)$"),
    expected_user_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
):
    if expected_user_id and expected_user_id != user.id:
        raise HTTPException(status_code=403, detail="expected_user_id mismatch")
    return {
        "filter": filter,
        "summary": {"received": 0, "total": 0},
        "items": [],
        "nearest": None,
    }
