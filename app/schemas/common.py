"""Shared schemas and DTO models."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class LocationCoordinates(BaseModel):
    """Geographic location details of survey submission."""
    model_config = ConfigDict(extra="ignore")

    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")
    accuracy_meters: Optional[float] = Field(None, description="Accuracy in meters")
    altitude_meters: Optional[float] = Field(None, description="Altitude in meters")


class TemporalMarkers(BaseModel):
    """Timing and latency markers for response evaluation."""
    model_config = ConfigDict(extra="ignore")

    notification_sent_at: datetime = Field(..., description="Timestamp when notification prompt was dispatched")
    started_at: Optional[datetime] = Field(None, description="Timestamp when participant began answering")
    completed_at: Optional[datetime] = Field(None, description="Timestamp when survey was completed on client")
    received_at: Optional[datetime] = Field(None, description="Timestamp when backend received the submission")
    latency_seconds: Optional[float] = Field(None, description="Seconds between notification_sent_at and received_at")
    completion_duration_seconds: Optional[float] = Field(None, description="Seconds between started_at and completed_at")
    time_to_complete_limit_minutes: Optional[int] = Field(None, description="Configured expiration limit in minutes")


class ImageMetadata(BaseModel):
    """Metadata regarding associated photo capture."""
    model_config = ConfigDict(extra="ignore")

    has_image: bool = Field(False, description="Indicates if a photo was attached")
    image_id: Optional[str] = Field(None, description="Unique identifier for the image (mirrors response_id)")
    image_filename: Optional[str] = Field(None, description="Filename on disk/storage")
    relative_path: Optional[str] = Field(None, description="Relative storage path")
