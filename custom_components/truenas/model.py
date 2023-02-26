"""TrueNAS HA entity model."""
from __future__ import annotations

from collections.abc import Mapping
from logging import getLogger
from typing import Any

from homeassistant.const import ATTR_ATTRIBUTION, CONF_HOST, CONF_NAME
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import TrueNASDataUpdateCoordinator
from .helper import format_attribute

_LOGGER = getLogger(__name__)


class TrueNASEntity(CoordinatorEntity[TrueNASDataUpdateCoordinator], Entity):
    """Define entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TrueNASDataUpdateCoordinator,
        description,
        uid: str | None = None,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.description = description
        self._inst = coordinator.config_entry.data[CONF_NAME]
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._uid = uid
        self._data = coordinator.data[self.description.data_path]
        if self._uid:
            self._data = self._data[self._uid]

    @property
    def name(self) -> str:
        """Return the name for this entity."""
        if not self._uid:
            return f"{self.description.name}"

        if self.description.name:
            return f"{self._data[self.description.data_name]} {self.description.name}"

        return f"{self._data[self.description.data_name]}"

    @property
    def unique_id(self) -> str:
        """Return a unique id for this entity."""
        if self._uid:
            return f"{self._inst.lower()}-{self.description.key}-{str(self._data[self.description.data_reference]).lower()}"
        else:
            return f"{self._inst.lower()}-{self.description.key}"

    @property
    def available(self) -> bool:
        """Return if coordinator is available."""
        return self.coordinator.connected()

    @property
    def device_info(self) -> DeviceInfo:
        """Return a description for device registry."""
        dev_connection = DOMAIN
        dev_connection_value = f"{self.coordinator.name}_{self.description.ha_group}"
        dev_group = self.description.ha_group
        if self.description.ha_group == "System":
            dev_connection_value = self.coordinator.data["system_info"]["hostname"]

        if self.description.ha_group.startswith("data__"):
            dev_group = self.description.ha_group[6:]
            if dev_group in self._data:
                dev_group = self._data[dev_group]
                dev_connection_value = dev_group

        if self.description.ha_connection:
            dev_connection = self.description.ha_connection

        if self.description.ha_connection_value:
            dev_connection_value = self.description.ha_connection_value
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
        for variable in self.description.data_attributes_list:
            if variable in self._data:
                attributes[format_attribute(variable)] = self._data[variable]

        return attributes

    async def async_added_to_hass(self) -> None:
        """Run when entity is about to be added to hass."""
        await super().async_added_to_hass()
        _LOGGER.debug("ADD %s", self.unique_id)

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity is being removed from hass."""
        _LOGGER.debug("REMOVE %s", self.unique_id)
