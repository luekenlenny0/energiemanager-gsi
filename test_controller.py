import math

import pytest

from allocator import allocate_power
from controller import run_controller

from models import (
    ControllableLoad,
    ControllerInputs,
    ControllerState,
    LoadRuntimeState,
    OperatingMode,
)


# ============================================================
# GRUNDLEGENDER ALLOCATOR
# ============================================================


def test_allocator_priority_1_gets_available_budget():
    loads = [
        ControllableLoad(
            name="Wärmepumpe",
            priority=1,
            requested_kw=20.0,
            min_kw=5.0,
            max_kw=20.0,
        ),
        ControllableLoad(
            name="Wallbox 1",
            priority=2,
            requested_kw=11.0,
            min_kw=4.14,
            max_kw=11.0,
        ),
        ControllableLoad(
            name="Heizstab",
            priority=3,
            requested_kw=10.0,
            min_kw=1.0,
            max_kw=10.0,
        ),
    ]

    result = allocate_power(
        loads=loads,
        available_budget_kw=10.0,
    )

    assert (
        result["Wärmepumpe"]
        == pytest.approx(10.0)
    )

    assert (
        result["Wallbox 1"]
        == pytest.approx(0.0)
    )

    assert (
        result["Heizstab"]
        == pytest.approx(0.0)
    )


def test_allocator_distributes_remaining_power():
    loads = [
        ControllableLoad(
            name="Wärmepumpe",
            priority=1,
            requested_kw=20.0,
            min_kw=5.0,
            max_kw=20.0,
        ),
        ControllableLoad(
            name="Wallbox 1",
            priority=2,
            requested_kw=11.0,
            min_kw=4.14,
            max_kw=11.0,
        ),
        ControllableLoad(
            name="Heizstab",
            priority=3,
            requested_kw=10.0,
            min_kw=1.0,
            max_kw=10.0,
        ),
    ]

    result = allocate_power(
        loads=loads,
        available_budget_kw=25.0,
    )

    assert (
        result["Wärmepumpe"]
        == pytest.approx(20.0)
    )

    assert (
        result["Wallbox 1"]
        == pytest.approx(5.0)
    )

    assert (
        result["Heizstab"]
        == pytest.approx(0.0)
    )


def test_allocator_switches_load_off_below_minimum():
    load = ControllableLoad(
        name="Last",
        priority=1,
        requested_kw=20.0,
        min_kw=5.0,
        max_kw=20.0,
    )

    result = allocate_power(
        loads=[load],
        available_budget_kw=4.0,
    )

    assert (
        result["Last"]
        == pytest.approx(0.0)
    )


def test_allocator_skips_unavailable_load():
    loads = [
        ControllableLoad(
            name="Last 1",
            priority=1,
            requested_kw=20.0,
            min_kw=5.0,
            max_kw=20.0,
            available=False,
        ),
        ControllableLoad(
            name="Last 2",
            priority=2,
            requested_kw=10.0,
            min_kw=1.0,
            max_kw=10.0,
        ),
    ]

    result = allocate_power(
        loads=loads,
        available_budget_kw=10.0,
    )

    assert (
        result["Last 1"]
        == pytest.approx(0.0)
    )

    assert (
        result["Last 2"]
        == pytest.approx(10.0)
    )


# ============================================================
# NORMALBETRIEB / PEAKSHAVING
# ============================================================


def test_controller_130_kw_grid_140_kw_limit():
    loads = [
        ControllableLoad(
            name="Wärmepumpe",
            priority=1,
            requested_kw=20.0,
            actual_kw=0.0,
            min_kw=5.0,
            max_kw=20.0,
        ),
        ControllableLoad(
            name="Wallbox 1",
            priority=2,
            requested_kw=11.0,
            actual_kw=0.0,
            min_kw=4.14,
            max_kw=11.0,
        ),
        ControllableLoad(
            name="Heizstab",
            priority=3,
            requested_kw=10.0,
            actual_kw=0.0,
            min_kw=1.0,
            max_kw=10.0,
        ),
    ]

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=130.0,
            grid_limit_kw=140.0,
            battery_soc=70.0,
        ),
        loads=loads,
    )

    assert (
        result.base_load_kw
        == pytest.approx(130.0)
    )

    assert (
        result.available_budget_kw
        == pytest.approx(10.0)
    )

    assert (
        result.targets_kw["Wärmepumpe"]
        == pytest.approx(10.0)
    )

    assert (
        result.targets_kw["Wallbox 1"]
        == pytest.approx(0.0)
    )

    assert (
        result.targets_kw["Heizstab"]
        == pytest.approx(0.0)
    )

    assert (
        result.projected_grid_kw
        == pytest.approx(140.0)
    )

    assert (
        result.peak_shaving_active
        is True
    )


