import asyncio

from app.config import get_settings
from app.schemas.quiz import GenerateQuestionsRequest
from app.services import generator


def test_http_generator_falls_back_to_stub():
    get_settings.cache_clear()
    settings = get_settings()
    settings.generator_mode = "http"
    settings.generator_url = "http://127.0.0.1:9/generate"
    settings.generator_timeout_sec = 1
    settings.generator_ranked_timeout_sec = 1

    result = asyncio.run(
        generator.generate_questions(
            GenerateQuestionsRequest(topic="Тест", count=2, difficulty="easy", mode="ranked"),
            settings=settings,
        )
    )
    assert result.count == 2
    assert result.source == "stub"
    assert len(result.questions) == 2
