# Infinite Quiz — Backend

Монолитный API для бесконечного квиза с генерацией вопросов (stub → ML).

Org: [infinite-quiz](https://github.com/infinite-quiz)  
Стек: **FastAPI · SQLAlchemy · Alembic · SQLite/Postgres**

## Архитектура системы

```mermaid
flowchart LR
  subgraph Org["GitHub: infinite-quiz"]
    FE["frontend<br/>Quizly / React FSD"]
    BE["backend<br/>FastAPI monolith"]
    ML["ml<br/>LLM generator"]
  end

  Browser["Браузер / PWA"] -->|HTTP /api/quiz/*| BE
  FE -.->|код UI| Browser
  BE -->|POST /generate<br/>GENERATOR_MODE=http| ML
  BE --> DB[(SQLite / Postgres)]
```

## Поток игры

```mermaid
sequenceDiagram
  actor Player as Игрок
  participant FE as Frontend
  participant BE as Backend
  participant Gen as Stub / ML
  participant DB as БД

  Player->>FE: тема, count, сложность
  FE->>BE: POST /api/quiz/start
  BE->>Gen: generate questions
  Gen-->>BE: questions JSON
  BE->>DB: session + questions
  BE-->>FE: session_id, вопросы без correct_index
  FE-->>Player: экран вопроса

  Player->>FE: ответ
  FE->>BE: POST /api/quiz/{id}/answer
  BE->>DB: answer, lives, score
  BE-->>FE: is_correct, lives_left, status
  FE-->>Player: результат / game over
```

## Модули backend

```mermaid
flowchart TB
  subgraph API["app/api/routes"]
    H["/health"]
    G["/quiz/generate"]
    S["/quiz/start"]
    A["/quiz/{id}/answer"]
    Q["/quiz/{id}"]
  end

  subgraph Services["app/services"]
    QS["quiz_service<br/>сессии, жизни, ответы"]
    GEN["generator<br/>stub | http→ML"]
  end

  subgraph Data["app/db"]
    M["models<br/>sessions / questions / answers"]
    AL["alembic migrations"]
  end

  G --> GEN
  S --> QS
  A --> QS
  Q --> QS
  QS --> GEN
  QS --> M
  M --> AL
```

## Быстрый старт

```bash
cd backendquiz   # или клон репозитория
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

- Docs: http://localhost:8000/docs  
- Health: http://localhost:8000/api/health  
- Generate stub: `POST http://localhost:8000/api/quiz/generate`

```bash
curl -X POST http://localhost:8000/api/quiz/generate ^
  -H "Content-Type: application/json" ^
  -d "{\"topic\":\"Космос\",\"count\":3,\"difficulty\":\"easy\"}"
```

## Структура репозитория

```text
app/
  api/routes/     # HTTP
  db/models/      # ORM
  schemas/        # Pydantic-контракты
  services/       # game + generator
alembic/          # миграции
docs/             # архитектура, API, БД, ветки
```

## Документация

- [Обзор системы (для презентации)](docs/system-overview.md)
- [Архитектура](docs/architecture.md)
- [API contract](docs/api.md)
- [Схема БД](docs/database.md)
- [Ветки](docs/branches.md)

## Конфиг

Скопируй `.env.example` → `.env`.

| Переменная | Описание |
|------------|----------|
| `DATABASE_URL` | SQLite или Postgres |
| `CORS_ORIGINS` | origins фронта |
| `GENERATOR_MODE` | `stub` или `http` |
| `GENERATOR_URL` | URL ML-сервиса при `http` |

## Роли в этом репо

| Роль | Зона |
|------|------|
| Backend #1 | `services/quiz_service`, модели, жизни |
| Backend #2 | миграции, конфиг, CORS, инфраструктура |
| ML | контракт generate; позже `GENERATOR_MODE=http` |
| Тимлид | `docs/`, ревью PR |
