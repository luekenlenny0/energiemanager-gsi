"""Pure configuration helpers for Power Manager loads."""

from __future__ import annotations

from math import isfinite
from typing import Any

from .const import (
    CONF_ACTUAL_SENSOR_TIMEOUT_S,
    CONF_ACTUAL_POWER_FACTOR,
    CONF_REQUEST_FACTOR,
    CONF_COMMAND_ON,
    CONF_COMMAND_OFF,
    CONF_DEFAULT_REQUEST_KW,
    CONF_ENABLE_ENTITY,
    CONF_EVSE_MAX_CURRENT_A,
    CONF_EVSE_MIN_CURRENT_A,
    CONF_EVSE_PAUSE_CURRENT_A,
    CONF_EVSE_PHASES,
    CONF_EVSE_VOLTAGE_V,
    CONF_LOAD_NAME,
    CONF_LOAD_TYPE,
    CONF_MAX_KW,
    CONF_MIN_KW,
    CONF_MIN_OFF_TIME_S,
    CONF_MIN_ON_TIME_S,
    CONF_OUTPUT_ENTITY,
    CONF_OUTPUT_UNIT,
    CONF_PRIORITY,
    CONF_SAFE_OUTPUT_VALUE,
    CONF_SETTLING_TIME_S,
    CONF_START_MARGIN_KW,
    CONF_STOP_MARGIN_KW,
    DEFAULT_ACTUAL_SENSOR_TIMEOUT_S,
    DEFAULT_DEFAULT_REQUEST_KW,
    DEFAULT_EVSE_MAX_CURRENT_A,
    DEFAULT_EVSE_MIN_CURRENT_A,
    DEFAULT_EVSE_PAUSE_CURRENT_A,
    DEFAULT_EVSE_PHASES,
    DEFAULT_EVSE_VOLTAGE_V,
    DEFAULT_LOAD_TYPE,
    DEFAULT_MAX_KW,
    DEFAULT_MIN_KW,
    DEFAULT_MIN_OFF_TIME_S,
    DEFAULT_MIN_ON_TIME_S,
    DEFAULT_OUTPUT_UNIT,
    DEFAULT_PRIORITY,
    DEFAULT_SAFE_OUTPUT_VALUE,
    DEFAULT_SETTLING_TIME_S,
    DEFAULT_START_MARGIN_KW,
    DEFAULT_STOP_MARGIN_KW,
    LOAD_TYPE_EVSE,
    LOAD_TYPE_SWITCH,
    LOAD_TYPES,
    OUTPUT_UNITS,
    SUPPORTED_NUMBER_DOMAINS,
    SUPPORTED_SWITCH_DOMAINS,
    SUPPORTED_COMMAND_DOMAINS,
    INPUT_FACTORS,
)


def _float_value(data: dict[str, Any], key: str, default: float) -> float:
    """Return a finite float or raise ValueError."""

    value = float(data.get(key, default))
    if not isfinite(value):
        raise ValueError(f"{key} must be finite")
    return value


def _entity_domain(entity_id: str | None) -> str | None:
    """Return the domain part of an entity id."""

    if not entity_id or "." not in entity_id:
        return None
    return entity_id.split(".", 1)[0]


