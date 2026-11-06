"""Ranked match REST helpers + round engine."""

from __future__ import annotations

import asyncio
import secrets
import string
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.db.models.ranked import (
    Match,
    MatchPlayer,
    MatchStatus,
    Round,
    RoundAnswer,
    RoundStatus,
)
from app.db.models.user import User
from app.db.session import SessionLocal
from app.schemas.quiz import GenerateQuestionsRequest
from app.schemas.ranked import (
    CreateMatchRequest,
    JoinMatchRequest,
    MatchPlayerPublic,
    MatchResponse,
)
from app.services.generator import generate_questions
from app.services.ws_manager import ws_manager

# match_id -> topic candidates chosen at create
_TOPIC_CANDIDATES: dict[str, list[str]] = {}
# match_id -> asyncio.Task for round timer
_ROUND_TIMERS: dict[str, asyncio.Task] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _invite_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _ws_url(match_id: str) -> str:
    settings = get_settings()
    return f"{settings.public_ws_base_url}/ws/ranked/{match_id}"


def _ensure_user(db: Session, user_id: str, display_name: str | None) -> User:
    user = db.get(User, user_id)
    if user is None:
        name = (display_name or f"player_{user_id[:6]}").strip() or f"player_{user_id[:6]}"
        # username must be unique — prefix with id slice if collision
        base = name[:80]
        username = base
        exists = db.query(User).filter(User.username == username).first()
        if exists:
            username = f"{base}_{user_id[:6]}"
        user = User(id=user_id, username=username, display_name=name)
        db.add(user)
        db.flush()
    elif display_name and not user.display_name:
        user.display_name = display_name
    return user


def _player_public(p: MatchPlayer) -> MatchPlayerPublic:
    return MatchPlayerPublic(
        id=p.id,
        user_id=p.user_id,
        slot=p.slot,
        display_name=p.display_name,
        is_ready=p.is_ready,
        is_connected=p.is_connected,
        score=p.score,
        banned_topics=list(p.banned_topics or []),
    )


def serialize_match(db: Session, match: Match) -> MatchResponse:
    match = (
        db.query(Match)
        .options(joinedload(Match.players))
        .filter(Match.id == match.id)
        .one()
    )
    return MatchResponse(
        match_id=match.id,
        status=match.status.value,
        invite_code=match.invite_code,
        topic=match.topic,
        difficulty=match.difficulty,  # type: ignore[arg-type]
        round_count=match.round_count,
        current_round=match.current_round,
        round_seconds=match.round_seconds,
        banned_topics=list(match.banned_topics or []),
        topic_candidates=_TOPIC_CANDIDATES.get(match.id),
        players=[_player_public(p) for p in match.players],
        ws_url=_ws_url(match.id),
        created_at=match.created_at,
    )


def match_state_payload(db: Session, match: Match) -> dict:
    data = serialize_match(db, match)
    return {"type": "match_state", **data.model_dump(mode="json")}


def create_match(db: Session, payload: CreateMatchRequest) -> MatchResponse:
    settings = get_settings()
    user = _ensure_user(db, payload.user_id, payload.display_name)

    match = Match(
        status=MatchStatus.lobby,
        difficulty=payload.difficulty,
        language=payload.language,
        round_count=payload.round_count or settings.ranked_default_rounds,
        round_seconds=payload.round_seconds or settings.ranked_round_seconds,
        banned_topics=[],
        invite_code=_invite_code(),
        host_user_id=user.id,
    )
    db.add(match)
    db.flush()

    player = MatchPlayer(
        match_id=match.id,
        user_id=user.id,
        slot=1,
        display_name=user.display_name or user.username,
        banned_topics=[],
    )
    db.add(player)
    db.commit()

    _TOPIC_CANDIDATES[match.id] = list(payload.topic_candidates)
    return serialize_match(db, match)


