"""TrueNAS sensor platform"""
from logging import getLogger
from typing import Optional
from datetime import datetime
from homeassistant.components.sensor import SensorEntity
from .model import model_async_setup_entry, TrueNASEntity
from .sensor_types import SENSOR_TYPES, SENSOR_SERVICES

_LOGGER = getLogger(__name__)


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry for TrueNAS component"""
    dispatcher = {
        "TrueNASSensor": TrueNASSensor,
        "TrueNASUptimeSensor": TrueNASUptimeSensor,
        "TrueNASClousyncSensor": TrueNASClousyncSensor,
        "TrueNASDatasetSensor": TrueNASDatasetSensor,
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
#   TrueNASSensor
# ---------------------------
class TrueNASSensor(TrueNASEntity, SensorEntity):
    """Define an TrueNAS sensor"""

    @property
    def state(self) -> Optional[str]:
        """Return the state"""
        if self.entity_description.data_attribute:
            return self._data[self.entity_description.data_attribute]
        else:
            return "unknown"

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in"""
        if self.entity_description.native_unit_of_measurement:
            if self.entity_description.native_unit_of_measurement.startswith("data__"):
                uom = self.entity_description.native_unit_of_measurement[6:]
                if uom in self._data:
                    uom = self._data[uom]
                    return uom

            return self.entity_description.native_unit_of_measurement

        return None


# ---------------------------
#   TrueNASUptimeSensor
# ---------------------------
class TrueNASUptimeSensor(TrueNASSensor):
    """Define an TrueNAS Uptime sensor"""

    async def restart(self):
        """Restart TrueNAS systen"""
        await self.hass.async_add_executor_job(
            self._ctrl.api.query,
            "system/reboot",
            "post",
        )

    async def stop(self):
        """Shutdown TrueNAS systen"""
        await self.hass.async_add_executor_job(
            self._ctrl.api.query,
            "system/shutdown",
            "post",
        )


# ---------------------------
#   TrueNASDatasetSensor
# ---------------------------
class TrueNASDatasetSensor(TrueNASSensor):
    """Define an TrueNAS Dataset sensor"""

    async def snapshot(self):
        """Create dataset snapshot"""
        ts = datetime.now().isoformat(sep="_", timespec="microseconds")
        await self.hass.async_add_executor_job(
            self._ctrl.api.query,
            "zfs/snapshot",
            "post",
            {"dataset": f"{self._data['name']}", "name": f"custom-{ts}"},
        )


# ---------------------------
#   TrueNASClousyncSensor
# ---------------------------
class TrueNASClousyncSensor(TrueNASSensor):
    """Define an TrueNAS Cloudsync sensor"""

    async def start(self):
        """Run cloudsync job"""
        tmp_job = await self.hass.async_add_executor_job(
            self._ctrl.api.query, f"cloudsync/id/{self._data['id']}"
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
            self._ctrl.api.query, f"cloudsync/id/{self._data['id']}/sync", "post"
        )
