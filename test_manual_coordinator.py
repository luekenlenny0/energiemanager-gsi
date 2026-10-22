"""Exercise the real coordinator behind lightweight HA state/service doubles."""

import asyncio
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture
def coordinator(monkeypatch):
    class CoordinatorBase:
        def __class_getitem__(cls, item):
            return cls

        def __init__(self, hass, *args, **kwargs):
            self.hass, self.data = hass, None

        async def async_request_refresh(self):
            self.data = await self._async_update_data()

    class HomeAssistantError(RuntimeError):
        pass

    modules = {
        "homeassistant": {},
        "homeassistant.config_entries": {"ConfigEntry": object},
        "homeassistant.const": dict(ATTR_UNIT_OF_MEASUREMENT="unit_of_measurement", SERVICE_TURN_ON="turn_on", SERVICE_TURN_OFF="turn_off", STATE_ON="on", STATE_OFF="off", STATE_UNKNOWN="unknown", STATE_UNAVAILABLE="unavailable"),
        "homeassistant.core": {"Event": object, "HomeAssistant": object, "State": object, "callback": lambda fn: fn},
        "homeassistant.exceptions": {"HomeAssistantError": HomeAssistantError},
        "homeassistant.helpers": {},
        "homeassistant.helpers.debounce": {"Debouncer": lambda *args, **kwargs: None},
        "homeassistant.helpers.event": {"async_track_state_change_event": lambda *args: None, "async_track_time_interval": lambda *args: None},
        "homeassistant.helpers.update_coordinator": {"DataUpdateCoordinator": CoordinatorBase},
    }
    for name, attributes in modules.items():
        module = ModuleType(name)
        vars(module).update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    # Keep imports local so these doubles never become global test dependencies.
    for name in ("actuator", "coordinator"):
        monkeypatch.delitem(sys.modules, "custom_components.power_manager." + name, raising=False)
    name = "custom_components.power_manager.coordinator"
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / "custom_components/power_manager/coordinator.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)

    def state(value, unit="W"):
        return SimpleNamespace(state=str(value), attributes={"unit_of_measurement": unit}, last_reported=datetime.now(timezone.utc))

    hass = SimpleNamespace(states={"sensor.grid": state(1000), "sensor.pv": state(5000), "sensor.battery": state(-1000), "sensor.heat": state(2000), "sensor.wall": state(1000)})
    subentries = {
        "heat": SimpleNamespace(subentry_type="load", data=dict(load_name="Wärmepumpe", load_type="modulating", min_kw=0.5, max_kw=5, default_request_kw=2, actual_power_entity="sensor.heat", priority=1)),
        "wall": SimpleNamespace(subentry_type="load", data=dict(load_name="Wallbox", load_type="modulating", min_kw=1, max_kw=7, default_request_kw=1, actual_power_entity="sensor.wall", priority=2)),
    }
    entry = SimpleNamespace(data=dict(grid_power_entity="sensor.grid", grid_limit_kw=4, pv_power_entity="sensor.pv", battery_power_entity="sensor.battery"), options={}, subentries=subentries)
    instance = module.PowerManagerCoordinator(hass, entry)
    yield instance, HomeAssistantError
    sys.modules.pop("custom_components.power_manager.actuator", None)


def run(coro):
    return asyncio.run(coro)


def test_manual_control_uses_core_budgets_and_meter_balance(coordinator):
    instance, _ = coordinator
    run(instance.async_request_refresh())
    assert instance.data.house_balance.base_kw == 2
    run(instance.async_set_manual_power("wall", 5))
    run(instance.async_set_manual_mode("wall", "manual"))
    assert instance.data.loads["heat"].calculated_target_kw == 2
    assert instance.data.loads["wall"].calculated_target_kw == 4
    assert instance.data.result.projected_grid_kw == 4
    assert instance.data.house_balance.base_kw == 2
    assert instance.live_control_enabled is False
    run(instance.async_set_manual_mode("wall", "off"))
    assert instance.data.loads["wall"].calculated_target_kw == 0
    run(instance.async_set_manual_mode("wall", "auto"))
    assert instance.data.loads["wall"].requested_kw == 1


def test_dry_run_targets_do_not_appear_as_physical_household_consumption(coordinator):
    instance, _ = coordinator
    instance.config_entry.subentries["wall"].data.pop("actual_power_entity")
    run(instance.async_request_refresh())
    assert instance.data.house_balance.base_kw == 3
    assert instance.data.house_balance.estimated is True
    run(instance.async_request_refresh())
    assert instance.data.house_balance.base_kw == 3


