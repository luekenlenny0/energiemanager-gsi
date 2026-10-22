"""Config and load-subentry flows for Power Manager."""

from __future__ import annotations

from math import isfinite
from typing import Any

# HA 2026.8 provides voluptuous; HA 2026.9+ redirects this supported import
# to its Probatio compatibility module during Home Assistant startup.
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import Platform
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_HOUSE_POWER_ENTITY,
    CONF_HOUSE_POWER_FACTOR,
    CONF_GRID_POWER_FACTOR,
    CONF_PV_POWER_FACTOR,
    CONF_BATTERY_POWER_FACTOR,
    CONF_BATTERY_SOC_FACTOR,
    CONF_ACTUAL_POWER_FACTOR,
    CONF_REQUEST_FACTOR,
    CONF_COMMAND_ON,
    CONF_COMMAND_OFF,
    CONF_SURPLUS_STRATEGY,
    INPUT_FACTORS,
    SURPLUS_STRATEGIES,
    BATTERY_SOC_SCALES,
    CONF_ACTUAL_POWER_ENTITY,
    CONF_ACTUAL_SENSOR_TIMEOUT_S,
    CONF_AVAILABILITY_ENTITY,
    CONF_BATTERY_POWER_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_BATTERY_SOC_SCALE,
    CONF_DEFAULT_REQUEST_KW,
    CONF_ENABLE_ENTITY,
    CONF_EVSE_MAX_CURRENT_A,
    CONF_EVSE_MIN_CURRENT_A,
    CONF_EVSE_PAUSE_CURRENT_A,
    CONF_EVSE_PHASES,
    CONF_EVSE_VOLTAGE_V,
    CONF_GRID_LIMIT_KW,
    CONF_GRID_POWER_ENTITY,
    CONF_GRID_RESERVE_KW,
    CONF_GRID_SENSOR_TIMEOUT_S,
    CONF_INVERT_ACTUAL_POWER,
    CONF_INVERT_BATTERY_POWER,
    CONF_INVERT_GRID_POWER,
    CONF_INVERT_PV_POWER,
    CONF_LOAD_NAME,
    CONF_LOAD_TYPE,
    CONF_MAX_KW,
    CONF_MIN_KW,
    CONF_MIN_OFF_TIME_S,
    CONF_MIN_ON_TIME_S,
    CONF_OUTPUT_ENTITY,
    CONF_OUTPUT_UNIT,
    CONF_PEAK_SHAVING_ENABLED,
    CONF_PRIORITY,
    CONF_PV_POWER_ENTITY,
    CONF_REQUEST_ENTITY,
    CONF_SAFE_OUTPUT_VALUE,
    CONF_SETTLING_TIME_S,
    CONF_START_MARGIN_KW,
    CONF_STOP_MARGIN_KW,
    CONF_SURPLUS_ENABLED,
    CONF_SURPLUS_MIN_BATTERY_SOC,
    DEFAULT_ACTUAL_SENSOR_TIMEOUT_S,
    DEFAULT_BATTERY_SOC_SCALE,
    DEFAULT_DEFAULT_REQUEST_KW,
    DEFAULT_EVSE_MAX_CURRENT_A,
    DEFAULT_EVSE_MIN_CURRENT_A,
    DEFAULT_EVSE_PAUSE_CURRENT_A,
    DEFAULT_EVSE_PHASES,
    DEFAULT_EVSE_VOLTAGE_V,
    DEFAULT_GRID_RESERVE_KW,
    DEFAULT_GRID_SENSOR_TIMEOUT_S,
    DEFAULT_INVERT_ACTUAL_POWER,
    DEFAULT_INVERT_BATTERY_POWER,
    DEFAULT_INVERT_GRID_POWER,
    DEFAULT_INVERT_PV_POWER,
    DEFAULT_LOAD_TYPE,
    DEFAULT_MAX_KW,
    DEFAULT_MIN_KW,
    DEFAULT_MIN_OFF_TIME_S,
    DEFAULT_MIN_ON_TIME_S,
    DEFAULT_OUTPUT_UNIT,
    DEFAULT_PEAK_SHAVING_ENABLED,
    DEFAULT_PRIORITY,
    DEFAULT_SAFE_OUTPUT_VALUE,
    DEFAULT_SETTLING_TIME_S,
    DEFAULT_START_MARGIN_KW,
    DEFAULT_STOP_MARGIN_KW,
    DEFAULT_SURPLUS_ENABLED,
    DOMAIN,
    LOAD_TYPES,
    NAME,
    OUTPUT_UNITS,
    SUBENTRY_TYPE_LOAD,
)
from .load_config import normalize_load_data, validate_load_data
from .point_config import SUBENTRY_TYPE_POINT
from .point_flow import PowerManagerPointSubentryFlow


