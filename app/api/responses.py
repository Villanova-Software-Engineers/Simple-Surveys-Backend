"""Survey response submission and retrieval endpoints."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from app.crud.file_storage import format_filename_timestamp
from app.dependencies import SchedulerServiceDep, StorageRepoDep
from app.schemas.common import ImageMetadata
from app.schemas.survey_response import (
    SurveyResponseCreate,
    SurveyResponseRecord,
    SurveyResponseSubmissionResult,
)

router = APIRouter(prefix="/responses", tags=["Responses"])


@router.get("", response_model=List[SurveyResponseRecord])
async def list_responses(
    storage_repo: StorageRepoDep,
    survey_id: Optional[str] = Query(None, description="Optional survey_id filter"),
) -> List[SurveyResponseRecord]:
    """Retrieve persisted response records."""
    return await storage_repo.list_responses(survey_id=survey_id)


@router.get("/{survey_id}/{response_id}", response_model=SurveyResponseRecord)
async def get_response(
    survey_id: str,
    response_id: str,
    storage_repo: StorageRepoDep,
) -> SurveyResponseRecord:
    """Retrieve a specific response record."""
    record = await storage_repo.get_response(survey_id, response_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Response '{response_id}' for survey '{survey_id}' not found.",
        )
    return record


@router.get("/{survey_id}/images/{filename}")
async def get_response_image(
    survey_id: str,
    filename: str,
    storage_repo: StorageRepoDep,
) -> FileResponse:
    """Download an uploaded survey response photo."""
    image_path = await storage_repo.get_image_path(survey_id, filename)
    if not image_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image '{filename}' not found for survey '{survey_id}'.",
        )
    return FileResponse(image_path)


@router.post("", response_model=SurveyResponseSubmissionResult)
async def submit_response(
    request: Request,
    storage_repo: StorageRepoDep,
    scheduler_service: SchedulerServiceDep,
) -> JSONResponse:
    """
    Ingests anonymous survey response data with optional camera photo.
    Evaluates submission against the configured time_to_complete_minutes window.
    Supports both multipart/form-data (with JSON string + file) and application/json.
    """
    content_type = request.headers.get("content-type", "")
    submission: SurveyResponseCreate
    uploaded_image: Optional[UploadFile] = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        data_field = form.get("data")
        if not data_field:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Multipart form-data submission requires 'data' field containing survey JSON.",
            )
        try:
            parsed_data = json.loads(data_field) if isinstance(data_field, str) else data_field
            submission = SurveyResponseCreate.model_validate(parsed_data)
        except (json.JSONDecodeError, ValidationError) as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid JSON in 'data' field: {e}",
            )

        img_field = form.get("image")
        if hasattr(img_field, "filename") and bool(getattr(img_field, "filename", None)):
            uploaded_image = img_field
    else:
        try:
            body = await request.json()
            submission = SurveyResponseCreate.model_validate(body)
        except (json.JSONDecodeError, ValidationError) as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid JSON request body: {e}",
            )

    survey = await storage_repo.get_survey(submission.survey_id)
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Survey '{submission.survey_id}' does not exist.",
        )

    response_id = submission.response_id or f"resp_{uuid.uuid4().hex[:8]}"
    received_at = datetime.now(timezone.utc)

    schedule_config = await storage_repo.get_schedule_config()
    time_limit_minutes = schedule_config.time_to_complete_minutes

    res_status, status_message, is_expired, temporal_markers = (
        scheduler_service.evaluate_response_expiration(
            submission=submission,
            time_to_complete_limit_minutes=time_limit_minutes,
            received_at=received_at,
        )
    )

    anchor_dt = submission.completed_at or received_at
    timestamp_str = format_filename_timestamp(anchor_dt)

    image_metadata = ImageMetadata(has_image=False)
    image_stored = False
    stored_img_filename: Optional[str] = None

    if uploaded_image:
        image_bytes = await uploaded_image.read()
        if image_bytes:
            ext = Path(uploaded_image.filename).suffix.lstrip(".") or "jpg"
            stored_img_filename = await storage_repo.save_image(
                survey_id=submission.survey_id,
                response_id=response_id,
                timestamp_str=timestamp_str,
                image_bytes=image_bytes,
                extension=ext,
            )

            img_id = "img_" + response_id[5:] if response_id.startswith("resp_") else f"img_{response_id}"
            image_metadata = ImageMetadata(
                has_image=True,
                image_id=img_id,
                image_filename=stored_img_filename,
                relative_path=f"images/{stored_img_filename}",
            )
            image_stored = True

    # Assemble answers: empty if expired, otherwise retain user answers
    final_answers = [] if is_expired else submission.answers

    record = SurveyResponseRecord(
        response_id=response_id,
        survey_id=submission.survey_id,
        status=res_status,
        status_message=status_message,
        temporal_markers=temporal_markers,
        location=submission.location,
        image=image_metadata,
        answers=final_answers,
    )
    await storage_repo.save_response(record, timestamp_str=timestamp_str)

    if is_expired:
        response_payload = SurveyResponseSubmissionResult(
            response_id=response_id,
            survey_id=submission.survey_id,
            status="EXPIRED",
            status_message=status_message,
            message=status_message,
            image_stored=image_stored,
            image_filename=stored_img_filename,
            received_at=received_at,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=response_payload.model_dump(mode="json"),
        )

    response_payload = SurveyResponseSubmissionResult(
        response_id=response_id,
        survey_id=submission.survey_id,
        status="COMPLETED",
        status_message=status_message,
        message=status_message,
        image_stored=image_stored,
        image_filename=stored_img_filename,
        received_at=received_at,
    )
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=response_payload.model_dump(mode="json"),
    )