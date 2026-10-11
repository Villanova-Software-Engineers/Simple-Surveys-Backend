"""Notification scheduler service evaluating daily windows, randomization, and dispatch jobs."""

import logging
import random
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import BaseModel, ConfigDict

from app.config import settings
from app.crud.base import BaseStorageRepository
from app.schemas.notification_config import SamplingRules
from app.schemas.survey_config import SurveyConfig
from app.schemas.survey_response import SurveyResponseCreate
from app.schemas.common import TemporalMarkers
from app.services.dispatchers.base import BaseNotificationDispatcher
from app.services.survey_selector import SurveySelector

logger = logging.getLogger("simple_surveys.scheduler")


class ScheduledDispatch(BaseModel):
    """Represents a planned survey notification dispatch event."""
    model_config = ConfigDict(extra="ignore")

    survey_id: Optional[str] = None
    dispatch_time: datetime
    is_random_pool: bool = False
    position: Optional[str] = None


def parse_time_str(time_str: str) -> time:
    """Parse 'HH:MM' string into time object."""
    parts = time_str.strip().split(":")
    return time(hour=int(parts[0]), minute=int(parts[1]))


def random_time_between(start_dt: datetime, end_dt: datetime) -> datetime:
    """Generate uniform random datetime between start_dt and end_dt."""
    delta = (end_dt - start_dt).total_seconds()
    if delta <= 0:
        raise ValueError(f"end_time '{end_dt}' must be after start_time '{start_dt}'")
    rand_secs = random.uniform(0, delta)
    return start_dt + timedelta(seconds=rand_secs)


