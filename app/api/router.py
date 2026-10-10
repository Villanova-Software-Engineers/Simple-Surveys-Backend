"""Main API router combining all endpoint modules."""

from fastapi import APIRouter
from app.api import health, notifications, responses, surveys

api_router = APIRouter(prefix="/api")

api_router.include_router(health.router)
api_router.include_router(surveys.router)
api_router.include_router(responses.router)
api_router.include_router(notifications.router)