def test_controller_uses_actual_power_measurements():
    loads = [
        ControllableLoad(
            name="Wärmepumpe",
            priority=1,
            requested_kw=20.0,
            actual_kw=15.0,
            min_kw=5.0,
            max_kw=20.0,
        ),
        ControllableLoad(
            name="Wallbox 1",
            priority=2,
            requested_kw=11.0,
            actual_kw=8.0,
            min_kw=4.14,
            max_kw=11.0,
        ),
        ControllableLoad(
            name="Heizstab",
            priority=3,
            requested_kw=10.0,
            actual_kw=5.0,
            min_kw=1.0,
            max_kw=10.0,
        ),
    ]

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=135.0,
            grid_limit_kw=140.0,
            battery_soc=70.0,
        ),
        loads=loads,
    )

    assert (
        result.measured_controlled_power_kw
        == pytest.approx(28.0)
    )

    assert (
        result.base_load_kw
        == pytest.approx(107.0)
    )

    assert (
        result.available_budget_kw
        == pytest.approx(33.0)
    )

    assert (
        result.targets_kw["Wärmepumpe"]
        == pytest.approx(20.0)
    )

    assert (
        result.targets_kw["Wallbox 1"]
        == pytest.approx(11.0)
    )

    assert (
        result.targets_kw["Heizstab"]
        == pytest.approx(2.0)
    )

    assert (
        result.projected_grid_kw
        == pytest.approx(140.0)
    )


def test_controller_without_actual_power_is_conservative_first_cycle():
    load = ControllableLoad(
        name="Wärmepumpe",
        priority=1,
        requested_kw=20.0,
        actual_kw=None,
        min_kw=5.0,
        max_kw=20.0,
    )

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=130.0,
            grid_limit_kw=140.0,
        ),
        loads=[load],
    )

    assert (
        result.estimated_controlled_power_kw
        == pytest.approx(0.0)
    )

    assert (
        result.base_load_kw
        == pytest.approx(130.0)
    )

    assert (
        result.targets_kw["Wärmepumpe"]
        == pytest.approx(10.0)
    )


def test_controller_respects_grid_reserve():
    load = ControllableLoad(
        name="Wärmepumpe",
        priority=1,
        requested_kw=20.0,
        actual_kw=0.0,
        min_kw=5.0,
        max_kw=20.0,
    )

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=130.0,
            grid_limit_kw=140.0,
            grid_reserve_kw=1.0,
        ),
        loads=[load],
    )

    assert (
        result.effective_grid_limit_kw
        == pytest.approx(139.0)
    )

    assert (
        result.available_budget_kw
        == pytest.approx(9.0)
    )

    assert (
        result.targets_kw["Wärmepumpe"]
        == pytest.approx(9.0)
    )


# ============================================================
# FEHLENDE ISTWERTE
# ============================================================


def test_unmeasured_load_uses_last_target_as_estimate():
    load = ControllableLoad(
        name="Wärmepumpe",
        priority=1,
        requested_kw=20.0,
        actual_kw=None,
        min_kw=5.0,
        max_kw=20.0,
    )

    first = run_controller(
        inputs=ControllerInputs(
            grid_kw=130.0,
            grid_limit_kw=140.0,
        ),
        loads=[load],
    )

    second = run_controller(
        inputs=ControllerInputs(
            grid_kw=140.0,
            grid_limit_kw=140.0,
            now_s=1.0,
        ),
        loads=[load],
        state=first.state,
    )

    assert (
        second.estimated_controlled_power_kw
        == pytest.approx(10.0)
    )

    assert (
        second.base_load_kw
        == pytest.approx(130.0)
    )

    assert (
        second.targets_kw["Wärmepumpe"]
        == pytest.approx(10.0)
    )


