"""Manual demand must obey the same hard budgets; base load is a house balance."""

import pytest

from custom_components.power_manager.balance import calculate_house_balance
from custom_components.power_manager.manual import ManualControl, manual_requested_kw, validate_manual_power
from custom_components.power_manager.models import ControllableLoad, ControllerInputs, OperatingMode
from custom_components.power_manager.controller import run_controller


def test_grid_meter_balance_subtracts_all_four_consumers():
    consumers = 2.0 + 2.2 + 0.0 + 0.0
    result = calculate_house_balance(grid_kw=0.002, pv_kw=7.5, battery_kw=-2.76, consumer_kw=consumers)
    assert result.house_kw == pytest.approx(4.742)
    assert result.base_kw == pytest.approx(0.542)
    assert result.source == "grid_pv_battery"
    assert result.estimated is False


def test_battery_discharge_supplies_house_and_charging_is_not_house_base():
    assert calculate_house_balance(grid_kw=1, pv_kw=2, battery_kw=3, consumer_kw=4).base_kw == 2
    assert calculate_house_balance(grid_kw=1, pv_kw=7, battery_kw=-2, consumer_kw=4).base_kw == 2


def test_explicit_house_meter_bypasses_grid_reconstruction():
    result = calculate_house_balance(grid_kw=-10, pv_kw=2, battery_kw=0, consumer_kw=4, house_meter_kw=5)
    assert result.base_kw == 1
    assert result.source == "house_meter"


def test_inconsistent_meter_values_keep_raw_negative_for_diagnostics():
    result = calculate_house_balance(grid_kw=1, pv_kw=0, battery_kw=0, consumer_kw=2, consumer_estimated=True)
    assert result.base_kw == 0
    assert result.raw_base_kw == -1
    assert result.estimated is True


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 11, 0.5])
def test_manual_value_rejects_nonfinite_out_of_range_and_below_minimum(value):
    with pytest.raises(ValueError):
        validate_manual_power(value, min_kw=1, max_kw=10)


def test_manual_power_accepts_zero_or_technical_range():
    assert validate_manual_power(0, min_kw=1, max_kw=10) == 0
    assert validate_manual_power(3.5, min_kw=1, max_kw=10) == 3.5


def test_manual_demand_and_off_never_bypass_peak_or_surplus_budgets():
    control = ManualControl(mode="manual", power_kw=5)
    load = ControllableLoad(name="Lader", priority=1, requested_kw=manual_requested_kw(10, control), min_kw=1, max_kw=10, actual_kw=0)
    inputs = ControllerInputs(grid_kw=2, grid_limit_kw=4)
    assert run_controller(inputs, [load]).total_target_kw == 2
    inputs.mode, inputs.surplus_strategy = OperatingMode.SURPLUS, "net_export"
    assert run_controller(inputs, [load]).total_target_kw == 0
    inputs.mode = OperatingMode.NORMAL
    control.mode = "off"
    load.requested_kw = manual_requested_kw(10, control)
    assert run_controller(inputs, [load]).total_target_kw == 0
    control.mode = "auto"
    assert manual_requested_kw(3, control) == 3


def test_off_request_overrides_minimum_runtime():
    load = ControllableLoad(name="Pumpe", priority=1, requested_kw=2, min_kw=1, max_kw=3, actual_kw=0, min_on_time_s=600)
    inputs = ControllerInputs(grid_kw=0, grid_limit_kw=10, now_s=0)
    first = run_controller(inputs, [load])
    assert first.total_target_kw == 2
    load.actual_kw, load.requested_kw = 2, 0
    inputs.grid_kw, inputs.now_s = 2, 1
    assert run_controller(inputs, [load], first.state).total_target_kw == 0


def test_unavailable_load_remains_unavailable_when_manually_requested():
    load = ControllableLoad(name="Pumpe", priority=1, requested_kw=5, min_kw=1, max_kw=5, available=False)
    assert run_controller(ControllerInputs(grid_kw=0, grid_limit_kw=20), [load]).total_target_kw == 0
