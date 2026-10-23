# Infinite Quiz / Quizly — обзор для презентации

Кратко: игрок задаёт тему и сложность → backend создаёт сессию с жизнями → вопросы генерирует ML → фронт показывает игру.

## Три репозитория

```mermaid
flowchart LR
  subgraph Org["infinite-quiz"]
    FE["frontend<br/>Quizly UI"]
    BE["backend<br/>игра + БД"]
    ML["ml<br/>генерация"]
  end

  User((Игрок)) --> FE
  FE -->|REST| BE
  BE -->|HTTP generate| ML
  BE --> DB[(БД)]
```

## Frontend — слои FSD

```mermaid
flowchart TB
  app["app<br/>router, styles, PWA"]
  pages["pages<br/>экраны"]
  widgets["widgets<br/>блоки UI"]
  features["features<br/>действия"]
  entities["entities<br/>модели"]
  shared["shared<br/>UI-kit, api, theme"]

  app --> pages --> widgets --> features --> entities --> shared
```

## Backend — монолит

```mermaid
flowchart LR
  API["api/routes"] --> SVC["services"]
  SVC --> ORM["db/models"]
  ORM --> DB[(SQLite/Postgres)]
  SVC --> GEN{"generator"}
  GEN -->|stub| Local[локальный банк]
  GEN -->|http| ML[ml service]
```

## ML — генератор

```mermaid
flowchart LR
  In["POST /generate"] --> Gen["generator.py"]
  Gen --> Prompts["prompts/"]
  Gen --> LLM["LLM API"]
  Gen --> Out["questions JSON"]
```

## Сквозной сценарий

```mermaid
sequenceDiagram
  actor U as Игрок
  participant F as Frontend
  participant B as Backend
  participant M as ML

  U->>F: тема / сложность / N
  F->>B: POST /quiz/start
  B->>M: POST /generate
  M-->>B: вопросы
  B-->>F: сессия + вопросы
  U->>F: ответ
  F->>B: POST /quiz/{id}/answer
  B-->>F: lives / score / status
```
