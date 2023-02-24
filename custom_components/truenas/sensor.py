"""TrueNAS sensor platform."""
from __future__ import annotations

from datetime import datetime
from logging import getLogger

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .model import TrueNASEntity
from .sensor_types import SENSOR_SERVICES, SENSOR_TYPES

_LOGGER = getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up entry for TrueNAS component."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    platform = entity_platform.async_get_current_platform()
    for service in SENSOR_SERVICES:
        platform.async_register_entity_service(service[0], service[1], service[2])

    entities = []
    for description in SENSOR_TYPES:
        if not description.data_reference:
            if (
                coordinator.data[description.data_path].get(description.data_attribute)
                is None
            ):
                continue
            obj = eval(description.func)(coordinator, description)
            entities.append(obj)
        else:
            for uid in coordinator.data[description.data_path]:
                obj = eval(description.func)(coordinator, description, uid)
                entities.append(obj)

    async_add_entities(entities, True)


class TrueNASSensor(TrueNASEntity, SensorEntity):
    """Define an TrueNAS sensor."""

    @property
    def state(self) -> str:
        """Return the state."""
        return self._data.get(self.description.data_attribute, "unknown")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        if self.description.native_unit_of_measurement:
            if self.description.native_unit_of_measurement.startswith("data__"):
                uom = self.description.native_unit_of_measurement[6:]
                if uom in self._data:
                    uom = self._data[uom]
                    return uom

            return self.description.native_unit_of_measurement


class TrueNASUptimeSensor(TrueNASSensor):
    """Define an TrueNAS Uptime sensor."""

    async def restart(self) -> None:
        """Restart TrueNAS systen."""
        await self.hass.async_add_executor_job(
            self.coordinator.api.query,
            "system/reboot",
            "post",
        )

    async def stop(self) -> None:
        """Shutdown TrueNAS systen."""
        await self.hass.async_add_executor_job(
            self.coordinator.api.query,
            "system/shutdown",
            "post",
        )


class TrueNASDatasetSensor(TrueNASSensor):
    """Define an TrueNAS Dataset sensor."""

    async def snapshot(self) -> None:
        """Create dataset snapshot."""
        ts = datetime.now().isoformat(sep="_", timespec="microseconds")
        await self.hass.async_add_executor_job(
            self.coordinator.api.query,
            "zfs/snapshot",
            "post",
            {"dataset": f"{self._data['name']}", "name": f"custom-{ts}"},
        )


class TrueNASClousyncSensor(TrueNASSensor):
    """Define an TrueNAS Cloudsync sensor."""

    async def start(self) -> None:
        """Run cloudsync job."""
        tmp_job = await self.hass.async_add_executor_job(
            self.coordinator.api.query, f"cloudsync/id/{self._data['id']}"
        )

        if "job" not in tmp_job:
            _LOGGER.error(
                "Clousync job %s (%s) invalid",
                self._data["description"],
                self._data["id"],
            )
            return
        if tmp_job["job"]["state"] in ["WAITING", "RUNNING"]:
            _LOGGER.warning(
                "Clousync job %s (%s) is already running",
                self._data["description"],
                self._data["id"],
            )
            return

        await self.hass.async_add_executor_job(
            self.coordinator.api.query, f"cloudsync/id/{self._data['id']}/sync", "post"
        )
