"""Ranked match REST helpers + round engine."""

from __future__ import annotations

import asyncio
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any

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
    CurrentQuestionPublic,
    JoinMatchRequest,
    MatchPlayerPublic,
    MatchResponse,
    OwnAnswerPublic,
)
from app.services.generator import generate_questions
from app.services.ws_manager import ws_manager

_TOPIC_CANDIDATES: dict[str, list[str]] = {}
_ROUND_TIMERS: dict[str, asyncio.Task] = {}
_BAN_SUBMITTED: dict[str, set[str]] = {}
_LAST_ROUND_RESULT: dict[str, dict[str, Any]] = {}
_FINISH_META: dict[str, dict[str, Any]] = {}


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
        base = name[:80]
        username = base
        if db.query(User).filter(User.username == username).first():
            username = f"{base}_{user_id[:6]}"
        user = User(id=user_id, username=username, display_name=name)
        db.add(user)
        db.flush()
    elif display_name and not user.display_name:
        user.display_name = display_name
    return user


def _player_public(p: MatchPlayer, match_id: str) -> MatchPlayerPublic:
    return MatchPlayerPublic(
        id=p.id,
        user_id=p.user_id,
        slot=p.slot,
        display_name=p.display_name,
        is_ready=p.is_ready,
        is_connected=p.is_connected,
        score=p.score,
        banned_topics=list(p.banned_topics or []),
        ban_submitted=p.user_id in _BAN_SUBMITTED.get(match_id, set()),
    )


def _active_round(match: Match) -> Round | None:
    return next((r for r in match.rounds if r.status == RoundStatus.active), None)


def _closed_round_pause(match: Match) -> Round | None:
    """If waiting between rounds, last closed round may still be shown."""
    closed = [r for r in match.rounds if r.status == RoundStatus.closed]
    if not closed:
        return None
    last = max(closed, key=lambda r: r.round_index)
    if match.status == MatchStatus.in_progress and _active_round(match) is None:
        return last
    if match.status in {MatchStatus.finished, MatchStatus.cancelled}:
        return last
    return None


def serialize_match(
    db: Session,
    match: Match,
    viewer_user_id: str | None = None,
) -> MatchResponse:
    settings = get_settings()
    match = (
        db.query(Match)
        .options(
            joinedload(Match.players),
            joinedload(Match.rounds).joinedload(Round.answers),
        )
        .filter(Match.id == match.id)
        .one()
    )

    current_question = None
    own_answer = None
    active = _active_round(match)
    if active and active.deadline_at is not None:
        now = _now()
        current_question = CurrentQuestionPublic(
            question_id=active.id,
            round=active.round_index + 1,
            round_index=active.round_index,
            text=active.question_text,
            options=list(active.options),
            deadline_ts=active.deadline_at.timestamp(),
            server_now_ts=now.timestamp(),
            round_seconds=match.round_seconds,
        )
        if viewer_user_id:
            viewer = next((p for p in match.players if p.user_id == viewer_user_id), None)
            if viewer:
                ans = next((a for a in active.answers if a.player_id == viewer.id), None)
                if ans:
                    own_answer = OwnAnswerPublic(
                        question_id=active.id,
                        selected_index=ans.selected_index,
                    )

    finish_meta = _FINISH_META.get(match.id, {})
    last_result = _LAST_ROUND_RESULT.get(match.id)
    # during pause after round_result keep last result for reconnect
    if last_result is None and match.status == MatchStatus.in_progress and active is None:
        last_result = _LAST_ROUND_RESULT.get(match.id)

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
        players=[_player_public(p, match.id) for p in match.players],
        ws_url=_ws_url(match.id),
        created_at=match.created_at,
        max_bans=settings.ranked_max_bans,
        finish_reason=finish_meta.get("finish_reason"),
        current_question=current_question,
        own_answer=own_answer,
        last_round_result=last_result,
        rating_delta=finish_meta.get("rating_deltas", {}).get(viewer_user_id)
        if viewer_user_id
        else None,
    )


def match_state_payload(
    db: Session,
    match: Match,
    viewer_user_id: str | None = None,
) -> dict:
    data = serialize_match(db, match, viewer_user_id=viewer_user_id)
    return {"type": "match_state", **data.model_dump(mode="json")}


async def broadcast_match_state(match_id: str) -> None:
    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        if match is None:
            return
        uids = ws_manager.connected_user_ids(match_id)
        if not uids:
            await ws_manager.broadcast(match_id, match_state_payload(db, match))
            return
        for uid in uids:
            await ws_manager.send_user(match_id, uid, match_state_payload(db, match, uid))
    finally:
        db.close()