def join_match(db: Session, match_id: str, payload: JoinMatchRequest) -> MatchResponse:
    match = (
        db.query(Match)
        .options(joinedload(Match.players))
        .filter(Match.id == match_id)
        .one_or_none()
    )
    if match is None and payload.invite_code:
        match = (
            db.query(Match)
            .options(joinedload(Match.players))
            .filter(Match.invite_code == payload.invite_code.upper())
            .one_or_none()
        )
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    if match.status not in {MatchStatus.lobby, MatchStatus.banning}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Match not joinable")
    if any(p.user_id == payload.user_id for p in match.players):
        return serialize_match(db, match)
    if len(match.players) >= 2:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Match is full")

    user = _ensure_user(db, payload.user_id, payload.display_name)
    db.add(
        MatchPlayer(
            match_id=match.id,
            user_id=user.id,
            slot=2,
            display_name=user.display_name or user.username,
            banned_topics=[],
        )
    )
    match.status = MatchStatus.banning
    db.commit()
    return serialize_match(db, match)


def join_by_code(db: Session, payload: JoinMatchRequest) -> MatchResponse:
    if not payload.invite_code:
        raise HTTPException(status_code=400, detail="invite_code required")
    match = (
        db.query(Match)
        .options(joinedload(Match.players))
        .filter(Match.invite_code == payload.invite_code.upper())
        .one_or_none()
    )
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return join_match(db, match.id, payload)


def get_match(db: Session, match_id: str) -> MatchResponse:
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return serialize_match(db, match)


async def broadcast_match_state(match_id: str) -> None:
    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        if match is None:
            return
        await ws_manager.broadcast(match_id, match_state_payload(db, match))
    finally:
        db.close()


def _cancel_timer(match_id: str) -> None:
    task = _ROUND_TIMERS.pop(match_id, None)
    if task and not task.done():
        task.cancel()


async def _schedule_round_close(match_id: str, round_id: str, delay: float) -> None:
    try:
        await asyncio.sleep(delay)
        await close_round(match_id, round_id, reason="timeout")
    except asyncio.CancelledError:
        return


async def handle_ws_event(match_id: str, user_id: str, event: dict) -> None:
    etype = event.get("type")
    db = SessionLocal()
    try:
        match = (
            db.query(Match)
            .options(joinedload(Match.players), joinedload(Match.rounds))
            .filter(Match.id == match_id)
            .one_or_none()
        )
        if match is None:
            await ws_manager.send_user(match_id, user_id, {"type": "error", "detail": "Match not found"})
            return

        player = next((p for p in match.players if p.user_id == user_id), None)
        if player is None:
            await ws_manager.send_user(match_id, user_id, {"type": "error", "detail": "Not a player"})
            return

        if etype == "join":
            player.is_connected = True
            db.commit()
            await ws_manager.broadcast(match_id, match_state_payload(db, match))
            if match.status == MatchStatus.banning:
                await ws_manager.broadcast(
                    match_id,
                    {
                        "type": "ban_phase",
                        "topic_candidates": _TOPIC_CANDIDATES.get(match_id, []),
                        "max_bans": 1,
                    },
                )
            return

        if etype == "ban_topics":
            topics = event.get("topics") or []
            if not isinstance(topics, list):
                await ws_manager.send_user(match_id, user_id, {"type": "error", "detail": "topics must be list"})
                return
            if match.status in {
                MatchStatus.in_progress,
                MatchStatus.finished,
                MatchStatus.cancelled,
            }:
                await ws_manager.send_user(match_id, user_id, {"type": "error", "detail": "Ban phase closed"})
                return
            # allow bans until match actually starts (lobby/banning/ready_check)
            if match.status != MatchStatus.ready_check:
                match.status = MatchStatus.banning
            player.banned_topics = [str(t) for t in topics][:3]
            # merge bans
            merged: list[str] = []
            for p in match.players:
                for t in p.banned_topics or []:
                    if t not in merged:
                        merged.append(t)
            match.banned_topics = merged
            db.commit()
            await ws_manager.broadcast(
                match_id,
                {
                    "type": "ban_update",
                    "by_user_id": user_id,
                    "banned_topics": match.banned_topics,
                    "players": [_player_public(p).model_dump() for p in match.players],
                },
            )
            return

        if etype == "ready":
            player.is_ready = True
            match.status = MatchStatus.ready_check
            db.commit()
            await ws_manager.broadcast(match_id, match_state_payload(db, match))
            if len(match.players) == 2 and all(p.is_ready for p in match.players):
                await start_match(db, match)
            return

        if etype == "answer":
            await submit_answer(db, match, player, event)
            return

        await ws_manager.send_user(
            match_id, user_id, {"type": "error", "detail": f"Unknown event: {etype}"}
        )
    finally:
        db.close()


