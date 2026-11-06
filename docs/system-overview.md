# Infinite Quiz / Quizly — обзор для презентации

Игрок выбирает тему и сложность.  
**Solo** — один игрок, REST, жизни.  
**Ranked** — 1v1, WebSocket, таймер, бан тем, один вопрос за раз.

## Три репозитория

```mermaid
flowchart LR
  subgraph Org["infinite-quiz"]
    FE["frontend<br/>Quizly UI"]
    BE["backend<br/>solo + ranked"]
    ML["ml<br/>генерация"]
  end

  User((Игрок)) --> FE
  FE -->|REST solo / ranked lobby| BE
  FE -->|WebSocket ranked| BE
  BE -->|HTTP generate| ML
  BE --> DB[(БД)]
```

## Два режима

```mermaid
flowchart TB
  Solo["Solo<br/>REST /api/quiz/*<br/>пачка вопросов + жизни"]
  Ranked["Ranked<br/>REST лобби + WS /ws/ranked/*<br/>один вопрос + таймер"]
  Solo --> BE["Backend monolith"]
  Ranked --> BE
```

## Frontend — FSD

```mermaid
flowchart TB
  app["app"] --> pages["pages"] --> widgets["widgets"]
  widgets --> features["features"] --> entities["entities"] --> shared["shared"]
```

## Backend — модули

```mermaid
flowchart LR
  Quiz["/api/quiz"] --> QuizSvc["quiz_service"]
  RankedREST["/api/ranked"] --> RankedSvc["ranked_service"]
  RankedWS["/ws/ranked"] --> RankedSvc
  QuizSvc --> Gen["generator"]
  RankedSvc --> Gen
  Gen -->|stub/http| ML["ml"]
  QuizSvc --> DB[(БД)]
  RankedSvc --> DB
```

## Ranked коротко

1. REST: создать / войти в матч → `match_id` + `ws_url`  
2. WS: ban → ready → вопросы по одному → answer → round_result → match_finished  
3. Будущие вопросы и правильный ответ до конца раунда клиенту не отдаются  

Детали: [architecture.md](architecture.md), [ws.md](ws.md), [api.md](api.md).