def create_match(db: Session, payload: CreateMatchRequest) -> MatchResponse:
    if not payload.user_id:
        raise HTTPException(status_code=400, detail="user_id required")
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

    db.add(
        MatchPlayer(
            match_id=match.id,
            user_id=user.id,
            slot=1,
            display_name=user.display_name or user.username,
            banned_topics=[],
        )
    )
    db.commit()

    candidates = payload.topic_candidates or settings.ranked_topic_list
    _TOPIC_CANDIDATES[match.id] = list(candidates)
    _BAN_SUBMITTED[match.id] = set()
    return serialize_match(db, match, viewer_user_id=user.id)


def join_match(db: Session, match_id: str, payload: JoinMatchRequest) -> MatchResponse:
    if not payload.user_id:
        raise HTTPException(status_code=400, detail="user_id required")
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
        return serialize_match(db, match, viewer_user_id=payload.user_id)
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
    return serialize_match(db, match, viewer_user_id=user.id)


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


def get_match(
    db: Session,
    match_id: str,
    viewer_user_id: str | None = None,
) -> MatchResponse:
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return serialize_match(db, match, viewer_user_id=viewer_user_id)


def find_active_match_for_user(db: Session, user_id: str) -> MatchResponse | None:
    row = (
        db.query(Match)
        .join(MatchPlayer)
        .filter(
            MatchPlayer.user_id == user_id,
            Match.status.in_(
                [
                    MatchStatus.lobby,
                    MatchStatus.banning,
                    MatchStatus.ready_check,
                    MatchStatus.in_progress,
                ]
            ),
        )
        .order_by(Match.created_at.desc())
        .first()
    )
    if row is None:
        return None
    return serialize_match(db, row, viewer_user_id=user_id)


