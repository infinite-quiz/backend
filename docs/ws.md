# Ranked: REST + WebSocket

Solo остаётся на `/api/quiz/*`.  
Ranked: REST готовит матч, игра идёт по WebSocket.

Все WS-сообщения — JSON-объект с обязательным полем `type`.

## REST

Base: `http://localhost:8000/api/ranked`

### `POST /matches` — создать матч (хост)

**Request**
```json
{
  "user_id": "u1",
  "display_name": "Host",
  "topic_candidates": ["Космос", "История", "Наука", "Кино", "Спорт"],
  "difficulty": "medium",
  "round_count": 5,
  "round_seconds": 20,
  "language": "ru"
}
```

**Response 200**
```json
{
  "match_id": "86fdca1a-5aef-49bc-90c1-6aa5933b14f2",
  "status": "lobby",
  "invite_code": "MADH5Z",
  "topic": null,
  "difficulty": "medium",
  "round_count": 5,
  "current_round": 0,
  "round_seconds": 20,
  "banned_topics": [],
  "topic_candidates": ["Космос", "История", "Наука", "Кино", "Спорт"],
  "players": [
    {
      "id": "player-uuid",
      "user_id": "u1",
      "slot": 1,
      "display_name": "Host",
      "is_ready": false,
      "is_connected": false,
      "score": 0,
      "banned_topics": []
    }
  ],
  "ws_url": "ws://localhost:8000/ws/ranked/86fdca1a-5aef-49bc-90c1-6aa5933b14f2",
  "created_at": "2026-11-06T14:00:00+00:00"
}
```

### `POST /matches/join` — войти по коду

**Request**
```json
{
  "user_id": "u2",
  "display_name": "Guest",
  "invite_code": "MADH5Z"
}
```

**Response 200** — тот же `MatchResponse`, `status` обычно `banning`, в `players` двое.

### `POST /matches/{match_id}/join` — войти по id

**Request**
```json
{
  "user_id": "u2",
  "display_name": "Guest"
}
```

### `GET /matches/{match_id}` — состояние матча

**Response 200** — `MatchResponse` как выше.

`ws_url` в ответе без `user_id`. Подключение:

```text
ws://localhost:8000/ws/ranked/{match_id}?user_id={user_id}
```

---

## WebSocket

`WS /ws/ranked/{match_id}?user_id={user_id}`

После connect сервер сам делает `join` и шлёт `match_state`  
(+ `ban_phase`, если статус `banning`).

---

## Клиент → сервер

### `join`

Опционально (уже вызывается на connect).

```json
{ "type": "join" }
```

**Ответ сервера:** `match_state` (broadcast), при `banning` ещё `ban_phase`.

---

### `ban_topics`

```json
{
  "type": "ban_topics",
  "topics": ["Кино"]
}
```

| Field | Type | Rules |
|-------|------|--------|
| topics | string[] | до 3 тем; сервер обрезает |

**Ответ сервера:** `ban_update` (broadcast).  
**Ошибки:** `error` с `topics must be list` / `Ban phase closed`.

---

### `ready`

```json
{ "type": "ready" }
```

**Ответ сервера:** `match_state` (`status: ready_check`).  
Если оба ready → дальше `match_start` + `question`.

---

### `answer`

```json
{
  "type": "answer",
  "question_id": "c5873697-c2d8-4b3f-a69b-90f1c009d011",
  "selected_index": 1
}
```

| Field | Type | Rules |
|-------|------|--------|
| question_id | string | id из события `question` |
| selected_index | int | индекс в `options`, с 0 |

**Ответ сервера (только тебе):** `answer_accepted`.  
Когда оба ответили (или таймер) → всем `round_result`, затем следующий `question` или `match_finished`.

**Ошибки:** `Match not in progress`, `question_id and selected_index required`, `Round not active`, `Already answered`, `Invalid selected_index`, `selected_index out of range`.

---

## Сервер → клиент (body каждого события)

### `match_state`

Полное состояние матча (как REST `MatchResponse` + `type`).

```json
{
  "type": "match_state",
  "match_id": "86fdca1a-5aef-49bc-90c1-6aa5933b14f2",
  "status": "banning",
  "invite_code": "MADH5Z",
  "topic": null,
  "difficulty": "easy",
  "round_count": 2,
  "current_round": 0,
  "round_seconds": 15,
  "banned_topics": ["Кино", "Спорт"],
  "topic_candidates": ["Космос", "История", "Наука", "Кино", "Спорт"],
  "players": [
    {
      "id": "93c6d945-1a70-4060-a084-9a4bfc461cb9",
      "user_id": "host_smoke",
      "slot": 1,
      "display_name": "Host",
      "is_ready": false,
      "is_connected": true,
      "score": 0,
      "banned_topics": ["Кино"]
    },
    {
      "id": "a2167b24-5082-4f0a-9c11-aaaaaaaaaaaa",
      "user_id": "guest_smoke",
      "slot": 2,
      "display_name": "Guest",
      "is_ready": false,
      "is_connected": true,
      "score": 0,
      "banned_topics": ["Спорт"]
    }
  ],
  "ws_url": "ws://localhost:8000/ws/ranked/86fdca1a-5aef-49bc-90c1-6aa5933b14f2",
  "created_at": "2026-11-06T14:00:00+00:00"
}
```

