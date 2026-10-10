"""Survey selection service supporting weighted randomized sampling and fixed lookup."""

import logging
import random
from typing import List, Optional
from app.crud.base import BaseStorageRepository
from app.schemas.survey_config import SurveyConfig

logger = logging.getLogger("simple_surveys.selector")


class SurveySelector:
    """Selects fixed anchor surveys or randomized surveys based on weights defined in survey definitions."""

    def __init__(self, repository: BaseStorageRepository):
        self.repository = repository

    async def get_survey_by_id(self, survey_id: str) -> Optional[SurveyConfig]:
        """Fetch survey by its unique ID."""
        return await self.repository.get_survey(survey_id)

    async def select_weighted_random_survey(
        self,
        eligible_survey_ids: List[str]
    ) -> Optional[SurveyConfig]:
        """
        Picks an active survey from eligible_survey_ids according to weights
        specified in each survey's definition file.
        """
        if not eligible_survey_ids:
            logger.warning("No eligible survey IDs provided for randomized selection.")
            return None

        candidates: List[SurveyConfig] = []
        weights: List[float] = []

        for sid in eligible_survey_ids:
            survey = await self.repository.get_survey(sid)
            if survey and survey.is_active:
                candidates.append(survey)
                # Weights must be positive numbers
                w = max(0.001, float(survey.weight))
                weights.append(w)

        if not candidates:
            logger.warning("No active surveys found matching eligible IDs: %s", eligible_survey_ids)
            return None

        selected = random.choices(candidates, weights=weights, k=1)[0]
        logger.info(
            "Selected survey '%s' (weight=%.2f) from pool of %d surveys.",
            selected.survey_id,
            selected.weight,
            len(candidates),
        )
        return selected
