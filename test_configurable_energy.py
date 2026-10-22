"""Behavior tests for scaling, device commands and net-export allocation."""

import asyncio
import importlib
import random
import sys
from types import ModuleType, SimpleNamespace

import pytest

from custom_components.power_manager.const import INPUT_FACTORS
from custom_components.power_manager.load_adapter import actual_kw_from_source, requested_kw_from_source
from custom_components.power_manager.load_config import normalize_load_data, validate_load_data
from custom_components.power_manager.measurements import MeasurementError, power_to_kw, scaled_value
from custom_components.power_manager.outputs import build_output_plan


@pytest.mark.parametrize("factor", INPUT_FACTORS)
def test_power_scaling_is_applied_before_unit_conversion(factor):
    assert power_to_kw(5000, "W", factor=factor) == pytest.approx(5 * factor)
    assert power_to_kw(-5, "kW", invert=True, factor=factor) == pytest.approx(5 * factor)


@pytest.mark.parametrize("factor", [0, 2, -1, float("nan"), float("inf"), "bad"])
def test_bad_scaling_never_reaches_controller(factor):
    with pytest.raises(MeasurementError):
        scaled_value(5, factor)


def test_request_and_actual_scaling_use_same_contract():
    assert actual_kw_from_source(5000, "W", factor=0.1) == pytest.approx(0.5)
    assert requested_kw_from_source(5000, "W", factor=0.1, load_type="modulating", max_kw=10, default_request_kw_value=0) == pytest.approx(0.5)
    assert requested_kw_from_source("on", None, factor=1000, load_type="switch", max_kw=2, default_request_kw_value=0) == 2


def test_consumer_accepts_custom_switch_codes_and_amp_output():
    data = dict(load_name="Heizung", load_type="switch", output_entity="number.mode", max_kw=2, command_on="12", command_off="14")
    assert validate_load_data(data) == {}
    normalized = normalize_load_data(data)
    assert normalized["min_kw"] == 2
    assert normalized["command_on"] == "12"
    assert validate_load_data(dict(data, command_off="12"))["command_on"] == "invalid_commands"
    assert validate_load_data(dict(data, command_off="12.0"))["command_on"] == "invalid_commands"
    assert validate_load_data(dict(data, actual_power_factor=2))["actual_power_factor"] == "invalid_input_factor"
    assert validate_load_data(dict(data, enable_entity="number.mode"))["enable_entity"] == "duplicate_output_entity"
    assert validate_load_data(dict(load_name="Lader", load_type="modulating", output_entity="number.current", output_unit="A", max_kw=6.9)) == {}


@pytest.mark.parametrize("load_type", ["modulating", "evse"])
def test_same_power_can_be_written_as_amps_or_watts(load_type):
    assert build_output_plan(load_type=load_type, target_kw=6.9, power_unit="A").numeric_value == pytest.approx(10)
    assert build_output_plan(load_type=load_type, target_kw=6.9, power_unit="W").numeric_value == pytest.approx(6900)
    assert build_output_plan(load_type=load_type, target_kw=2.3, power_unit="A", evse_phases=1).numeric_value == pytest.approx(10)


@pytest.mark.parametrize("prefix", ["", "custom_components.power_manager."])
def test_net_export_preserves_household_demand_and_charging(prefix):
    controller = importlib.import_module(prefix + "controller")
    models = importlib.import_module(prefix + "models")
    load = models.ControllableLoad(name="Lader", priority=1, requested_kw=10, actual_kw=2, min_kw=0, max_kw=10)
    inputs = models.ControllerInputs(grid_kw=-1, grid_limit_kw=20, pv_kw=10, battery_kw=-3, mode=models.OperatingMode.SURPLUS, surplus_strategy="net_export")
    result = controller.run_controller(inputs, [load])
    assert result.total_target_kw == pytest.approx(3)
    # After consuming the extra 1 kW export, measured grid power is zero.
    assert result.projected_grid_kw == pytest.approx(0)
    # Updating the meter to the newly commanded load must not switch it off.
    load.actual_kw = 3
    inputs.grid_kw = 0
    next_result = controller.run_controller(inputs, [load], result.state)
    assert next_result.total_target_kw == pytest.approx(3)


@pytest.mark.parametrize("prefix", ["", "custom_components.power_manager."])
def test_net_export_never_budgets_battery_discharge(prefix):
    controller = importlib.import_module(prefix + "controller")
    models = importlib.import_module(prefix + "models")
    loads = [models.ControllableLoad(name="A", priority=1, requested_kw=4, actual_kw=2, min_kw=0, max_kw=4), models.ControllableLoad(name="B", priority=2, requested_kw=4, actual_kw=0, min_kw=0, max_kw=4)]
    inputs = models.ControllerInputs(grid_kw=-4, grid_limit_kw=20, pv_kw=20, battery_kw=3, mode=models.OperatingMode.SURPLUS, surplus_strategy="net_export")
    result = controller.run_controller(inputs, loads)
    assert result.total_target_kw == pytest.approx(3)
    assert result.targets_kw == pytest.approx({"A": 3, "B": 0})
    inputs.battery_soc, inputs.surplus_min_battery_soc = 20, 20
    assert controller.run_controller(inputs, loads).total_target_kw == 0


