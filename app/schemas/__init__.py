"""DTO schemas package for Simple Surveys."""

from app.schemas.common import ImageMetadata, LocationCoordinates, TemporalMarkers
from app.schemas.survey_config import (
    QuestionConfig,
    SurveyConfig,
    SurveyConfigCreate,
    SurveyConfigUpdate,
    SurveyDeleteResponse,
    SurveyNotificationPrompt,
)
from app.schemas.survey_response import (
    AnswerItem,
    SurveyResponseCreate,
    SurveyResponseRecord,
    SurveyResponseSubmissionResult,
)
from app.schemas.notification_config import (
    DailyScheduleWindows,
    DeviceRegistration,
    DeviceRegistrationResponse,
    FixedSurveyConfig,
    RandomizedSamplingConfig,
    SamplingRules,
    TimeWindow,
)

__all__ = [
    "ImageMetadata",
    "LocationCoordinates",
    "TemporalMarkers",
    "QuestionConfig",
    "SurveyConfig",
    "SurveyConfigCreate",
    "SurveyConfigUpdate",
    "SurveyDeleteResponse",
    "SurveyNotificationPrompt",
    "AnswerItem",
    "SurveyResponseCreate",
    "SurveyResponseRecord",
    "SurveyResponseSubmissionResult",
    "TimeWindow",
    "DailyScheduleWindows",
    "FixedSurveyConfig",
    "RandomizedSamplingConfig",
    "SamplingRules",
    "DeviceRegistration",
    "DeviceRegistrationResponse",
]