def test_unmeasured_load_reduces_when_base_load_increases():
    load = ControllableLoad(
        name="Wärmepumpe",
        priority=1,
        requested_kw=20.0,
        actual_kw=None,
        min_kw=5.0,
        max_kw=20.0,
    )

    state = ControllerState(
        last_targets_kw={
            "Wärmepumpe": 10.0
        }
    )

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=145.0,
            grid_limit_kw=140.0,
        ),
        loads=[load],
        state=state,
    )

    assert (
        result.base_load_kw
        == pytest.approx(135.0)
    )

    assert (
        result.available_budget_kw
        == pytest.approx(5.0)
    )

    assert (
        result.targets_kw["Wärmepumpe"]
        == pytest.approx(5.0)
    )


def test_unmeasured_load_turns_off_below_minimum():
    load = ControllableLoad(
        name="Wärmepumpe",
        priority=1,
        requested_kw=20.0,
        actual_kw=None,
        min_kw=5.0,
        max_kw=20.0,
    )

    state = ControllerState(
        last_targets_kw={
            "Wärmepumpe": 10.0
        }
    )

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=146.0,
            grid_limit_kw=140.0,
        ),
        loads=[load],
        state=state,
    )

    assert (
        result.available_budget_kw
        == pytest.approx(4.0)
    )

    assert (
        result.targets_kw["Wärmepumpe"]
        == pytest.approx(0.0)
    )


# ============================================================
# ÜBERSCHUSSBETRIEB
# ============================================================


def test_surplus_uses_pv_generation_as_budget():
    load = ControllableLoad(
        name="Verbraucher",
        priority=1,
        requested_kw=20.0,
        actual_kw=0.0,
        min_kw=0.0,
        max_kw=20.0,
    )

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=-15.0,
            grid_limit_kw=140.0,
            pv_kw=30.0,
            battery_soc=70.0,
            mode=OperatingMode.SURPLUS,
        ),
        loads=[load],
    )

    assert (
        result.raw_surplus_budget_kw
        == pytest.approx(30.0)
    )

    assert (
        result.surplus_budget_kw
        == pytest.approx(30.0)
    )

    assert (
        result.targets_kw["Verbraucher"]
        == pytest.approx(20.0)
    )


def test_surplus_priority_prefers_heat_pump_and_frees_battery_charging():
    loads = [
        ControllableLoad(
            name="Wärmepumpe",
            priority=1,
            requested_kw=20.0,
            actual_kw=0.0,
            min_kw=0.0,
            max_kw=20.0,
        ),
        ControllableLoad(
            name="Wallbox 1",
            priority=2,
            requested_kw=11.0,
            actual_kw=4.45,
            min_kw=0.0,
            max_kw=11.0,
        ),
    ]

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=0.0,
            grid_limit_kw=140.0,
            pv_kw=14.42,
            battery_soc=71.7,
            battery_kw=-9.93,
            mode=OperatingMode.SURPLUS,
        ),
        loads=loads,
    )

    assert (
        result.base_load_kw
        == pytest.approx(-14.38)
    )

    assert (
        result.available_budget_kw
        == pytest.approx(14.42)
    )

    assert (
        result.targets_kw["Wärmepumpe"]
        == pytest.approx(14.42)
    )

    assert (
        result.targets_kw["Wallbox 1"]
        == pytest.approx(0.0)
    )

    assert (
        result.projected_grid_kw
        == pytest.approx(0.04)
    )


def test_surplus_does_not_add_battery_discharge_to_pv_budget():
    load = ControllableLoad(
        name="Wallbox",
        priority=1,
        requested_kw=20.0,
        actual_kw=0.0,
        min_kw=0.0,
        max_kw=20.0,
    )

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=0.0,
            grid_limit_kw=140.0,
            pv_kw=10.0,
            battery_soc=70.0,
            battery_kw=10.0,
            mode=OperatingMode.SURPLUS,
        ),
        loads=[load],
    )

    assert (
        result.battery_discharge_kw
        == pytest.approx(10.0)
    )

    assert (
        result.raw_surplus_budget_kw
        == pytest.approx(10.0)
    )

    assert (
        result.surplus_budget_kw
        == pytest.approx(10.0)
    )

    assert (
        result.targets_kw["Wallbox"]
        == pytest.approx(10.0)
    )


