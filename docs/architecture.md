# Архитектура Infinite Quiz

Монолитный backend (FastAPI) + frontend (Quizly) + ML-генератор вопросов.

Два режима игры:

| Режим | Транспорт | Вопросы клиенту |
|--------|-----------|-----------------|
| **Solo** | REST `/api/quiz/*` | можно пачкой при `start` |
| **Ranked** | REST лобби + **WebSocket** | строго по одному вопросу |

## Обзор системы

```mermaid
flowchart TB
  subgraph Org["GitHub org: infinite-quiz"]
    FE["frontend<br/>Quizly · React · FSD"]
    BE["backend<br/>FastAPI monolith"]
    ML["ml<br/>prompts + LLM"]
  end

  Browser["Браузер / PWA"]
  DB[(SQLite / Postgres)]

  Browser -->|Solo REST /api/quiz/*| BE
  Browser -->|Ranked WS /ws/ranked/*| BE
  FE -.->|собирается в| Browser
  BE -->|GENERATOR_MODE=http<br/>POST /generate| ML
  BE --> DB
```

## Внутренности backend

```mermaid
flowchart LR
  subgraph Backend["backend :8000"]
    RQ["routes/quiz<br/>solo REST"]
    RR["routes/ranked<br/>lobby REST"]
    WS["ws/ranked<br/>матч в реальном времени"]
    SQ["quiz_service"]
    SR["ranked_service"]
    GEN["generator<br/>stub / ML"]
    M["models<br/>solo + ranked"]
  end

  RQ --> SQ
  RR --> SR
  WS --> SR
  SQ --> GEN
  SR --> GEN
  SQ --> M
  SR --> M
  M --> DB[(БД)]
  GEN --> ML["ml :8001"]
```

## Solo — поток

```mermaid
sequenceDiagram
  actor P as Игрок
  participant C as Frontend
  participant B as Backend
  participant G as Generator
  participant D as БД

  P->>C: тема, count, difficulty
  C->>B: POST /api/quiz/start
  B->>G: generate
  G-->>B: questions[]
  B->>D: QuizSession + Questions
  B-->>C: вопросы без correct_index
  P->>C: ответ
  C->>B: POST /api/quiz/{id}/answer
  B-->>C: is_correct, lives, status
```

## Ranked — поток

```mermaid
sequenceDiagram
  actor H as Host
  actor G as Guest
  participant API as REST
  participant WS as WebSocket
  participant S as ranked_service
  participant Gen as Generator

  H->>API: POST /api/ranked/matches
  API-->>H: match_id, invite_code, ws_url
  G->>API: POST /api/ranked/matches/join
  H->>WS: connect
  G->>WS: connect
  H->>WS: ban_topics
  G->>WS: ban_topics
  H->>WS: ready
  G->>WS: ready
  S->>Gen: пачка вопросов на сервере
  WS-->>H: match_start + question
  WS-->>G: match_start + question
  H->>WS: answer
  G->>WS: answer
  WS-->>H: round_result
  WS-->>G: round_result
  Note over WS: следующий question или match_finished
```

Подробный контракт событий: [ws.md](ws.md).

## Модули и ответственность

| Путь | Зона |
|------|------|
| `app/api/routes/quiz.py` | Solo REST |
| `app/api/routes/ranked.py` | Ranked REST (create/join/get) |
| `app/api/ws/ranked.py` | Ranked WebSocket |
| `app/services/quiz_service.py` | Solo: жизни, ответы |
| `app/services/ranked_service.py` | Ranked: бан, раунды, таймер |
| `app/services/generator.py` | Stub / HTTP → ML |
| `app/services/ws_manager.py` | Комнаты WS по match_id |
| `app/db/models/quiz.py` | Solo-модели |
| `app/db/models/ranked.py` | Match, MatchPlayer, Round, RoundAnswer |
| `docs/` | Контракты и схемы |

## Граница с ML

```mermaid
flowchart LR
  BE["generator.py"]
  Stub["GENERATOR_MODE=stub"]
  HTTP["GENERATOR_MODE=http"]
  ML["ml POST /generate"]

  BE --> Stub
  BE --> HTTP --> ML
```

- Сейчас: `stub`.
- Цель: `http` + репозиторий `ml`.
- Для ranked вопросы генерируются **пачкой на сервере**, клиенту уходит только текущий раунд.

Контракты: [api.md](api.md) (solo), [ws.md](ws.md) (ranked).
