"""In-memory ranked matchmaking queue."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.schemas.ranked import (
    CreateMatchRequest,
    JoinMatchRequest,
    QueueTicketResponse,
    RankedCurrentResponse,
)
from app.services import ranked_service


@dataclass
class QueueTicket:
    ticket_id: str
    user_id: str
    display_name: str | None
    status: str = "searching"  # searching | matched | cancelled | expired
    revision: int = 1
    match_id: str | None = None
    ws_url: str | None = None
    reason: str | None = None
    created_at: float = field(default_factory=time.time)


_TICKETS: dict[str, QueueTicket] = {}
_USER_TICKET: dict[str, str] = {}
_WAITING: list[str] = []  # ticket_ids


def _to_response(t: QueueTicket) -> QueueTicketResponse:
    return QueueTicketResponse(
        ticket_id=t.ticket_id,
        status=t.status,  # type: ignore[arg-type]
        revision=t.revision,
        match_id=t.match_id,
        ws_url=t.ws_url,
        reason=t.reason,
    )


def enqueue(db: Session, user_id: str, display_name: str | None) -> QueueTicketResponse:
    existing_id = _USER_TICKET.get(user_id)
    if existing_id and existing_id in _TICKETS:
        t = _TICKETS[existing_id]
        if t.status in {"searching", "matched"}:
            return _to_response(t)

    ticket_id = secrets.token_urlsafe(8)
    ticket = QueueTicket(ticket_id=ticket_id, user_id=user_id, display_name=display_name)
    _TICKETS[ticket_id] = ticket
    _USER_TICKET[user_id] = ticket_id
    _WAITING.append(ticket_id)
    _try_match(db)
    return _to_response(_TICKETS[ticket_id])


def cancel(ticket_id: str, user_id: str) -> QueueTicketResponse:
    ticket = _TICKETS.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your ticket")
    if ticket.status == "matched" and ticket.match_id:
        raise HTTPException(
            status_code=409,
            detail={"message": "Match already assigned", "match_id": ticket.match_id},
        )
    ticket.status = "cancelled"
    ticket.reason = "user_cancelled"
    ticket.revision += 1
    if ticket_id in _WAITING:
        _WAITING.remove(ticket_id)
    return _to_response(ticket)


def _try_match(db: Session) -> None:
    while len(_WAITING) >= 2:
        a_id = _WAITING.pop(0)
        b_id = _WAITING.pop(0)
        a = _TICKETS[a_id]
        b = _TICKETS[b_id]
        if a.status != "searching" or b.status != "searching":
            continue
        settings = get_settings()
        host = ranked_service.create_match(
            db,
            CreateMatchRequest(
                user_id=a.user_id,
                display_name=a.display_name,
                topic_candidates=settings.ranked_topic_list,
                round_count=settings.ranked_default_rounds,
                round_seconds=settings.ranked_round_seconds,
            ),
        )
        joined = ranked_service.join_match(
            db,
            host.match_id,
            JoinMatchRequest(user_id=b.user_id, display_name=b.display_name),
        )
        for t in (a, b):
            t.status = "matched"
            t.match_id = joined.match_id
            t.ws_url = joined.ws_url
            t.revision += 1


def get_current(db: Session, user_id: str) -> RankedCurrentResponse:
    ticket_id = _USER_TICKET.get(user_id)
    ticket = _TICKETS.get(ticket_id) if ticket_id else None

    if ticket and ticket.status == "searching":
        return RankedCurrentResponse(
            status="searching",
            ticket_id=ticket.ticket_id,
            queue=_to_response(ticket),
        )

    if ticket and ticket.status == "matched" and ticket.match_id:
        match = ranked_service.get_match(db, ticket.match_id, viewer_user_id=user_id)
        return RankedCurrentResponse(
            status="matched",
            ticket_id=ticket.ticket_id,
            match_id=ticket.match_id,
            ws_url=ticket.ws_url,
            queue=_to_response(ticket),
            match=match,
        )

    # active match for user without ticket
    active = ranked_service.find_active_match_for_user(db, user_id)
    if active is not None:
        return RankedCurrentResponse(
            status="matched",
            match_id=active.match_id,
            ws_url=active.ws_url,
            match=active,
        )

    return RankedCurrentResponse(status="idle")
