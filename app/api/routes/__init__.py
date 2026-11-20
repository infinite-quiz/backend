from fastapi import APIRouter

from app.api.routes import auth, health, leaderboard, quiz, ranked, solo, user

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(leaderboard.router, tags=["leaderboard"])
api_router.include_router(quiz.router, prefix="/quiz", tags=["quiz"])
api_router.include_router(solo.router, prefix="/solo", tags=["solo"])
api_router.include_router(ranked.router, prefix="/ranked", tags=["ranked"])
