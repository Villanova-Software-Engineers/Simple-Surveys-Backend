"""Abstract base class for survey and response storage repositories."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional
from app.schemas.notification_config import DeviceRegistration, SamplingRules
from app.schemas.survey_config import SurveyConfig
from app.schemas.survey_response import SurveyResponseRecord


class BaseStorageRepository(ABC):
    """Abstract interface defining storage operations for Simple Surveys."""

    # Survey definitions
    @abstractmethod
    async def save_survey(self, survey: SurveyConfig) -> SurveyConfig:
        """Persist a survey definition."""
        pass

    @abstractmethod
    async def get_survey(self, survey_id: str) -> Optional[SurveyConfig]:
        """Retrieve a survey definition by unique ID."""
        pass

    @abstractmethod
    async def list_surveys(self, active_only: bool = False) -> List[SurveyConfig]:
        """List all stored survey definitions."""
        pass

    @abstractmethod
    async def delete_survey(self, survey_id: str, delete_responses: bool = False) -> bool:
        """
        Delete a survey definition by unique ID.
        Optionally deletes associated responses and media.
        Returns True if deleted, False if not found.
        """
        pass

    # Responses
    @abstractmethod
    async def save_response(
        self,
        record: SurveyResponseRecord,
        timestamp_str: Optional[str] = None
    ) -> SurveyResponseRecord:
        """Save a response record as JSON."""
        pass

    @abstractmethod
    async def get_response(self, survey_id: str, response_id: str) -> Optional[SurveyResponseRecord]:
        """Retrieve a specific response record."""
        pass

    @abstractmethod
    async def list_responses(self, survey_id: Optional[str] = None) -> List[SurveyResponseRecord]:
        """List response records, optionally filtered by survey_id."""
        pass

    # Media / Images
    @abstractmethod
    async def save_image(
        self,
        survey_id: str,
        response_id: str,
        timestamp_str: str,
        image_bytes: bytes,
        extension: str = "jpg"
    ) -> str:
        """Save an image file with matched timestamp and ID prefix."""
        pass

    @abstractmethod
    async def get_image_path(self, survey_id: str, filename: str) -> Optional[Path]:
        """Get absolute path to an image file if it exists."""
        pass

    # Schedule Configuration
    @abstractmethod
    async def get_schedule_config(self) -> Optional[SamplingRules]:
        """Retrieve the current sampling rules configuration, or None if not configured."""
        pass

    @abstractmethod
    async def save_schedule_config(self, config: SamplingRules) -> SamplingRules:
        """Persist updated sampling rules configuration."""
        pass

    # Device Registrations
    @abstractmethod
    async def save_device(self, device: DeviceRegistration) -> DeviceRegistration:
        """Save a registered device token."""
        pass

    @abstractmethod
    async def list_devices(self) -> List[DeviceRegistration]:
        """List all registered devices."""
        pass
