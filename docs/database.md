# Схема БД

## ER-диаграмма

```text
┌─────────────────────┐
│        users        │
├─────────────────────┤
│ id (PK, uuid)       │
│ username (unique)   │
│ display_name        │
│ created_at          │
└──────────┬──────────┘
           │ 1:N
           ▼
┌─────────────────────┐       1:N       ┌─────────────────────┐
│    quiz_sessions    │────────────────▶│      questions      │
├─────────────────────┤                 ├─────────────────────┤
│ id (PK, uuid)       │                 │ id (PK, uuid)       │
│ user_id (FK, null)  │                 │ session_id (FK)     │
│ topic               │                 │ order_index         │
│ difficulty          │                 │ text                │
│ requested_count     │                 │ options (JSON)      │
│ lives_total         │                 │ correct_index       │
│ lives_left          │                 │ explanation         │
│ score               │                 └──────────┬──────────┘
│ status              │                            │
│ player_name         │                            │ 1:N
│ created_at          │                            ▼
│ finished_at         │                 ┌─────────────────────┐
└──────────┬──────────┘                 │       answers       │
           │ 1:N                        ├─────────────────────┤
           └───────────────────────────▶│ id (PK, uuid)       │
                                        │ session_id (FK)     │
                                        │ question_id (FK)    │
                                        │ selected_index      │
                                        │ is_correct          │
                                        │ answered_at         │
                                        └─────────────────────┘
```

## Enums

- `difficulty`: `easy` | `medium` | `hard`
- `session_status`: `active` | `finished` | `abandoned`

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
