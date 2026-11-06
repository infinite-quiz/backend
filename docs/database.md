# Схема БД

## ER-диаграмма (solo)

```mermaid
erDiagram
  users ||--o{ quiz_sessions : owns
  quiz_sessions ||--o{ questions : contains
  quiz_sessions ||--o{ answers : has
  questions ||--o{ answers : receives

  users {
    string id PK
    string username UK
    string display_name
    datetime created_at
  }

  quiz_sessions {
    string id PK
    string user_id FK
    string topic
    enum difficulty
    int requested_count
    int lives_total
    int lives_left
    int score
    enum status
    string player_name
    datetime created_at
    datetime finished_at
  }

  questions {
    string id PK
    string session_id FK
    int order_index
    text text
    json options
    int correct_index
    text explanation
  }

  answers {
    string id PK
    string session_id FK
    string question_id FK
    int selected_index
    bool is_correct
    datetime answered_at
  }
```

## Enums

```mermaid
flowchart LR
  subgraph difficulty
    E[easy]
    M[medium]
    H[hard]
  end

  subgraph session_status
    A[active]
    F[finished]
    X[abandoned]
  end
```

## Миграции

```bash
# применить
alembic upgrade head

# новая (после изменения models)
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```

Локально по умолчанию: SQLite файл `quiz.db`.  
Прод: `DATABASE_URL=postgresql+psycopg://...` в `.env`.

## Ranked

```mermaid
erDiagram
  users ||--o{ match_players : plays
  matches ||--o{ match_players : has
  matches ||--o{ rounds : has
  rounds ||--o{ round_answers : receives
  match_players ||--o{ round_answers : gives

  matches {
    string id PK
    enum status
    string topic
    string invite_code
    int round_count
    int current_round
    int round_seconds
  }

  match_players {
    string id PK
    string match_id FK
    string user_id FK
    int slot
    bool is_ready
    int score
  }

  rounds {
    string id PK
    string match_id FK
    int round_index
    enum status
    text question_text
    json options
    int correct_index
    datetime deadline_at
  }
```
