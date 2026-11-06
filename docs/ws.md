# Ranked: REST + WebSocket

Solo остаётся на `/api/quiz/*`.  
Ranked: REST готовит матч, игра идёт по WebSocket.

## REST

Base: `http://localhost:8000/api/ranked`

### `POST /matches` — создать матч (хост)

```json
{
  "user_id": "u1",
  "display_name": "Host",
  "topic_candidates": ["Космос", "История", "Наука", "Кино", "Спорт"],
  "difficulty": "medium",
  "round_count": 5,
  "round_seconds": 20
}
```

**Response:** `match_id`, `invite_code`, `ws_url`, игроки, статус `lobby`.

### `POST /matches/join` — войти по коду

```json
{ "user_id": "u2", "display_name": "Guest", "invite_code": "ABC123" }
```

### `POST /matches/{match_id}/join` — войти по id

```json
{ "user_id": "u2", "display_name": "Guest" }
```

### `GET /matches/{match_id}` — состояние матча

`ws_url` вида: `ws://localhost:8000/ws/ranked/{match_id}?user_id=...`  
(`user_id` обязателен в query при коннекте)

---

## WebSocket

`WS /ws/ranked/{match_id}?user_id={user_id}`

После коннекта сервер сам шлёт `join` → `match_state` (+ `ban_phase`, если 2 игрока).

### Клиент → сервер

| type | body | когда |
|------|------|--------|
| `join` | `{}` | опционально (уже на connect) |
| `ban_topics` | `{ "topics": ["Кино"] }` | фаза бана |
| `ready` | `{}` | оба готовы → старт |
| `answer` | `{ "question_id": "...", "selected_index": 1 }` | активный раунд |

### Сервер → клиент

| type | смысл |
|------|--------|
| `match_state` | лобби / игроки / статус |
| `ban_phase` | кандидаты тем, лимит банов |
| `ban_update` | обновление банов |
| `match_start` | тема выбрана, игра началась |
| `question` | **один** текущий вопрос + `deadline_ts` (без correct_index) |
| `answer_accepted` | твой ответ принят (вердикт позже) |
| `round_result` | правильный индекс, ответы игроков, очки |
| `match_finished` | ranking |
| `opponent_left` | соперник отключился |
| `error` | ошибка |

### Пример `question`

```json
{
  "type": "question",
  "match_id": "...",
  "round": 1,
  "round_index": 0,
  "question_id": "...",
  "text": "...",
  "options": ["A", "B", "C", "D"],
  "deadline_ts": 1730000020.0,
  "server_now_ts": 1730000000.0,
  "round_seconds": 20
}
```

Вопросы генерируются пачкой на сервере при старте; клиенту уходит только текущий раунд.

---

## Сценарий 1v1

1. Host: `POST /matches` → `invite_code`, `ws_url`  
2. Guest: `POST /matches/join` с кодом  
3. Оба: WS connect  
4. Оба: `ban_topics`  
5. Оба: `ready` → `match_start` → `question`  
6. `answer` / таймер → `round_result` → следующий `question`  
7. `match_finished`
