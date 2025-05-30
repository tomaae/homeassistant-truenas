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
    def icon(self) -> str | None:
        """Return the icon."""
        if self.entity_description.icon_enabled:
            if self._data[self.entity_description.data_is_on]:
                return self.entity_description.icon_enabled
            else:
                return self.entity_description.icon_disabled

        return None


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
        """Start a VM."""  # virt.instance.start
        if self.coordinator._version_major >= 25:
            tmp_vm = await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "virt.instance.get_instance",
                "get",
                [self._data["id"]],
            )
        else:
            tmp_vm = await self.hass.async_add_executor_job(
                self.coordinator.api.query, f"vm/id/{self._data['id']}"
            )

        if "status" not in tmp_vm:
            _LOGGER.error("VM %s (%s) invalid", self._data["name"], self._data["id"])
            return

        if (
            self.coordinator._version_major < 25
            and tmp_vm["status"]["state"] != "STOPPED"
        ) or (self.coordinator._version_major >= 25 and tmp_vm["status"] != "STOPPED"):
            _LOGGER.warning(
                "VM %s (%s) is not down", self._data["name"], self._data["id"]
            )
            return

        if self.coordinator._version_major >= 25:
            await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "virt.instance.start",
                "post",
                [self._data["id"]],
            )
        else:
            await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                f"vm/id/{self._data['id']}/start",
                "post",
                {"overcommit": overcommit},
            )

    async def stop(self):
        """Stop a VM."""
        if self.coordinator._version_major >= 25:
            tmp_vm = await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "virt.instance.get_instance",
                "get",
                [self._data["id"]],
            )
        else:
            tmp_vm = await self.hass.async_add_executor_job(
                self.coordinator.api.query, f"vm/id/{self._data['id']}"
            )

        if "status" not in tmp_vm:
            _LOGGER.error("VM %s (%s) invalid", self._data["name"], self._data["id"])
            return

        if (
            self.coordinator._version_major < 25
            and tmp_vm["status"]["state"] != "RUNNING"
        ) or (self.coordinator._version_major >= 25 and tmp_vm["status"] != "RUNNING"):
            _LOGGER.warning(
                "VM %s (%s) is not up", self._data["name"], self._data["id"]
            )
            return

        if self.coordinator._version_major >= 25:
            await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "virt.instance.stop",
                "post",
                [self._data["id"], {"timeout": 0, "force": True}],
            )
        else:
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
        if self.coordinator._version_major >= 25:
            tmp_service = await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "service.get_instance",
                "get",
                [self._data["id"]],
            )
        else:
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

        if self.coordinator._version_major >= 25:
            await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "service.start",
                "post",
                [self._data["service"]],
            )
        else:
            await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "service/start",
                "post",
                {"service": self._data["service"]},
            )
        await self.coordinator.async_refresh()

    async def stop(self):
        """Stop a Service."""
        if self.coordinator._version_major >= 25:
            tmp_service = await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "service.get_instance",
                "get",
                [self._data["id"]],
            )
        else:
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

        if self.coordinator._version_major >= 25:
            await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "service.stop",
                "post",
                [self._data["service"]],
            )
        else:
            await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "service/stop",
                "post",
                {"service": self._data["service"]},
            )
        await self.coordinator.async_refresh()

    async def restart(self):
        """Restart a Service."""
        if self.coordinator._version_major >= 25:
            tmp_service = await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "service.get_instance",
                "get",
                [self._data["id"]],
            )
        else:
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

        if self.coordinator._version_major >= 25:
            await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "service.restart",
                "post",
                [self._data["service"]],
            )
        else:
            await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "service/restart",
                "post",
                {"service": self._data["service"]},
            )
        await self.coordinator.async_refresh()

    async def reload(self):
        """Reload a Service."""
        if self.coordinator._version_major >= 25:
            tmp_service = await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "service.get_instance",
                "get",
                [self._data["id"]],
            )
        else:
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

        if self.coordinator._version_major >= 25:
            await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "service.reload",
                "post",
                [self._data["service"]],
            )
        else:
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
        """Start an App."""
        if self.coordinator._version_major >= 25:
            tmp_app = await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "app.get_instance",
                "get",
                [self._data["id"]],
            )
        else:
            tmp_app = await self.hass.async_add_executor_job(
                self.coordinator.api.query, f"/app/id/{self._data['id']}"
            )

        if tmp_app is None or "state" not in tmp_app:
            _LOGGER.error("App %s (%s) invalid", self._data["name"], self._data["id"])
            return

        if tmp_app["state"] == "RUNNING":
            _LOGGER.warning(
                "App %s (%s) is not down", self._data["name"], self._data["id"]
            )
            return

        if self.coordinator._version_major >= 25:
            await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "app.start",
                "post",
                [self._data["id"]],
            )
        else:
            await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "/app/start",
                "post",
                self._data["id"],
            )

    async def stop(self):
        """Stop an App."""
        if self.coordinator._version_major >= 25:
            tmp_app = await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "app.get_instance",
                "get",
                [self._data["id"]],
            )
        else:
            tmp_app = await self.hass.async_add_executor_job(
                self.coordinator.api.query, f"/app/id/{self._data['id']}"
            )

        if tmp_app is None or "state" not in tmp_app:
            _LOGGER.error("App %s (%s) invalid", self._data["name"], self._data["id"])
            return

        if tmp_app["state"] != "RUNNING":
            _LOGGER.warning(
                "App %s (%s) is not up", self._data["name"], self._data["id"]
            )
            return

        if self.coordinator._version_major >= 25:
            await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "app.stop",
                "post",
                [self._data["id"]],
            )
        else:
            await self.hass.async_add_executor_job(
                self.coordinator.api.query,
                "/app/stop",
                "post",
                self._data["id"],
            )
