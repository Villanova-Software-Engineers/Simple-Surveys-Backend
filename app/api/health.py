"""Health check endpoint."""

from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter
from app.config import settings
from app.dependencies import StorageRepoDep

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=Dict[str, Any])
async def check_health(storage_repo: StorageRepoDep) -> Dict[str, Any]:
    """
    Verifies that the FastAPI server is running and the storage directory is accessible.
    """
    surveys = await storage_repo.list_surveys(active_only=True)
    return {
        "status": "healthy",
        "storage_backend": settings.storage_backend,
        "storage_path": f"{settings.data_dir}/",
        "active_surveys_count": len(surveys),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