def _optional_marker(key: str, values: dict[str, Any]) -> vol.Optional:
    """Create optional marker with suggested existing value."""

    current_value = values.get(key)
    if current_value is not None and current_value != "":
        return vol.Optional(
            key,
            description={"suggested_value": current_value},
        )
    return vol.Optional(key)


def _required_marker(
    key: str,
    values: dict[str, Any],
    default: Any,
) -> vol.Required:
    """Create required marker using current value or a default."""

    return vol.Required(
        key,
        default=values.get(key, default),
    )


def _required_entity_marker(
    key: str,
    values: dict[str, Any],
) -> vol.Required:
    """Create a required entity marker without an invalid empty default."""

    current_value = values.get(key)
    if current_value:
        return vol.Required(key, default=current_value)
    return vol.Required(key)


def _power_number_selector(*, minimum: float = 0.0) -> NumberSelector:
    """Build a kW number selector."""

    return NumberSelector(
        NumberSelectorConfig(
            min=minimum,
            step=0.1,
            unit_of_measurement="kW",
            mode=NumberSelectorMode.BOX,
        )
    )


def _seconds_selector() -> NumberSelector:
    """Build a seconds selector."""

    return NumberSelector(
        NumberSelectorConfig(
            min=0.0,
            step=1.0,
            unit_of_measurement="s",
            mode=NumberSelectorMode.BOX,
        )
    )


def _factor_selector() -> SelectSelector:
    return SelectSelector(SelectSelectorConfig(options=[
        SelectOptionDict(value=f"{factor:g}", label=f"{factor:g}".replace(".", ","))
        for factor in INPUT_FACTORS
    ]))


def _factor_marker(key: str, values: dict[str, Any]) -> vol.Required:
    try:
        factor = float(values.get(key, 1))
    except (TypeError, ValueError):
        factor = 1.0
    if factor not in INPUT_FACTORS:
        factor = 1.0
    return vol.Required(key, default=f"{factor:g}")


def _entity_selector(*, domain: str | list[str] | None = None) -> EntitySelector:
    """Build a single-entity selector without serializing a null domain filter."""

    config = EntitySelectorConfig(multiple=False)
    if domain is not None:
        config["domain"] = domain

    return EntitySelector(config)


