# Архитектура Infinite Quiz

Монолитный backend (FastAPI) + отдельный frontend-репозиторий + ML-сервис генерации вопросов.

## Обзор системы

```mermaid
flowchart TB
  subgraph Org["GitHub org: infinite-quiz"]
    FE["frontend<br/>Quizly · React 19 · FSD"]
    BE["backend<br/>FastAPI monolith"]
    ML["ml<br/>prompts + LLM"]
  end

  Browser["Браузер / PWA"]
  DB[(SQLite / Postgres)]

  Browser -->|HTTP JSON<br/>/api/quiz/*| BE
  FE -.->|собирается в| Browser
  BE -->|GENERATOR_MODE=http<br/>POST /generate| ML
  BE --> DB
```

## Внутренности backend

```mermaid
flowchart LR
  subgraph Backend["backend :8000"]
    R["routes/quiz<br/>generate · start · answer"]
    S["services<br/>quiz_service · generator"]
    M["models<br/>sessions · questions · answers"]
  end

  R --> S --> M
  M --> DB[(БД)]
  S -->|stub или http| ML["ml :8001"]
```

## Поток игры

```mermaid
sequenceDiagram
  actor P as Игрок
  participant C as Frontend
  participant B as Backend
  participant G as Generator stub/ML
  participant D as БД

  P->>C: тема, count, difficulty
  C->>B: POST /api/quiz/start
  B->>G: сгенерировать вопросы
  G-->>B: questions[]
  B->>D: QuizSession + Questions
  B-->>C: вопросы без correct_index
  C-->>P: показать вопрос

  P->>C: выбрать вариант
  C->>B: POST /api/quiz/{id}/answer
  B->>D: Answer, lives, score
  alt lives = 0 или вопросы кончились
    B-->>C: status = finished
  else ещё играет
    B-->>C: is_correct, lives_left
  end
```

## Модули backend и ответственность

```mermaid
flowchart TB
  Routes["app/api/routes/<br/>HTTP-эндпоинты · Backend #2"]
  QuizSvc["app/services/quiz_service.py<br/>Жизни, сессии, ответы · Backend #1"]
  GenSvc["app/services/generator.py<br/>Stub / вызов ML · Backend #1 + ML"]
  Models["app/db/models/<br/>Схема БД · Backend #1"]
  Alembic["alembic/<br/>Миграции · Backend #2"]
  Docs["docs/<br/>Контракт API, архитектура · Тимлид"]

  Routes --> QuizSvc
  Routes --> GenSvc
  QuizSvc --> GenSvc
  QuizSvc --> Models
  Models --> Alembic
  Docs -.-> Routes
```

## Граница с ML

```mermaid
flowchart LR
  BE["backend generator.py"]
  Stub["GENERATOR_MODE=stub<br/>локальный банк вопросов"]
  HTTP["GENERATOR_MODE=http<br/>GENERATOR_URL"]
  ML["ml POST /generate<br/>тот же JSON-контракт"]

  BE --> Stub
  BE --> HTTP --> ML
```

- Сейчас: `GENERATOR_MODE=stub`.
- Цель: `GENERATOR_MODE=http` + сервис из репозитория `ml`.

Контракт генерации — см. [api.md](api.md).
