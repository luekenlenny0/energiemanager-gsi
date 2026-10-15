import pytest

from custom_components.power_manager.outputs import (
    OutputConversionError,
    build_output_plan,
    evse_target_to_current_a,
    kw_to_power_value,
)


def test_kw_to_watts():
    assert kw_to_power_value(7.5, "W") == pytest.approx(7500.0)


def test_kw_to_kw():
    assert kw_to_power_value(7.5, "kW") == pytest.approx(7.5)


def test_kw_to_mw():
    assert kw_to_power_value(750.0, "MW") == pytest.approx(0.75)


def test_unsupported_output_unit_is_rejected():
    with pytest.raises(OutputConversionError):
        kw_to_power_value(1.0, "A")


def test_modulating_zero_target_uses_safe_output_value():
    plan = build_output_plan(
        load_type="modulating",
        target_kw=0.0,
        power_unit="kW",
        safe_output_value=0.2,
    )
    assert plan.enabled is False
    assert plan.numeric_value == pytest.approx(0.2)
    assert plan.numeric_unit == "kW"


def test_modulating_positive_target_is_converted():
    plan = build_output_plan(
        load_type="modulating",
        target_kw=5.5,
        power_unit="W",
    )
    assert plan.enabled is True
    assert plan.numeric_value == pytest.approx(5500.0)
    assert plan.numeric_unit == "W"


def test_switch_target_is_boolean():
    assert build_output_plan(load_type="switch", target_kw=0.0).enabled is False
    assert build_output_plan(load_type="switch", target_kw=10.0).enabled is True


def test_evse_three_phase_conversion():
    current = evse_target_to_current_a(
        6.9,
        phases=3,
        voltage_v=230.0,
        min_current_a=6.0,
        max_current_a=16.0,
        pause_current_a=0.01,
    )
    assert current == pytest.approx(10.0)


def test_evse_zero_target_uses_pause_current_not_zero():
    current = evse_target_to_current_a(
        0.0,
        phases=3,
        voltage_v=230.0,
        min_current_a=6.0,
        max_current_a=16.0,
        pause_current_a=0.01,
    )
    assert current == pytest.approx(0.01)


def test_evse_target_below_minimum_is_paused_not_rounded_up():
    current = evse_target_to_current_a(
        3.0,
        phases=3,
        voltage_v=230.0,
        min_current_a=6.0,
        max_current_a=16.0,
        pause_current_a=0.01,
    )
    assert current == pytest.approx(0.01)


def test_evse_plan_below_minimum_is_marked_disabled():
    plan = build_output_plan(
        load_type="evse",
        target_kw=3.0,
        evse_phases=3,
        evse_voltage_v=230.0,
        evse_min_current_a=6.0,
        evse_max_current_a=16.0,
        evse_pause_current_a=0.01,
    )
    assert plan.enabled is False
    assert plan.numeric_value == pytest.approx(0.01)


def test_evse_target_above_configured_current_cap_is_rejected_not_clamped():
    with pytest.raises(OutputConversionError):
        evse_target_to_current_a(
            12.0,
            phases=3,
            voltage_v=230.0,
            min_current_a=6.0,
            max_current_a=16.0,
            pause_current_a=0.01,
        )


def test_evse_arbitrary_32a_configuration_is_supported():
    current = evse_target_to_current_a(
        20.7,
        phases=3,
        voltage_v=230.0,
        min_current_a=6.0,
        max_current_a=32.0,
        pause_current_a=0.5,
    )
    assert current == pytest.approx(30.0)


def test_invalid_evse_pause_current_is_rejected():
    with pytest.raises(OutputConversionError):
        evse_target_to_current_a(
            0.0,
            phases=3,
            voltage_v=230.0,
            min_current_a=6.0,
            max_current_a=16.0,
            pause_current_a=6.0,
        )


def test_negative_target_is_rejected():
    with pytest.raises(OutputConversionError):
        build_output_plan(load_type="modulating", target_kw=-1.0)
