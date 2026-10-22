"""Check native entity registration and write-only actuator preflight behavior."""

import asyncio
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture
def entities(monkeypatch):
    class Entity:
        async def async_added_to_hass(self):
            pass
        def async_on_remove(self, fn):
            self.remove = fn
        def async_write_ha_state(self):
            self.updates = getattr(self, "updates", 0) + 1
    modules = {
        "homeassistant": {}, "homeassistant.components": {},
        "homeassistant.components.number": {"NumberEntity": type("NumberEntity", (), {}), "NumberMode": SimpleNamespace(BOX="box")},
        "homeassistant.components.sensor": {"SensorEntity": type("SensorEntity", (), {}), "SensorDeviceClass": SimpleNamespace(POWER="power", CURRENT="current", VOLTAGE="voltage"), "SensorStateClass": SimpleNamespace(MEASUREMENT="measurement")},
        "homeassistant.components.switch": {"SwitchEntity": type("SwitchEntity", (), {})},
        "homeassistant.helpers": {}, "homeassistant.helpers.entity": {"Entity": Entity},
        "homeassistant.helpers.device_registry": {"DeviceInfo": lambda **kwargs: kwargs},
        "homeassistant.const": dict(ATTR_UNIT_OF_MEASUREMENT="unit_of_measurement", SERVICE_TURN_ON="turn_on", SERVICE_TURN_OFF="turn_off", STATE_ON="on", STATE_OFF="off", STATE_UNKNOWN="unknown", STATE_UNAVAILABLE="unavailable"),
        "homeassistant.core": {"HomeAssistant": object, "State": object},
    }
    for name, attrs in modules.items():
        module = ModuleType(name)
        vars(module).update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
    for suffix in ("point_entity", "actuator"):
        monkeypatch.delitem(sys.modules, "custom_components.power_manager." + suffix, raising=False)
    return importlib.import_module("custom_components.power_manager.point_entity"), importlib.import_module("custom_components.power_manager.actuator")


def test_points_register_to_subentries_and_only_services_write(entities):
    module, _ = entities
    from custom_components.power_manager.point_config import normalize_point
    calls = []
    async def write(key, value):
        calls.append((key, value))
    points = {}
    for kind in ("sensor", "number", "switch"):
        config = normalize_point(dict(name=kind, protocol="mqtt", kind=kind,
            state_topic="state" if kind == "sensor" else "", command_topic="set" if kind != "sensor" else ""))
        points[kind] = SimpleNamespace(config=config, value=None, available=kind != "sensor", error=None, listeners=set())
    manager = SimpleNamespace(entry=SimpleNamespace(entry_id="entry"), points=points, write=write)
    entry = SimpleNamespace(runtime_data=SimpleNamespace(direct_io=manager))
    records = []
    for kind in points:
        module.add_point_entities(entry, kind, lambda items, **kwargs: records.extend((item, kwargs["config_subentry_id"]) for item in items))
    assert [key for _, key in records] == ["sensor", "number", "switch"]
    assert not calls
    sensor, number, switch = [item for item, _ in records]
    assert not sensor.available
    assert number.available and number.native_value is None
    assert switch.is_on is None
    assert number.extra_state_attributes["power_manager_write_only"] is True
    assert sensor._attr_force_update
    assert sensor._attr_native_unit_of_measurement == "W"
    asyncio.run(sensor.async_added_to_hass())
    for listener in tuple(points["sensor"].listeners):
        listener()
    assert sensor.updates == 1
    sensor.remove()
    assert not points["sensor"].listeners
    asyncio.run(number.async_set_native_value(2000))
    asyncio.run(switch.async_turn_on())
    asyncio.run(switch.async_turn_off())
    assert calls == [("number", 2000), ("switch", True), ("switch", False)]


def test_only_explicit_write_only_points_can_start_unknown(entities):
    _, actuator = entities
    state = SimpleNamespace(state="unknown", attributes={"min": 0, "max": 22000, "unit_of_measurement": "W"})
    hass = SimpleNamespace(states=SimpleNamespace(get=lambda entity_id: state))
    load = dict(output_entity="number.direct", load_type="modulating", min_kw=.5, max_kw=5, output_unit="W")
    with pytest.raises(actuator.ActuatorError):
        actuator.validate_actuator(hass, load)
    state.attributes.update(power_manager_point=True, power_manager_write_only=True)
    actuator.validate_actuator(hass, load)
    state.state = "unavailable"
    with pytest.raises(actuator.ActuatorError):
        actuator.validate_actuator(hass, load)
    state.state = "unknown"
    state.attributes["power_manager_write_only"] = False
    with pytest.raises(actuator.ActuatorError):
        actuator.validate_actuator(hass, load)
