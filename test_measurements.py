from datetime import (
    datetime,
    timedelta,
    timezone,
)
import math

import pytest

from custom_components.power_manager.measurements import (
    MeasurementError,
    measurement_age_seconds,
    measurement_is_fresh,
    percentage_value,
    power_to_kw,
)


def test_power_watt_is_converted_to_kw():
    result = power_to_kw(
        12500.0,
        "W",
    )

    assert result == pytest.approx(
        12.5
    )


def test_power_kw_remains_kw():
    result = power_to_kw(
        12.5,
        "kW",
    )

    assert result == pytest.approx(
        12.5
    )


def test_power_mw_is_converted_to_kw():
    result = power_to_kw(
        0.0125,
        "MW",
    )

    assert result == pytest.approx(
        12.5
    )


def test_negative_power_sign_is_preserved():
    result = power_to_kw(
        -7.5,
        "kW",
    )

    assert result == pytest.approx(
        -7.5
    )


def test_power_sign_can_be_inverted():
    result = power_to_kw(
        -7.5,
        "kW",
        invert=True,
    )

    assert result == pytest.approx(
        7.5
    )


def test_unknown_power_unit_is_rejected():
    with pytest.raises(
        MeasurementError
    ):
        power_to_kw(
            10.0,
            "VA",
        )


def test_non_finite_measurement_is_rejected():
    with pytest.raises(
        MeasurementError
    ):
        power_to_kw(
            math.nan,
            "kW",
        )


def test_percentage_sensor_is_accepted():
    result = percentage_value(
        67.5,
        "%",
    )

    assert result == pytest.approx(
        67.5
    )


def test_percentage_outside_range_is_rejected():
    with pytest.raises(
        MeasurementError
    ):
        percentage_value(
            120.0,
            "%",
        )


def test_measurement_age_is_calculated():
    now = datetime(
        2026,
        10,
        14,
        12,
        0,
        10,
        tzinfo=timezone.utc,
    )

    last_reported = (
        now
        - timedelta(
            seconds=4.5
        )
    )

    result = measurement_age_seconds(
        last_reported,
        now,
    )

    assert result == pytest.approx(
        4.5
    )


def test_future_measurement_timestamp_is_clamped_to_zero():
    now = datetime(
        2026,
        10,
        14,
        12,
        0,
        0,
        tzinfo=timezone.utc,
    )

    last_reported = (
        now
        + timedelta(
            seconds=2.0
        )
    )

    result = measurement_age_seconds(
        last_reported,
        now,
    )

    assert result == pytest.approx(
        0.0
    )


def test_measurement_is_fresh_below_timeout():
    assert (
        measurement_is_fresh(
            age_s=4.0,
            timeout_s=5.0,
        )
        is True
    )


def test_measurement_is_fresh_exactly_at_timeout():
    assert (
        measurement_is_fresh(
            age_s=5.0,
            timeout_s=5.0,
        )
        is True
    )


def test_measurement_is_stale_above_timeout():
    assert (
        measurement_is_fresh(
            age_s=5.01,
            timeout_s=5.0,
        )
        is False
    )


def test_zero_timeout_is_rejected():
    with pytest.raises(
        MeasurementError
    ):
        measurement_is_fresh(
            age_s=1.0,
            timeout_s=0.0,
        )

def test_fraction_soc_is_converted_to_percent():
    from custom_components.power_manager.measurements import percentage_from_scale

    result = percentage_from_scale(
        0.675,
        None,
        scale="fraction",
    )

    assert result == pytest.approx(67.5)


def test_fraction_soc_accepts_dimensionless_unit_one():
    from custom_components.power_manager.measurements import percentage_from_scale

    result = percentage_from_scale(
        0.42,
        "1",
        scale="fraction",
    )

    assert result == pytest.approx(42.0)


def test_fraction_soc_rejects_percent_unit():
    from custom_components.power_manager.measurements import percentage_from_scale

    with pytest.raises(MeasurementError):
        percentage_from_scale(
            0.5,
            "%",
            scale="fraction",
        )


def test_fraction_soc_rejects_value_above_one():
    from custom_components.power_manager.measurements import percentage_from_scale

    with pytest.raises(MeasurementError):
        percentage_from_scale(
            1.01,
            None,
            scale="fraction",
        )


def test_percent_scale_still_requires_percent_unit():
    from custom_components.power_manager.measurements import percentage_from_scale

    with pytest.raises(MeasurementError):
        percentage_from_scale(
            50.0,
            None,
            scale="percent",
        )
