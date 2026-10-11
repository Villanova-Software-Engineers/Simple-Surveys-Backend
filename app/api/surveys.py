"""Survey management endpoints."""

from typing import List
from fastapi import APIRouter, HTTPException, Query, status
from app.dependencies import SchedulerServiceDep, StorageRepoDep
from app.schemas.survey_config import (
    SurveyConfig,
    SurveyConfigCreate,
    SurveyConfigUpdate,
    SurveyDeleteResponse,
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


@router.patch("/{survey_id}", response_model=SurveyConfig)
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


@router.delete("/{survey_id}", response_model=SurveyDeleteResponse)
async def delete_survey(
    survey_id: str,
    storage_repo: StorageRepoDep,
    scheduler_service: SchedulerServiceDep,
    delete_responses: bool = Query(
        False,
        description="Whether to also delete associated response records and uploaded images",
    ),
    clean_schedule_references: bool = Query(
        True,
        description="Whether to automatically remove references to this survey from sampling rules",
    ),
) -> SurveyDeleteResponse:
    """
    Admin endpoint to delete a survey JSON definition file.
    Optionally removes associated response records, uploaded images, and sampling schedule references.
    """
    existing = await storage_repo.get_survey(survey_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Survey with id '{survey_id}' not found.",
        )

    deleted = await storage_repo.delete_survey(survey_id, delete_responses=delete_responses)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Survey with id '{survey_id}' not found.",
        )


    schedule_references_cleaned = False
    if clean_schedule_references:
        try:
            schedule_config = await storage_repo.get_schedule_config()
            if schedule_config is None:
                schedule_references_cleaned = True
            else:
                fixed_survey_ids = {fs.survey_id for fs in schedule_config.fixed_surveys}
                eligible_survey_ids = {rs_id for rs_id in schedule_config.randomized_sampling.eligible_survey_ids}

                if (survey_id in fixed_survey_ids) or (survey_id in eligible_survey_ids):
                    schedule_config.fixed_surveys = [
                        fs for fs in schedule_config.fixed_surveys if fs.survey_id != survey_id
                    ]
                    schedule_config.randomized_sampling.eligible_survey_ids = [
                        sid for sid in schedule_config.randomized_sampling.eligible_survey_ids if sid != survey_id
                    ]
                    await storage_repo.save_schedule_config(schedule_config)
                    await scheduler_service.schedule_daily_jobs()

                schedule_references_cleaned = True
        except Exception:
            schedule_references_cleaned = False

    return SurveyDeleteResponse(
        status="deleted",
        survey_id=survey_id,
        message=f"Survey '{survey_id}' deleted successfully.",
        responses_deleted=delete_responses,
        schedule_references_cleaned=schedule_references_cleaned,
    )
