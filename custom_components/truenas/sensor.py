"""TrueNAS sensor platform."""
import logging
from typing import Any, Optional
from collections.abc import Mapping

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_NAME,
    CONF_HOST,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers import entity_platform
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback


from .const import (
    DOMAIN,
    ATTRIBUTION,
    SERVICE_CLOUDSYNC_RUN,
    SCHEMA_SERVICE_CLOUDSYNC_RUN,
)

from .sensor_types import (
    TrueNASSensorEntityDescription,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker for TrueNAS component."""
    inst = config_entry.data[CONF_NAME]
    truenas_controller = hass.data[DOMAIN][config_entry.entry_id]
    sensors = {}

    platform = entity_platform.async_get_current_platform()
    assert platform is not None
    platform.async_register_entity_service(
        SERVICE_CLOUDSYNC_RUN,
        SCHEMA_SERVICE_CLOUDSYNC_RUN,
        "start",
    )

    @callback
    def update_controller():
        """Update the values of the controller."""
        update_items(inst, truenas_controller, async_add_entities, sensors)

    truenas_controller.listeners.append(
        async_dispatcher_connect(
            hass, truenas_controller.signal_update, update_controller
        )
    )

    update_controller()


# ---------------------------
#   update_items
# ---------------------------
@callback
def update_items(inst, truenas_controller, async_add_entities, sensors):
    """Update sensor state from the controller."""
    new_sensors = []

    for sensor, sid_func in zip(
        # Sensor type name
        ["dataset", "disk", "pool_free", "cloudsync"],
        # Entity function
        [
            TrueNASSensor,
            TrueNASSensor,
            TrueNASSensor,
            TrueNASClousyncSensor,
        ],
    ):
        uid_sensor = SENSOR_TYPES[sensor]
        for uid in truenas_controller.data[uid_sensor.data_path]:
            uid_data = truenas_controller.data[uid_sensor.data_path]
            item_id = f"{inst}-{sensor}-{str(uid_data[uid][uid_sensor.data_reference]).lower()}"
            _LOGGER.debug("Updating sensor %s", item_id)
            if item_id in sensors:
                if sensors[item_id].enabled:
                    sensors[item_id].async_schedule_update_ha_state()
                continue

            sensors[item_id] = sid_func(
                inst=inst,
                uid=uid,
                truenas_controller=truenas_controller,
                entity_description=uid_sensor,
            )
            new_sensors.append(sensors[item_id])

    for sensor in SENSOR_TYPES:
        if sensor.startswith("system_"):
            uid_sensor = SENSOR_TYPES[sensor]
            if (
                uid_sensor.data_attribute
                not in truenas_controller.data[uid_sensor.data_path]
                or truenas_controller.data[uid_sensor.data_path][
                    uid_sensor.data_attribute
                ]
                == "unknown"
            ):
                continue
            item_id = f"{inst}-{sensor}"
            _LOGGER.debug("Updating sensor %s", item_id)
            if item_id in sensors:
                if sensors[item_id].enabled:
                    sensors[item_id].async_schedule_update_ha_state()
                continue

            sensors[item_id] = TrueNASSensor(
                inst=inst,
                uid="",
                truenas_controller=truenas_controller,
                entity_description=uid_sensor,
            )
            new_sensors.append(sensors[item_id])

    if new_sensors:
        async_add_entities(new_sensors, True)


# ---------------------------
#   TrueNASSensor
# ---------------------------
class TrueNASSensor(SensorEntity):
    """Define an TrueNAS sensor."""

    def __init__(
        self,
        inst,
        uid: "",
        truenas_controller,
        entity_description: TrueNASSensorEntityDescription,
    ):
        """Initialize."""
        self.entity_description = entity_description
        self._inst = inst
        self._ctrl = truenas_controller
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._uid = uid
        if self._uid:
            self._data = truenas_controller.data[self.entity_description.data_path][
                self._uid
            ]
        else:
            self._data = truenas_controller.data[self.entity_description.data_path]

    @property
    def name(self) -> str:
        """Return the name."""
        if self._uid:
            if self.entity_description.name:
                return f"{self._inst} {self._data[self.entity_description.data_name]} {self.entity_description.name}"

            return f"{self._inst} {self._data[self.entity_description.data_name]}"
        else:
            return f"{self._inst} {self.entity_description.name}"

    @property
    def unique_id(self) -> str:
        """Return a unique id for this entity."""
        if self._uid:
            return f"{self._inst.lower()}-{self.entity_description.key}-{str(self._data[self.entity_description.data_reference]).lower()}"
        else:
            return f"{self._inst.lower()}-{self.entity_description.key}"

    @property
    def state(self) -> Optional[str]:
        """Return the state."""
        if self.entity_description.data_attribute:
            return self._data[self.entity_description.data_attribute]
        else:
            return "unknown"

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if self.entity_description.native_unit_of_measurement:
            if self.entity_description.native_unit_of_measurement.startswith("data__"):
                uom = self.entity_description.native_unit_of_measurement[6:]
                if uom in self._data:
                    uom = self._data[uom]
                    return uom

            return self.entity_description.native_unit_of_measurement

        return None

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return self._ctrl.connected()

    @property
    def device_info(self) -> DeviceInfo:
        """Return a description for device registry."""
        dev_connection = DOMAIN
        dev_connection_value = self.entity_description.ha_group
        dev_group = self.entity_description.ha_group
        if self.entity_description.ha_group == "System":
            dev_connection_value = self._ctrl.data["system_info"]["hostname"]

        if self.entity_description.ha_group.startswith("data__"):
            dev_group = self.entity_description.ha_group[6:]
            if dev_group in self._data:
                dev_group = self._data[dev_group]
                dev_connection_value = dev_group

        if self.entity_description.ha_connection:
            dev_connection = self.entity_description.ha_connection

        if self.entity_description.ha_connection_value:
            dev_connection_value = self.entity_description.ha_connection_value
            if dev_connection_value.startswith("data__"):
                dev_connection_value = dev_connection_value[6:]
                dev_connection_value = self._data[dev_connection_value]

        info = DeviceInfo(
            connections={(dev_connection, f"{dev_connection_value}")},
            identifiers={(dev_connection, f"{dev_connection_value}")},
            default_name=f"{self._inst} {dev_group}",
            default_manufacturer=f"{self._ctrl.data['system_info']['system_manufacturer']}",
            default_model=f"{self._ctrl.data['system_info']['system_product']}",
            sw_version=f"{self._ctrl.data['system_info']['version']}",
            configuration_url=f"http://{self._ctrl.config_entry.data[CONF_HOST]}",
            via_device=(DOMAIN, f"{self._ctrl.data['system_info']['hostname']}"),
        )

        return info

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes."""
        attributes = super().extra_state_attributes
        for variable in self.entity_description.data_attributes_list:
            if variable in self._data:
                attributes[variable] = self._data[variable]

        return attributes

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        _LOGGER.debug("New sensor %s (%s)", self._inst, self.unique_id)

    async def start(self):
        """Dummy run function."""
        _LOGGER.error("Start functionality does not exist for %s", self.entity_id)

    async def stop(self):
        """Dummy stop function."""
        _LOGGER.error("Stop functionality does not exist for %s", self.entity_id)

    async def restart(self):
        """Dummy restart function."""
        _LOGGER.error("Restart functionality does not exist for %s", self.entity_id)


# ---------------------------
#   TrueNASClousyncSensor
# ---------------------------
class TrueNASClousyncSensor(TrueNASSensor):
    """Define an TrueNAS Cloudsync sensor."""

    async def start(self):
        """Run cloudsync job."""
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
