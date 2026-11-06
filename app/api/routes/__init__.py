from fastapi import APIRouter

from app.api.routes import health, quiz, ranked

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(quiz.router, prefix="/quiz", tags=["quiz"])
api_router.include_router(ranked.router, prefix="/ranked", tags=["ranked"])