def _build_global_schema(values: dict[str, Any] | None = None) -> vol.Schema:
    """Build global configuration schema."""

    values = values or {}

    return vol.Schema(
        {
            _optional_marker(CONF_GRID_POWER_ENTITY, values): _entity_selector(
                domain=Platform.SENSOR
            ),
            _required_marker("configure_points_first", values, False): BooleanSelector(),
            _factor_marker(CONF_GRID_POWER_FACTOR, values): _factor_selector(),
            _optional_marker(CONF_HOUSE_POWER_ENTITY, values): _entity_selector(domain=Platform.SENSOR),
            _factor_marker(CONF_HOUSE_POWER_FACTOR, values): _factor_selector(),
            _required_marker(CONF_SURPLUS_STRATEGY, values, "pv_budget" if values.get(CONF_GRID_POWER_ENTITY) else "net_export"): SelectSelector(
                SelectSelectorConfig(options=list(SURPLUS_STRATEGIES), translation_key=CONF_SURPLUS_STRATEGY)
            ),
            _required_marker(CONF_GRID_LIMIT_KW, values, 1.0): _power_number_selector(
                minimum=0.1
            ),
            _required_marker(
                CONF_GRID_RESERVE_KW,
                values,
                DEFAULT_GRID_RESERVE_KW,
            ): _power_number_selector(),
            _required_marker(
                CONF_GRID_SENSOR_TIMEOUT_S,
                values,
                DEFAULT_GRID_SENSOR_TIMEOUT_S,
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0.1,
                    step=0.1,
                    unit_of_measurement="s",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            _required_marker(
                CONF_INVERT_GRID_POWER,
                values,
                DEFAULT_INVERT_GRID_POWER,
            ): BooleanSelector(),
            _optional_marker(CONF_PV_POWER_ENTITY, values): _entity_selector(
                domain=Platform.SENSOR
            ),
            _factor_marker(CONF_PV_POWER_FACTOR, values): _factor_selector(),
            _required_marker(
                CONF_INVERT_PV_POWER,
                values,
                DEFAULT_INVERT_PV_POWER,
            ): BooleanSelector(),
            _optional_marker(CONF_BATTERY_POWER_ENTITY, values): _entity_selector(
                domain=Platform.SENSOR
            ),
            _factor_marker(CONF_BATTERY_POWER_FACTOR, values): _factor_selector(),
            _required_marker(
                CONF_INVERT_BATTERY_POWER,
                values,
                DEFAULT_INVERT_BATTERY_POWER,
            ): BooleanSelector(),
            _optional_marker(CONF_BATTERY_SOC_ENTITY, values): _entity_selector(
                domain=Platform.SENSOR
            ),
            _factor_marker(CONF_BATTERY_SOC_FACTOR, values): _factor_selector(),
            _required_marker(
                CONF_BATTERY_SOC_SCALE,
                values,
                DEFAULT_BATTERY_SOC_SCALE,
            ): SelectSelector(
                SelectSelectorConfig(options=list(BATTERY_SOC_SCALES), translation_key=CONF_BATTERY_SOC_SCALE)
            ),
            _optional_marker(CONF_SURPLUS_MIN_BATTERY_SOC, values): NumberSelector(
                NumberSelectorConfig(
                    min=0.0,
                    max=100.0,
                    step=1.0,
                    unit_of_measurement="%",
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _normalize_global_configuration(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return a complete global mapping so options can also clear old values."""

    normalized = dict(user_input)
    normalized.setdefault(CONF_GRID_POWER_ENTITY, None)
    for key in (CONF_GRID_POWER_FACTOR, CONF_PV_POWER_FACTOR, CONF_BATTERY_POWER_FACTOR, CONF_BATTERY_SOC_FACTOR, CONF_HOUSE_POWER_FACTOR):
        normalized[key] = float(normalized.get(key, 1))
    for key in (
        CONF_PV_POWER_ENTITY,
        CONF_HOUSE_POWER_ENTITY,
        CONF_BATTERY_POWER_ENTITY,
        CONF_BATTERY_SOC_ENTITY,
        CONF_SURPLUS_MIN_BATTERY_SOC,
    ):
        normalized.setdefault(key, None)
    return normalized


def _validate_global_configuration(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate global configuration."""

    errors: dict[str, str] = {}
    if not user_input.get(CONF_GRID_POWER_ENTITY) and not user_input.get("configure_points_first"):
        errors[CONF_GRID_POWER_ENTITY] = "grid_entity_required"

    try:
        grid_limit_kw = float(user_input[CONF_GRID_LIMIT_KW])
        grid_reserve_kw = float(user_input[CONF_GRID_RESERVE_KW])
        grid_sensor_timeout_s = float(user_input[CONF_GRID_SENSOR_TIMEOUT_S])
    except (KeyError, TypeError, ValueError):
        return {"base": "invalid_number"}

    if grid_limit_kw <= 0.0:
        errors[CONF_GRID_LIMIT_KW] = "grid_limit_must_be_positive"

    if not all(isfinite(v) for v in (grid_limit_kw, grid_reserve_kw, grid_sensor_timeout_s)):
        return {"base": "invalid_number"}
    for key in (CONF_GRID_POWER_FACTOR, CONF_PV_POWER_FACTOR, CONF_BATTERY_POWER_FACTOR, CONF_BATTERY_SOC_FACTOR, CONF_HOUSE_POWER_FACTOR):
        try:
            if float(user_input.get(key, 1)) not in INPUT_FACTORS:
                raise ValueError
        except (TypeError, ValueError):
            errors[key] = "invalid_input_factor"
    if user_input.get(CONF_SURPLUS_STRATEGY, "net_export") not in SURPLUS_STRATEGIES:
        errors[CONF_SURPLUS_STRATEGY] = "invalid_surplus_strategy"

    if grid_reserve_kw < 0.0 or grid_reserve_kw >= grid_limit_kw:
        errors[CONF_GRID_RESERVE_KW] = "reserve_must_be_below_grid_limit"

    if grid_sensor_timeout_s <= 0.0:
        errors[CONF_GRID_SENSOR_TIMEOUT_S] = "grid_timeout_must_be_positive"

    battery_soc_entity = user_input.get(CONF_BATTERY_SOC_ENTITY)
    surplus_min_soc = user_input.get(CONF_SURPLUS_MIN_BATTERY_SOC)

    if surplus_min_soc is not None and not battery_soc_entity:
        errors[CONF_SURPLUS_MIN_BATTERY_SOC] = "soc_limit_requires_soc_entity"

    selected_entities = [
        user_input.get(CONF_GRID_POWER_ENTITY),
        user_input.get(CONF_HOUSE_POWER_ENTITY),
        user_input.get(CONF_PV_POWER_ENTITY),
        user_input.get(CONF_BATTERY_POWER_ENTITY),
        user_input.get(CONF_BATTERY_SOC_ENTITY),
    ]
    selected_entities = [entity for entity in selected_entities if entity]
    if len(selected_entities) != len(set(selected_entities)):
        errors["base"] = "duplicate_entities"

    return errors


def _build_load_schema(values: dict[str, Any] | None = None) -> vol.Schema:
    """Build one complete load configuration form."""

    values = values or {}

    return vol.Schema(
        {
            _required_marker(CONF_LOAD_NAME, values, "Verbraucher"): str,
            _required_marker(CONF_LOAD_TYPE, values, DEFAULT_LOAD_TYPE): SelectSelector(
                SelectSelectorConfig(options=list(LOAD_TYPES), translation_key=CONF_LOAD_TYPE)
            ),
            _required_marker(CONF_PRIORITY, values, DEFAULT_PRIORITY): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=1000,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            _required_marker(CONF_MIN_KW, values, DEFAULT_MIN_KW): _power_number_selector(),
            _required_marker(CONF_MAX_KW, values, DEFAULT_MAX_KW): _power_number_selector(
                minimum=0.1
            ),
            _required_marker(
                CONF_DEFAULT_REQUEST_KW,
                values,
                DEFAULT_DEFAULT_REQUEST_KW,
            ): _power_number_selector(),
            _optional_marker(CONF_ACTUAL_POWER_ENTITY, values): _entity_selector(
                domain=Platform.SENSOR
            ),
            _factor_marker(CONF_ACTUAL_POWER_FACTOR, values): _factor_selector(),
            _required_marker(
                CONF_ACTUAL_SENSOR_TIMEOUT_S,
                values,
                DEFAULT_ACTUAL_SENSOR_TIMEOUT_S,
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0.1,
                    step=0.1,
                    unit_of_measurement="s",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            _required_marker(
                CONF_INVERT_ACTUAL_POWER,
                values,
                DEFAULT_INVERT_ACTUAL_POWER,
            ): BooleanSelector(),
            _optional_marker(CONF_REQUEST_ENTITY, values): _entity_selector(),
            _factor_marker(CONF_REQUEST_FACTOR, values): _factor_selector(),
            _optional_marker(CONF_AVAILABILITY_ENTITY, values): _entity_selector(),
            _optional_marker(CONF_OUTPUT_ENTITY, values): _entity_selector(),
            _optional_marker(CONF_ENABLE_ENTITY, values): _entity_selector(
                domain=["switch", "input_boolean", "number", "input_number", "select", "input_select"]
            ),
            _required_marker(CONF_COMMAND_ON, values, "1"): str,
            _required_marker(CONF_COMMAND_OFF, values, "0"): str,
            _required_marker(CONF_OUTPUT_UNIT, values, DEFAULT_OUTPUT_UNIT): SelectSelector(
                SelectSelectorConfig(
                    options=[SelectOptionDict(value=unit, label=unit) for unit in OUTPUT_UNITS]
                )
            ),
            _required_marker(
                CONF_SAFE_OUTPUT_VALUE,
                values,
                DEFAULT_SAFE_OUTPUT_VALUE,
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0.0,
                    step=0.01,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            _required_marker(
                CONF_PEAK_SHAVING_ENABLED,
                values,
                DEFAULT_PEAK_SHAVING_ENABLED,
            ): BooleanSelector(),
            _required_marker(
                CONF_SURPLUS_ENABLED,
                values,
                DEFAULT_SURPLUS_ENABLED,
            ): BooleanSelector(),
            _required_marker(
                CONF_START_MARGIN_KW,
                values,
                DEFAULT_START_MARGIN_KW,
            ): _power_number_selector(),
            _required_marker(
                CONF_STOP_MARGIN_KW,
                values,
                DEFAULT_STOP_MARGIN_KW,
            ): _power_number_selector(),
            _required_marker(
                CONF_MIN_ON_TIME_S,
                values,
                DEFAULT_MIN_ON_TIME_S,
            ): _seconds_selector(),
            _required_marker(
                CONF_MIN_OFF_TIME_S,
                values,
                DEFAULT_MIN_OFF_TIME_S,
            ): _seconds_selector(),
            _required_marker(
                CONF_SETTLING_TIME_S,
                values,
                DEFAULT_SETTLING_TIME_S,
            ): _seconds_selector(),
            _required_marker(
                CONF_EVSE_PHASES,
                values,
                DEFAULT_EVSE_PHASES,
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=3,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            _required_marker(
                CONF_EVSE_VOLTAGE_V,
                values,
                DEFAULT_EVSE_VOLTAGE_V,
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    step=1,
                    unit_of_measurement="V",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            _required_marker(
                CONF_EVSE_MIN_CURRENT_A,
                values,
                DEFAULT_EVSE_MIN_CURRENT_A,
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0.01,
                    step=0.01,
                    unit_of_measurement="A",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            _required_marker(
                CONF_EVSE_MAX_CURRENT_A,
                values,
                DEFAULT_EVSE_MAX_CURRENT_A,
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0.01,
                    step=0.01,
                    unit_of_measurement="A",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            _required_marker(
                CONF_EVSE_PAUSE_CURRENT_A,
                values,
                DEFAULT_EVSE_PAUSE_CURRENT_A,
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0.0,
                    step=0.01,
                    unit_of_measurement="A",
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _duplicate_load_name(
    entry: ConfigEntry,
    name: str,
    *,
    exclude_subentry_id: str | None = None,
) -> bool:
    """Return whether another load already uses the same name."""

    normalized_name = name.strip().casefold()
    for subentry_id, subentry in entry.subentries.items():
        if subentry_id == exclude_subentry_id:
            continue
        if subentry.subentry_type != SUBENTRY_TYPE_LOAD:
            continue
        existing_name = str(subentry.data.get(CONF_LOAD_NAME, subentry.title))
        if existing_name.strip().casefold() == normalized_name:
            return True
    return False


class PowerManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Power Manager config flow."""

    VERSION = 4
    MINOR_VERSION = 0

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure global settings."""

        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_global_configuration(user_input)
            if not errors:
                return self.async_create_entry(
                    title=NAME,
                    data=_normalize_global_configuration(user_input),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_global_schema(user_input),
            errors=errors,
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls,
        config_entry: ConfigEntry,
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return supported load subentry types."""

        return {SUBENTRY_TYPE_LOAD: PowerManagerLoadSubentryFlow,
                SUBENTRY_TYPE_POINT: PowerManagerPointSubentryFlow}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> PowerManagerOptionsFlow:
        """Return global options flow."""

        return PowerManagerOptionsFlow()


class PowerManagerOptionsFlow(OptionsFlow):
    """Edit global Power Manager settings."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Edit global settings."""

        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_global_configuration(user_input)
            if not errors:
                return self.async_create_entry(
                    title="",
                    data=_normalize_global_configuration(user_input),
                )

        current_values = {
            **self.config_entry.data,
            **self.config_entry.options,
        }
        if user_input is not None:
            current_values.update(user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_global_schema(current_values),
            errors=errors,
        )


class PowerManagerLoadSubentryFlow(ConfigSubentryFlow):
    """Add and reconfigure arbitrary controllable loads."""

    def _validate_with_name(
        self,
        user_input: dict[str, Any],
        *,
        exclude_subentry_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Normalize and validate one subentry form."""

        errors = validate_load_data(user_input)
        try:
            normalized = normalize_load_data(user_input)
        except (TypeError, ValueError, OverflowError):
            return dict(user_input), {"base": "invalid_number"}

        if not errors and _duplicate_load_name(
            self._get_entry(),
            normalized[CONF_LOAD_NAME],
            exclude_subentry_id=exclude_subentry_id,
        ):
            errors[CONF_LOAD_NAME] = "duplicate_load_name"

        for subentry_id, subentry in self._get_entry().subentries.items():
            if subentry_id == exclude_subentry_id or subentry.subentry_type != SUBENTRY_TYPE_LOAD:
                continue
            used = {subentry.data.get(CONF_OUTPUT_ENTITY), subentry.data.get(CONF_ENABLE_ENTITY)} - {None, ""}
            for key in (CONF_OUTPUT_ENTITY, CONF_ENABLE_ENTITY):
                if normalized.get(key) and normalized[key] in used:
                    errors[key] = "duplicate_output_entity"

        return normalized, errors

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """Add a new load."""

        errors: dict[str, str] = {}
        values = user_input or {}

        if user_input is not None:
            normalized, errors = self._validate_with_name(user_input)
            values = normalized
            if not errors:
                return self.async_create_entry(
                    title=normalized[CONF_LOAD_NAME],
                    data=normalized,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_load_schema(values),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """Reconfigure an existing load."""

        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        values = dict(subentry.data)

        if user_input is not None:
            normalized, errors = self._validate_with_name(
                user_input,
                exclude_subentry_id=subentry.subentry_id,
            )
            values = normalized
            if not errors:
                # The parent config entry update listener performs the reload.
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    data=normalized,
                    title=normalized[CONF_LOAD_NAME],
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_load_schema(values),
            errors=errors,
        )
