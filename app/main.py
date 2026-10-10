"""Main FastAPI Application Entrypoint."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.dependencies import get_scheduler_service, get_storage_repository

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("simple_surveys")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown lifecycle management."""
    logger.info("Initializing Simple Surveys Backend service...")

    # Ensure repository and schedule configurations are ready
    repo = get_storage_repository()
    await repo.get_schedule_config()

    # Start notification scheduler
    scheduler = get_scheduler_service()
    scheduler.start()
    try:
        await scheduler.schedule_daily_jobs()
    except Exception as e:
        logger.warning("Could not pre-schedule initial daily jobs: %s", e)

    logger.info("Simple Surveys Backend initialized and running.")
    yield

    # Clean shutdown
    logger.info("Shutting down Simple Surveys Backend service...")
    scheduler.shutdown()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title="Simple Surveys Backend",
        description="Persistent backend service for experience sampling surveys, notifications, and responses.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers
    app.include_router(api_router)

    @app.get("/", tags=["Root"])
    async def root():
        return {
            "name": "Simple Surveys Backend",
            "version": "1.0.0",
            "status": "online",
            "docs_url": "/docs",
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
