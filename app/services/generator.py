"""Question generator: stub locally, ML HTTP with stub fallback."""

from __future__ import annotations

import logging

import httpx

from app.config import Settings, get_settings
from app.schemas.quiz import (
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
    GeneratedQuestion,
)

logger = logging.getLogger(__name__)

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
        prefix = f"[{payload.topic} / {payload.difficulty}] "
        text = base.text if payload.mode == "ranked" else f"{prefix}{base.text}"
        if payload.mode == "ranked" and len(text.split()) > 12:
            text = " ".join(text.split()[:10]) + "?"
        questions.append(
            GeneratedQuestion(
                text=text,
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


def _timeout_for(payload: GenerateQuestionsRequest, settings: Settings) -> float:
    if payload.mode == "ranked":
        return float(settings.generator_ranked_timeout_sec)
    return float(settings.generator_timeout_sec)


async def _http_generate(
    payload: GenerateQuestionsRequest,
    settings: Settings,
) -> GenerateQuestionsResponse:
    if not settings.generator_url:
        raise RuntimeError("GENERATOR_URL is not configured")

    body = payload.model_dump()
    timeout = _timeout_for(payload, settings)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(settings.generator_url, json=body)
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

    if mode != "http":
        return _stub_generate(payload)

    try:
        return await _http_generate(payload, settings)
    except Exception as exc:  # noqa: BLE001 — матч не должен падать
        logger.warning("ML generate failed (%s), using stub fallback", exc)
        stub = _stub_generate(payload)
        stub.source = "stub"
        return stub