async def start_match(db: Session, match: Match) -> None:
    candidates = _TOPIC_CANDIDATES.get(match.id) or ["Общие знания"]
    banned = set(match.banned_topics or [])
    available = [t for t in candidates if t not in banned] or candidates
    topic = available[0]
    match.topic = topic
    match.status = MatchStatus.in_progress
    match.started_at = _now()
    match.current_round = 0

    generated = await generate_questions(
        GenerateQuestionsRequest(
            topic=topic,
            count=match.round_count,
            difficulty=match.difficulty,  # type: ignore[arg-type]
            language=match.language,
        )
    )

    # clear old rounds if any
    for r in list(match.rounds):
        db.delete(r)
    db.flush()

    for idx, q in enumerate(generated.questions):
        db.add(
            Round(
                match_id=match.id,
                round_index=idx,
                status=RoundStatus.pending,
                question_text=q.text,
                options=list(q.options),
                correct_index=q.correct_index,
                explanation=q.explanation,
            )
        )
    db.commit()

    await ws_manager.broadcast(
        match.id,
        {
            "type": "match_start",
            "match_id": match.id,
            "topic": topic,
            "round_count": match.round_count,
            "round_seconds": match.round_seconds,
        },
    )
    await open_round(match.id, 0)


async def open_round(match_id: str, round_index: int) -> None:
    db = SessionLocal()
    try:
        match = (
            db.query(Match)
            .options(joinedload(Match.rounds), joinedload(Match.players))
            .filter(Match.id == match_id)
            .one_or_none()
        )
        if match is None or match.status != MatchStatus.in_progress:
            return

        rnd = next((r for r in match.rounds if r.round_index == round_index), None)
        if rnd is None:
            await finish_match(db, match)
            return

        now = _now()
        deadline = now + timedelta(seconds=match.round_seconds)
        rnd.status = RoundStatus.active
        rnd.started_at = now
        rnd.deadline_at = deadline
        match.current_round = round_index
        db.commit()

        payload = {
            "type": "question",
            "match_id": match_id,
            "round": round_index + 1,
            "round_index": round_index,
            "question_id": rnd.id,
            "text": rnd.question_text,
            "options": list(rnd.options),
            "deadline_ts": deadline.timestamp(),
            "server_now_ts": now.timestamp(),
            "round_seconds": match.round_seconds,
        }
        await ws_manager.broadcast(match_id, payload)

        _cancel_timer(match_id)
        delay = max(0.1, (deadline - _now()).total_seconds())
        _ROUND_TIMERS[match_id] = asyncio.create_task(
            _schedule_round_close(match_id, rnd.id, delay)
        )
    finally:
        db.close()


