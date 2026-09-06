"""Tests for the TrueNAS config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_NAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.truenas.const import DOMAIN

USER_INPUT = {
    CONF_NAME: "TrueNAS",
    CONF_HOST: "10.0.0.1",
    CONF_API_KEY: "api-key",
    CONF_VERIFY_SSL: False,
}


class StubAPI:
    """Stub replacing TrueNASAPI in the config flow."""

    result: tuple[bool, str] = (True, "")
    instances: list[StubAPI] = []

    def __init__(self, host, api_key, verify_ssl):
        """Record the constructor arguments."""
        self.host = host
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        StubAPI.instances.append(self)

    def connection_test(self):
        """Return the canned connection result."""
        return StubAPI.result


@pytest.fixture(autouse=True)
def reset_stub():
    """Reset the stub between tests."""
    StubAPI.instances = []
    StubAPI.result = (True, "")
    yield


async def test_user_flow_shows_form(hass: HomeAssistant) -> None:
    """The user step starts with an empty form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """A reachable TrueNAS creates a config entry."""
    with patch("custom_components.truenas.config_flow.TrueNASAPI", StubAPI):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "TrueNAS"
    assert result["data"] == USER_INPUT
    assert StubAPI.instances[0].host == "10.0.0.1"


async def test_user_flow_connection_error(hass: HomeAssistant) -> None:
    """A failed connection is surfaced on the host field."""
    StubAPI.result = (False, "connection_refused")
    with patch("custom_components.truenas.config_flow.TrueNASAPI", StubAPI):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "connection_refused"}