def normalize_load_data(data: dict[str, Any]) -> dict[str, Any]:
    """Return normalized JSON-serializable load configuration."""

    normalized = dict(data)
    load_type = str(normalized.get(CONF_LOAD_TYPE, DEFAULT_LOAD_TYPE))

    normalized[CONF_LOAD_NAME] = str(normalized.get(CONF_LOAD_NAME, "")).strip()
    normalized[CONF_LOAD_TYPE] = load_type
    normalized[CONF_PRIORITY] = int(normalized.get(CONF_PRIORITY, DEFAULT_PRIORITY))
    normalized[CONF_MIN_KW] = _float_value(normalized, CONF_MIN_KW, DEFAULT_MIN_KW)
    normalized[CONF_MAX_KW] = _float_value(normalized, CONF_MAX_KW, DEFAULT_MAX_KW)
    normalized[CONF_DEFAULT_REQUEST_KW] = _float_value(
        normalized,
        CONF_DEFAULT_REQUEST_KW,
        DEFAULT_DEFAULT_REQUEST_KW,
    )
    normalized[CONF_ACTUAL_SENSOR_TIMEOUT_S] = _float_value(
        normalized,
        CONF_ACTUAL_SENSOR_TIMEOUT_S,
        DEFAULT_ACTUAL_SENSOR_TIMEOUT_S,
    )
    normalized[CONF_START_MARGIN_KW] = _float_value(
        normalized,
        CONF_START_MARGIN_KW,
        DEFAULT_START_MARGIN_KW,
    )
    normalized[CONF_STOP_MARGIN_KW] = _float_value(
        normalized,
        CONF_STOP_MARGIN_KW,
        DEFAULT_STOP_MARGIN_KW,
    )
    normalized[CONF_MIN_ON_TIME_S] = _float_value(
        normalized,
        CONF_MIN_ON_TIME_S,
        DEFAULT_MIN_ON_TIME_S,
    )
    normalized[CONF_MIN_OFF_TIME_S] = _float_value(
        normalized,
        CONF_MIN_OFF_TIME_S,
        DEFAULT_MIN_OFF_TIME_S,
    )
    normalized[CONF_SETTLING_TIME_S] = _float_value(
        normalized,
        CONF_SETTLING_TIME_S,
        DEFAULT_SETTLING_TIME_S,
    )
    normalized[CONF_SAFE_OUTPUT_VALUE] = _float_value(
        normalized,
        CONF_SAFE_OUTPUT_VALUE,
        DEFAULT_SAFE_OUTPUT_VALUE,
    )
    normalized[CONF_OUTPUT_UNIT] = str(
        normalized.get(CONF_OUTPUT_UNIT, DEFAULT_OUTPUT_UNIT)
    )
    for key in (CONF_ACTUAL_POWER_FACTOR, CONF_REQUEST_FACTOR):
        normalized[key] = _float_value(normalized, key, 1.0)
    normalized[CONF_COMMAND_ON] = str(normalized.get(CONF_COMMAND_ON, "1")).strip()
    normalized[CONF_COMMAND_OFF] = str(normalized.get(CONF_COMMAND_OFF, "0")).strip()

    normalized[CONF_EVSE_PHASES] = int(
        normalized.get(CONF_EVSE_PHASES, DEFAULT_EVSE_PHASES)
    )
    normalized[CONF_EVSE_VOLTAGE_V] = _float_value(
        normalized,
        CONF_EVSE_VOLTAGE_V,
        DEFAULT_EVSE_VOLTAGE_V,
    )
    normalized[CONF_EVSE_MIN_CURRENT_A] = _float_value(
        normalized,
        CONF_EVSE_MIN_CURRENT_A,
        DEFAULT_EVSE_MIN_CURRENT_A,
    )
    normalized[CONF_EVSE_MAX_CURRENT_A] = _float_value(
        normalized,
        CONF_EVSE_MAX_CURRENT_A,
        DEFAULT_EVSE_MAX_CURRENT_A,
    )
    normalized[CONF_EVSE_PAUSE_CURRENT_A] = _float_value(
        normalized,
        CONF_EVSE_PAUSE_CURRENT_A,
        DEFAULT_EVSE_PAUSE_CURRENT_A,
    )

    # A switchable load cannot physically modulate. Its technical minimum is
    # therefore identical to its rated / maximum power.
    if load_type == LOAD_TYPE_SWITCH:
        normalized[CONF_MIN_KW] = normalized[CONF_MAX_KW]

    return normalized


