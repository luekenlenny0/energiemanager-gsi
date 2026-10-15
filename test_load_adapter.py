import pytest

from custom_components.power_manager.load_adapter import (
    actual_kw_from_source,
    availability_from_source,
    boolean_value,
    default_requested_kw,
    requested_kw_from_source,
)
from custom_components.power_manager.measurements import MeasurementError


def test_boolean_value_accepts_common_true_states():
    for value in (True, "on", "TRUE", "enabled", "1"):
        assert boolean_value(value) is True


def test_boolean_value_accepts_common_false_states():
    for value in (False, "off", "FALSE", "disabled", "0"):
        assert boolean_value(value) is False


def test_boolean_value_does_not_guess_unknown_text():
    assert boolean_value("charging") is None


def test_zero_default_request_means_maximum_request():
    assert default_requested_kw(0.0, 22.0) == pytest.approx(22.0)


def test_default_request_is_clamped_to_maximum():
    assert default_requested_kw(30.0, 22.0) == pytest.approx(22.0)


def test_boolean_request_on_requests_maximum():
    assert requested_kw_from_source(
        "on",
        None,
        load_type="modulating",
        max_kw=12.0,
        default_request_kw_value=0.0,
    ) == pytest.approx(12.0)


def test_boolean_request_off_requests_zero():
    assert requested_kw_from_source(
        "off",
        None,
        load_type="modulating",
        max_kw=12.0,
        default_request_kw_value=0.0,
    ) == pytest.approx(0.0)


def test_numeric_request_converts_watts_to_kw():
    assert requested_kw_from_source(
        "7500",
        "W",
        load_type="modulating",
        max_kw=12.0,
        default_request_kw_value=0.0,
    ) == pytest.approx(7.5)


def test_numeric_request_is_clamped_to_maximum():
    assert requested_kw_from_source(
        50,
        "kW",
        load_type="modulating",
        max_kw=12.0,
        default_request_kw_value=0.0,
    ) == pytest.approx(12.0)


def test_switch_positive_numeric_request_means_full_rated_power():
    assert requested_kw_from_source(
        1.0,
        "kW",
        load_type="switch",
        max_kw=10.0,
        default_request_kw_value=0.0,
    ) == pytest.approx(10.0)


def test_request_without_unit_or_boolean_is_rejected():
    with pytest.raises(MeasurementError):
        requested_kw_from_source(
            "charging",
            None,
            load_type="modulating",
            max_kw=10.0,
            default_request_kw_value=0.0,
        )


def test_actual_power_can_be_inverted_and_converted():
    assert actual_kw_from_source(-5000, "W", invert=True) == pytest.approx(5.0)


def test_negative_actual_power_after_sign_handling_is_rejected():
    with pytest.raises(MeasurementError):
        actual_kw_from_source(-1.0, "kW")


def test_missing_actual_power_stays_unknown():
    assert actual_kw_from_source(None, None) is None


def test_missing_availability_defaults_to_available():
    assert availability_from_source(None) is True


def test_invalid_availability_is_rejected():
    with pytest.raises(MeasurementError):
        availability_from_source("maybe")
