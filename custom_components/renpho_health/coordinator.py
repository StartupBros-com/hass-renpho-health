"""DataUpdateCoordinator for Renpho Health."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RenphoApiError, RenphoHealthApi, RenphoMeasurement, RenphoUser
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RenphoHealthCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching Renpho Health data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: RenphoHealthApi,
        update_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )
        self.api = api
        self._user: RenphoUser | None = None
        self._latest_measurement: RenphoMeasurement | None = None

    @property
    def user(self) -> RenphoUser | None:
        """Return the user data."""
        return self._user

    @property
    def latest_measurement(self) -> RenphoMeasurement | None:
        """Return the latest measurement."""
        return self._latest_measurement

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the API."""
        try:
            _LOGGER.debug("Fetching Renpho Health data...")
            self._user = await self.api.get_user()
            _LOGGER.debug("Got user: %s", self._user)
            self._latest_measurement = await self.api.get_latest_measurement()
            _LOGGER.debug("Got measurement: %s", self._latest_measurement)

            if not self._latest_measurement:
                _LOGGER.warning("No measurements found for Renpho Health")
                return {}

            m = self._latest_measurement
            return {
                "weight": m.weight,
                "bmi": m.bmi,
                "bodyfat": m.bodyfat,
                "water": m.water,
                "muscle": m.muscle,
                "bone": m.bone,
                "bmr": m.bmr,
                "visceral_fat": m.visceral_fat,
                "body_age": m.body_age,
                "protein": m.protein,
                "subcutaneous_fat": m.subcutaneous_fat,
                "skeletal_muscle": m.skeletal_muscle,
                "heart_rate": m.heart_rate,
                "last_updated": m.datetime,
            }
        except RenphoApiError as err:
            _LOGGER.error("Renpho API error: %s", err)
            raise UpdateFailed(f"Error fetching Renpho data: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching Renpho data")
            raise UpdateFailed(f"Unexpected error: {err}") from err
