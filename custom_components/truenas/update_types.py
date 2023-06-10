"""Definitions for TrueNAS update entities."""
from dataclasses import dataclass, field
from typing import List

from homeassistant.components.update import UpdateEntityDescription


@dataclass
class TrueNASUpdateEntityDescription(UpdateEntityDescription):
    """Class describing mikrotik entities."""

    ha_group: str = ""
    ha_connection: str = ""
    ha_connection_value: str = ""
    title: str = ""
    data_path: str = ""
    data_attribute: str = "available"
    data_name: str = ""
    data_uid: str = ""
    data_reference: str = ""
    data_attributes_list: List = field(default_factory=lambda: [])
    func: str = ""


SENSOR_TYPES = {
    "system_update": TrueNASUpdateEntityDescription(
        key="system_update",
        name="Update",
        ha_group="System",
        title="TrueNAS",
        data_path="system_info",
        data_attribute="update_available",
        data_name="",
        data_uid="",
        data_reference="",
        func="TrueNASUpdate",
    ),
    "app_update": TrueNASUpdateEntityDescription(
        key="app_update",
        name="Update",
        ha_group="Apps",
        title="TrueNAS",
        data_path="app",
        data_attribute="update_available",
        data_name="name",
        data_uid="",
        data_reference="id",
        func="TrueNASAppUpdate",
    ),
}

SENSOR_SERVICES = []
