import pytest

import controller as root_controller
import models as root_models

from custom_components.power_manager import (
    controller as ha_controller,
)
from custom_components.power_manager import (
    models as ha_models,
)


def test_normal_mode_matches_reference_core():
    """
    Normalbetrieb muss im HA-Paket exakt dasselbe
    Ergebnis liefern wie der getestete Referenz-Core.
    """

    root_loads = [
        root_models.ControllableLoad(
            name="Last A",
            priority=1,
            requested_kw=18.0,
            actual_kw=8.0,
            min_kw=3.0,
            max_kw=18.0,
        ),
        root_models.ControllableLoad(
            name="Last B",
            priority=2,
            requested_kw=12.0,
            actual_kw=4.0,
            min_kw=2.0,
            max_kw=12.0,
        ),
    ]

    ha_loads = [
        ha_models.ControllableLoad(
            name="Last A",
            priority=1,
            requested_kw=18.0,
            actual_kw=8.0,
            min_kw=3.0,
            max_kw=18.0,
        ),
        ha_models.ControllableLoad(
            name="Last B",
            priority=2,
            requested_kw=12.0,
            actual_kw=4.0,
            min_kw=2.0,
            max_kw=12.0,
        ),
    ]

    root_inputs = root_models.ControllerInputs(
        grid_kw=79.0,
        grid_limit_kw=90.0,
        grid_reserve_kw=2.0,
        pv_kw=5.0,
        battery_soc=65.0,
        battery_kw=0.0,
        mode=root_models.OperatingMode.NORMAL,
        now_s=100.0,
    )

    ha_inputs = ha_models.ControllerInputs(
        grid_kw=79.0,
        grid_limit_kw=90.0,
        grid_reserve_kw=2.0,
        pv_kw=5.0,
        battery_soc=65.0,
        battery_kw=0.0,
        mode=ha_models.OperatingMode.NORMAL,
        now_s=100.0,
    )

    root_result = root_controller.run_controller(
        inputs=root_inputs,
        loads=root_loads,
    )

    ha_result = ha_controller.run_controller(
        inputs=ha_inputs,
        loads=ha_loads,
    )

    assert (
        ha_result.targets_kw
        == pytest.approx(
            root_result.targets_kw
        )
    )

    assert (
        ha_result.base_load_kw
        == pytest.approx(
            root_result.base_load_kw
        )
    )

    assert (
        ha_result.available_budget_kw
        == pytest.approx(
            root_result.available_budget_kw
        )
    )

    assert (
        ha_result.projected_grid_kw
        == pytest.approx(
            root_result.projected_grid_kw
        )
    )

    assert (
        ha_result.effective_grid_limit_kw
        == pytest.approx(
            root_result.effective_grid_limit_kw
        )
    )


def test_surplus_mode_matches_reference_core():
    """
    Überschussbetrieb inklusive Batterieentladung
    muss im HA-Paket identisch arbeiten.
    """

    root_load = root_models.ControllableLoad(
        name="Überschusslast",
        priority=1,
        requested_kw=20.0,
        actual_kw=10.0,
        min_kw=5.0,
        max_kw=20.0,
    )

    ha_load = ha_models.ControllableLoad(
        name="Überschusslast",
        priority=1,
        requested_kw=20.0,
        actual_kw=10.0,
        min_kw=5.0,
        max_kw=20.0,
    )

    root_inputs = root_models.ControllerInputs(
        grid_kw=-4.0,
        grid_limit_kw=100.0,
        pv_kw=25.0,
        battery_soc=70.0,
        battery_kw=2.0,
        mode=root_models.OperatingMode.SURPLUS,
        now_s=200.0,
    )

    ha_inputs = ha_models.ControllerInputs(
        grid_kw=-4.0,
        grid_limit_kw=100.0,
        pv_kw=25.0,
        battery_soc=70.0,
        battery_kw=2.0,
        mode=ha_models.OperatingMode.SURPLUS,
        now_s=200.0,
    )

    root_result = root_controller.run_controller(
        inputs=root_inputs,
        loads=[root_load],
    )

    ha_result = ha_controller.run_controller(
        inputs=ha_inputs,
        loads=[ha_load],
    )

    assert (
        ha_result.targets_kw
        == pytest.approx(
            root_result.targets_kw
        )
    )

    assert (
        ha_result.raw_surplus_budget_kw
        == pytest.approx(
            root_result.raw_surplus_budget_kw
        )
    )

    assert (
        ha_result.surplus_budget_kw
        == pytest.approx(
            root_result.surplus_budget_kw
        )
    )

    assert (
        ha_result.battery_discharge_kw
        == pytest.approx(
            root_result.battery_discharge_kw
        )
    )

    assert (
        ha_result.projected_grid_kw
        == pytest.approx(
            root_result.projected_grid_kw
        )
    )


