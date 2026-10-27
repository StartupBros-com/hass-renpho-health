"""Config flow for Renpho Health integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .api import RenphoAuthError, RenphoHealthApi
from .const import CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(
            CONF_REFRESH_INTERVAL, default=DEFAULT_REFRESH_INTERVAL
        ): vol.All(vol.Coerce(int), vol.Range(min=300, max=86400)),
    }
)


class RenphoHealthConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Renpho Health."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check if already configured
            await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
            self._abort_if_unique_id_configured()

            # Validate credentials
            api = RenphoHealthApi(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            try:
                if await api.validate_credentials():
                    await api.close()
                    return self.async_create_entry(
                        title=user_input[CONF_EMAIL],
                        data=user_input,
                    )
                errors["base"] = "invalid_auth"
            except RenphoAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during authentication")
                errors["base"] = "unknown"
            finally:
                await api.close()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
