"""TrueNAS HA shared entity model"""
from logging import getLogger
from typing import Any
from collections.abc import Mapping
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.core import callback
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME, CONF_HOST
from .helper import format_attribute
from .const import DOMAIN, ATTRIBUTION

_LOGGER = getLogger(__name__)


# ---------------------------
#   model_async_setup_entry
# ---------------------------
async def model_async_setup_entry(
    hass, config_entry, async_add_entities, sensor_services, sensor_types, dispatcher
):
    inst = config_entry.data[CONF_NAME]
    truenas_controller = hass.data[DOMAIN][config_entry.entry_id]
    sensors = {}

    platform = entity_platform.async_get_current_platform()
    for tmp in sensor_services:
        platform.async_register_entity_service(tmp[0], tmp[1], tmp[2])

    @callback
    def update_controller():
        """Update the values of the controller"""
        model_update_items(
            inst,
            truenas_controller,
            async_add_entities,
            sensors,
            dispatcher,
            sensor_types,
        )

    truenas_controller.listeners.append(
        async_dispatcher_connect(
            hass, truenas_controller.signal_update, update_controller
        )
    )
    update_controller()


# ---------------------------
#   model_update_items
# ---------------------------
def model_update_items(
    inst, truenas_controller, async_add_entities, sensors, dispatcher, sensor_types
):
    def _register_entity(_sensors, _item_id, _uid, _uid_sensor):
        _LOGGER.debug("Updating entity %s", _item_id)
        if _item_id in _sensors:
            if _sensors[_item_id].enabled:
                _sensors[_item_id].async_schedule_update_ha_state()
            return None

        return dispatcher[_uid_sensor.func](
            inst=inst,
            uid=_uid,
            truenas_controller=truenas_controller,
            entity_description=_uid_sensor,
        )

    new_sensors = []
    for sensor in sensor_types:
        uid_sensor = sensor_types[sensor]
        if not uid_sensor.data_reference:
            uid_sensor = sensor_types[sensor]
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
            if tmp := _register_entity(sensors, item_id, "", uid_sensor):
                sensors[item_id] = tmp
                new_sensors.append(sensors[item_id])
        else:
            for uid in truenas_controller.data[uid_sensor.data_path]:
                uid_data = truenas_controller.data[uid_sensor.data_path]
                item_id = f"{inst}-{sensor}-{str(uid_data[uid][uid_sensor.data_reference]).lower()}"
                if tmp := _register_entity(sensors, item_id, uid, uid_sensor):
                    sensors[item_id] = tmp
                    new_sensors.append(sensors[item_id])

    if new_sensors:
        async_add_entities(new_sensors, True)


# ---------------------------
#   TrueNASEntity
# ---------------------------
class TrueNASEntity:
    """Define entity"""

    _attr_has_entity_name = True

    def __init__(
        self,
        inst,
        uid: "",
        truenas_controller,
        entity_description,
    ):
        """Initialize entity"""
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
        """Return the name for this entity"""
        if not self._uid:
            return f"{self.entity_description.name}"

        if self.entity_description.name:
            return f"{self._data[self.entity_description.data_name]} {self.entity_description.name}"

        return f"{self._data[self.entity_description.data_name]}"

    @property
    def unique_id(self) -> str:
        """Return a unique id for this entity"""
        if self._uid:
            return f"{self._inst.lower()}-{self.entity_description.key}-{str(self._data[self.entity_description.data_reference]).lower()}"
        else:
            return f"{self._inst.lower()}-{self.entity_description.key}"

    @property
    def available(self) -> bool:
        """Return if controller is available"""
        return self._ctrl.connected()

    @property
    def device_info(self) -> DeviceInfo:
        """Return a description for device registry"""
        dev_connection = DOMAIN
        dev_connection_value = f"{self._ctrl.name}_{self.entity_description.ha_group}"
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

        return DeviceInfo(
            connections={(dev_connection, f"{dev_connection_value}")},
            identifiers={(dev_connection, f"{dev_connection_value}")},
            default_name=f"{self._inst} {dev_group}",
            default_manufacturer=f"{self._ctrl.data['system_info']['system_manufacturer']}",
            default_model=f"{self._ctrl.data['system_info']['system_product']}",
            sw_version=f"{self._ctrl.data['system_info']['version']}",
            configuration_url=f"http://{self._ctrl.config_entry.data[CONF_HOST]}",
            via_device=(DOMAIN, f"{self._ctrl.data['system_info']['hostname']}"),
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes"""
        attributes = super().extra_state_attributes
        for variable in self.entity_description.data_attributes_list:
            if variable in self._data:
                attributes[format_attribute(variable)] = self._data[variable]

        return attributes

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass"""
        _LOGGER.debug("New binary sensor %s (%s)", self._inst, self.unique_id)

    async def start(self):
        """Dummy run function"""
        _LOGGER.error("Start functionality does not exist for %s", self.entity_id)

    async def stop(self):
        """Dummy stop function"""
        _LOGGER.error("Stop functionality does not exist for %s", self.entity_id)

    async def restart(self):
        """Dummy restart function"""
        _LOGGER.error("Restart functionality does not exist for %s", self.entity_id)

    async def reload(self):
        """Dummy reload function"""
        _LOGGER.error("Reload functionality does not exist for %s", self.entity_id)

    async def snapshot(self):
        """Dummy snapshot function"""
        _LOGGER.error("Snapshot functionality does not exist for %s", self.entity_id)