async def submit_answer(db: Session, match: Match, player: MatchPlayer, event: dict) -> None:
    if match.status != MatchStatus.in_progress:
        await ws_manager.send_user(
            match.id, player.user_id, {"type": "error", "detail": "Match not in progress"}
        )
        return

    question_id = event.get("question_id")
    selected = event.get("selected_index")
    if question_id is None or selected is None:
        await ws_manager.send_user(
            match.id, player.user_id, {"type": "error", "detail": "question_id and selected_index required"}
        )
        return

    rnd = next((r for r in match.rounds if r.id == question_id), None)
    if rnd is None or rnd.status != RoundStatus.active:
        await ws_manager.send_user(
            match.id, player.user_id, {"type": "error", "detail": "Round not active"}
        )
        return

    if any(a.player_id == player.id for a in rnd.answers):
        await ws_manager.send_user(
            match.id, player.user_id, {"type": "error", "detail": "Already answered"}
        )
        return

    try:
        selected_index = int(selected)
    except (TypeError, ValueError):
        await ws_manager.send_user(
            match.id, player.user_id, {"type": "error", "detail": "Invalid selected_index"}
        )
        return

    if selected_index < 0 or selected_index >= len(rnd.options):
        await ws_manager.send_user(
            match.id, player.user_id, {"type": "error", "detail": "selected_index out of range"}
        )
        return

    is_correct = selected_index == rnd.correct_index
    db.add(
        RoundAnswer(
            round_id=rnd.id,
            player_id=player.id,
            selected_index=selected_index,
            is_correct=is_correct,
        )
    )
    if is_correct:
        player.score += 1
    db.commit()

    await ws_manager.send_user(
        match.id,
        player.user_id,
        {
            "type": "answer_accepted",
            "question_id": rnd.id,
            "selected_index": selected_index,
        },
    )

    answered_ids = {
        row.player_id
        for row in db.query(RoundAnswer).filter(RoundAnswer.round_id == rnd.id).all()
    }
    if all(p.id in answered_ids for p in match.players):
        _cancel_timer(match.id)
        await close_round(match.id, rnd.id, reason="all_answered")


async def close_round(match_id: str, round_id: str, reason: str) -> None:
    db = SessionLocal()
    try:
        match = (
            db.query(Match)
            .options(
                joinedload(Match.players),
                joinedload(Match.rounds).joinedload(Round.answers),
            )
            .filter(Match.id == match_id)
            .one_or_none()
        )
        if match is None or match.status != MatchStatus.in_progress:
            return

        rnd = next((r for r in match.rounds if r.id == round_id), None)
        if rnd is None or rnd.status != RoundStatus.active:
            return

        rnd.status = RoundStatus.closed
        rnd.closed_at = _now()
        db.commit()

        answers_payload = []
        for p in match.players:
            ans = next((a for a in rnd.answers if a.player_id == p.id), None)
            answers_payload.append(
                {
                    "user_id": p.user_id,
                    "display_name": p.display_name,
                    "selected_index": ans.selected_index if ans else None,
                    "is_correct": ans.is_correct if ans else False,
                    "score": p.score,
                }
            )

        await ws_manager.broadcast(
            match_id,
            {
                "type": "round_result",
                "match_id": match_id,
                "round": rnd.round_index + 1,
                "round_index": rnd.round_index,
                "question_id": rnd.id,
                "correct_index": rnd.correct_index,
                "explanation": rnd.explanation,
                "reason": reason,
                "answers": answers_payload,
            },
        )

        next_index = rnd.round_index + 1
        if next_index >= match.round_count:
            await finish_match(db, match)
        else:
            await asyncio.sleep(1.5)
            await open_round(match_id, next_index)
    finally:
        db.close()


async def finish_match(db: Session, match: Match) -> None:
    _cancel_timer(match.id)
    match.status = MatchStatus.finished
    match.finished_at = _now()
    db.commit()

    ranking = sorted(
        [{"user_id": p.user_id, "display_name": p.display_name, "score": p.score} for p in match.players],
        key=lambda x: x["score"],
        reverse=True,
    )
    await ws_manager.broadcast(
        match.id,
        {
            "type": "match_finished",
            "match_id": match.id,
            "topic": match.topic,
            "ranking": ranking,
        },
    )


async def on_disconnect(match_id: str, user_id: str) -> None:
    db = SessionLocal()
    try:
        match = (
            db.query(Match)
            .options(joinedload(Match.players))
            .filter(Match.id == match_id)
            .one_or_none()
        )
        if match is None:
            return
        player = next((p for p in match.players if p.user_id == user_id), None)
        if player is None:
            return
        player.is_connected = False
        db.commit()
        await ws_manager.broadcast(
            match_id,
            {
                "type": "opponent_left",
                "user_id": user_id,
                "match_status": match.status.value,
            },
        )
        await ws_manager.broadcast(match_id, match_state_payload(db, match))
    finally:
        db.close()
