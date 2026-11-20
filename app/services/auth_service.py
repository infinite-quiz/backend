"""Simple cookie-session auth for frontend contracts."""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.user import User

COOKIE_NAME = "quiz_session"


@dataclass
class SessionRecord:
    token: str
    user_id: str
    expires_at: float


_SESSIONS: dict[str, SessionRecord] = {}


def hash_password(password: str) -> str:
    salt = secrets.token_hex(8)
    digest = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash or "$" not in password_hash:
        return False
    salt, digest = password_hash.split("$", 1)
    check = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return secrets.compare_digest(check, digest)


def create_session(user_id: str) -> str:
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = SessionRecord(
        token=token,
        user_id=user_id,
        expires_at=time.time() + settings.session_ttl_sec,
    )
    return token


def destroy_session(token: str | None) -> None:
    if token:
        _SESSIONS.pop(token, None)


def refresh_session(token: str | None) -> str:
    if not token or token not in _SESSIONS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    rec = _SESSIONS[token]
    if rec.expires_at < time.time():
        _SESSIONS.pop(token, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    # rotate
    _SESSIONS.pop(token, None)
    return create_session(rec.user_id)


def user_id_from_token(token: str | None) -> str | None:
    if not token:
        return None
    rec = _SESSIONS.get(token)
    if rec is None or rec.expires_at < time.time():
        if token in _SESSIONS:
            _SESSIONS.pop(token, None)
        return None
    return rec.user_id


def register_user(db: Session, email: str, password: str, display_name: str) -> User:
    email_n = email.strip().lower()
    exists = db.query(User).filter(User.email == email_n).one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Email already registered")
    username = email_n.split("@")[0][:80]
    if db.query(User).filter(User.username == username).first():
        username = f"{username}_{secrets.token_hex(3)}"
    user = User(
        email=email_n,
        username=username,
        display_name=display_name.strip() or username,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_user(db: Session, email: str, password: str) -> User:
    email_n = email.strip().lower()
    user = db.query(User).filter(User.email == email_n).one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user


def public_profile(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "displayName": user.display_name or user.username,
        "username": user.username,
        "level": user.level,
        "energy": user.energy,
        "streakDays": user.streak_days,
        "rank": user.rank_tier,
        "rankPoints": user.rank_points,
    }