def test_surplus_pmax_still_caps_pv_budget():
    load = ControllableLoad(
        name="Verbraucher",
        priority=1,
        requested_kw=30.0,
        actual_kw=0.0,
        min_kw=0.0,
        max_kw=30.0,
    )

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=130.0,
            grid_limit_kw=140.0,
            pv_kw=30.0,
            battery_soc=70.0,
            battery_kw=0.0,
            mode=OperatingMode.SURPLUS,
        ),
        loads=[load],
    )

    assert (
        result.peak_budget_kw
        == pytest.approx(10.0)
    )

    assert (
        result.available_budget_kw
        == pytest.approx(10.0)
    )

    assert (
        result.targets_kw["Verbraucher"]
        == pytest.approx(10.0)
    )

    assert (
        result.projected_grid_kw
        == pytest.approx(140.0)
    )


# ============================================================
# GLEICHE PRIORITÄT
# ============================================================


def test_four_equal_priority_wallboxes_share_20_kw():
    loads = [
        ControllableLoad(
            name=f"Wallbox {number}",
            priority=2,
            requested_kw=11.0,
            min_kw=4.14,
            max_kw=11.0,
        )
        for number in range(1, 5)
    ]

    result = allocate_power(
        loads=loads,
        available_budget_kw=20.0,
    )

    for number in range(1, 5):

        assert (
            result[f"Wallbox {number}"]
            == pytest.approx(5.0)
        )


def test_equal_priority_distribution_respects_request_limit():
    loads = [
        ControllableLoad(
            name="Wallbox 1",
            priority=2,
            requested_kw=4.5,
            min_kw=4.14,
            max_kw=11.0,
        ),
        ControllableLoad(
            name="Wallbox 2",
            priority=2,
            requested_kw=11.0,
            min_kw=4.14,
            max_kw=11.0,
        ),
        ControllableLoad(
            name="Wallbox 3",
            priority=2,
            requested_kw=11.0,
            min_kw=4.14,
            max_kw=11.0,
        ),
        ControllableLoad(
            name="Wallbox 4",
            priority=2,
            requested_kw=11.0,
            min_kw=4.14,
            max_kw=11.0,
        ),
    ]

    result = allocate_power(
        loads=loads,
        available_budget_kw=20.0,
    )

    assert (
        result["Wallbox 1"]
        == pytest.approx(4.5)
    )

    assert (
        result["Wallbox 2"]
        == pytest.approx(5.1666666667)
    )

    assert (
        result["Wallbox 3"]
        == pytest.approx(5.1666666667)
    )

    assert (
        result["Wallbox 4"]
        == pytest.approx(5.1666666667)
    )


def test_insufficient_budget_only_starts_possible_wallboxes():
    loads = [
        ControllableLoad(
            name=f"Wallbox {number}",
            priority=2,
            requested_kw=11.0,
            min_kw=4.14,
            max_kw=11.0,
        )
        for number in range(1, 5)
    ]

    result = allocate_power(
        loads=loads,
        available_budget_kw=12.5,
    )

    assert (
        result["Wallbox 1"]
        == pytest.approx(4.1666666667)
    )

    assert (
        result["Wallbox 2"]
        == pytest.approx(4.1666666667)
    )

    assert (
        result["Wallbox 3"]
        == pytest.approx(4.1666666667)
    )

    assert (
        result["Wallbox 4"]
        == pytest.approx(0.0)
    )


def test_higher_priority_load_is_served_before_group():
    loads = [
        ControllableLoad(
            name="Priorität 1",
            priority=1,
            requested_kw=10.0,
            min_kw=5.0,
            max_kw=20.0,
        ),
        *[
            ControllableLoad(
                name=f"Wallbox {number}",
                priority=2,
                requested_kw=11.0,
                min_kw=4.14,
                max_kw=11.0,
            )
            for number in range(1, 5)
        ],
    ]

    result = allocate_power(
        loads=loads,
        available_budget_kw=30.0,
    )

    assert (
        result["Priorität 1"]
        == pytest.approx(10.0)
    )

    for number in range(1, 5):

        assert (
            result[f"Wallbox {number}"]
            == pytest.approx(5.0)
        )