async def leave_match(db: Session, match_id: str, user_id: str) -> MatchResponse:
    match = (
        db.query(Match)
        .options(joinedload(Match.players))
        .filter(Match.id == match_id)
        .one_or_none()
    )
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    player = next((p for p in match.players if p.user_id == user_id), None)
    if player is None:
        raise HTTPException(status_code=403, detail="Not a player")

    if match.status in {MatchStatus.finished, MatchStatus.cancelled}:
        return serialize_match(db, match, viewer_user_id=user_id)

    await finish_match(db, match, reason="leave", leaver_user_id=user_id)
    return serialize_match(db, match, viewer_user_id=user_id)


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
            .options(
                joinedload(Match.players),
                joinedload(Match.rounds).joinedload(Round.answers),
            )
            .filter(Match.id == match_id)
            .one_or_none()
        )
        if match is None:
            await ws_manager.send_user(
                match_id, user_id, {"type": "error", "code": "match_not_found", "detail": "Match not found"}
            )
            return

        player = next((p for p in match.players if p.user_id == user_id), None)
        if player is None:
            await ws_manager.send_user(
                match_id, user_id, {"type": "error", "code": "not_a_player", "detail": "Not a player"}
            )
            return

        settings = get_settings()

        if etype == "join":
            was_disconnected = not player.is_connected
            player.is_connected = True
            db.commit()
            # personalized snapshot for reconnect
            await ws_manager.send_user(
                match_id, user_id, match_state_payload(db, match, viewer_user_id=user_id)
            )
            if match.status == MatchStatus.banning:
                await ws_manager.send_user(
                    match_id,
                    user_id,
                    {
                        "type": "ban_phase",
                        "match_id": match_id,
                        "topic_candidates": _TOPIC_CANDIDATES.get(match_id, []),
                        "max_bans": settings.ranked_max_bans,
                    },
                )
            # replay active question
            active = _active_round(match)
            if active and active.deadline_at is not None:
                now = _now()
                await ws_manager.send_user(
                    match_id,
                    user_id,
                    {
                        "type": "question",
                        "match_id": match_id,
                        "round": active.round_index + 1,
                        "round_index": active.round_index,
                        "question_id": active.id,
                        "text": active.question_text,
                        "options": list(active.options),
                        "deadline_ts": active.deadline_at.timestamp(),
                        "server_now_ts": now.timestamp(),
                        "round_seconds": match.round_seconds,
                    },
                )
                ans = next((a for a in active.answers if a.player_id == player.id), None)
                if ans:
                    await ws_manager.send_user(
                        match_id,
                        user_id,
                        {
                            "type": "answer_accepted",
                            "match_id": match_id,
                            "question_id": active.id,
                            "selected_index": ans.selected_index,
                        },
                    )
            if match_id in _LAST_ROUND_RESULT and active is None:
                await ws_manager.send_user(
                    match_id, user_id, {"type": "round_result", **_LAST_ROUND_RESULT[match_id]}
                )
            if match.status in {MatchStatus.finished, MatchStatus.cancelled}:
                meta = _FINISH_META.get(match_id, {})
                await ws_manager.send_user(
                    match_id,
                    user_id,
                    {
                        "type": "match_finished",
                        "match_id": match_id,
                        "topic": match.topic,
                        "reason": meta.get("finish_reason", "finished"),
                        "ranking": meta.get("ranking", []),
                        "rating_delta": meta.get("rating_deltas", {}).get(user_id, 0),
                    },
                )
            if was_disconnected:
                await ws_manager.broadcast(
                    match_id,
                    {
                        "type": "opponent_reconnected",
                        "match_id": match_id,
                        "user_id": user_id,
                    },
                )
                await broadcast_match_state(match_id)
            return

        if etype == "ban_topics":
            topics = event.get("topics") or []
            if not isinstance(topics, list):
                await ws_manager.send_user(
                    match_id,
                    user_id,
                    {"type": "error", "code": "invalid_topics", "detail": "topics must be list"},
                )
                return
            if match.status in {
                MatchStatus.in_progress,
                MatchStatus.finished,
                MatchStatus.cancelled,
            }:
                await ws_manager.send_user(
                    match_id,
                    user_id,
                    {"type": "error", "code": "ban_closed", "detail": "Ban phase closed"},
                )
                return
            if match.status != MatchStatus.ready_check:
                match.status = MatchStatus.banning
            max_bans = settings.ranked_max_bans
            player.banned_topics = [str(t) for t in topics][:max_bans]
            _BAN_SUBMITTED.setdefault(match_id, set()).add(user_id)
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
                    "match_id": match_id,
                    "by_user_id": user_id,
                    "banned_topics": match.banned_topics,
                    "players": [_player_public(p, match_id).model_dump() for p in match.players],
                },
            )
            # auto-start when both submitted ban (including empty skip)
            submitted = _BAN_SUBMITTED.get(match_id, set())
            if len(match.players) == 2 and all(p.user_id in submitted for p in match.players):
                for p in match.players:
                    p.is_ready = True
                match.status = MatchStatus.ready_check
                db.commit()
                await start_match(db, match)
            return

        if etype == "ready":
            # kept for invite/manual mode; queue flow uses auto-start after ban
            player.is_ready = True
            match.status = MatchStatus.ready_check
            db.commit()
            await broadcast_match_state(match_id)
            if len(match.players) == 2 and all(p.is_ready for p in match.players):
                await start_match(db, match)
            return

        if etype == "answer":
            await submit_answer(db, match, player, event)
            return

        await ws_manager.send_user(
            match_id,
            user_id,
            {
                "type": "error",
                "code": "unknown_event",
                "detail": f"Unknown event: {etype}",
            },
        )
    finally:
        db.close()