def test_randomized_net_export_respects_surplus_and_peak_limits():
    from custom_components.power_manager.controller import run_controller
    from custom_components.power_manager.models import ControllableLoad, ControllerInputs, OperatingMode

    rng = random.Random(123)
    for _ in range(200):
        actual = rng.uniform(0, 10)
        grid = rng.uniform(-20, 20)
        battery = rng.uniform(-10, 10)
        limit = rng.uniform(1, 20)
        inputs = ControllerInputs(grid_kw=grid, grid_limit_kw=limit, battery_kw=battery, mode=OperatingMode.SURPLUS, surplus_strategy="net_export")
        loads = [ControllableLoad(name="Lader", priority=1, requested_kw=10, actual_kw=actual, min_kw=0, max_kw=10)]
        result = run_controller(inputs, loads)
        assert result.total_target_kw <= max(0, actual - grid - max(0, battery)) + 1e-6
        assert result.total_target_kw <= max(0, limit - (grid - actual)) + 1e-6


@pytest.fixture
def actuator(monkeypatch):
    """Load the real actuator with a small HA service/state boundary double."""

    ha = ModuleType("homeassistant")
    constants = ModuleType("homeassistant.const")
    for key, value in dict(ATTR_UNIT_OF_MEASUREMENT="unit_of_measurement", SERVICE_TURN_OFF="turn_off", SERVICE_TURN_ON="turn_on", STATE_OFF="off", STATE_ON="on", STATE_UNAVAILABLE="unavailable", STATE_UNKNOWN="unknown").items():
        setattr(constants, key, value)
    core = ModuleType("homeassistant.core")
    core.HomeAssistant = core.State = object
    for name, value in {"homeassistant": ha, "homeassistant.const": constants, "homeassistant.core": core}.items():
        monkeypatch.setitem(sys.modules, name, value)
    name = "custom_components.power_manager.actuator"
    monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module(name)
    yield module
    sys.modules.pop(name, None)


class FakeHass:
    def __init__(self, states):
        self.states = states
        self.calls = []
        self.services = self

    async def async_call(self, domain, service, data, blocking):
        self.calls.append((domain, service, data))
        entity = self.states[data["entity_id"]]
        entity.state = str(data.get("value", data.get("option", "on" if service == "turn_on" else "off")))


def state(value, **attributes):
    return SimpleNamespace(state=str(value), attributes=attributes)


def test_numeric_switch_sends_12_and_14_and_skips_duplicates(actuator):
    hass = FakeHass({"number.mode": state(14, min=0, max=20)})
    data = dict(load_type="switch", output_entity="number.mode", command_on="12", command_off="14")
    actuator.validate_actuator(hass, data)
    asyncio.run(actuator.async_apply_target(hass, data, 2))
    asyncio.run(actuator.async_apply_target(hass, data, 2))
    asyncio.run(actuator.async_apply_safe_state(hass, data))
    assert [call[2]["value"] for call in hass.calls] == [12, 14]


def test_select_switch_uses_option_text(actuator):
    hass = FakeHass({"select.mode": state("14", options=["12", "14"])})
    data = dict(load_type="switch", output_entity="select.mode", command_on="12", command_off="14")
    actuator.validate_actuator(hass, data)
    asyncio.run(actuator.async_apply_target(hass, data, 2))
    asyncio.run(actuator.async_apply_safe_state(hass, data))
    assert hass.calls == [("select", "select_option", {"entity_id": "select.mode", "option": "12"}), ("select", "select_option", {"entity_id": "select.mode", "option": "14"})]


def test_numeric_enable_disables_before_zero_and_enables_after_setpoint(actuator):
    hass = FakeHass({"number.power": state(0, min=0, max=10000, unit_of_measurement="W"), "number.mode": state(14, min=0, max=20)})
    data = dict(load_type="modulating", output_entity="number.power", output_unit="W", enable_entity="number.mode", command_on="12", command_off="14", min_kw=0, max_kw=10)
    actuator.validate_actuator(hass, data)
    asyncio.run(actuator.async_apply_target(hass, data, 5))
    asyncio.run(actuator.async_apply_safe_state(hass, data))
    assert [(call[2]["entity_id"], call[2]["value"]) for call in hass.calls] == [("number.power", 5000), ("number.mode", 12), ("number.mode", 14), ("number.power", 0)]


def test_safe_off_still_works_when_on_command_is_invalid(actuator):
    hass = FakeHass({"number.mode": state(12, min=0, max=20)})
    data = dict(load_type="switch", output_entity="number.mode", command_on="99", command_off="14")
    with pytest.raises(actuator.ActuatorError):
        actuator.validate_actuator(hass, data)
    asyncio.run(actuator.async_apply_safe_state(hass, data))
    assert hass.calls[0][2]["value"] == 14


def test_switch_load_also_applies_separate_enable_in_safe_order(actuator):
    hass = FakeHass({"switch.heater": state("off"), "number.mode": state(14, min=0, max=20)})
    data = dict(load_type="switch", output_entity="switch.heater", enable_entity="number.mode", command_on="12", command_off="14")
    actuator.validate_actuator(hass, data)
    asyncio.run(actuator.async_apply_target(hass, data, 2))
    asyncio.run(actuator.async_apply_safe_state(hass, data))
    assert [(call[1], call[2]["entity_id"]) for call in hass.calls] == [("turn_on", "switch.heater"), ("set_value", "number.mode"), ("set_value", "number.mode"), ("turn_off", "switch.heater")]


@pytest.mark.parametrize("unit,expected", [("A", 10), ("W", 6900), ("auto", 10)])
def test_evse_output_unit_reaches_service_boundary(actuator, unit, expected):
    hass = FakeHass({"number.wallbox": state(0, min=0, max=20000)})
    data = dict(load_type="evse", output_entity="number.wallbox", output_unit=unit, min_kw=4.14, max_kw=11.04)
    actuator.validate_actuator(hass, data)
    result = asyncio.run(actuator.async_apply_target(hass, data, 6.9))
    assert result.numeric_value == pytest.approx(expected)
    assert hass.calls[0][2]["value"] == pytest.approx(expected)
