"""Measurement conversion helpers for Power Manager."""

from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any

from .const import (
    BATTERY_SOC_SCALE_FRACTION,
    BATTERY_SOC_SCALE_PERCENT,
    INPUT_FACTORS,
)


class MeasurementError(ValueError):
    """Raised when a measurement cannot be used safely."""


POWER_UNIT_TO_KW: dict[str, float] = {
    "mW": 0.000001,
    "W": 0.001,
    "kW": 1.0,
    "MW": 1000.0,
    "GW": 1000000.0,
}


def _finite_float(
    value: Any,
    *,
    label: str,
) -> float:
    """Convert a value to a finite float."""

    try:
        number = float(value)
    except (TypeError, ValueError) as err:
        raise MeasurementError(
            f"{label}: Wert '{value}' ist keine Zahl."
        ) from err

    if not isfinite(number):
        raise MeasurementError(
            f"{label}: Wert muss endlich sein."
        )

    return number


def power_to_kw(
    value: Any,
    unit: str | None,
    *,
    invert: bool = False,
    factor: float = 1.0,
    label: str = "Leistung",
) -> float:
    """Convert a power value to kW without guessing its unit."""

    number = _finite_float(
        value,
        label=label,
    )

    if unit is None:
        raise MeasurementError(
            f"{label}: Keine Leistungseinheit vorhanden."
        )

    normalized_unit = unit.strip()

    if normalized_unit not in POWER_UNIT_TO_KW:
        raise MeasurementError(
            f"{label}: Nicht unterstützte Leistungseinheit '{unit}'."
        )

    result_kw = scaled_value(number, factor, label=label) * POWER_UNIT_TO_KW[normalized_unit]
    if not isfinite(result_kw):
        raise MeasurementError(f"{label}: Umgerechneter Wert muss endlich sein.")

    if invert:
        result_kw = -result_kw

    return result_kw


def scaled_value(value: Any, factor: Any = 1.0, *, label: str = "Messwert") -> float:
    """Apply an explicit input factor before the normal unit conversion."""

    number = _finite_float(value, label=label)
    multiplier = _finite_float(factor, label=f"{label} Faktor")
    if multiplier not in INPUT_FACTORS:
        raise MeasurementError(f"{label}: Nicht unterstützter Skalierungsfaktor.")
    result = number * multiplier
    if not isfinite(result):
        raise MeasurementError(f"{label}: Skalierter Wert muss endlich sein.")
    return result


def percentage_value(
    value: Any,
    unit: str | None,
    *,
    label: str = "Prozentwert",
) -> float:
    """Convert a percent sensor that explicitly uses %."""

    number = _finite_float(
        value,
        label=label,
    )

    if unit != "%":
        raise MeasurementError(
            f"{label}: Erwartete Einheit '%', erhalten: '{unit}'."
        )

    if not 0.0 <= number <= 100.0:
        raise MeasurementError(
            f"{label}: Wert muss zwischen 0 und 100 % liegen."
        )

    return number


def percentage_from_scale(
    value: Any,
    unit: str | None,
    *,
    scale: str,
    label: str = "Prozentwert",
) -> float:
    """Convert percent or fractional 0..1 state to 0..100 percent."""

    if scale == BATTERY_SOC_SCALE_PERCENT:
        return percentage_value(value, unit, label=label)

    if scale == BATTERY_SOC_SCALE_FRACTION:
        number = _finite_float(value, label=label)
        if unit not in (None, "", "1"):
            raise MeasurementError(
                f"{label}: Für 0..1-Skalierung wird keine Prozent-Einheit erwartet."
            )
        if not 0.0 <= number <= 1.0:
            raise MeasurementError(
                f"{label}: Wert muss bei 0..1-Skalierung zwischen 0 und 1 liegen."
            )
        return number * 100.0

    raise MeasurementError(f"{label}: Unbekannte Skalierung '{scale}'.")


def measurement_age_seconds(
    last_reported: datetime,
    now: datetime,
) -> float:
    """Calculate the age of a measurement; future timestamps clamp to zero."""

    if last_reported.tzinfo is None or now.tzinfo is None:
        raise MeasurementError(
            "Zeitstempel müssen eine Zeitzone besitzen."
        )

    age_s = (now - last_reported).total_seconds()
    return max(0.0, age_s)


def measurement_is_fresh(
    age_s: float,
    timeout_s: float,
) -> bool:
    """Check whether a measurement is still fresh."""

    age_s = _finite_float(
        age_s,
        label="Messwertalter",
    )

    timeout_s = _finite_float(
        timeout_s,
        label="Messwert-Timeout",
    )

    if age_s < 0.0:
        raise MeasurementError(
            "Messwertalter darf nicht negativ sein."
        )

    if timeout_s <= 0.0:
        raise MeasurementError(
            "Messwert-Timeout muss größer als 0 sein."
        )

    return age_s <= timeout_s