def test_dynamic_hysteresis_matches_reference_core():
    """
    Auch zustandsabhängige Funktionen wie Hysterese,
    Mindestlaufzeit und dynamische Leistungsgrenzen
    müssen identisch bleiben.
    """

    root_load = root_models.ControllableLoad(
        name="Dynamische Last",
        priority=1,
        requested_kw=20.0,
        min_kw=6.0,
        max_kw=22.0,
        start_margin_kw=0.4,
        stop_margin_kw=0.15,
        min_on_time_s=30.0,
        min_off_time_s=20.0,
        settling_time_s=5.0,
    )

    ha_load = ha_models.ControllableLoad(
        name="Dynamische Last",
        priority=1,
        requested_kw=20.0,
        min_kw=6.0,
        max_kw=22.0,
        start_margin_kw=0.4,
        stop_margin_kw=0.15,
        min_on_time_s=30.0,
        min_off_time_s=20.0,
        settling_time_s=5.0,
    )

    root_state = root_models.ControllerState(
        last_targets_kw={
            "Dynamische Last": 8.0,
        },
        load_states={
            "Dynamische Last":
                root_models.LoadRuntimeState(
                    is_on=True,
                    last_target_kw=8.0,
                    last_switch_s=80.0,
                    last_target_change_s=95.0,
                    settling_until_s=100.0,
                )
        },
    )

    ha_state = ha_models.ControllerState(
        last_targets_kw={
            "Dynamische Last": 8.0,
        },
        load_states={
            "Dynamische Last":
                ha_models.LoadRuntimeState(
                    is_on=True,
                    last_target_kw=8.0,
                    last_switch_s=80.0,
                    last_target_change_s=95.0,
                    settling_until_s=100.0,
                )
        },
    )

    root_inputs = root_models.ControllerInputs(
        grid_kw=88.0,
        grid_limit_kw=90.0,
        battery_soc=None,
        now_s=97.0,
    )

    ha_inputs = ha_models.ControllerInputs(
        grid_kw=88.0,
        grid_limit_kw=90.0,
        battery_soc=None,
        now_s=97.0,
    )

    root_result = root_controller.run_controller(
        inputs=root_inputs,
        loads=[root_load],
        state=root_state,
    )

    ha_result = ha_controller.run_controller(
        inputs=ha_inputs,
        loads=[ha_load],
        state=ha_state,
    )

    assert (
        ha_result.targets_kw
        == pytest.approx(
            root_result.targets_kw
        )
    )

    assert (
        ha_result.available_budget_kw
        == pytest.approx(
            root_result.available_budget_kw
        )
    )

    assert (
        ha_result.projected_grid_kw
        == pytest.approx(
            root_result.projected_grid_kw
        )
    )

    ha_runtime = (
        ha_result
        .state
        .load_states[
            "Dynamische Last"
        ]
    )

    root_runtime = (
        root_result
        .state
        .load_states[
            "Dynamische Last"
        ]
    )

    assert (
        ha_runtime.last_target_kw
        == pytest.approx(
            root_runtime.last_target_kw
        )
    )

    assert (
        ha_runtime.is_on
        == root_runtime.is_on
    )