"""TrueNAS HA shared entity model."""
from collections.abc import Mapping
from logging import getLogger
from typing import Any

from homeassistant.const import ATTR_ATTRIBUTION, CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import TrueNASDataUpdateCoordinator
from .helper import format_attribute

_LOGGER = getLogger(__name__)


# ---------------------------
#   model_async_setup_entry
# ---------------------------
async def model_async_setup_entry(
    hass: HomeAssistant,
    coordinator: TrueNASDataUpdateCoordinator,
    async_add_entities: AddEntitiesCallback,
    sensor_services: dict[Any, Any],
    sensor_types: dict[Any, Any],
    dispatcher: dict[str, Any],
) -> None:
    """Set up integration from a config entry."""
    platform = entity_platform.async_get_current_platform()
    for service in sensor_services:
        platform.async_register_entity_service(service[0], service[1], service[2])

    sensors = []
    for sensor in sensor_types:
        uid_sensor = sensor_types[sensor]
        if not uid_sensor.data_reference:
            uid_sensor = sensor_types[sensor]
            if (
                uid_sensor.data_attribute not in coordinator.data[uid_sensor.data_path]
                or coordinator.data[uid_sensor.data_path][uid_sensor.data_attribute]
                == "unknown"
            ):
                continue
            sensors.append(
                dispatcher[uid_sensor.func](
                    coordinator=coordinator, entity_description=uid_sensor
                )
            )
        else:
            for uid in coordinator.data[uid_sensor.data_path]:
                sensors.append(
                    dispatcher[uid_sensor.func](
                        coordinator=coordinator, entity_description=uid_sensor, uid=uid
                    )
                )

    async_add_entities(sensors, True)


# ---------------------------
#   TrueNASEntity
# ---------------------------
class TrueNASEntity(CoordinatorEntity[TrueNASDataUpdateCoordinator], Entity):
    """Define entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TrueNASDataUpdateCoordinator,
        entity_description,
        uid: str | None = None,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entity_description = entity_description
        self._inst = coordinator.config_entry.data[CONF_NAME]
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._uid = uid
        self._data = coordinator.data[self.entity_description.data_path]
        if self._uid:
            self._data = self._data[self._uid]

    @property
    def name(self) -> str:
        """Return the name for this entity."""
        if not self._uid:
            return f"{self.entity_description.name}"

        if self.entity_description.name:
            return f"{self._data[self.entity_description.data_name]} {self.entity_description.name}"

        return f"{self._data[self.entity_description.data_name]}"

    @property
    def unique_id(self) -> str:
        """Return a unique id for this entity."""
        if self._uid:
            return f"{self._inst.lower()}-{self.entity_description.key}-{str(self._data[self.entity_description.data_reference]).lower()}"
        else:
            return f"{self._inst.lower()}-{self.entity_description.key}"

    @property
    def available(self) -> bool:
        """Return if coordinator is available."""
        return self.coordinator.connected()

    @property
    def device_info(self) -> DeviceInfo:
        """Return a description for device registry."""
        dev_connection = DOMAIN
        dev_connection_value = (
            f"{self.coordinator.name}_{self.entity_description.ha_group}"
        )
        dev_group = self.entity_description.ha_group
        if self.entity_description.ha_group == "System":
            dev_connection_value = self.coordinator.data["system_info"]["hostname"]

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
            default_manufacturer=f"{self.coordinator.data['system_info']['system_manufacturer']}",
            default_model=f"{self.coordinator.data['system_info']['system_product']}",
            sw_version=f"{self.coordinator.data['system_info']['version']}",
            configuration_url=f"http://{self.coordinator.config_entry.data[CONF_HOST]}",
            via_device=(DOMAIN, f"{self.coordinator.data['system_info']['hostname']}"),
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes."""
        attributes = super().extra_state_attributes
        for variable in self.entity_description.data_attributes_list:
            if variable in self._data:
                attributes[format_attribute(variable)] = self._data[variable]

        return attributes

    async def start(self):
        """Run function."""
        raise NotImplementedError()

    async def stop(self):
        """Stop function."""
        raise NotImplementedError()

    async def restart(self):
        """Restart function."""
        raise NotImplementedError()

    async def reload(self):
        """Reload function."""
        raise NotImplementedError()

    async def snapshot(self):
        """Snapshot function."""
        raise NotImplementedError()