async def start_match(db: Session, match: Match) -> None:
    candidates = _TOPIC_CANDIDATES.get(match.id) or get_settings().ranked_topic_list
    banned = set(match.banned_topics or [])
    available = [t for t in candidates if t not in banned] or list(candidates)
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
            mode="ranked",
        )
    )

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
            await finish_match(db, match, reason="completed")
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
    command_id = event.get("command_id")
    if match.status != MatchStatus.in_progress:
        await ws_manager.send_user(
            match.id,
            player.user_id,
            {
                "type": "error",
                "code": "match_not_in_progress",
                "detail": "Match not in progress",
                "command_id": command_id,
            },
        )
        return

    question_id = event.get("question_id")
    selected = event.get("selected_index")
    if question_id is None or selected is None:
        await ws_manager.send_user(
            match.id,
            player.user_id,
            {
                "type": "error",
                "code": "invalid_answer",
                "detail": "question_id and selected_index required",
                "command_id": command_id,
            },
        )
        return

    rnd = next((r for r in match.rounds if r.id == question_id), None)
    if rnd is None or rnd.status != RoundStatus.active:
        await ws_manager.send_user(
            match.id,
            player.user_id,
            {
                "type": "error",
                "code": "round_not_active",
                "detail": "Round not active",
                "command_id": command_id,
                "question_id": question_id,
            },
        )
        return

    existing = next((a for a in rnd.answers if a.player_id == player.id), None)
    if existing:
        # idempotent restore of previous acceptance
        await ws_manager.send_user(
            match.id,
            player.user_id,
            {
                "type": "answer_accepted",
                "match_id": match.id,
                "question_id": rnd.id,
                "selected_index": existing.selected_index,
                "command_id": command_id,
                "replay": True,
            },
        )
        return

    try:
        selected_index = int(selected)
    except (TypeError, ValueError):
        await ws_manager.send_user(
            match.id,
            player.user_id,
            {
                "type": "error",
                "code": "invalid_selected_index",
                "detail": "Invalid selected_index",
                "command_id": command_id,
                "question_id": question_id,
            },
        )
        return

    if selected_index < 0 or selected_index >= len(rnd.options):
        await ws_manager.send_user(
            match.id,
            player.user_id,
            {
                "type": "error",
                "code": "selected_index_out_of_range",
                "detail": "selected_index out of range",
                "command_id": command_id,
                "question_id": question_id,
            },
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
            "match_id": match.id,
            "question_id": rnd.id,
            "selected_index": selected_index,
            "command_id": command_id,
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
                    "is_correct": bool(ans.is_correct) if ans else False,
                    "score": p.score,  # накопленный счёт после раунда
                    "round_points": 1 if (ans and ans.is_correct) else 0,
                }
            )

        result = {
            "match_id": match_id,
            "round": rnd.round_index + 1,
            "round_index": rnd.round_index,
            "question_id": rnd.id,
            "correct_index": rnd.correct_index,
            "explanation": rnd.explanation,
            "reason": reason,
            "answers": answers_payload,
        }
        _LAST_ROUND_RESULT[match_id] = result
        await ws_manager.broadcast(match_id, {"type": "round_result", **result})

        next_index = rnd.round_index + 1
        if next_index >= match.round_count:
            await finish_match(db, match, reason="completed")
        else:
            await asyncio.sleep(1.5)
            await open_round(match_id, next_index)
    finally:
        db.close()


async def finish_match(
    db: Session,
    match: Match,
    reason: str = "completed",
    leaver_user_id: str | None = None,
) -> None:
    _cancel_timer(match.id)
    if reason == "leave":
        match.status = MatchStatus.cancelled
    else:
        match.status = MatchStatus.finished
    match.finished_at = _now()

    # simple rating: +15 win / -10 loss / 0 draw
    ranking = sorted(
        [
            {"user_id": p.user_id, "display_name": p.display_name, "score": p.score}
            for p in match.players
        ],
        key=lambda x: x["score"],
        reverse=True,
    )
    rating_deltas: dict[str, int] = {}
    if len(ranking) == 2:
        if leaver_user_id:
            for row in ranking:
                rating_deltas[row["user_id"]] = -10 if row["user_id"] == leaver_user_id else 15
        elif ranking[0]["score"] == ranking[1]["score"]:
            rating_deltas = {ranking[0]["user_id"]: 0, ranking[1]["user_id"]: 0}
        else:
            rating_deltas = {ranking[0]["user_id"]: 15, ranking[1]["user_id"]: -10}

        for p in match.players:
            user = db.get(User, p.user_id)
            if user is None:
                continue
            delta = rating_deltas.get(p.user_id, 0)
            user.rank_points = max(0, user.rank_points + delta)
            if user.rank_points >= 1500:
                user.rank_tier = "gold"
            elif user.rank_points >= 1200:
                user.rank_tier = "silver"
            else:
                user.rank_tier = "bronze"

    for row in ranking:
        row["rating_delta"] = rating_deltas.get(row["user_id"], 0)
        user = db.get(User, row["user_id"])
        if user:
            row["rank_points"] = user.rank_points
            row["rank"] = user.rank_tier

    db.commit()
    _FINISH_META[match.id] = {
        "finish_reason": reason,
        "ranking": ranking,
        "rating_deltas": rating_deltas,
    }

    for uid in ws_manager.connected_user_ids(match.id) or [p.user_id for p in match.players]:
        await ws_manager.send_user(
            match.id,
            uid,
            {
                "type": "match_finished",
                "match_id": match.id,
                "topic": match.topic,
                "reason": reason,
                "ranking": ranking,
                "rating_delta": rating_deltas.get(uid, 0),
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
                "match_id": match_id,
                "user_id": user_id,
                "match_status": match.status.value,
                "reconnect_grace_sec": 60,
            },
        )
        await broadcast_match_state(match_id)
    finally:
        db.close()
