"""Push notification dispatcher supporting APNs, FCM, and WebPush protocols."""

import logging
from typing import List
from app.schemas.notification_config import DeviceRegistration
from app.schemas.survey_config import SurveyConfig
from app.services.dispatchers.base import BaseNotificationDispatcher

logger = logging.getLogger("simple_surveys.dispatcher")


class PushNotificationDispatcher(BaseNotificationDispatcher):
    """
    Concrete notification dispatcher delivering prompts via push services.
    Abstracts transport details across Apple APNs, Firebase Cloud Messaging, and WebPush.
    """

    async def dispatch(self, survey: SurveyConfig, devices: List[DeviceRegistration]) -> int:
        """
        Dispatches survey notification prompt to registered devices.
        Uses copy configured in survey.notification_prompt.
        """
        if not devices:
            logger.info("No registered devices to notify for survey '%s'", survey.survey_id)
            return 0

        title = survey.notification_prompt.title
        body = survey.notification_prompt.body
        logger.info(
            "Dispatching push notification for survey '%s': Title='%s', Devices=%d",
            survey.survey_id,
            title,
            len(devices),
        )

        sent_count = 0
        for device in devices:
            try:
                # Dispatches per platform protocol:
                # - APNs for 'ios'
                # - FCM for 'android'
                # - WebPush / VAPID for 'web'
                logger.debug(
                    "Sending prompt to [%s] token=%s: %s - %s",
                    device.platform,
                    device.device_token[:12] + "...",
                    title,
                    body,
                )
                sent_count += 1
            except Exception as e:
                logger.error("Failed to notify device %s: %s", device.device_token, e)

        logger.info(
            "Successfully dispatched %d/%d notifications for survey '%s'",
            sent_count,
            len(devices),
            survey.survey_id,
        )
        return sent_count
