"""Survey management endpoints."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from app.dependencies import StorageRepoDep
from app.schemas.survey_config import (
    SurveyConfig,
    SurveyConfigCreate,
    SurveyConfigUpdate,
)

router = APIRouter(prefix="/surveys", tags=["Surveys"])


@router.get("", response_model=List[SurveyConfig])
async def list_surveys(
    storage_repo: StorageRepoDep,
    active_only: bool = Query(True, description="Filter for only active surveys"),
) -> List[SurveyConfig]:
    """Retrieve surveys stored on the backend."""
    return await storage_repo.list_surveys(active_only=active_only)


@router.get("/{survey_id}", response_model=SurveyConfig)
async def get_survey(
    survey_id: str,
    storage_repo: StorageRepoDep,
) -> SurveyConfig:
    """Retrieve a specific survey definition by ID."""
    survey = await storage_repo.get_survey(survey_id)
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Survey with id '{survey_id}' not found.",
        )
    return survey


@router.post("", response_model=SurveyConfig, status_code=status.HTTP_201_CREATED)
async def create_survey(
    payload: SurveyConfigCreate,
    storage_repo: StorageRepoDep,
) -> SurveyConfig:
    """
    Admin endpoint to create and persist a new survey JSON definition file.
    """
    existing = await storage_repo.get_survey(payload.survey_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Survey with id '{payload.survey_id}' already exists. Use PUT to update.",
        )

    survey = SurveyConfig(**payload.model_dump())
    return await storage_repo.save_survey(survey)


@router.put("/{survey_id}", response_model=SurveyConfig)
async def update_survey(
    survey_id: str,
    payload: SurveyConfigUpdate,
    storage_repo: StorageRepoDep,
) -> SurveyConfig:
    """
    Admin endpoint to update an existing survey JSON definition file.
    """
    existing = await storage_repo.get_survey(survey_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Survey with id '{survey_id}' not found.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    existing_data = existing.model_dump()
    existing_data.update(update_data)
    # Ensure ID does not change unexpectedly
    existing_data["survey_id"] = survey_id

    updated_survey = SurveyConfig(**existing_data)
    return await storage_repo.save_survey(updated_survey)
