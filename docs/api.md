# API Contract — Infinite Quiz

Base URL (local): `http://localhost:8000`  
Prefix: `/api`  
Interactive docs: `http://localhost:8000/docs`

Все даты — ISO 8601. Ошибки FastAPI: `{ "detail": "..." }`.

---

## Health

### `GET /api/health`

**Response 200**
```json
{ "status": "ok", "version": "0.1.0" }
```

---

## Generate questions (stub / ML)

### `POST /api/quiz/generate`

Генерирует вопросы **без** создания игровой сессии. Использует stub или ML.

**Request**
```json
{
  "topic": "Космос",
  "count": 5,
  "difficulty": "medium",
  "language": "ru"
}
```

| Field | Type | Rules |
|-------|------|--------|
| topic | string | 1–255 |
| count | int | 1–20 |
| difficulty | string | `easy` \| `medium` \| `hard` |
| language | string | default `ru` |

**Response 200**
```json
{
  "topic": "Космос",
  "difficulty": "medium",
  "count": 5,
  "source": "stub",
  "questions": [
    {
      "text": "[Космос / medium] Сколько планет в Солнечной системе?",
      "options": ["7", "8", "9", "10"],
      "correct_index": 1,
      "explanation": "После исключения Плутона официально 8 планет."
    }
  ]
}
```

**Контракт для ML-сервиса** — тот же request/response body (поле `source` на стороне ML можно не слать; backend проставит `ml`).

---

## Start quiz

### `POST /api/quiz/start`

Создаёт сессию, генерирует вопросы, возвращает их **без** `correct_index`.

**Request**
```json
{
  "topic": "История",
  "count": 5,
  "difficulty": "easy",
  "player_name": "Alex",
  "language": "ru"
}
```

**Response 200**
```json
{
  "session_id": "uuid",
  "topic": "История",
  "difficulty": "easy",
  "lives_total": 3,
  "lives_left": 3,
  "score": 0,
  "status": "active",
  "questions": [
    {
      "id": "uuid",
      "order_index": 0,
      "text": "...",
      "options": ["A", "B", "C", "D"]
    }
  ]
}
```

---

## Get session

### `GET /api/quiz/{session_id}`

**Response 200** — см. `QuizSessionResponse` (вопросы без правильного ответа).  
**404** — сессия не найдена.

---

## Answer

### `POST /api/quiz/{session_id}/answer`

**Request**
```json
{
  "question_id": "uuid",
  "selected_index": 1
}
```

**Response 200**
```json
{
  "session_id": "uuid",
  "question_id": "uuid",
  "is_correct": false,
  "correct_index": 2,
  "lives_left": 2,
  "score": 0,
  "status": "active",
  "explanation": "..."
}
```

**409** — сессия не active / вопрос уже отвечен.  
**404** — сессия или вопрос не найдены.

Правила:
- верный ответ → `score += 1`
- неверный → `lives_left -= 1`
- `lives_left == 0` или все вопросы отвечены → `status = finished`

---

## Статусы сессии

| status | смысл |
|--------|--------|
| `active` | игра идёт |
| `finished` | жизни кончились или вопросы закончились |
| `abandoned` | зарезервировано |

---

## Frontend env

```env
VITE_API_URL=http://localhost:8000/api
```
