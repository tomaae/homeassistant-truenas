"""TrueNAS binary sensor platform."""
from __future__ import annotations

from logging import getLogger
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .binary_sensor_types import SENSOR_SERVICES, SENSOR_TYPES
from .model import TrueNASEntity, model_async_setup_entry

_LOGGER = getLogger(__name__)


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker for OpenMediaVault component."""
    dispatcher = {
        "TrueNASBinarySensor": TrueNASBinarySensor,
        "TrueNASJailBinarySensor": TrueNASJailBinarySensor,
        "TrueNASVMBinarySensor": TrueNASVMBinarySensor,
        "TrueNASServiceBinarySensor": TrueNASServiceBinarySensor,
        "TrueNASAppBinarySensor": TrueNASAppBinarySensor,
    }
    await model_async_setup_entry(
        hass,
        config_entry,
        async_add_entities,
        SENSOR_SERVICES,
        SENSOR_TYPES,
        dispatcher,
    )


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

    async def start(self) -> None:
        """Start a Jail."""
        tmp_jail = await self.hass.async_add_executor_job(
            self._ctrl.api.query, f"jail/id/{self._data['id']}"
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
            self._ctrl.api.query, "jail/start", "post", self._data["id"]
        )

    async def stop(self) -> None:
        """Stop a Jail."""
        tmp_jail = await self.hass.async_add_executor_job(
            self._ctrl.api.query, f"jail/id/{self._data['id']}"
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
            self._ctrl.api.query, "jail/stop", "post", {"jail": self._data["id"]}
        )

    async def restart(self) -> None:
        """Restart a Jail."""
        tmp_jail = await self.hass.async_add_executor_job(
            self._ctrl.api.query, f"jail/id/{self._data['id']}"
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
            self._ctrl.api.query, "jail/restart", "post", self._data["id"]
        )


# ---------------------------
#   TrueNASVMBinarySensor
# ---------------------------
class TrueNASVMBinarySensor(TrueNASBinarySensor):
    """Define a TrueNAS VM Binary Sensor."""

    async def start(self) -> None:
        """Start a VM."""
        tmp_vm = await self.hass.async_add_executor_job(
            self._ctrl.api.query, f"vm/id/{self._data['id']}"
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
            self._ctrl.api.query, f"vm/id/{self._data['id']}/start", "post"
        )

    async def stop(self) -> None:
        """Stop a VM."""
        tmp_vm = await self.hass.async_add_executor_job(
            self._ctrl.api.query, f"vm/id/{self._data['id']}"
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
            self._ctrl.api.query, f"vm/id/{self._data['id']}/stop", "post"
        )


# ---------------------------
#   TrueNASServiceBinarySensor
# ---------------------------
class TrueNASServiceBinarySensor(TrueNASBinarySensor):
    """Define a TrueNAS Service Binary Sensor."""

    async def start(self) -> None:
        """Start a Service."""
        tmp_service = await self.hass.async_add_executor_job(
            self._ctrl.api.query, f"service/id/{self._data['id']}"
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
            self._ctrl.api.query,
            "service/start",
            "post",
            {"service": self._data["service"]},
        )
        await self._ctrl.async_update()

    async def stop(self) -> None:
        """Stop a Service."""
        tmp_service = await self.hass.async_add_executor_job(
            self._ctrl.api.query, f"service/id/{self._data['id']}"
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
            self._ctrl.api.query,
            "service/stop",
            "post",
            {"service": self._data["service"]},
        )
        await self._ctrl.async_update()

    async def restart(self) -> None:
        """Restart a Service."""
        tmp_service = await self.hass.async_add_executor_job(
            self._ctrl.api.query, f"service/id/{self._data['id']}"
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
            self._ctrl.api.query,
            "service/restart",
            "post",
            {"service": self._data["service"]},
        )
        await self._ctrl.async_update()

    async def reload(self) -> None:
        """Reload a Service."""
        tmp_service = await self.hass.async_add_executor_job(
            self._ctrl.api.query, f"service/id/{self._data['id']}"
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
            self._ctrl.api.query,
            "service/reload",
            "post",
            {"service": self._data["service"]},
        )
        await self._ctrl.async_update()


# ---------------------------
#   TrueNASAppsBinarySensor
# ---------------------------
class TrueNASAppBinarySensor(TrueNASBinarySensor):
    """Define a TrueNAS Applications Binary Sensor."""

    async def start(self) -> None:
        """Start a VM."""
        tmp_vm = await self.hass.async_add_executor_job(
            self._ctrl.api.query, f"/chart/release/id/{self._data['id']}"
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
            self._ctrl.api.query,
            "/chart/release/scale",
            "post",
            {"release_name": self._data["id"], "scale_options": {"replica_count": 1}},
        )

    async def stop(self) -> None:
        """Stop a VM."""
        tmp_vm = await self.hass.async_add_executor_job(
            self._ctrl.api.query, f"/chart/release/id/{self._data['id']}"
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
            self._ctrl.api.query,
            "/chart/release/scale",
            "post",
            {"release_name": self._data["id"], "scale_options": {"replica_count": 0}},
        )

    async def upgrade(self, **kwargs: Any) -> None:
        """Update chart to latest release."""
        version = kwargs.get("version", self._data["latest_version"])
        await self.hass.async_add_executor_job(
            self._ctrl.api.query,
            "/chart/release/upgrade",
            "post",
            {
                "release_name": self._data["id"],
                "upgrade_options": {"values": {}, "item_version": version},
            },
        )
