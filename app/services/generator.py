"""Question generator: stub now, ML HTTP later."""

from __future__ import annotations

import httpx

from app.config import Settings, get_settings
from app.schemas.quiz import (
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
    GeneratedQuestion,
)


STUB_BANK: dict[str, list[GeneratedQuestion]] = {
    "default": [
        GeneratedQuestion(
            text="Сколько планет в Солнечной системе?",
            options=["7", "8", "9", "10"],
            correct_index=1,
            explanation="После исключения Плутона официально 8 планет.",
        ),
        GeneratedQuestion(
            text="Какой газ преобладает в атмосфере Земли?",
            options=["Кислород", "Азот", "Углекислый газ", "Гелий"],
            correct_index=1,
            explanation="Азот составляет около 78% атмосферы.",
        ),
        GeneratedQuestion(
            text="Столица Франции?",
            options=["Берлин", "Мадрид", "Париж", "Рим"],
            correct_index=2,
            explanation="Париж — столица Франции.",
        ),
        GeneratedQuestion(
            text="2 + 2 × 2 = ?",
            options=["6", "8", "4", "10"],
            correct_index=0,
            explanation="Сначала умножение: 2 + 4 = 6.",
        ),
        GeneratedQuestion(
            text="Кто написал «Войну и мир»?",
            options=["Достоевский", "Толстой", "Чехов", "Пушкин"],
            correct_index=1,
            explanation="Лев Толстой.",
        ),
    ],
}


def _stub_generate(payload: GenerateQuestionsRequest) -> GenerateQuestionsResponse:
    bank = STUB_BANK["default"]
    questions: list[GeneratedQuestion] = []
    for i in range(payload.count):
        base = bank[i % len(bank)]
        questions.append(
            GeneratedQuestion(
                text=f"[{payload.topic} / {payload.difficulty}] {base.text}",
                options=list(base.options),
                correct_index=base.correct_index,
                explanation=base.explanation,
            )
        )
    return GenerateQuestionsResponse(
        topic=payload.topic,
        difficulty=payload.difficulty,
        count=len(questions),
        questions=questions,
        source="stub",
    )


async def _http_generate(
    payload: GenerateQuestionsRequest,
    settings: Settings,
) -> GenerateQuestionsResponse:
    if not settings.generator_url:
        raise RuntimeError("GENERATOR_URL is not configured")

    async with httpx.AsyncClient(timeout=settings.generator_timeout_sec) as client:
        response = await client.post(
            settings.generator_url,
            json=payload.model_dump(),
        )
        response.raise_for_status()
        data = response.json()

    return GenerateQuestionsResponse(
        topic=data.get("topic", payload.topic),
        difficulty=data.get("difficulty", payload.difficulty),
        count=len(data["questions"]),
        questions=[GeneratedQuestion(**q) for q in data["questions"]],
        source="ml",
    )


async def generate_questions(
    payload: GenerateQuestionsRequest,
    settings: Settings | None = None,
) -> GenerateQuestionsResponse:
    settings = settings or get_settings()
    mode = settings.generator_mode.lower()

    if mode == "http":
        return await _http_generate(payload, settings)
    return _stub_generate(payload)