# ============================================================
# DYNAMISCHE HYSTERESE / ZEITEN
# ============================================================


def test_dynamic_six_kw_load_does_not_start_below_start_threshold():
    load = ControllableLoad(
        name="Dynamische Last",
        priority=1,
        requested_kw=20.0,
        min_kw=6.0,
        max_kw=22.0,
        start_margin_kw=0.3,
        stop_margin_kw=0.1,
    )

    result = allocate_power(
        loads=[load],
        available_budget_kw=6.2,
    )

    assert (
        result["Dynamische Last"]
        == pytest.approx(0.0)
    )


def test_dynamic_six_kw_load_starts_at_dynamic_threshold():
    load = ControllableLoad(
        name="Dynamische Last",
        priority=1,
        requested_kw=20.0,
        min_kw=6.0,
        max_kw=22.0,
        start_margin_kw=0.3,
        stop_margin_kw=0.1,
    )

    result = allocate_power(
        loads=[load],
        available_budget_kw=6.3,
    )

    assert (
        result["Dynamische Last"]
        == pytest.approx(6.3)
    )


def test_minimum_on_time_holds_load_when_hard_budget_allows_it():
    load = ControllableLoad(
        name="Last",
        priority=1,
        requested_kw=20.0,
        min_kw=6.0,
        max_kw=22.0,
        start_margin_kw=0.3,
        stop_margin_kw=0.1,
        min_on_time_s=30.0,
    )

    state = ControllerState(
        last_targets_kw={
            "Last": 6.5
        },
        load_states={
            "Last": LoadRuntimeState(
                is_on=True,
                last_target_kw=6.5,
                last_switch_s=0.0,
            )
        },
    )

    result = allocate_power(
        loads=[load],
        available_budget_kw=6.05,
        state=state,
        now_s=10.0,
    )

    assert (
        result["Last"]
        == pytest.approx(6.05)
    )


def test_load_stops_after_minimum_on_time_below_stop_threshold():
    load = ControllableLoad(
        name="Last",
        priority=1,
        requested_kw=20.0,
        min_kw=6.0,
        max_kw=22.0,
        start_margin_kw=0.3,
        stop_margin_kw=0.1,
        min_on_time_s=30.0,
    )

    state = ControllerState(
        last_targets_kw={
            "Last": 6.5
        },
        load_states={
            "Last": LoadRuntimeState(
                is_on=True,
                last_target_kw=6.5,
                last_switch_s=0.0,
            )
        },
    )

    result = allocate_power(
        loads=[load],
        available_budget_kw=6.05,
        state=state,
        now_s=31.0,
    )

    assert (
        result["Last"]
        == pytest.approx(0.0)
    )


def test_hard_pmax_overrides_minimum_on_time():
    load = ControllableLoad(
        name="Last",
        priority=1,
        requested_kw=20.0,
        min_kw=6.0,
        max_kw=22.0,
        start_margin_kw=0.3,
        stop_margin_kw=0.1,
        min_on_time_s=300.0,
    )

    state = ControllerState(
        last_targets_kw={
            "Last": 6.5
        },
        load_states={
            "Last": LoadRuntimeState(
                is_on=True,
                last_target_kw=6.5,
                last_switch_s=0.0,
            )
        },
    )

    result = allocate_power(
        loads=[load],
        available_budget_kw=5.9,
        state=state,
        now_s=10.0,
    )

    assert (
        result["Last"]
        == pytest.approx(0.0)
    )


def test_minimum_off_time_prevents_immediate_restart():
    load = ControllableLoad(
        name="Last",
        priority=1,
        requested_kw=20.0,
        min_kw=6.0,
        max_kw=22.0,
        start_margin_kw=0.3,
        stop_margin_kw=0.1,
        min_off_time_s=30.0,
    )

    state = ControllerState(
        last_targets_kw={
            "Last": 0.0
        },
        load_states={
            "Last": LoadRuntimeState(
                is_on=False,
                last_target_kw=0.0,
                last_switch_s=0.0,
            )
        },
    )

    result = allocate_power(
        loads=[load],
        available_budget_kw=20.0,
        state=state,
        now_s=10.0,
    )

    assert (
        result["Last"]
        == pytest.approx(0.0)
    )


