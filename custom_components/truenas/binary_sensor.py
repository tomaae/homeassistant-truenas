"""TrueNAS binary sensor platform."""
from __future__ import annotations

from logging import getLogger

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .binary_sensor_types import SENSOR_SERVICES, SENSOR_TYPES  # noqa: F401
from .coordinator import async_add_entities
from .model import TrueNASEntity

_LOGGER = getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, _async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for OpenMediaVault component."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    dispatcher = {
        "TrueNASBinarySensor": TrueNASBinarySensor,
        "TrueNASJailBinarySensor": TrueNASJailBinarySensor,
        "TrueNASVMBinarySensor": TrueNASVMBinarySensor,
        "TrueNASServiceBinarySensor": TrueNASServiceBinarySensor,
        "TrueNASAppBinarySensor": TrueNASAppBinarySensor,
    }
    await async_add_entities(hass, entry, dispatcher)


class TrueNASBinarySensor(TrueNASEntity, BinarySensorEntity):
    """Define an TrueNAS Binary Sensor."""

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._data[self.description.data_is_on]

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self._data[self.description.data_is_on]:
            return self.description.icon_enabled
        return self.description.icon_disabled


class TrueNASJailBinarySensor(TrueNASBinarySensor):
    """Define a TrueNAS Jail Binary Sensor."""

    async def start(self) -> None:
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

    async def stop(self) -> None:
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

    async def restart(self) -> None:
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


class TrueNASVMBinarySensor(TrueNASBinarySensor):
    """Define a TrueNAS VM Binary Sensor."""

    async def start(self) -> None:
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
            self.coordinator.api.query, f"vm/id/{self._data['id']}/start", "post"
        )

    async def stop(self) -> None:
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


class TrueNASServiceBinarySensor(TrueNASBinarySensor):
    """Define a TrueNAS Service Binary Sensor."""

    async def start(self) -> None:
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
        await self.coordinator.async_request_refresh()

    async def stop(self) -> None:
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
        await self.coordinator.async_request_refresh()

    async def restart(self) -> None:
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
        await self.coordinator.async_request_refresh()

    async def reload(self) -> None:
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
        await self.coordinator.async_request_refresh()


class TrueNASAppBinarySensor(TrueNASBinarySensor):
    """Define a TrueNAS Applications Binary Sensor."""

    async def start(self) -> None:
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
        await self.coordinator.async_request_refresh()

    async def stop(self) -> None:
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
        await self.coordinator.async_request_refresh()