def test_manual_override_ignores_bad_automatic_request_but_not_availability(coordinator):
    instance, _ = coordinator
    instance.config_entry.subentries["wall"].data["request_entity"] = "sensor.missing"
    run(instance.async_set_manual_mode("wall", "manual"))
    assert instance.data.loads["wall"].input_error is None
    instance.config_entry.subentries["wall"].data["availability_entity"] = "sensor.missing"
    run(instance.async_request_refresh())
    assert instance.data.loads["wall"].available is False
    assert instance.data.loads["wall"].calculated_target_kw == 0


def test_invalid_manual_values_leave_previous_setting_intact(coordinator):
    instance, Error = coordinator
    previous = instance.manual_control("wall").power_kw
    with pytest.raises(Error):
        run(instance.async_set_manual_power("wall", 0.5))
    assert instance.manual_control("wall").power_kw == previous
    with pytest.raises(Error):
        run(instance.async_set_manual_mode("wall", "bad"))
    assert instance.manual_control("wall").mode == "auto"


def test_stale_or_missing_house_meter_is_visible_not_faked(coordinator):
    instance, _ = coordinator
    instance.config_entry.data["house_power_entity"] = "sensor.missing"
    run(instance.async_request_refresh())
    assert instance.data.house_balance is None
    assert instance.data.balance_error
    assert instance.data.grid_measurement_healthy is True


def test_restart_defaults_to_automatic_with_live_control_off(coordinator):
    instance, _ = coordinator
    assert instance.manual_control("heat").mode == "auto"
    assert instance.live_control_enabled is False


def test_entities_register_under_each_consumer_and_delegate_to_real_coordinator(coordinator, monkeypatch):
    import importlib

    instance, _ = coordinator
    instance.config_entry.entry_id = "demo"
    instance.config_entry.runtime_data = instance
    for subentry in instance.config_entry.subentries.values():
        subentry.title = subentry.data["load_name"]

    class CoordinatorEntity:
        def __class_getitem__(cls, item):
            return cls

        def __init__(self, coordinator):
            self.coordinator = coordinator

    class NumberEntity:
        pass

    class SelectEntity:
        pass

    modules = {
        "homeassistant.components": {},
        "homeassistant.components.number": {"NumberEntity": NumberEntity, "NumberMode": SimpleNamespace(BOX="box")},
        "homeassistant.components.sensor": {"SensorEntity": type("SensorEntity", (), {}), "SensorDeviceClass": SimpleNamespace(POWER="power", CURRENT="current", VOLTAGE="voltage"), "SensorStateClass": SimpleNamespace(MEASUREMENT="measurement")},
        "homeassistant.components.switch": {"SwitchEntity": type("SwitchEntity", (), {})},
        "homeassistant.helpers.entity": {"Entity": type("Entity", (), {})},
        "homeassistant.components.select": {"SelectEntity": SelectEntity},
        "homeassistant.helpers.device_registry": {"DeviceInfo": lambda **kwargs: kwargs},
        "homeassistant.helpers.entity_platform": {"AddConfigEntryEntitiesCallback": object},
    }
    for name, values in modules.items():
        module = ModuleType(name)
        vars(module).update(values)
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(sys.modules["homeassistant.helpers.update_coordinator"], "CoordinatorEntity", CoordinatorEntity, raising=False)
    for suffix in ("number", "select"):
        monkeypatch.delitem(sys.modules, "custom_components.power_manager." + suffix, raising=False)
    number = importlib.import_module("custom_components.power_manager.number")
    select = importlib.import_module("custom_components.power_manager.select")
    records = []
    instance.direct_io = SimpleNamespace(points={})

    def collect(entities, **kwargs):
        records.extend((entity, kwargs.get("config_subentry_id")) for entity in entities)

    run(number.async_setup_entry(instance.hass, instance.config_entry, collect))
    run(select.async_setup_entry(instance.hass, instance.config_entry, collect))
    power_entity = next(entity for entity, subentry_id in records if subentry_id == "heat" and isinstance(entity, number.PowerManagerManualPower))
    mode_entity = next(entity for entity, subentry_id in records if subentry_id == "heat" and isinstance(entity, select.PowerManagerLoadModeSelect))
    assert power_entity.native_value == 2
    run(power_entity.async_set_native_value(3.2))
    run(mode_entity.async_select_option("manual"))
    assert power_entity.native_value == 3.2
    assert mode_entity.current_option == "manual"
    assert instance.data.loads["heat"].requested_kw == 3.2
    assert power_entity._attr_unique_id == "demo_heat_manual_power"
    assert mode_entity._attr_unique_id == "demo_heat_manual_mode"
    sys.modules.pop("custom_components.power_manager.number", None)
    sys.modules.pop("custom_components.power_manager.select", None)
