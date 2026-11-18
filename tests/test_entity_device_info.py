"""Device metadata and grouping without starting Home Assistant or a NAS."""

from inspect import signature
from types import SimpleNamespace
import unittest

from homeassistant.helpers.device_registry import DeviceRegistry

from custom_components.truenas.entity import TrueNASEntity


class DeviceInfoTests(unittest.TestCase):
    """Keep device identity and parent links while using supported metadata."""

    def device_info(self, group, data=None):
        entity = object.__new__(TrueNASEntity)
        entity._inst = "NAS"
        entity._data = data or {}
        entity.entity_description = SimpleNamespace(
            ha_group=group, ha_connection=None, ha_connection_value=None
        )
        entity.coordinator = SimpleNamespace(
            data={
                "system_info": {
                    "hostname": "storage",
                    "system_product": "Test NAS",
                    "system_manufacturer": "Test vendor",
                    "version": "25.10.7",
                }
            },
            config_entry=SimpleNamespace(data={"host": "nas.example"}),
        )
        return entity.device_info

    def test_child_metadata_uses_supported_registration_fields(self):
        info = self.device_info("Disks")
        self.assertEqual(info["name"], "Disks")
        self.assertEqual(info["model"], "Test NAS")
        self.assertEqual(info["manufacturer"], "Test vendor")
        self.assertEqual(info["connections"], {("truenas", "NAS_Disks")})
        self.assertEqual(info["via_device"], ("truenas", "NAS_storage"))
        self.assertFalse(any(key.startswith("default_") for key in info))
        # Validate the returned fields against Home Assistant's registration API.
        signature(DeviceRegistry.async_get_or_create).bind(
            None, config_entry_id="test-entry", **info
        )

    def test_dynamic_child_keeps_its_connection_and_parent(self):
        info = self.device_info("data__pool", {"pool": "tank"})
        self.assertEqual(info["name"], "tank")
        self.assertEqual(info["connections"], {("truenas", "tank")})
        self.assertEqual(info["via_device"], ("truenas", "NAS_storage"))

    def test_system_device_keeps_identity_and_version(self):
        info = self.device_info("System")
        self.assertEqual(info["identifiers"], {("truenas", "NAS_storage")})
        self.assertEqual(info["connections"], {("truenas", "NAS_storage")})
        self.assertEqual(info["sw_version"], "25.10.7")
        self.assertEqual(info["configuration_url"], "http://nas.example")
        self.assertNotIn("via_device", info)
