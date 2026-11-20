from __future__ import annotations

from fastapi import Cookie, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.session import get_db
from app.services import auth_service
from fastapi import Depends


def get_session_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> str | None:
    token = request.cookies.get(auth_service.COOKIE_NAME)
    if token:
        return token
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


def get_current_user_optional(
    db: Session = Depends(get_db),
    token: str | None = Depends(get_session_token),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> User | None:
    user_id = auth_service.user_id_from_token(token)
    if user_id:
        return db.get(User, user_id)
    if x_user_id:
        return db.get(User, x_user_id)
    return None


def get_current_user(
    user: User | None = Depends(get_current_user_optional),
) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def resolve_user_id(
    user: User | None = Depends(get_current_user_optional),
    user_id: str | None = Query(default=None),
) -> str:
    if user is not None:
        return user.id
    if user_id:
        return user_id
    raise HTTPException(status_code=401, detail="user_id or session required")
