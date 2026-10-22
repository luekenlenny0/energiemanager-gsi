"""Pure conversion helpers from Home Assistant-like source values to load power."""

from __future__ import annotations

from typing import Any

from .const import LOAD_TYPE_SWITCH
from .measurements import MeasurementError, power_to_kw

TRUE_STATES = frozenset({"1", "true", "on", "yes", "active", "enabled"})
FALSE_STATES = frozenset({"0", "false", "off", "no", "inactive", "disabled"})


def boolean_value(value: Any) -> bool | None:
    """Interpret common boolean states without guessing arbitrary text."""

    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()
    if text in TRUE_STATES:
        return True
    if text in FALSE_STATES:
        return False
    return None


def default_requested_kw(default_request_kw: float, max_kw: float) -> float:
    """Return the configured default request; zero means use max_kw."""

    if default_request_kw <= 0.0:
        return max(0.0, max_kw)
    return max(0.0, min(default_request_kw, max_kw))


def requested_kw_from_source(
    value: Any | None,
    unit: str | None,
    *,
    load_type: str,
    max_kw: float,
    default_request_kw_value: float,
    factor: float = 1.0,
) -> float:
    """Convert an optional request source to a power request in kW."""

    if value is None:
        return default_requested_kw(default_request_kw_value, max_kw)

    boolean = boolean_value(value)
    if boolean is not None and unit is None:
        return max_kw if boolean else 0.0

    if unit is None:
        raise MeasurementError(
            "Anforderungswert ist weder ein boolescher Zustand noch eine Leistung mit Einheit."
        )

    requested_kw = power_to_kw(value, unit, factor=factor, label="Anforderungsleistung")
    requested_kw = max(0.0, min(requested_kw, max_kw))

    # A switching load is all-or-nothing. A positive request therefore means
    # its configured rated power, never the numeric request itself.
    if load_type == LOAD_TYPE_SWITCH:
        return max_kw if requested_kw > 0.0 else 0.0

    return requested_kw


def actual_kw_from_source(
    value: Any | None,
    unit: str | None,
    *,
    invert: bool = False,
    factor: float = 1.0,
) -> float | None:
    """Convert an optional actual-power source to kW."""

    if value is None:
        return None

    actual_kw = power_to_kw(
        value,
        unit,
        invert=invert,
        factor=factor,
        label="Istleistung",
    )
    if actual_kw < 0.0:
        raise MeasurementError("Istleistung eines Verbrauchers darf nicht negativ sein.")
    return actual_kw


def availability_from_source(value: Any | None) -> bool:
    """Convert an optional availability state; missing means available."""

    if value is None:
        return True

    boolean = boolean_value(value)
    if boolean is None:
        raise MeasurementError("Verfügbarkeitswert ist kein eindeutiger Ein/Aus-Zustand.")
    return boolean