def test_settling_time_is_stored_after_target_change():
    load = ControllableLoad(
        name="Träge Last",
        priority=1,
        requested_kw=10.0,
        actual_kw=0.0,
        min_kw=2.0,
        max_kw=10.0,
        settling_time_s=5.0,
    )

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=90.0,
            grid_limit_kw=100.0,
            now_s=20.0,
        ),
        loads=[load],
    )

    runtime = (
        result.state.load_states[
            "Träge Last"
        ]
    )

    assert (
        runtime.last_target_kw
        == pytest.approx(10.0)
    )

    assert (
        runtime.last_target_change_s
        == pytest.approx(20.0)
    )

    assert (
        runtime.settling_until_s
        == pytest.approx(25.0)
    )


# ============================================================
# BELIEBIGE PARAMETER / PMAX
# ============================================================


def test_completely_different_grid_limit_values():
    load = ControllableLoad(
        name="Andere Last",
        priority=1,
        requested_kw=10.0,
        actual_kw=0.0,
        min_kw=2.0,
        max_kw=10.0,
    )

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=79.0,
            grid_limit_kw=85.0,
            grid_reserve_kw=2.0,
        ),
        loads=[load],
    )

    assert (
        result.effective_grid_limit_kw
        == pytest.approx(83.0)
    )

    assert (
        result.available_budget_kw
        == pytest.approx(4.0)
    )

    assert (
        result.targets_kw["Andere Last"]
        == pytest.approx(4.0)
    )

    assert (
        result.projected_grid_kw
        == pytest.approx(83.0)
    )


def test_invalid_minimum_greater_than_maximum_is_rejected():
    load = ControllableLoad(
        name="Fehlerhafte Last",
        priority=1,
        requested_kw=10.0,
        min_kw=15.0,
        max_kw=10.0,
    )

    with pytest.raises(ValueError):

        run_controller(
            inputs=ControllerInputs(
                grid_kw=50.0,
                grid_limit_kw=100.0,
            ),
            loads=[load],
        )


def test_projected_grid_never_exceeds_reachable_pmax():
    load = ControllableLoad(
        name="Große Last",
        priority=1,
        requested_kw=30.0,
        actual_kw=10.0,
        min_kw=1.0,
        max_kw=30.0,
    )

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=130.0,
            grid_limit_kw=140.0,
            grid_reserve_kw=1.0,
        ),
        loads=[load],
    )

    assert (
        result.targets_kw["Große Last"]
        == pytest.approx(19.0)
    )

    assert (
        result.projected_grid_kw
        == pytest.approx(139.0)
    )

    assert (
        result.projected_grid_kw
        <= result.effective_grid_limit_kw
    )


def test_uncontrollable_base_load_over_pmax_is_reported():
    load = ControllableLoad(
        name="Regelbare Last",
        priority=1,
        requested_kw=10.0,
        actual_kw=0.0,
        min_kw=1.0,
        max_kw=10.0,
    )

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=150.0,
            grid_limit_kw=140.0,
        ),
        loads=[load],
    )

    assert (
        result.available_budget_kw
        == pytest.approx(0.0)
    )

    assert (
        result.targets_kw["Regelbare Last"]
        == pytest.approx(0.0)
    )

    assert (
        result.grid_limit_unachievable
        is True
    )

    assert (
        result.projected_grid_kw
        == pytest.approx(150.0)
    )


# ============================================================
# V1.5 - BATTERIE-SOC
# ============================================================