`status`: `lobby` | `banning` | `ready_check` | `in_progress` | `finished` | `cancelled`.

---

### `ban_phase`

```json
{
  "type": "ban_phase",
  "topic_candidates": ["Космос", "История", "Наука", "Кино", "Спорт"],
  "max_bans": 1
}
```

---

### `ban_update`

```json
{
  "type": "ban_update",
  "by_user_id": "host_smoke",
  "banned_topics": ["Кино", "Спорт"],
  "players": [
    {
      "id": "93c6d945-1a70-4060-a084-9a4bfc461cb9",
      "user_id": "host_smoke",
      "slot": 1,
      "display_name": "Host",
      "is_ready": false,
      "is_connected": true,
      "score": 0,
      "banned_topics": ["Кино"]
    },
    {
      "id": "a2167b24-5082-4f0a-9c11-aaaaaaaaaaaa",
      "user_id": "guest_smoke",
      "slot": 2,
      "display_name": "Guest",
      "is_ready": false,
      "is_connected": true,
      "score": 0,
      "banned_topics": ["Спорт"]
    }
  ]
}
```

---

### `match_start`

```json
{
  "type": "match_start",
  "match_id": "86fdca1a-5aef-49bc-90c1-6aa5933b14f2",
  "topic": "Космос",
  "round_count": 2,
  "round_seconds": 15
}
```

Сразу после него приходит первый `question`.

---

### `question`

Один текущий вопрос. **Без** `correct_index` и без следующих вопросов.

```json
{
  "type": "question",
  "match_id": "86fdca1a-5aef-49bc-90c1-6aa5933b14f2",
  "round": 1,
  "round_index": 0,
  "question_id": "c5873697-c2d8-4b3f-a69b-90f1c009d011",
  "text": "[Космос / easy] Сколько планет в Солнечной системе?",
  "options": ["7", "8", "9", "10"],
  "deadline_ts": 1730000020.0,
  "server_now_ts": 1730000000.0,
  "round_seconds": 15
}
```

| Field | смысл |
|-------|--------|
| `round` | номер раунда с 1 (для UI) |
| `round_index` | индекс с 0 |
| `deadline_ts` | unix timestamp конца раунда (сервер) |
| `server_now_ts` | unix timestamp «сейчас» на сервере |

Таймер на клиенте: `deadline_ts - server_now_ts` (или относительно локальных часов с поправкой).

---

### `answer_accepted`

Только отправителю ответа. Вердикт ещё не финальный для UI соперника.

```json
{
  "type": "answer_accepted",
  "question_id": "c5873697-c2d8-4b3f-a69b-90f1c009d011",
  "selected_index": 1
}
```

---

### `round_result`

```json
{
  "type": "round_result",
  "match_id": "86fdca1a-5aef-49bc-90c1-6aa5933b14f2",
  "round": 1,
  "round_index": 0,
  "question_id": "c5873697-c2d8-4b3f-a69b-90f1c009d011",
  "correct_index": 1,
  "explanation": "После исключения Плутона официально 8 планет.",
  "reason": "all_answered",
  "answers": [
    {
      "user_id": "host_smoke",
      "display_name": "Host",
      "selected_index": 1,
      "is_correct": true,
      "score": 1
    },
    {
      "user_id": "guest_smoke",
      "display_name": "Guest",
      "selected_index": 0,
      "is_correct": false,
      "score": 0
    }
  ]
}
```

| `reason` | когда |
|----------|--------|
| `all_answered` | оба ответили |
| `timeout` | вышло время раунда |

Если игрок не ответил: `selected_index: null`, `is_correct: false`.

Через ~1.5 с сервер шлёт следующий `question` или `match_finished`.

---

### `match_finished`

```json
{
  "type": "match_finished",
  "match_id": "86fdca1a-5aef-49bc-90c1-6aa5933b14f2",
  "topic": "Космос",
  "ranking": [
    {
      "user_id": "host_smoke",
      "display_name": "Host",
      "score": 2
    },
    {
      "user_id": "guest_smoke",
      "display_name": "Guest",
      "score": 0
    }
  ]
}
```

`ranking` отсортирован по `score` убыв.

---

### `opponent_left`

```json
{
  "type": "opponent_left",
  "user_id": "guest_smoke",
  "match_status": "in_progress"
}
```

После этого обычно ещё приходит обновлённый `match_state` (`is_connected: false`).

---

### `error`

```json
{
  "type": "error",
  "detail": "Already answered"
}
```

Возможные `detail`:

- `Match not found`
- `Not a player`
- `topics must be list`
- `Ban phase closed`
- `Match not in progress`
- `question_id and selected_index required`
- `Round not active`
- `Already answered`
- `Invalid selected_index`
- `selected_index out of range`
- `Unknown event: ...`
- `Invalid JSON` / `Event must have type` (на уровне WS-хендлера)

---

## Сценарий 1v1

1. Host: `POST /matches` → `invite_code`, `ws_url`  
2. Guest: `POST /matches/join`  
3. Оба: WS connect → `match_state` (+ `ban_phase`)  
4. Оба: `ban_topics` → `ban_update`  
5. Оба: `ready` → `match_state` → `match_start` → `question`  
6. `answer` → `answer_accepted` → (оба/таймер) `round_result` → следующий `question`  
7. `match_finished`

Smoke: `py -3 scripts/ranked_ws_smoke.py`
