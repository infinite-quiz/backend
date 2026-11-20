# API для фронтенда (актуально)

Base: `http://localhost:8000/api`  
Solo quiz: [api.md](api.md)  
Ranked WS bodies: [ws.md](ws.md)

Auth: cookie `quiz_session` (HttpOnly) или `Authorization: Bearer <token>`  
Либо временно `X-User-Id` / `?user_id=` для отладки без логина.

## Auth

| Method | Path | Body |
|--------|------|------|
| POST | `/auth/register` | `{ "email", "password", "displayName" }` |
| POST | `/auth/login` | `{ "email", "password" }` |
| POST | `/auth/refresh` | — |
| POST | `/auth/logout` | — |

Response register/login: `{ "user": { id, email, displayName, level, energy, streakDays, rank, rankPoints } }`

## User / meta

| Method | Path |
|--------|------|
| GET | `/user/me` |
| GET | `/user/me/statistics?period=week\|month\|all&expected_user_id=` |
| GET | `/user/me/achievements?filter=all\|received\|progress&expected_user_id=` |
| GET | `/leaderboard?rank=all\|bronze\|silver\|gold` |

## Solo

| Method | Path | Notes |
|--------|------|--------|
| POST | `/quiz/start` | как в api.md |
| POST | `/quiz/{id}/answer` | |
| GET | `/quiz/{id}` | |
| POST | `/solo/results` | outbox sync + `Idempotency-Key` |

`POST /solo/results` body:
```json
{
  "version": 1,
  "user_id": "optional",
  "session_id": "...",
  "completed_at": "2026-11-20T12:00:00Z",
  "answers": [{ "question_id": "...", "selected_index": 1, "answered_at": "..." }]
}
```
Response: `{ "session_id", "status": "saved" }`

## Ranked HTTP

| Method | Path | Назначение |
|--------|------|------------|
| POST | `/ranked/queue` | автоподбор → `{ ticket_id, status }` |
| DELETE | `/ranked/queue/{ticket_id}` | отмена поиска |
| GET | `/ranked/current` | idle / searching / matched + snapshot |
| POST | `/ranked/matches/{id}/leave` | выход / сдача |
| GET | `/ranked/matches/{id}` | snapshot с `current_question`, `own_answer`, `last_round_result` |
| POST | `/ranked/matches` | invite-режим (опционально) |
| POST | `/ranked/matches/join` | invite по коду |

### Сценарий автоподбора (без ready)

1. `POST /ranked/queue`  
2. poll `GET /ranked/current` пока `matched`  
3. WS connect на `ws_url?user_id=`  
4. оба `ban_topics` (можно `[]` = пропуск) → **автостарт**  
5. `question` → `answer` → `round_result` → … → `match_finished` (+ `rating_delta`)

Invite + `ready` оставлены для ручных комнат.

## ML

Backend: `GENERATOR_MODE=http`, `GENERATOR_URL=http://127.0.0.1:8001/generate`  
ML поднимается отдельно на `:8001`. При ошибке/таймауте backend отдаёт stub, матч не падает.
