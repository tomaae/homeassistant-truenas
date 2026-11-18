"""Unknown first measurements must not prevent later sensor updates."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.truenas.entity import async_add_entities
from custom_components.truenas.sensor import TrueNASSensor


@pytest.mark.parametrize(
    "attribute", ["cpu_usage", "memory-free_value", "memory-usage_percent"]
)
def test_unknown_first_reading_registers_and_recovers(attribute):
    data = {attribute: None}
    description = SimpleNamespace(
        data_path="system_info",
        data_reference=None,
        data_attribute=attribute,
        func="sensor",
        key=attribute,
    )
    coordinator = SimpleNamespace(data={"system_info": data})

    def sensor_factory(controller, entity_description):
        sensor = object.__new__(TrueNASSensor)
        sensor.coordinator = controller
        sensor.entity_description = entity_description
        sensor._inst = "NAS"
        sensor._data = controller.data[entity_description.data_path]
        return sensor

    platform = SimpleNamespace(
        platform=SimpleNamespace(SENSOR_SERVICES=[], SENSOR_TYPES=[description]),
        domain="sensor",
        entities={},
        async_add_entities=AsyncMock(),
    )
    registry = Mock()
    registry.async_get_entity_id.return_value = None
    registry.async_get.return_value = None
    hass = SimpleNamespace(data={"truenas": {"entry": coordinator}})
    entry = SimpleNamespace(entry_id="entry", async_on_unload=Mock())
    with (
        patch(
            "custom_components.truenas.entity.ep.async_get_current_platform",
            return_value=platform,
        ),
        patch("custom_components.truenas.entity.er.async_get", return_value=registry),
        patch("custom_components.truenas.entity.async_dispatcher_connect"),
    ):
        asyncio.run(async_add_entities(hass, entry, {"sensor": sensor_factory}))
    platform.async_add_entities.assert_awaited_once()
    sensor = platform.async_add_entities.call_args.args[0][0]
    assert sensor.native_value is None
    data[attribute] = 25
    assert sensor.native_value == 25


def test_absent_measurement_is_not_registered():
    description = SimpleNamespace(
        data_path="system_info",
        data_reference=None,
        data_attribute="unsupported",
        func="sensor",
    )
    platform = SimpleNamespace(
        platform=SimpleNamespace(SENSOR_SERVICES=[], SENSOR_TYPES=[description]),
        async_add_entities=AsyncMock(),
    )
    factory = Mock()
    hass = SimpleNamespace(
        data={"truenas": {"entry": SimpleNamespace(data={"system_info": {}})}}
    )
    entry = SimpleNamespace(entry_id="entry", async_on_unload=Mock())
    with (
        patch(
            "custom_components.truenas.entity.ep.async_get_current_platform",
            return_value=platform,
        ),
        patch("custom_components.truenas.entity.async_dispatcher_connect"),
    ):
        asyncio.run(async_add_entities(hass, entry, {"sensor": factory}))
    factory.assert_not_called()
    platform.async_add_entities.assert_not_awaited()
