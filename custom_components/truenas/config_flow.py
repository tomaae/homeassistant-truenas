"""Config flow to configure TrueNAS"""

import voluptuous as vol
from logging import getLogger
from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.core import callback
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_API_KEY,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from .const import (
    DEFAULT_DEVICE_NAME,
    DEFAULT_HOST,
    DEFAULT_SSL,
    DEFAULT_SSL_VERIFY,
    DOMAIN,
)
from .truenas_api import TrueNASAPI

_LOGGER = getLogger(__name__)


# ---------------------------
#   configured_instances
# ---------------------------
@callback
def configured_instances(hass):
    """Return a set of configured instances"""
    return {
        entry.data[CONF_NAME] for entry in hass.config_entries.async_entries(DOMAIN)
    }


# ---------------------------
#   TrueNASConfigFlow
# ---------------------------
class TrueNASConfigFlow(ConfigFlow, domain=DOMAIN):
    """TrueNASConfigFlow class"""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize TrueNASConfigFlow"""

    async def async_step_import(self, user_input=None):
        """Occurs when a previous entry setup fails and is re-initiated"""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user"""
        errors = {}
        if user_input is not None:
            # Check if instance with this name already exists
            if user_input[CONF_NAME] in configured_instances(self.hass):
                errors["base"] = "name_exists"

            # Test connection
            api = await self.hass.async_add_executor_job(
                TrueNASAPI,
                self.hass,
                user_input[CONF_HOST],
                user_input[CONF_API_KEY],
                user_input[CONF_SSL],
                user_input[CONF_VERIFY_SSL],
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
                    title=user_input[CONF_NAME], data=user_input
                )

            return self._show_config_form(user_input=user_input, errors=errors)

        return self._show_config_form(
            user_input={
                CONF_NAME: DEFAULT_DEVICE_NAME,
                CONF_HOST: DEFAULT_HOST,
                CONF_API_KEY: "",
                CONF_SSL: DEFAULT_SSL,
                CONF_VERIFY_SSL: DEFAULT_SSL_VERIFY,
            },
            errors=errors,
        )

    def _show_config_form(self, user_input, errors=None):
        """Show the configuration form"""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=user_input[CONF_NAME]): str,
                    vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str,
                    vol.Required(CONF_API_KEY, default=user_input[CONF_API_KEY]): str,
                    vol.Optional(CONF_SSL, default=user_input[CONF_SSL]): bool,
                    vol.Optional(
                        CONF_VERIFY_SSL, default=user_input[CONF_VERIFY_SSL]
                    ): bool,
                }
            ),
            errors=errors,
        )
