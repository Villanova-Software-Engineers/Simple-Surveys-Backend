"""Notification scheduling and device registration schemas."""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

SamplingMode = Literal["hybrid", "all_random", "all_fixed"]
DevicePlatform = Literal["ios", "android"]


class TimeWindow(BaseModel):
    """Start and end bounds for a time window (HH:MM format)."""
    model_config = ConfigDict(extra="ignore")

    start_time: str = Field(..., description="Start of window in HH:MM format (e.g. '08:00')")
    end_time: str = Field(..., description="End of window in HH:MM format (e.g. '22:00')")


class DailyScheduleWindows(BaseModel):
    """Daily schedule window definitions."""
    model_config = ConfigDict(extra="ignore")

    overall_window: TimeWindow = Field(..., description="Overall daily active window")
    first_window: TimeWindow = Field(..., description="Dedicated window for the first survey of the day")
    last_window: TimeWindow = Field(..., description="Dedicated window for the last survey of the day")


class FixedSurveyConfig(BaseModel):
    """Specification for a fixed survey position or explicit time."""
    model_config = ConfigDict(extra="ignore")

    survey_id: str = Field(..., description="Referenced survey ID")
    position: Optional[Literal["first", "last"]] = Field(
        None,
        description="Anchor position ('first' or 'last'). If scheduled_time is not set, randomized within dedicated window."
    )
    scheduled_time: Optional[str] = Field(
        None,
        description="Explicit dispatch time in HH:MM format (snaps to this time if provided)."
    )


class RandomizedSamplingConfig(BaseModel):
    """Rules for randomized daytime survey sampling."""
    model_config = ConfigDict(extra="ignore")

    prompts_per_day: int = Field(4, description="Number of randomized prompts per day")
    min_interval_minutes: int = Field(90, description="Minimum separation between consecutive prompts in minutes")
    eligible_survey_ids: List[str] = Field(
        default_factory=list,
        description="List of survey IDs eligible for randomized selection"
    )


class SamplingRules(BaseModel):
    """Complete sampling configuration stored in sampling_rules.json."""
    model_config = ConfigDict(extra="ignore")

    mode: SamplingMode = Field("hybrid", description="Sampling mode ('hybrid', 'all_random', 'all_fixed')")
    time_to_complete_minutes: int = Field(
        5,
        description="Window in minutes participants have to submit before answers expire"
    )
    daily_schedule: DailyScheduleWindows = Field(..., description="Window bounds for the day")
    fixed_surveys: List[FixedSurveyConfig] = Field(
        default_factory=list,
        description="List of fixed anchor surveys"
    )
    randomized_sampling: RandomizedSamplingConfig = Field(
        ...,
        description="Settings for intraday randomized sampling"
    )


class DeviceRegistration(BaseModel):
    """Device registration payload for push notifications."""
    model_config = ConfigDict(extra="ignore")

    device_token: str = Field(..., description="Unique push notification device token")
    platform: DevicePlatform = Field("ios", description="Operating system platform ('ios', 'android', 'web')")
    timezone: str = Field("America/New_York", description="Device timezone string")
    registered_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now().astimezone(),
        description="Registration timestamp"
    )


class DeviceRegistrationResponse(BaseModel):
    """Acknowledgement returned on device registration."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field("registered", description="Registration status")
    device_token: str = Field(..., description="Registered device token")
