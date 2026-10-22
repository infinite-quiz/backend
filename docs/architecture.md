# Архитектура Infinite Quiz

## Обзор

Монолитный backend (FastAPI) + отдельный frontend-репозиторий + опциональный ML-сервис генерации вопросов.

```text
┌─────────────────────────────────────────────────────────────────┐
│                         GitHub org                              │
│                      infinite-quiz                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   frontend   │  │   backend    │  │         ml           │  │
│  │  (UI / SPA)  │  │  (monolith)  │  │ (prompts / generate) │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
└─────────┼─────────────────┼─────────────────────┼──────────────┘
          │ HTTP/JSON       │                     │
          │                 │  GENERATOR_MODE=http│
          ▼                 ▼                     ▼
   Browser / PWA     ┌──────────────┐      POST /generate
                     │  FastAPI API │◄─────────────┘
                     └──────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
         routes/quiz   services/     SQLAlchemy
         /generate     quiz_service  models
         /start        generator     (sessions,
         /answer                     questions,
                                     answers)
                            │
                            ▼
                      SQLite / Postgres
```

## Поток игры

```text
1. Клиент → POST /api/quiz/start { topic, count, difficulty }
2. Backend → generator (stub | ML HTTP) → список вопросов
3. Backend сохраняет QuizSession + Questions, отдаёт вопросы без correct_index клиенту
4. Клиент → POST /api/quiz/{id}/answer { question_id, selected_index }
5. Backend проверяет ответ, меняет lives/score, при lives=0 → finished
6. Клиент → GET /api/quiz/{id} — текущее состояние сессии
```

## Модули backend (монолит)

| Путь | Ответственность | Кто |
|------|-----------------|-----|
| `app/api/routes/` | HTTP-эндпоинты | Backend #2 |
| `app/services/quiz_service.py` | Жизни, сессии, ответы | Backend #1 |
| `app/services/generator.py` | Stub / вызов ML | Backend #1 + ML |
| `app/db/models/` | Схема БД | Backend #1 |
| `alembic/` | Миграции | Backend #2 |
| `docs/` | Контракт API, архитектура | Тимлид |

## Граница с ML

- Сейчас: `GENERATOR_MODE=stub` — заглушка в backend.
- Потом: `GENERATOR_MODE=http` + `GENERATOR_URL` → репозиторий `ml` отдаёт тот же JSON-контракт, что и `POST /api/quiz/generate`.

Контракт генерации общий — см. `docs/api.md`.