def test_surplus_is_blocked_at_or_below_configured_battery_soc():
    load = ControllableLoad(
        name="Überschusslast",
        priority=1,
        requested_kw=20.0,
        actual_kw=0.0,
        min_kw=2.0,
        max_kw=20.0,
    )

    for battery_soc in (39.9, 40.0):
        result = run_controller(
            inputs=ControllerInputs(
                grid_kw=-12.0,
                grid_limit_kw=100.0,
                pv_kw=12.0,
                battery_soc=battery_soc,
                surplus_min_battery_soc=40.0,
                mode=OperatingMode.SURPLUS,
            ),
            loads=[load],
        )

        assert (
            result.raw_surplus_budget_kw
            == pytest.approx(12.0)
        )

        assert (
            result.surplus_budget_kw
            == pytest.approx(0.0)
        )

        assert (
            result.battery_soc_gate_enabled
            is True
        )

        assert (
            result.battery_soc_blocking_surplus
            is True
        )

        assert (
            result.targets_kw["Überschusslast"]
            == pytest.approx(0.0)
        )


def test_surplus_is_allowed_above_configured_battery_soc():
    load = ControllableLoad(
        name="Überschusslast",
        priority=1,
        requested_kw=20.0,
        actual_kw=0.0,
        min_kw=2.0,
        max_kw=20.0,
    )

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=-12.0,
            grid_limit_kw=100.0,
            pv_kw=12.0,
            battery_soc=40.1,
            surplus_min_battery_soc=40.0,
            mode=OperatingMode.SURPLUS,
        ),
        loads=[load],
    )

    assert (
        result.battery_soc_blocking_surplus
        is False
    )

    assert (
        result.surplus_budget_kw
        == pytest.approx(12.0)
    )

    assert (
        result.targets_kw["Überschusslast"]
        == pytest.approx(12.0)
    )


def test_normal_mode_ignores_surplus_soc_gate():
    load = ControllableLoad(
        name="Normallast",
        priority=1,
        requested_kw=10.0,
        actual_kw=0.0,
        min_kw=2.0,
        max_kw=10.0,
    )

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=80.0,
            grid_limit_kw=100.0,
            battery_soc=10.0,
            surplus_min_battery_soc=40.0,
            mode=OperatingMode.NORMAL,
        ),
        loads=[load],
    )

    assert (
        result.battery_soc_gate_enabled
        is True
    )

    assert (
        result.battery_soc_blocking_surplus
        is False
    )

    assert (
        result.targets_kw["Normallast"]
        == pytest.approx(10.0)
    )


def test_soc_gate_requires_battery_soc_value():
    load = ControllableLoad(
        name="Last",
        priority=1,
        requested_kw=10.0,
        min_kw=1.0,
        max_kw=10.0,
    )

    with pytest.raises(ValueError):

        run_controller(
            inputs=ControllerInputs(
                grid_kw=0.0,
                grid_limit_kw=100.0,
                battery_soc=None,
                surplus_min_battery_soc=40.0,
                mode=OperatingMode.SURPLUS,
            ),
            loads=[load],
        )


def test_controller_works_without_battery_when_soc_gate_disabled():
    load = ControllableLoad(
        name="Last",
        priority=1,
        requested_kw=5.0,
        actual_kw=0.0,
        min_kw=1.0,
        max_kw=5.0,
    )

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=50.0,
            grid_limit_kw=60.0,
            battery_soc=None,
            battery_kw=0.0,
        ),
        loads=[load],
    )

    assert (
        result.targets_kw["Last"]
        == pytest.approx(5.0)
    )

    assert (
        result.battery_soc_gate_enabled
        is False
    )


# ============================================================
# V1.5 - DIAGNOSE
# ============================================================


def test_diagnostics_report_requested_target_and_unused_budget():
    loads = [
        ControllableLoad(
            name="Last 1",
            priority=1,
            requested_kw=4.0,
            actual_kw=0.0,
            min_kw=1.0,
            max_kw=10.0,
        ),
        ControllableLoad(
            name="Last 2",
            priority=2,
            requested_kw=3.0,
            actual_kw=0.0,
            min_kw=1.0,
            max_kw=10.0,
        ),
    ]

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=50.0,
            grid_limit_kw=70.0,
        ),
        loads=loads,
    )

    assert (
        result.total_requested_kw
        == pytest.approx(7.0)
    )

    assert (
        result.total_target_kw
        == pytest.approx(7.0)
    )

    assert (
        result.unused_budget_kw
        == pytest.approx(13.0)
    )

    assert (
        result.active_load_count
        == 2
    )

    assert (
        result.limited_load_count
        == 0
    )

    assert (
        result.grid_headroom_kw
        == pytest.approx(13.0)
    )


