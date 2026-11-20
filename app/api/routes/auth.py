from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps_auth import get_current_user, get_session_token
from app.db.models.user import User
from app.db.session import get_db
from app.services import auth_service

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    displayName: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: str
    password: str


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=auth_service.COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 14,
    )


@router.post("/register")
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    user = auth_service.register_user(db, payload.email, payload.password, payload.displayName)
    token = auth_service.create_session(user.id)
    _set_cookie(response, token)
    return {"user": auth_service.public_profile(user)}


@router.post("/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = auth_service.login_user(db, payload.email, payload.password)
    token = auth_service.create_session(user.id)
    _set_cookie(response, token)
    return {"user": auth_service.public_profile(user)}


@router.post("/refresh")
def refresh(response: Response, token: str | None = Depends(get_session_token)):
    new_token = auth_service.refresh_session(token)
    _set_cookie(response, new_token)
    return {"status": "ok"}


@router.post("/logout")
def logout(response: Response, token: str | None = Depends(get_session_token)):
    auth_service.destroy_session(token)
    response.delete_cookie(auth_service.COOKIE_NAME)
    return {"status": "ok"}


@router.get("/me")
def me_via_auth(user: User = Depends(get_current_user)):
    return auth_service.public_profile(user)
