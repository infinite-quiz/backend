from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user_optional
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter()


@router.get("/leaderboard")
def leaderboard(
    rank: str = Query(default="all"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    q = db.query(User).order_by(User.rank_points.desc()).limit(50)
    if rank != "all":
        q = q.filter(User.rank_tier == rank)
    rows = q.all()
    leaders = [
        {
            "userId": u.id,
            "displayName": u.display_name or u.username,
            "rank": u.rank_tier,
            "rankPoints": u.rank_points,
            "place": i + 1,
        }
        for i, u in enumerate(rows)
    ]
    me = None
    if user is not None:
        place = next((i + 1 for i, u in enumerate(rows) if u.id == user.id), None)
        me = {
            "userId": user.id,
            "displayName": user.display_name or user.username,
            "rank": user.rank_tier,
            "rankPoints": user.rank_points,
            "place": place,
            "movement": 0,
        }
    return {"leaders": leaders, "me": me, "others": []}