def validate_load_data(data: dict[str, Any]) -> dict[str, str]:
    """Validate load configuration and return Home Assistant style errors."""

    errors: dict[str, str] = {}

    try:
        values = normalize_load_data(data)
    except (TypeError, ValueError, OverflowError):
        return {"base": "invalid_number"}

    name = values[CONF_LOAD_NAME]
    load_type = values[CONF_LOAD_TYPE]
    priority = values[CONF_PRIORITY]
    min_kw = values[CONF_MIN_KW]
    max_kw = values[CONF_MAX_KW]
    default_request_kw = values[CONF_DEFAULT_REQUEST_KW]
    start_margin_kw = values[CONF_START_MARGIN_KW]
    stop_margin_kw = values[CONF_STOP_MARGIN_KW]

    if not name:
        errors[CONF_LOAD_NAME] = "load_name_required"

    if load_type not in LOAD_TYPES:
        errors[CONF_LOAD_TYPE] = "invalid_load_type"

    if priority < 1:
        errors[CONF_PRIORITY] = "priority_must_be_positive"

    if min_kw < 0.0 or max_kw <= 0.0 or min_kw > max_kw:
        errors["base"] = "invalid_power_range"

    if default_request_kw < 0.0 or default_request_kw > max_kw:
        errors[CONF_DEFAULT_REQUEST_KW] = "invalid_default_request"
    elif 0.0 < default_request_kw < min_kw:
        errors[CONF_DEFAULT_REQUEST_KW] = "request_below_minimum"

    if values[CONF_ACTUAL_SENSOR_TIMEOUT_S] <= 0.0:
        errors[CONF_ACTUAL_SENSOR_TIMEOUT_S] = "actual_timeout_must_be_positive"

    if start_margin_kw < 0.0 or stop_margin_kw < 0.0:
        errors["base"] = "invalid_hysteresis"
    elif stop_margin_kw > start_margin_kw:
        errors[CONF_STOP_MARGIN_KW] = "stop_margin_above_start_margin"

    for key in (CONF_MIN_ON_TIME_S, CONF_MIN_OFF_TIME_S, CONF_SETTLING_TIME_S):
        if values[key] < 0.0:
            errors[key] = "time_must_be_nonnegative"

    if values[CONF_OUTPUT_UNIT] not in OUTPUT_UNITS:
        errors[CONF_OUTPUT_UNIT] = "invalid_output_unit"

    for key in (CONF_ACTUAL_POWER_FACTOR, CONF_REQUEST_FACTOR):
        if values[key] not in INPUT_FACTORS:
            errors[key] = "invalid_input_factor"

    if values[CONF_SAFE_OUTPUT_VALUE] < 0.0:
        errors[CONF_SAFE_OUTPUT_VALUE] = "safe_output_must_be_nonnegative"

    output_domain = _entity_domain(values.get(CONF_OUTPUT_ENTITY))
    enable_domain = _entity_domain(values.get(CONF_ENABLE_ENTITY))

    if values.get(CONF_OUTPUT_ENTITY):
        if load_type == LOAD_TYPE_SWITCH:
            if output_domain not in SUPPORTED_COMMAND_DOMAINS:
                errors[CONF_OUTPUT_ENTITY] = "switch_output_required"
        elif output_domain not in SUPPORTED_NUMBER_DOMAINS:
            errors[CONF_OUTPUT_ENTITY] = "number_output_required"

    if values.get(CONF_ENABLE_ENTITY) and enable_domain not in SUPPORTED_COMMAND_DOMAINS:
        errors[CONF_ENABLE_ENTITY] = "enable_switch_required"

    if values.get(CONF_ENABLE_ENTITY) and values.get(CONF_ENABLE_ENTITY) == values.get(CONF_OUTPUT_ENTITY):
        errors[CONF_ENABLE_ENTITY] = "duplicate_output_entity"

    command_domains = [enable_domain]
    if load_type == LOAD_TYPE_SWITCH:
        command_domains.append(output_domain)
    if any(domain in SUPPORTED_COMMAND_DOMAINS and domain not in SUPPORTED_SWITCH_DOMAINS for domain in command_domains):
        on, off = values[CONF_COMMAND_ON], values[CONF_COMMAND_OFF]
        if not on or not off or on == off:
            errors[CONF_COMMAND_ON] = "invalid_commands"
        if any(domain in SUPPORTED_NUMBER_DOMAINS for domain in command_domains):
            try:
                on_number, off_number = float(on), float(off)
                if not isfinite(on_number) or not isfinite(off_number) or on_number == off_number:
                    raise ValueError
            except (TypeError, ValueError):
                errors[CONF_COMMAND_ON] = "invalid_commands"

    if values[CONF_OUTPUT_UNIT] == "A" or load_type == LOAD_TYPE_EVSE:
        if values[CONF_EVSE_PHASES] not in (1, 2, 3):
            errors[CONF_EVSE_PHASES] = "invalid_evse_phases"
        if values[CONF_EVSE_VOLTAGE_V] <= 0:
            errors[CONF_EVSE_VOLTAGE_V] = "must_be_positive"

    if load_type == LOAD_TYPE_EVSE:
        phases = values[CONF_EVSE_PHASES]
        voltage_v = values[CONF_EVSE_VOLTAGE_V]
        min_current_a = values[CONF_EVSE_MIN_CURRENT_A]
        max_current_a = values[CONF_EVSE_MAX_CURRENT_A]
        pause_current_a = values[CONF_EVSE_PAUSE_CURRENT_A]

        if phases not in (1, 2, 3):
            errors[CONF_EVSE_PHASES] = "invalid_evse_phases"
        if voltage_v <= 0.0:
            errors[CONF_EVSE_VOLTAGE_V] = "must_be_positive"
        if min_current_a <= 0.0 or max_current_a < min_current_a:
            errors["base"] = "invalid_current_range"
        if pause_current_a < 0.0 or pause_current_a >= min_current_a:
            errors[CONF_EVSE_PAUSE_CURRENT_A] = "invalid_pause_current"

        min_power_kw = phases * voltage_v * min_current_a / 1000.0
        max_power_kw = phases * voltage_v * max_current_a / 1000.0
        if min_kw + 0.000001 < min_power_kw:
            errors[CONF_MIN_KW] = "evse_min_power_below_current_minimum"
        if max_kw > max_power_kw + 0.000001:
            errors[CONF_MAX_KW] = "evse_max_power_above_current_maximum"

    return errors
