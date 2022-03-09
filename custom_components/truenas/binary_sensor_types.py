"""Definitions for TrueNAS binary sensor entities."""
from dataclasses import dataclass, field
from typing import List
from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)

from .const import DOMAIN

DEVICE_ATTRIBUTES_POOL = [
    "path",
    "status",
    "healthy",
    "is_decrypted",
]

DEVICE_ATTRIBUTES_JAIL = [
    "comment",
    "jail_zfs_dataset",
    "last_started",
    "ip4_addr",
    "ip6_addr",
    "release",
    "type",
    "plugin_name",
]


@dataclass
class TrueNASBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing mikrotik entities."""

    icon_enabled: str = ""
    icon_disabled: str = ""
    ha_group: str = ""
    ha_connection: str = ""
    ha_connection_value: str = ""
    data_path: str = ""
    data_is_on: str = "available"
    data_name: str = ""
    data_uid: str = ""
    data_reference: str = ""
    data_attributes_list: List = field(default_factory=lambda: [])


SENSOR_TYPES = {
    "pool": TrueNASBinarySensorEntityDescription(
        key="pool",
        name="Pool",
        icon_enabled="mdi:database-settings",
        icon_disabled="mdi:database-settings",
        device_class=None,
        entity_category=None,
        ha_group="System",
        data_path="pool",
        data_is_on="healthy",
        data_name="name",
        data_uid="",
        data_reference="guid",
        data_attributes_list=DEVICE_ATTRIBUTES_POOL,
    ),
    "jail": TrueNASBinarySensorEntityDescription(
        key="jail",
        name="",
        icon_enabled="mdi:pound",
        icon_disabled="mdi:pound",
        device_class=None,
        entity_category=None,
        ha_group="Jails",
        data_path="jail",
        data_is_on="running",
        data_name="host_hostname",
        data_uid="",
        data_reference="id",
        data_attributes_list=DEVICE_ATTRIBUTES_JAIL,
    ),
}
