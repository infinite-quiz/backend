# Схема БД

## ER-диаграмма

```text
┌─────────────────────┐       1:N       ┌─────────────────────┐
│    quiz_sessions    │────────────────▶│      questions      │
├─────────────────────┤                 ├─────────────────────┤
│ id (PK, uuid)       │                 │ id (PK, uuid)       │
│ topic               │                 │ session_id (FK)     │
│ difficulty          │                 │ order_index         │
│ requested_count     │                 │ text                │
│ lives_total         │                 │ options (JSON)      │
│ lives_left          │                 │ correct_index       │
│ score               │                 │ explanation         │
│ status              │                 └──────────┬──────────┘
│ player_name         │                            │
│ created_at          │                            │ 1:N
│ finished_at         │                            ▼
└──────────┬──────────┘                 ┌─────────────────────┐
           │ 1:N                        │       answers       │
           └───────────────────────────▶├─────────────────────┤
                                        │ id (PK, uuid)       │
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
