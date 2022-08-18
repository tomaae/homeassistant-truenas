"""Definitions for TrueNAS binary sensor entities"""
from dataclasses import dataclass, field
from typing import List
from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from .const import (
    SERVICE_JAIL_START,
    SCHEMA_SERVICE_JAIL_START,
    SERVICE_JAIL_STOP,
    SCHEMA_SERVICE_JAIL_STOP,
    SERVICE_JAIL_RESTART,
    SCHEMA_SERVICE_JAIL_RESTART,
    SERVICE_SERVICE_START,
    SCHEMA_SERVICE_SERVICE_START,
    SERVICE_SERVICE_STOP,
    SCHEMA_SERVICE_SERVICE_STOP,
    SERVICE_SERVICE_RESTART,
    SCHEMA_SERVICE_SERVICE_RESTART,
    SERVICE_SERVICE_RELOAD,
    SCHEMA_SERVICE_SERVICE_RELOAD,
    SERVICE_VM_START,
    SCHEMA_SERVICE_VM_START,
    SERVICE_VM_STOP,
    SCHEMA_SERVICE_VM_STOP,
)

DEVICE_ATTRIBUTES_POOL = [
    "path",
    "status",
    "healthy",
    "is_decrypted",
    "autotrim",
    "scrub_state",
    "scrub_start",
    "scrub_end",
    "scrub_secs_left",
    "available_gib",
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

DEVICE_ATTRIBUTES_VM = [
    "description",
    "vcpus",
    "memory",
    "autostart",
    "cores",
    "threads",
]

DEVICE_ATTRIBUTES_SERVICE = [
    "enable",
    "state",
]


@dataclass
class TrueNASBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing mikrotik entities"""

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
    func: str = "TrueNASBinarySensor"


SENSOR_TYPES = {
    "pool_healthy": TrueNASBinarySensorEntityDescription(
        key="pool_healthy",
        name="healthy",
        icon_enabled="mdi:database",
        icon_disabled="mdi:database-off",
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
        icon_enabled="mdi:layers",
        icon_disabled="mdi:layers-off",
        device_class=None,
        entity_category=None,
        ha_group="Jails",
        data_path="jail",
        data_is_on="state",
        data_name="host_hostname",
        data_uid="",
        data_reference="id",
        data_attributes_list=DEVICE_ATTRIBUTES_JAIL,
        func="TrueNASJailBinarySensor",
    ),
    "vm": TrueNASBinarySensorEntityDescription(
        key="vm",
        name="",
        icon_enabled="mdi:server",
        icon_disabled="mdi:server-off",
        device_class=None,
        entity_category=None,
        ha_group="VMs",
        data_path="vm",
        data_is_on="running",
        data_name="name",
        data_uid="",
        data_reference="id",
        data_attributes_list=DEVICE_ATTRIBUTES_VM,
        func="TrueNASVMBinarySensor",
    ),
    "service": TrueNASBinarySensorEntityDescription(
        key="service",
        name="",
        icon_enabled="mdi:cog",
        icon_disabled="mdi:cog-off",
        device_class=None,
        entity_category=None,
        ha_group="Services",
        data_path="service",
        data_is_on="running",
        data_name="service",
        data_uid="",
        data_reference="id",
        data_attributes_list=DEVICE_ATTRIBUTES_SERVICE,
        func="TrueNASServiceBinarySensor",
    ),
}

SENSOR_SERVICES = [
    [SERVICE_JAIL_START, SCHEMA_SERVICE_JAIL_START, "start"],
    [SERVICE_JAIL_STOP, SCHEMA_SERVICE_JAIL_STOP, "stop"],
    [SERVICE_JAIL_RESTART, SCHEMA_SERVICE_JAIL_RESTART, "restart"],
    [SERVICE_VM_START, SCHEMA_SERVICE_VM_START, "start"],
    [SERVICE_VM_STOP, SCHEMA_SERVICE_VM_STOP, "stop"],
    [SERVICE_SERVICE_START, SCHEMA_SERVICE_SERVICE_START, "start"],
    [SERVICE_SERVICE_STOP, SCHEMA_SERVICE_SERVICE_STOP, "stop"],
    [SERVICE_SERVICE_RESTART, SCHEMA_SERVICE_SERVICE_RESTART, "restart"],
    [SERVICE_SERVICE_RELOAD, SCHEMA_SERVICE_SERVICE_RELOAD, "reload"],
]
