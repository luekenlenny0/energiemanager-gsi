import pytest

from custom_components.power_manager.const import (
    CONF_ACTUAL_SENSOR_TIMEOUT_S,
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
    CONF_OUTPUT_ENTITY,
    CONF_OUTPUT_UNIT,
    CONF_PRIORITY,
    CONF_SAFE_OUTPUT_VALUE,
)
from custom_components.power_manager.load_config import (
    normalize_load_data,
    validate_load_data,
)


def base_load(**updates):
    data = {
        CONF_LOAD_NAME: "Test",
        CONF_LOAD_TYPE: "modulating",
        CONF_PRIORITY: 1,
        CONF_MIN_KW: 1.0,
        CONF_MAX_KW: 10.0,
        CONF_DEFAULT_REQUEST_KW: 10.0,
        CONF_OUTPUT_ENTITY: "number.test",
        CONF_OUTPUT_UNIT: "kW",
        CONF_SAFE_OUTPUT_VALUE: 0.0,
    }
    data.update(updates)
    return data


def test_valid_modulating_load_has_no_errors():
    assert validate_load_data(base_load()) == {}


def test_switch_normalization_sets_min_equal_to_rated_power():
    data = normalize_load_data(
        base_load(
            **{
                CONF_LOAD_TYPE: "switch",
                CONF_MIN_KW: 0.0,
                CONF_MAX_KW: 10.0,
                CONF_OUTPUT_ENTITY: "switch.test",
            }
        )
    )
    assert data[CONF_MIN_KW] == pytest.approx(10.0)


def test_empty_name_is_rejected():
    errors = validate_load_data(base_load(**{CONF_LOAD_NAME: "  "}))
    assert errors[CONF_LOAD_NAME] == "load_name_required"


def test_priority_zero_is_rejected():
    errors = validate_load_data(base_load(**{CONF_PRIORITY: 0}))
    assert errors[CONF_PRIORITY] == "priority_must_be_positive"


def test_invalid_power_range_is_rejected():
    errors = validate_load_data(base_load(**{CONF_MIN_KW: 11.0, CONF_MAX_KW: 10.0}))
    assert errors["base"] == "invalid_power_range"


def test_default_request_below_nonzero_minimum_is_rejected():
    errors = validate_load_data(base_load(**{CONF_DEFAULT_REQUEST_KW: 0.5}))
    assert errors[CONF_DEFAULT_REQUEST_KW] == "request_below_minimum"


def test_negative_safe_output_is_rejected():
    errors = validate_load_data(base_load(**{CONF_SAFE_OUTPUT_VALUE: -0.1}))
    assert errors[CONF_SAFE_OUTPUT_VALUE] == "safe_output_must_be_nonnegative"


def test_switch_requires_switch_output_domain():
    errors = validate_load_data(
        base_load(**{CONF_LOAD_TYPE: "switch", CONF_OUTPUT_ENTITY: "number.test"})
    )
    assert errors[CONF_OUTPUT_ENTITY] == "switch_output_required"


def test_modulating_requires_number_output_domain():
    errors = validate_load_data(base_load(**{CONF_OUTPUT_ENTITY: "switch.test"}))
    assert errors[CONF_OUTPUT_ENTITY] == "number_output_required"


def test_enable_entity_requires_switch_domain():
    errors = validate_load_data(base_load(**{CONF_ENABLE_ENTITY: "number.enable"}))
    assert errors[CONF_ENABLE_ENTITY] == "enable_switch_required"


def valid_evse(**updates):
    data = base_load(
        **{
            CONF_LOAD_TYPE: "evse",
            CONF_MIN_KW: 4.14,
            CONF_MAX_KW: 11.04,
            CONF_DEFAULT_REQUEST_KW: 11.04,
            CONF_OUTPUT_ENTITY: "number.evse_current",
            CONF_EVSE_PHASES: 3,
            CONF_EVSE_VOLTAGE_V: 230.0,
            CONF_EVSE_MIN_CURRENT_A: 6.0,
            CONF_EVSE_MAX_CURRENT_A: 16.0,
            CONF_EVSE_PAUSE_CURRENT_A: 0.01,
        }
    )
    data.update(updates)
    return data


def test_valid_evse_configuration_has_no_errors():
    assert validate_load_data(valid_evse()) == {}


def test_evse_min_kw_must_cover_configured_minimum_current():
    errors = validate_load_data(valid_evse(**{CONF_MIN_KW: 4.0}))
    assert errors[CONF_MIN_KW] == "evse_min_power_below_current_minimum"


def test_evse_max_kw_must_not_exceed_current_capability():
    errors = validate_load_data(valid_evse(**{CONF_MAX_KW: 12.0}))
    assert errors[CONF_MAX_KW] == "evse_max_power_above_current_maximum"


def test_evse_configuration_is_not_hardcoded_to_16a():
    data = valid_evse(
        **{
            CONF_MIN_KW: 4.14,
            CONF_MAX_KW: 22.08,
            CONF_DEFAULT_REQUEST_KW: 22.08,
            CONF_EVSE_MAX_CURRENT_A: 32.0,
        }
    )
    assert validate_load_data(data) == {}


def test_evse_pause_current_must_be_below_min_current():
    errors = validate_load_data(valid_evse(**{CONF_EVSE_PAUSE_CURRENT_A: 6.0}))
    assert errors[CONF_EVSE_PAUSE_CURRENT_A] == "invalid_pause_current"


def test_actual_sensor_timeout_must_be_positive():
    errors = validate_load_data(base_load(**{CONF_ACTUAL_SENSOR_TIMEOUT_S: 0.0}))
    assert errors[CONF_ACTUAL_SENSOR_TIMEOUT_S] == "actual_timeout_must_be_positive"
