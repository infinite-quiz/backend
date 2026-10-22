# Ветки и workflow (org: infinite-quiz)

## Репозитории

| Repo | URL |
|------|-----|
| backend | https://github.com/infinite-quiz/backend |
| frontend | https://github.com/infinite-quiz/frontend |
| ml | https://github.com/infinite-quiz/ml |

## Ветки (одинаково во всех репо)

```text
main      — стабильное, только через PR
develop   — интеграция недели
feature/* — задачи
fix/*     — багфиксы
```

## Правила

1. В `main` и `develop` — **не пушить напрямую**, только Pull Request.
2. Одна задача = одна ветка, например:
   - `feature/quiz-generate-stub`
   - `feature/game-screen`
   - `feature/prompt-v1`
3. Перед PR: rebase/merge от `develop`, зелёный локальный запуск.
4. Approve: минимум тимлид (или 1 другой участник).

## Пример для backend

```bash
git checkout develop
git pull
git checkout -b feature/my-task
# ... работа ...
git push -u origin feature/my-task
# PR: feature/my-task → develop
```