class SchedulerService:
    """
    Manages daily sampling calculations, dispatches, and submission expiration checks.
    """

    def __init__(
        self,
        repository: BaseStorageRepository,
        dispatcher: BaseNotificationDispatcher,
        tz_name: Optional[str] = None,
    ):
        self.repository = repository
        self.dispatcher = dispatcher
        self.tz = ZoneInfo(tz_name or settings.scheduler_timezone)
        self.survey_selector = SurveySelector(repository)
        self.scheduler = AsyncIOScheduler(timezone=self.tz)

    async def calculate_daily_dispatch_plan(
        self,
        target_date: Optional[date] = None,
        rules: Optional[SamplingRules] = None,
    ) -> List[ScheduledDispatch]:
        """
        Calculates the complete notification schedule for a day:
        1. Fixed 'first' survey: randomized within first_window (or explicit scheduled_time)
        2. Fixed 'last' survey: randomized within last_window (or explicit scheduled_time)
        3. Intraday randomized surveys: placed between first and last dispatches, enforcing min_interval_minutes
        """
        rules = rules or await self.repository.get_schedule_config()
        if not rules:
            logger.info("No sampling rules configured. Skipping dispatch calculation.")
            return []

        if target_date is None:
            target_date = datetime.now(self.tz).date()

        dispatches: List[ScheduledDispatch] = []

        overall_start_t = parse_time_str(rules.daily_schedule.overall_window.start_time)
        overall_end_t = parse_time_str(rules.daily_schedule.overall_window.end_time)
        overall_start = datetime.combine(target_date, overall_start_t, tzinfo=self.tz)
        overall_end = datetime.combine(target_date, overall_end_t, tzinfo=self.tz)

        first_start_t = parse_time_str(rules.daily_schedule.first_window.start_time)
        first_end_t = parse_time_str(rules.daily_schedule.first_window.end_time)
        first_win_start = datetime.combine(target_date, first_start_t, tzinfo=self.tz)
        first_win_end = datetime.combine(target_date, first_end_t, tzinfo=self.tz)

        last_start_t = parse_time_str(rules.daily_schedule.last_window.start_time)
        last_end_t = parse_time_str(rules.daily_schedule.last_window.end_time)
        last_win_start = datetime.combine(target_date, last_start_t, tzinfo=self.tz)
        last_win_end = datetime.combine(target_date, last_end_t, tzinfo=self.tz)

        first_dispatch_dt: Optional[datetime] = None
        last_dispatch_dt: Optional[datetime] = None

        if rules.mode in ["hybrid", "all_fixed"]:
            for fixed in rules.fixed_surveys:
                if fixed.position == "first":
                    if fixed.scheduled_time:
                        t = parse_time_str(fixed.scheduled_time)
                        dispatch_dt = datetime.combine(target_date, t, tzinfo=self.tz)
                    else:
                        dispatch_dt = random_time_between(first_win_start, first_win_end)

                    first_dispatch_dt = dispatch_dt
                    dispatches.append(
                        ScheduledDispatch(
                            survey_id=fixed.survey_id,
                            dispatch_time=dispatch_dt,
                            is_random_pool=False,
                            position="first",
                        )
                    )

                elif fixed.position == "last":
                    if fixed.scheduled_time:
                        t = parse_time_str(fixed.scheduled_time)
                        dispatch_dt = datetime.combine(target_date, t, tzinfo=self.tz)
                    else:
                        dispatch_dt = random_time_between(last_win_start, last_win_end)

                    last_dispatch_dt = dispatch_dt
                    dispatches.append(
                        ScheduledDispatch(
                            survey_id=fixed.survey_id,
                            dispatch_time=dispatch_dt,
                            is_random_pool=False,
                            position="last",
                        )
                    )

                elif fixed.scheduled_time:
                    t = parse_time_str(fixed.scheduled_time)
                    dispatch_dt = datetime.combine(target_date, t, tzinfo=self.tz)
                    dispatches.append(
                        ScheduledDispatch(
                            survey_id=fixed.survey_id,
                            dispatch_time=dispatch_dt,
                            is_random_pool=False,
                        )
                    )

        if rules.mode in ["hybrid", "all_random"]:
            rand_start = first_dispatch_dt or overall_start
            rand_end = last_dispatch_dt or overall_end

            prompts_needed = rules.randomized_sampling.prompts_per_day
            min_interval = timedelta(minutes=rules.randomized_sampling.min_interval_minutes)

            if rand_end > rand_start + min_interval:
                sampled_times = self._sample_intraday_slots(
                    start_dt=rand_start,
                    end_dt=rand_end,
                    count=prompts_needed,
                    min_interval=min_interval,
                )
                for st in sampled_times:
                    dispatches.append(
                        ScheduledDispatch(
                            survey_id=None,
                            dispatch_time=st,
                            is_random_pool=True,
                        )
                    )

        dispatches.sort(key=lambda d: d.dispatch_time)
        return dispatches

    def _sample_intraday_slots(
        self,
        start_dt: datetime,
        end_dt: datetime,
        count: int,
        min_interval: timedelta,
    ) -> List[datetime]:
        """
        Samples 'count' timestamps between start_dt and end_dt
        with at least min_interval separation between each consecutive timestamp.
        """
        if count <= 0:
            return []

        total_secs = (end_dt - start_dt).total_seconds()
        min_secs = min_interval.total_seconds()

        # If span is too tight for strict min_interval, stratify evenly
        if total_secs < (count + 1) * min_secs:
            step = total_secs / (count + 1)
            return [start_dt + timedelta(seconds=step * (i + 1)) for i in range(count)]

        # Stratified sampling with random jitter
        slot_size = total_secs / count
        results: List[datetime] = []
        last_dt = start_dt

        for i in range(count):
            sub_start = start_dt + timedelta(seconds=i * slot_size)
            sub_end = start_dt + timedelta(seconds=(i + 1) * slot_size)
            
            earliest = max(sub_start, last_dt + min_interval)
            latest = sub_end - timedelta(seconds=1)

            if earliest >= latest:
                picked = earliest
            else:
                picked = random_time_between(earliest, latest)

            results.append(picked)
            last_dt = picked

        return results

    async def execute_dispatch(self, dispatch: ScheduledDispatch) -> None:
        """Execute a scheduled notification dispatch event."""
        rules = await self.repository.get_schedule_config()
        if not rules:
            logger.warning("No sampling rules configured. Skipping dispatch execution.")
            return

        survey: Optional[SurveyConfig] = None

        if dispatch.is_random_pool or not dispatch.survey_id:
            survey = await self.survey_selector.select_weighted_random_survey(
                rules.randomized_sampling.eligible_survey_ids
            )
        else:
            survey = await self.survey_selector.get_survey_by_id(dispatch.survey_id)

        if not survey:
            logger.error("Could not find or select survey for dispatch: %s", dispatch)
            return

        devices = await self.repository.list_devices()
        logger.info(
            "Executing dispatch for survey '%s' at %s to %d devices",
            survey.survey_id,
            dispatch.dispatch_time.isoformat(),
            len(devices),
        )
        await self.dispatcher.dispatch(survey, devices)

    async def schedule_daily_jobs(self) -> None:
        """Compute today's plan and register APScheduler trigger jobs."""
        rules = await self.repository.get_schedule_config()
        if not rules:
            logger.info("No sampling rules configured. Waiting for configuration via API before scheduling dispatches.")
            return

        plan = await self.calculate_daily_dispatch_plan(rules=rules)
        now = datetime.now(self.tz)

        logger.info("Scheduling %d daily dispatches for today", len(plan))
        for dispatch in plan:
            if dispatch.dispatch_time > now:
                job_id = f"dispatch_{dispatch.dispatch_time.strftime('%Y%m%d_%H%M%S')}"
                self.scheduler.add_job(
                    self.execute_dispatch,
                    trigger="date",
                    run_date=dispatch.dispatch_time,
                    args=[dispatch],
                    id=job_id,
                    replace_existing=True,
                )
                logger.info(
                    "Job %s scheduled for %s (survey=%s)",
                    job_id,
                    dispatch.dispatch_time.strftime("%H:%M:%S"),
                    dispatch.survey_id or "random_pool",
                )

    def evaluate_response_expiration(
        self,
        submission: SurveyResponseCreate,
        time_to_complete_limit_minutes: int,
        received_at: Optional[datetime] = None,
    ) -> tuple[str, str, bool, TemporalMarkers]:
        """
        Evaluates the survey submission against the 'time_to_complete_minutes' window:
        delta_t = received_at - notification_sent_at
        
        Returns:
            (status, status_message, is_expired, temporal_markers)
        """
        if received_at is None:
            received_at = datetime.now(timezone.utc)

        sent_at = submission.notification_sent_at
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)

        latency_secs = max(0.0, (received_at - sent_at).total_seconds())

        duration_secs: Optional[float] = None
        if submission.started_at and submission.completed_at:
            duration_secs = max(
                0.0,
                (submission.completed_at - submission.started_at).total_seconds()
            )

        allowed_limit_secs = time_to_complete_limit_minutes * 60
        is_expired = latency_secs > allowed_limit_secs

        temporal_markers = TemporalMarkers(
            notification_sent_at=sent_at,
            started_at=submission.started_at,
            completed_at=submission.completed_at,
            received_at=received_at,
            latency_seconds=round(latency_secs, 2),
            completion_duration_seconds=round(duration_secs, 2) if duration_secs is not None else None,
            time_to_complete_limit_minutes=time_to_complete_limit_minutes,
        )

        if is_expired:
            status = "EXPIRED"
            message = (
                f"User failed to complete survey within "
                f"{time_to_complete_limit_minutes} minutes of notification dispatch."
            )
        else:
            status = "COMPLETED"
            message = "Survey completed successfully within allowed window."

        return status, message, is_expired, temporal_markers

    def start(self) -> None:
        """Start the background scheduler."""
        if not self.scheduler.running:
            self.scheduler.add_job(
                self.schedule_daily_jobs,
                trigger="cron",
                hour=0,
                minute=1,
                id="daily_midnight_planner",
                replace_existing=True,
            )
            self.scheduler.start()
            logger.info("APScheduler started successfully.")

    def shutdown(self) -> None:
        """Stop the background scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("APScheduler shut down.")
