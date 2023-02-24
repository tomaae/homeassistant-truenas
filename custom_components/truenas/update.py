"""TrueNAS binary sensor platform."""
from logging import getLogger
from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TrueNASDataUpdateCoordinator
from .model import TrueNASEntity, model_async_setup_entry
from .update_types import SENSOR_SERVICES, SENSOR_TYPES

_LOGGER = getLogger(__name__)
DEVICE_UPDATE = "device_update"


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for OpenMediaVault component."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    dispatcher = {
        "TrueNASUpdate": TrueNASUpdate,
    }
    await model_async_setup_entry(
        hass, coordinator, async_add_entities, SENSOR_SERVICES, SENSOR_TYPES, dispatcher
    )


# ---------------------------
#   TrueNASUpdate
# ---------------------------
class TrueNASUpdate(TrueNASEntity, UpdateEntity):
    """Define an TrueNAS Update Sensor."""

    TYPE = DEVICE_UPDATE
    _attr_device_class = UpdateDeviceClass.FIRMWARE

    def __init__(
        self,
        coordinator: TrueNASDataUpdateCoordinator,
        entity_description: UpdateEntityDescription,
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
            "update/update",
            "post",
            {"reboot": True},
        )
        await self.coordinator.async_request_refresh()

    @property
    def in_progress(self) -> int:
        """Update installation progress."""
        if self._data["update_state"] != "RUNNING":
            return False

        if self._data["update_progress"] == 0:
            self._data["update_progress"] = 1

        return self._data["update_progress"]
