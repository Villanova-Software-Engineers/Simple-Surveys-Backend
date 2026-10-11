"""Notification configuration and device registration endpoints."""

from typing import List
from fastapi import APIRouter, HTTPException, status
from app.dependencies import SchedulerServiceDep, StorageRepoDep
from app.schemas.notification_config import (
    DeviceDeleteResponse,
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
    schedule = await storage_repo.get_schedule_config()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sampling rules have not been configured yet. Please configure via POST /api/notifications/schedule.",
        )
    return schedule


@router.get("/devices", response_model=List[DeviceRegistration])
async def list_devices(
    storage_repo: StorageRepoDep,
) -> List[DeviceRegistration]:
    """Retrieve list of all registered devices."""
    return await storage_repo.list_devices()


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


@router.delete("/devices/{device_token}", response_model=DeviceDeleteResponse)
async def delete_device(
    device_token: str,
    storage_repo: StorageRepoDep,
) -> DeviceDeleteResponse:
    """
    Unregister and delete a device push token.
    Clears its registration so it no longer receives scheduled survey notifications.
    """
    device = await storage_repo.get_device(device_token)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device token '{device_token}' not found.",
        )
    await storage_repo.delete_device(device_token)
    return DeviceDeleteResponse(
        status="deleted",
        device_token=device_token,
        message="Device token unregistered and deleted successfully.",
    )


@router.post("/schedule", response_model=SamplingRules)
async def set_schedule(
    payload: SamplingRules,
    storage_repo: StorageRepoDep,
    scheduler_service: SchedulerServiceDep,
) -> SamplingRules:
    """
    Admin endpoint to create or update (upsert) daily sampling rules.
    Validates that all referenced survey IDs exist before persisting.
    Immediately recalculates and re-registers daily scheduler jobs.
    """
    referenced_ids = set()
    for fs in payload.fixed_surveys:
        referenced_ids.add(fs.survey_id)
    for rs_id in payload.randomized_sampling.eligible_survey_ids:
        referenced_ids.add(rs_id)

    missing_surveys: List[str] = []
    for s_id in referenced_ids:
        survey = await storage_repo.get_survey(s_id)
        if not survey:
            missing_surveys.append(s_id)

    if missing_surveys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot configure schedule. The following referenced survey IDs do not exist: {missing_surveys}",
        )

    updated_rules = await storage_repo.save_schedule_config(payload)
    await scheduler_service.schedule_daily_jobs()
    return updated_rules
