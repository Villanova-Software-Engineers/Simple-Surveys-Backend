"""Base notification dispatcher interface."""

from abc import ABC, abstractmethod
from typing import List
from app.schemas.notification_config import DeviceRegistration
from app.schemas.survey_config import SurveyConfig


class BaseNotificationDispatcher(ABC):
    """Abstract interface for dispatching notifications to devices."""

    @abstractmethod
    async def dispatch(self, survey: SurveyConfig, devices: List[DeviceRegistration]) -> int:
        """
        Deliver notification prompt to the provided devices.
        
        Args:
            survey: Survey configuration holding the notification copy.
            devices: List of registered devices to notify.
            
        Returns:
            Count of successfully dispatched messages.
        """
        pass
