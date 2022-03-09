"""Definitions for TrueNAS sensor entities."""
from dataclasses import dataclass, field
from typing import List
from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS

DEVICE_ATTRIBUTES_DATASET = [
    "type",
    "pool",
    "mountpoint",
    "deduplication",
    "atime",
    "casesensitivity",
    "checksum",
    "exec",
    "sync",
    "compression",
    "compressratio",
    "quota",
    "copies",
    "readonly",
    "recordsize",
    "encryption_algorithm",
    "used",
    "available",
]

DEVICE_ATTRIBUTES_DISK = [
    "serial",
    "size",
    "hddstandby",
    "hddstandby_force",
    "advpowermgmt",
    "acousticlevel",
    "togglesmart",
    "model",
    "rotationrate",
    "type",
]


@dataclass
class TrueNASSensorEntityDescription(SensorEntityDescription):
    """Class describing mikrotik entities."""

    ha_group: str = ""
    ha_connection: str = ""
    ha_connection_value: str = ""
    data_path: str = ""
    data_attribute: str = ""
    data_name: str = ""
    data_uid: str = ""
    data_reference: str = ""
    data_attributes_list: List = field(default_factory=lambda: [])


SENSOR_TYPES = {
    "system_uptime": TrueNASSensorEntityDescription(
        key="system_uptime",
        name="Uptime",
        icon="mdi:clock-outline",
        native_unit_of_measurement=None,
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        ha_group="System",
        data_path="system_info",
        data_attribute="uptimeEpoch",
        data_name="",
        data_uid="",
        data_reference="",
    ),
    "dataset": TrueNASSensorEntityDescription(
        key="dataset",
        name="",
        icon="mdi:database",
        native_unit_of_measurement=PERCENTAGE,
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=None,
        ha_group="Datasets",
        data_path="dataset",
        data_attribute="usage",
        data_name="name",
        data_uid="",
        data_reference="id",
        data_attributes_list=DEVICE_ATTRIBUTES_DATASET,
    ),
    "disk": TrueNASSensorEntityDescription(
        key="disk",
        name="",
        icon="mdi:harddisk",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=None,
        ha_group="Disks",
        data_path="disk",
        data_attribute="temperature",
        data_name="name",
        data_uid="",
        data_reference="devname",
        data_attributes_list=DEVICE_ATTRIBUTES_DISK,
    ),
}
