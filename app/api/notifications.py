"""Notification configuration and device registration endpoints."""

from typing import List
from fastapi import APIRouter
from app.dependencies import SchedulerServiceDep, StorageRepoDep
from app.schemas.notification_config import (
    DeviceRegistration,
    DeviceRegistrationResponse,
    SamplingRules,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/schedule", response_model=SamplingRules)
async def get_schedule(
    storage_repo: StorageRepoDep,
) -> SamplingRules:
    """Retrieve active notification scheduling and sampling configuration."""
    return await storage_repo.get_schedule_config()


@router.put("/schedule", response_model=SamplingRules)
async def update_schedule(
    payload: SamplingRules,
    storage_repo: StorageRepoDep,
    scheduler_service: SchedulerServiceDep,
) -> SamplingRules:
    """
    Admin endpoint to update daily sampling rules.
    Immediately recalculates and re-registers daily scheduler jobs.
    """
    updated_rules = await storage_repo.save_schedule_config(payload)
    # Refresh scheduled jobs for today
    await scheduler_service.schedule_daily_jobs()
    return updated_rules


@router.post("/devices", response_model=DeviceRegistrationResponse)
async def register_device(
    payload: DeviceRegistration,
    storage_repo: StorageRepoDep,
) -> DeviceRegistrationResponse:
    """
    Registers an anonymous device push token for receiving survey prompts.
    """
    await storage_repo.save_device(payload)
    return DeviceRegistrationResponse(
        status="registered",
        device_token=payload.device_token,
    )


@router.get("/devices", response_model=List[DeviceRegistration])
async def list_devices(
    storage_repo: StorageRepoDep,
) -> List[DeviceRegistration]:
    """Retrieve list of all registered devices."""
    return await storage_repo.list_devices()
