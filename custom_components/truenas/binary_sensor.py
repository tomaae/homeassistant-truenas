"""TrueNAS binary sensor platform."""

from __future__ import annotations
from logging import getLogger

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .binary_sensor_types import (
    SENSOR_SERVICES,
    SENSOR_TYPES,
)
from .entity import TrueNASEntity, async_add_entities

_LOGGER = getLogger(__name__)


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    _async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker for OpenMediaVault component."""
    dispatcher = {
        "TrueNASBinarySensor": TrueNASBinarySensor,
        "TrueNASJailBinarySensor": TrueNASJailBinarySensor,
        "TrueNASVMBinarySensor": TrueNASVMBinarySensor,
        "TrueNASServiceBinarySensor": TrueNASServiceBinarySensor,
        "TrueNASAppBinarySensor": TrueNASAppBinarySensor,
    }
    await async_add_entities(hass, config_entry, dispatcher)


# ---------------------------
#   TrueNASBinarySensor
# ---------------------------
class TrueNASBinarySensor(TrueNASEntity, BinarySensorEntity):
    """Define an TrueNAS Binary Sensor."""

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._data[self.entity_description.data_is_on]

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self.entity_description.icon_enabled:
            if self._data[self.entity_description.data_is_on]:
                return self.entity_description.icon_enabled
            else:
                return self.entity_description.icon_disabled


# ---------------------------
#   TrueNASJailBinarySensor
# ---------------------------
class TrueNASJailBinarySensor(TrueNASBinarySensor):
    """Define a TrueNAS Jail Binary Sensor."""

    async def start(self):
        """Start a Jail."""
        tmp_jail = await self.hass.async_add_executor_job(
            self.coordinator.api.query, f"jail/id/{self._data['id']}"
        )

        if "state" not in tmp_jail:
            _LOGGER.error(
                "Jail %s (%s) invalid", self._data["comment"], self._data["id"]
            )
            return

        if tmp_jail["state"] != "down":
            _LOGGER.warning(
                "Jail %s (%s) is not down", self._data["comment"], self._data["id"]
            )
            return

        await self.hass.async_add_executor_job(
            self.coordinator.api.query, "jail/start", "post", self._data["id"]
        )

    async def stop(self):
        """Stop a Jail."""
        tmp_jail = await self.hass.async_add_executor_job(
            self.coordinator.api.query, f"jail/id/{self._data['id']}"
        )

        if "state" not in tmp_jail:
            _LOGGER.error(
                "Jail %s (%s) invalid", self._data["comment"], self._data["id"]
            )
            return

        if tmp_jail["state"] != "up":
            _LOGGER.warning(
                "Jail %s (%s) is not up", self._data["comment"], self._data["id"]
            )
            return

        await self.hass.async_add_executor_job(
            self.coordinator.api.query, "jail/stop", "post", {"jail": self._data["id"]}
        )

    async def restart(self):
        """Restart a Jail."""
        tmp_jail = await self.hass.async_add_executor_job(
            self.coordinator.api.query, f"jail/id/{self._data['id']}"
        )

        if "state" not in tmp_jail:
            _LOGGER.error(
                "Jail %s (%s) invalid", self._data["comment"], self._data["id"]
            )
            return

        if tmp_jail["state"] != "up":
            _LOGGER.warning(
                "Jail %s (%s) is not up", self._data["comment"], self._data["id"]
            )
            return

        await self.hass.async_add_executor_job(
            self.coordinator.api.query, "jail/restart", "post", self._data["id"]
        )


# ---------------------------
#   TrueNASVMBinarySensor
# ---------------------------
class TrueNASVMBinarySensor(TrueNASBinarySensor):
    """Define a TrueNAS VM Binary Sensor."""

    async def start(self, overcommit: bool = False):
        """Start a VM."""
        tmp_vm = await self.hass.async_add_executor_job(
            self.coordinator.api.query, f"vm/id/{self._data['id']}"
        )

        if "status" not in tmp_vm:
            _LOGGER.error("VM %s (%s) invalid", self._data["name"], self._data["id"])
            return

        if tmp_vm["status"]["state"] != "STOPPED":
            _LOGGER.warning(
                "VM %s (%s) is not down", self._data["name"], self._data["id"]
            )
            return

        await self.hass.async_add_executor_job(
            self.coordinator.api.query,
            f"vm/id/{self._data['id']}/start",
            "post",
            {"overcommit": overcommit},
        )

    async def stop(self):
        """Stop a VM."""
        tmp_vm = await self.hass.async_add_executor_job(
            self.coordinator.api.query, f"vm/id/{self._data['id']}"
        )

        if "status" not in tmp_vm:
            _LOGGER.error("VM %s (%s) invalid", self._data["name"], self._data["id"])
            return

        if tmp_vm["status"]["state"] != "RUNNING":
            _LOGGER.warning(
                "VM %s (%s) is not up", self._data["name"], self._data["id"]
            )
            return

        await self.hass.async_add_executor_job(
            self.coordinator.api.query, f"vm/id/{self._data['id']}/stop", "post"
        )


# ---------------------------
#   TrueNASServiceBinarySensor
# ---------------------------
class TrueNASServiceBinarySensor(TrueNASBinarySensor):
    """Define a TrueNAS Service Binary Sensor."""

    async def start(self):
        """Start a Service."""
        tmp_service = await self.hass.async_add_executor_job(
            self.coordinator.api.query, f"service/id/{self._data['id']}"
        )

        if "state" not in tmp_service:
            _LOGGER.error(
                "Service %s (%s) invalid", self._data["service"], self._data["id"]
            )
            return

        if tmp_service["state"] != "STOPPED":
            _LOGGER.warning(
                "Service %s (%s) is not stopped",
                self._data["service"],
                self._data["id"],
            )
            return

        await self.hass.async_add_executor_job(
            self.coordinator.api.query,
            "service/start",
            "post",
            {"service": self._data["service"]},
        )
        await self.coordinator.async_refresh()

    async def stop(self):
        """Stop a Service."""
        tmp_service = await self.hass.async_add_executor_job(
            self.coordinator.api.query, f"service/id/{self._data['id']}"
        )

        if "state" not in tmp_service:
            _LOGGER.error(
                "Service %s (%s) invalid", self._data["service"], self._data["id"]
            )
            return

        if tmp_service["state"] == "STOPPED":
            _LOGGER.warning(
                "Service %s (%s) is not running",
                self._data["service"],
                self._data["id"],
            )
            return

        await self.hass.async_add_executor_job(
            self.coordinator.api.query,
            "service/stop",
            "post",
            {"service": self._data["service"]},
        )
        await self.coordinator.async_refresh()

    async def restart(self):
        """Restart a Service."""
        tmp_service = await self.hass.async_add_executor_job(
            self.coordinator.api.query, f"service/id/{self._data['id']}"
        )

        if "state" not in tmp_service:
            _LOGGER.error(
                "Service %s (%s) invalid", self._data["service"], self._data["id"]
            )
            return

        if tmp_service["state"] == "STOPPED":
            _LOGGER.warning(
                "Service %s (%s) is not running",
                self._data["service"],
                self._data["id"],
            )
            return

        await self.hass.async_add_executor_job(
            self.coordinator.api.query,
            "service/restart",
            "post",
            {"service": self._data["service"]},
        )
        await self.coordinator.async_refresh()

    async def reload(self):
        """Reload a Service."""
        tmp_service = await self.hass.async_add_executor_job(
            self.coordinator.api.query, f"service/id/{self._data['id']}"
        )

        if "state" not in tmp_service:
            _LOGGER.error(
                "Service %s (%s) invalid", self._data["service"], self._data["id"]
            )
            return

        if tmp_service["state"] == "STOPPED":
            _LOGGER.warning(
                "Service %s (%s) is not running",
                self._data["service"],
                self._data["id"],
            )
            return

        await self.hass.async_add_executor_job(
            self.coordinator.api.query,
            "service/reload",
            "post",
            {"service": self._data["service"]},
        )
        await self.coordinator.async_refresh()


# ---------------------------
#   TrueNASAppsBinarySensor
# ---------------------------
class TrueNASAppBinarySensor(TrueNASBinarySensor):
    """Define a TrueNAS Applications Binary Sensor."""

    async def start(self):
        """Start a VM."""
        tmp_vm = await self.hass.async_add_executor_job(
            self.coordinator.api.query, f"/chart/release/id/{self._data['id']}"
        )

        if "status" not in tmp_vm:
            _LOGGER.error("VM %s (%s) invalid", self._data["name"], self._data["id"])
            return

        if tmp_vm["status"] == "ACTIVE":
            _LOGGER.warning(
                "VM %s (%s) is not down", self._data["name"], self._data["id"]
            )
            return

        await self.hass.async_add_executor_job(
            self.coordinator.api.query,
            "/chart/release/scale",
            "post",
            {"release_name": self._data["id"], "scale_options": {"replica_count": 1}},
        )

    async def stop(self):
        """Stop a VM."""
        tmp_vm = await self.hass.async_add_executor_job(
            self.coordinator.api.query, f"/chart/release/id/{self._data['id']}"
        )

        if "status" not in tmp_vm:
            _LOGGER.error("VM %s (%s) invalid", self._data["name"], self._data["id"])
            return

        if tmp_vm["status"] != "ACTIVE":
            _LOGGER.warning(
                "VM %s (%s) is not up", self._data["name"], self._data["id"]
            )
            return

        await self.hass.async_add_executor_job(
            self.coordinator.api.query,
            "/chart/release/scale",
            "post",
            {"release_name": self._data["id"], "scale_options": {"replica_count": 0}},
        )