def test_diagnostics_count_limited_loads():
    loads = [
        ControllableLoad(
            name="Last 1",
            priority=1,
            requested_kw=10.0,
            actual_kw=0.0,
            min_kw=1.0,
            max_kw=10.0,
        ),
        ControllableLoad(
            name="Last 2",
            priority=2,
            requested_kw=10.0,
            actual_kw=0.0,
            min_kw=1.0,
            max_kw=10.0,
        ),
    ]

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=95.0,
            grid_limit_kw=100.0,
        ),
        loads=loads,
    )

    assert (
        result.total_target_kw
        == pytest.approx(5.0)
    )

    assert (
        result.active_load_count
        == 1
    )

    assert (
        result.limited_load_count
        == 2
    )

    assert (
        result.grid_headroom_kw
        == pytest.approx(0.0)
    )


# ============================================================
# V1.5 - ROBUSTHEIT / EINSCHWINGEN
# ============================================================


def test_non_finite_grid_value_is_rejected_cleanly():
    load = ControllableLoad(
        name="Last",
        priority=1,
        requested_kw=5.0,
        min_kw=1.0,
        max_kw=5.0,
    )

    with pytest.raises(ValueError):

        run_controller(
            inputs=ControllerInputs(
                grid_kw=math.nan,
                grid_limit_kw=100.0,
            ),
            loads=[load],
        )


def test_old_target_is_clamped_when_maximum_is_changed():
    load = ControllableLoad(
        name="Dynamische Last",
        priority=1,
        requested_kw=7.0,
        actual_kw=None,
        min_kw=2.0,
        max_kw=7.0,
    )

    state = ControllerState(
        last_targets_kw={
            "Dynamische Last": 15.0
        },
        load_states={
            "Dynamische Last": LoadRuntimeState(
                is_on=True,
                last_target_kw=15.0,
            )
        },
    )

    result = run_controller(
        inputs=ControllerInputs(
            grid_kw=57.0,
            grid_limit_kw=60.0,
        ),
        loads=[load],
        state=state,
    )

    assert (
        result.estimated_controlled_power_kw
        == pytest.approx(7.0)
    )

    assert (
        result.targets_kw["Dynamische Last"]
        <= 7.0
    )


def test_settling_time_blocks_increase_but_allows_reduction():
    load = ControllableLoad(
        name="Träge Last",
        priority=1,
        requested_kw=10.0,
        min_kw=2.0,
        max_kw=10.0,
        settling_time_s=10.0,
    )

    state = ControllerState(
        last_targets_kw={
            "Träge Last": 5.0
        },
        load_states={
            "Träge Last": LoadRuntimeState(
                is_on=True,
                last_target_kw=5.0,
                last_switch_s=0.0,
                last_target_change_s=0.0,
                settling_until_s=10.0,
            )
        },
    )

    held = allocate_power(
        loads=[load],
        available_budget_kw=10.0,
        state=state,
        now_s=5.0,
    )

    reduced = allocate_power(
        loads=[load],
        available_budget_kw=4.0,
        state=state,
        now_s=5.0,
    )

    assert (
        held["Träge Last"]
        == pytest.approx(5.0)
    )

    assert (
        reduced["Träge Last"]
        == pytest.approx(4.0)
    )


def test_settling_time_allows_increase_after_expiry():
    load = ControllableLoad(
        name="Träge Last",
        priority=1,
        requested_kw=10.0,
        min_kw=2.0,
        max_kw=10.0,
        settling_time_s=10.0,
    )

    state = ControllerState(
        last_targets_kw={
            "Träge Last": 5.0
        },
        load_states={
            "Träge Last": LoadRuntimeState(
                is_on=True,
                last_target_kw=5.0,
                last_switch_s=0.0,
                last_target_change_s=0.0,
                settling_until_s=10.0,
            )
        },
    )

    result = allocate_power(
        loads=[load],
        available_budget_kw=10.0,
        state=state,
        now_s=10.0,
    )

    assert (
        result["Träge Last"]
        == pytest.approx(10.0)
    )