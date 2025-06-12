"""Config flow to configure TrueNAS."""

from __future__ import annotations

from collections.abc import Mapping
from logging import getLogger
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DEFAULT_DEVICE_NAME,
    DEFAULT_HOST,
    DEFAULT_SSL_VERIFY,
    DOMAIN,
)
from .api import TrueNASAPI

_LOGGER = getLogger(__name__)


def _base_schema(truenas_config: Mapping[str, Any]) -> vol.Schema:
    """Generate base schema."""
    base_schema = {
        vol.Required(
            CONF_NAME, default=truenas_config.get(CONF_NAME) or DEFAULT_DEVICE_NAME
        ): str,
        vol.Required(
            CONF_HOST, default=truenas_config.get(CONF_HOST) or DEFAULT_HOST
        ): str,
        vol.Required(CONF_API_KEY, default=truenas_config.get(CONF_API_KEY) or ""): str,
        vol.Required(
            CONF_VERIFY_SSL,
            default=truenas_config.get(CONF_VERIFY_SSL) or DEFAULT_SSL_VERIFY,
        ): bool,
    }

    return vol.Schema(base_schema)


def _reconfigure_schema(truenas_config: Mapping[str, Any]) -> vol.Schema:
    """Generate base schema."""
    base_schema = {
        vol.Required(
            CONF_HOST, default=truenas_config.get(CONF_HOST) or DEFAULT_HOST
        ): str,
        vol.Required(CONF_API_KEY, default=truenas_config.get(CONF_API_KEY) or ""): str,
        vol.Required(
            CONF_VERIFY_SSL,
            default=truenas_config.get(CONF_VERIFY_SSL) or DEFAULT_SSL_VERIFY,
        ): bool,
    }

    return vol.Schema(base_schema)


# ---------------------------
#   configured_instances
# ---------------------------
@callback
def configured_instances(hass):
    """Return a set of configured instances."""
    return {
        entry.data[CONF_NAME] for entry in hass.config_entries.async_entries(DOMAIN)
    }


# ---------------------------
#   TrueNASConfigFlow
# ---------------------------
class TrueNASConfigFlow(ConfigFlow, domain=DOMAIN):
    """TrueNASConfigFlow class."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.truenas_config: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        truenas_config = self.truenas_config
        errors = {}

        if user_input is not None:
            truenas_config.update(user_input)

            # Check if instance with this name already exists
            if truenas_config[CONF_NAME] in configured_instances(self.hass):
                errors["base"] = "name_exists"

            # Test connection
            api = await self.hass.async_add_executor_job(
                TrueNASAPI,
                truenas_config[CONF_HOST],
                truenas_config[CONF_API_KEY],
                truenas_config[CONF_VERIFY_SSL],
            )

            conn, errorcode = await self.hass.async_add_executor_job(
                api.connection_test
            )

            if not conn:
                errors[CONF_HOST] = errorcode
                _LOGGER.error("TrueNAS connection error (%s)", errorcode)

            # Save instance
            if not errors:
                return self.async_create_entry(
                    title=truenas_config[CONF_NAME], data=truenas_config
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_base_schema(truenas_config),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        truenas_config = self.truenas_config
        reconfigure_entry = self._get_reconfigure_entry()
        errors = {}

        if user_input is not None:
            truenas_config.update(user_input)

            # Test connection
            api = await self.hass.async_add_executor_job(
                TrueNASAPI,
                truenas_config[CONF_HOST],
                truenas_config[CONF_API_KEY],
                truenas_config[CONF_VERIFY_SSL],
            )

            conn, errorcode = await self.hass.async_add_executor_job(
                api.connection_test
            )

            if not conn:
                errors[CONF_HOST] = errorcode
                _LOGGER.error("TrueNAS connection error (%s)", errorcode)

            # Save instance
            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    title=reconfigure_entry.data[CONF_NAME],
                    data_updates=truenas_config,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_reconfigure_schema(reconfigure_entry.data),
            errors=errors,
        )
