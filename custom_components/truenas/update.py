"""TrueNAS binary sensor platform."""

from __future__ import annotations

from logging import getLogger
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)

from .coordinator import TrueNASCoordinator
from .entity import TrueNASEntity, async_add_entities
from .update_types import SENSOR_SERVICES, SENSOR_TYPES

_LOGGER = getLogger(__name__)
DEVICE_UPDATE = "device_update"


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    _async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker for TrueNAS component."""
    dispatcher = {
        "TrueNASUpdate": TrueNASUpdate,
        "TrueNASAppUpdate": TrueNASAppUpdate,
    }
    await async_add_entities(hass, config_entry, dispatcher)


# ---------------------------
#   TrueNASUpdate
# ---------------------------
class TrueNASUpdate(TrueNASEntity, UpdateEntity):
    """Define an TrueNAS Update Sensor."""

    TYPE = DEVICE_UPDATE
    _attr_device_class = UpdateDeviceClass.FIRMWARE

    def __init__(
        self,
        coordinator: TrueNASCoordinator,
        entity_description,
        uid: str | None = None,
    ):
        """Set up device update entity."""
        super().__init__(coordinator, entity_description, uid)

        self._attr_supported_features = UpdateEntityFeature.INSTALL
        self._attr_supported_features |= UpdateEntityFeature.PROGRESS
        self._attr_title = self.entity_description.title

    @property
    def installed_version(self) -> str:
        """Version installed and in use."""
        return self._data["version"]

    @property
    def latest_version(self) -> str:
        """Latest version available for install."""
        return self._data["update_version"]

    async def options_updated(self) -> None:
        """No action needed."""

    async def async_install(self, version: str, backup: bool, **kwargs: Any) -> None:
        """Install an update."""
        self._data["update_jobid"] = await self.hass.async_add_executor_job(
            self.coordinator.api.query,
            "update.update",
            {"reboot": True},
        )
        await self.coordinator.async_refresh()

    @property
    def in_progress(self) -> int:
        """Update installation progress."""
        if self._data["update_state"] != "RUNNING":
            return False

        if self._data["update_progress"] == 0:
            self._data["update_progress"] = 1

        return self._data["update_progress"]


# ---------------------------
#   TrueNASAppUpdate
# ---------------------------
class TrueNASAppUpdate(TrueNASEntity, UpdateEntity):
    """Define an TrueNAS App Update Sensor."""

    TYPE = DEVICE_UPDATE

    def __init__(
        self,
        coordinator: TrueNASCoordinator,
        entity_description,
        uid: str | None = None,
    ):
        """Set up device update entity."""
        super().__init__(coordinator, entity_description, uid)

        self._attr_supported_features = UpdateEntityFeature.INSTALL

    @property
    def installed_version(self) -> str:
        """Version installed and in use."""
        return self._data["version"]

    @property
    def latest_version(self) -> str:
        """Latest version available for install."""
        return self._data["version"]

    async def async_install(self, version: str, backup: bool, **kwargs: Any) -> None:
        """Install an update."""
        if self.coordinator.data["app"][self._data["id"]]["state"] != "RUNNING":
            _LOGGER.error(
                "In order to upgrade an app %s, it must not be in stopped state.",
                self._data["id"],
            )
            return

        self._data["update_jobid"] = await self.hass.async_add_executor_job(
            self.coordinator.api.query,
            "app.upgrade",
            [self._data["id"]],
        )
        await self.coordinator.async_refresh()

    @property
    def in_progress(self) -> bool:
        """Return if update is in progress."""
        return bool(self._data.get("update_jobid"))

    @property
    def title(self) -> str | None:
        """Return the title of the entity."""
        return self._data["name"]
