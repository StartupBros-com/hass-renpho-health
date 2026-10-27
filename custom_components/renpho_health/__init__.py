"""The Renpho Health integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

from .api import RenphoHealthApi
from .const import CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL, DOMAIN
from .coordinator import RenphoHealthCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Renpho Health from a config entry."""
    api = RenphoHealthApi(
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )

    coordinator = None
    previous = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    try:
        coordinator = RenphoHealthCoordinator(
            hass, api, entry.data.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)
        )
        await coordinator.async_config_entry_first_refresh()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        # Cancellation also releases this client's privately owned session.
        state = hass.data.get(DOMAIN, {})
        if coordinator is not None and state.get(entry.entry_id) is coordinator:
            if previous is None:
                state.pop(entry.entry_id)
            else:
                state[entry.entry_id] = previous
        await api.close()
        raise

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: RenphoHealthCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.api.close()

    return unload_ok
