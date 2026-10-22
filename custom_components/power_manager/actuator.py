"""Home Assistant actuator layer for Power Manager."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State

from .const import (
    CONF_ENABLE_ENTITY,
    CONF_COMMAND_ON,
    CONF_COMMAND_OFF,
    CONF_EVSE_MAX_CURRENT_A,
    CONF_EVSE_MIN_CURRENT_A,
    CONF_EVSE_PAUSE_CURRENT_A,
    CONF_EVSE_PHASES,
    CONF_EVSE_VOLTAGE_V,
    CONF_LOAD_TYPE,
    CONF_MAX_KW,
    CONF_MIN_KW,
    CONF_OUTPUT_ENTITY,
    CONF_OUTPUT_UNIT,
    CONF_SAFE_OUTPUT_VALUE,
    DEFAULT_EVSE_MAX_CURRENT_A,
    DEFAULT_EVSE_MIN_CURRENT_A,
    DEFAULT_EVSE_PAUSE_CURRENT_A,
    DEFAULT_EVSE_PHASES,
    DEFAULT_EVSE_VOLTAGE_V,
    DEFAULT_MAX_KW,
    DEFAULT_MIN_KW,
    DEFAULT_OUTPUT_UNIT,
    DEFAULT_SAFE_OUTPUT_VALUE,
    LOAD_TYPE_EVSE,
    LOAD_TYPE_SWITCH,
    OUTPUT_UNIT_AUTO,
    SUPPORTED_NUMBER_DOMAINS,
    SUPPORTED_OUTPUT_POWER_UNITS,
    SUPPORTED_SWITCH_DOMAINS,
    SUPPORTED_COMMAND_DOMAINS,
)
from .outputs import OutputConversionError, OutputPlan, build_output_plan


class ActuatorError(RuntimeError):
    """Raised when a configured actuator cannot be used safely."""


@dataclass(frozen=True, slots=True)
class AppliedCommand:
    """Result of applying one load target."""

    target_kw: float
    numeric_value: float | str | None = None
    numeric_unit: str | None = None
    enabled: bool | None = None
    wrote_numeric: bool = False
    wrote_enable: bool = False


def _domain(entity_id: str) -> str:
    """Return entity domain."""

    return entity_id.split(".", 1)[0] if "." in entity_id else ""


def _state_or_error(hass: HomeAssistant, entity_id: str, label: str) -> State:
    """Return an entity state or raise an actuator error."""

    state = hass.states.get(entity_id)
    if state is None:
        raise ActuatorError(f"{label}: Entity '{entity_id}' wurde nicht gefunden.")
    if state.state == STATE_UNAVAILABLE or (
        state.state == STATE_UNKNOWN and not (
            state.attributes.get("power_manager_point") is True
            and state.attributes.get("power_manager_write_only") is True
        )
    ):
        raise ActuatorError(f"{label}: Entity '{entity_id}' ist {state.state}.")
    return state


def _effective_power_unit(hass: HomeAssistant, load_data: dict[str, Any]) -> str:
    """Resolve generic power output unit without guessing."""

    configured_unit = str(load_data.get(CONF_OUTPUT_UNIT, DEFAULT_OUTPUT_UNIT))
    if configured_unit != OUTPUT_UNIT_AUTO:
        if configured_unit not in (*SUPPORTED_OUTPUT_POWER_UNITS, "A"):
            raise ActuatorError(
                f"Ausgangseinheit '{configured_unit}' wird nicht unterstützt."
            )
        return configured_unit

    if load_data.get(CONF_LOAD_TYPE) == LOAD_TYPE_EVSE:
        return "A"

    output_entity = str(load_data.get(CONF_OUTPUT_ENTITY, ""))
    state = _state_or_error(hass, output_entity, "Leistungsausgang")
    unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
    if unit not in (*SUPPORTED_OUTPUT_POWER_UNITS, "A"):
        raise ActuatorError(
            "Leistungsausgang hat keine unterstützte Einheit. "
            "Wähle W, kW, MW oder A explizit in der Verbraucher-Konfiguration."
        )
    return str(unit)


def _numeric_limits(state: State) -> tuple[float | None, float | None]:
    """Read optional min/max attributes from number-like entities."""

    def parsed(name: str) -> float | None:
        raw = state.attributes.get(name)
        if raw is None:
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        return value if isfinite(value) else None

    return parsed("min"), parsed("max")


def _numeric_in_range(value: float, state: State) -> bool:
    """Return whether a numeric value is accepted by advertised limits."""

    minimum, maximum = _numeric_limits(state)
    if minimum is not None and value < minimum - 1e-9:
        return False
    if maximum is not None and value > maximum + 1e-9:
        return False
    return True


def _numeric_equal(state: State, value: float) -> bool:
    """Compare current numeric entity state with a target."""

    try:
        current = float(state.state)
    except (TypeError, ValueError):
        return False
    return isfinite(current) and abs(current - value) <= 0.001


def _build_plan(
    hass: HomeAssistant,
    load_data: dict[str, Any],
    target_kw: float,
) -> OutputPlan:
    """Build one output plan and translate conversion errors."""

    load_type = str(load_data.get(CONF_LOAD_TYPE, ""))
    power_unit = "kW"
    if load_type != LOAD_TYPE_SWITCH:
        power_unit = _effective_power_unit(hass, load_data)

    try:
        return build_output_plan(
            load_type=load_type,
            target_kw=max(0.0, target_kw),
            power_unit=power_unit,
            safe_output_value=float(
                load_data.get(CONF_SAFE_OUTPUT_VALUE, DEFAULT_SAFE_OUTPUT_VALUE)
            ),
            evse_phases=int(load_data.get(CONF_EVSE_PHASES, DEFAULT_EVSE_PHASES)),
            evse_voltage_v=float(
                load_data.get(CONF_EVSE_VOLTAGE_V, DEFAULT_EVSE_VOLTAGE_V)
            ),
            evse_min_current_a=float(
                load_data.get(CONF_EVSE_MIN_CURRENT_A, DEFAULT_EVSE_MIN_CURRENT_A)
            ),
            evse_max_current_a=float(
                load_data.get(CONF_EVSE_MAX_CURRENT_A, DEFAULT_EVSE_MAX_CURRENT_A)
            ),
            evse_pause_current_a=float(
                load_data.get(CONF_EVSE_PAUSE_CURRENT_A, DEFAULT_EVSE_PAUSE_CURRENT_A)
            ),
        )
    except OutputConversionError as err:
        raise ActuatorError(str(err)) from err


async def _async_set_number(
    hass: HomeAssistant,
    entity_id: str,
    value: float,
) -> bool:
    """Set a number/input_number only when its state differs."""

    state = _state_or_error(hass, entity_id, "Numerischer Ausgang")
    if _numeric_equal(state, value):
        return False

    domain = _domain(entity_id)
    await hass.services.async_call(
        domain,
        "set_value",
        {"entity_id": entity_id, "value": value},
        blocking=True,
    )
    return True


async def _async_set_switch(
    hass: HomeAssistant,
    entity_id: str,
    enabled: bool,
) -> bool:
    """Set switch/input_boolean only when its state differs."""

    state = _state_or_error(hass, entity_id, "Schaltausgang")
    target_state = STATE_ON if enabled else STATE_OFF
    if state.state == target_state:
        return False

    domain = _domain(entity_id)
    await hass.services.async_call(
        domain,
        SERVICE_TURN_ON if enabled else SERVICE_TURN_OFF,
        {"entity_id": entity_id},
        blocking=True,
    )
    return True


def _command_value(entity_id: str, raw: Any) -> float | str:
    """Keep select options as text; parse numeric command entities strictly."""

    if _domain(entity_id) in SUPPORTED_NUMBER_DOMAINS:
        try:
            value = float(raw)
        except (TypeError, ValueError) as err:
            raise ActuatorError("AN/AUS-Befehl muss für diesen Ausgang eine Zahl sein.") from err
        if not isfinite(value):
            raise ActuatorError("AN/AUS-Befehl muss endlich sein.")
        return value
    value = str(raw)
    if not value.strip():
        raise ActuatorError("AN/AUS-Befehl darf nicht leer sein.")
    return value


def _validate_command(hass: HomeAssistant, entity_id: str, data: dict[str, Any]) -> None:
    """Validate both custom states before sending any live command."""

    domain = _domain(entity_id)
    if domain not in SUPPORTED_COMMAND_DOMAINS:
        raise ActuatorError("Schaltausgang benötigt switch, input_boolean, number, input_number, select oder input_select.")
    state = _state_or_error(hass, entity_id, "Schaltausgang")
    if domain in SUPPORTED_SWITCH_DOMAINS:
        return
    on = _command_value(entity_id, data.get(CONF_COMMAND_ON, "1"))
    off = _command_value(entity_id, data.get(CONF_COMMAND_OFF, "0"))
    if on == off:
        raise ActuatorError("AN und AUS müssen unterschiedliche Befehle haben.")
    for value in (on, off):
        if domain in SUPPORTED_NUMBER_DOMAINS:
            if not _numeric_in_range(float(value), state):
                raise ActuatorError(f"Schaltbefehl {value} liegt außerhalb des Entity-Bereichs.")
        elif value not in state.attributes.get("options", []):
            raise ActuatorError(f"Schaltbefehl '{value}' ist keine Option der Entity.")


async def _async_set_command(
    hass: HomeAssistant, entity_id: str, enabled: bool, data: dict[str, Any]
) -> bool:
    """Apply configurable commands to a switching or enable entity."""

    domain = _domain(entity_id)
    if domain not in SUPPORTED_COMMAND_DOMAINS:
        raise ActuatorError("Nicht unterstützter Schaltausgang.")
    if domain in SUPPORTED_SWITCH_DOMAINS:
        return await _async_set_switch(hass, entity_id, enabled)
    value = _command_value(entity_id, data.get(CONF_COMMAND_ON if enabled else CONF_COMMAND_OFF, "1" if enabled else "0"))
    if domain in SUPPORTED_NUMBER_DOMAINS:
        state = _state_or_error(hass, entity_id, "Schaltausgang")
        if not _numeric_in_range(float(value), state):
            raise ActuatorError("Schaltbefehl liegt außerhalb des Entity-Bereichs.")
        return await _async_set_number(hass, entity_id, float(value))
    state = _state_or_error(hass, entity_id, "Schaltausgang")
    if value not in state.attributes.get("options", []):
        raise ActuatorError("Schaltbefehl ist keine Option der Entity.")
    if state.state == value:
        return False
    await hass.services.async_call(
        domain, "select_option", {"entity_id": entity_id, "option": value}, blocking=True
    )
    return True


def _validate_positive_plan_range(
    plan: OutputPlan,
    state: State,
    *,
    label: str,
) -> None:
    """Require a positive controller target to be exactly representable."""

    if plan.numeric_value is None:
        raise ActuatorError(f"{label}: kein numerischer Ausgangswert berechnet.")
    if plan.enabled is not True:
        raise ActuatorError(
            f"{label}: technische Mindestleistung wird vom Ausgangsadapter "
            "als Pause/Aus abgebildet. min_kw und Gerätegrenzen passen nicht zusammen."
        )
    if not _numeric_in_range(plan.numeric_value, state):
        minimum, maximum = _numeric_limits(state)
        raise ActuatorError(
            f"{label}: berechneter Wert {plan.numeric_value:g} liegt außerhalb "
            f"des Entity-Bereichs [{minimum}, {maximum}]."
        )


def validate_actuator(hass: HomeAssistant, load_data: dict[str, Any]) -> None:
    """Validate one configured output before live control is armed.

    A positive controller target is never silently rounded up, rounded down,
    clamped or converted to off. Such a mismatch would make the controller's
    stored target differ from the command actually sent to the device and can
    invalidate the PMAX estimate when no actual-power sensor is available.
    """

    output_entity = str(load_data.get(CONF_OUTPUT_ENTITY, ""))
    if not output_entity:
        raise ActuatorError(
            "Für jeden Verbraucher ist im Livebetrieb ein Ausgang erforderlich."
        )

    load_type = str(load_data.get(CONF_LOAD_TYPE, ""))
    output_domain = _domain(output_entity)

    enable_entity = str(load_data.get(CONF_ENABLE_ENTITY, ""))
    if enable_entity:
        _validate_command(hass, enable_entity, load_data)

    if load_type == LOAD_TYPE_SWITCH:
        _validate_command(hass, output_entity, load_data)
        return

    if output_domain not in SUPPORTED_NUMBER_DOMAINS:
        raise ActuatorError(
            f"Modulierender Ausgang '{output_entity}' muss number oder input_number sein."
        )

    output_state = _state_or_error(hass, output_entity, "Numerischer Ausgang")

    min_kw = float(load_data.get(CONF_MIN_KW, DEFAULT_MIN_KW))
    max_kw = float(load_data.get(CONF_MAX_KW, DEFAULT_MAX_KW))

    # Verify that every positive technical boundary is representable without
    # modifying the controller's target behind its back.
    if min_kw > 0.0:
        _validate_positive_plan_range(
            _build_plan(hass, load_data, min_kw),
            output_state,
            label="Mindestleistung",
        )
    else:
        # With min_kw == 0 the controller may legitimately produce arbitrarily
        # small positive targets. The numeric output must therefore accept zero
        # as its lower boundary; a separate enable switch only solves target 0,
        # not positive targets below a number entity's minimum.
        minimum, _maximum = _numeric_limits(output_state)
        if minimum is not None and minimum > 1e-9:
            raise ActuatorError(
                "min_kw ist 0, aber die numerische Ausgangs-Entity hat einen "
                "positiven Mindestwert. Setze min_kw auf die technische Mindestleistung."
            )

    _validate_positive_plan_range(
        _build_plan(hass, load_data, max_kw),
        output_state,
        label="Maximalleistung",
    )

    zero_plan = _build_plan(hass, load_data, 0.0)
    if zero_plan.numeric_value is None:
        raise ActuatorError("Für den sicheren Zustand wurde kein Zahlenwert berechnet.")

    # A separate enable output can safely switch the device off even when its
    # numeric entity cannot represent the pause/zero value.
    if not enable_entity and not _numeric_in_range(zero_plan.numeric_value, output_state):
        raise ActuatorError(
            "Der sichere numerische Ausgangswert liegt außerhalb des Entity-Bereichs "
            "und es ist keine separate Freigabe-Entity konfiguriert."
        )


async def async_apply_target(
    hass: HomeAssistant,
    load_data: dict[str, Any],
    target_kw: float,
) -> AppliedCommand:
    """Apply one controller target to Home Assistant output entities."""

    output_entity = str(load_data.get(CONF_OUTPUT_ENTITY, ""))
    if not output_entity:
        raise ActuatorError("Kein Ausgang konfiguriert.")

    load_type = str(load_data.get(CONF_LOAD_TYPE, ""))
    enable_entity = str(load_data.get(CONF_ENABLE_ENTITY, ""))
    plan = _build_plan(hass, load_data, target_kw)

    wrote_numeric = False
    wrote_enable = False

    if load_type == LOAD_TYPE_SWITCH:
        assert plan.enabled is not None
        if enable_entity and not plan.enabled:
            wrote_enable = await _async_set_command(hass, enable_entity, False, load_data)
        wrote_output = await _async_set_command(hass, output_entity, plan.enabled, load_data)
        if enable_entity and plan.enabled:
            wrote_enable = await _async_set_command(hass, enable_entity, True, load_data)
        return AppliedCommand(
            target_kw=target_kw,
            numeric_value=(_command_value(output_entity, load_data.get(CONF_COMMAND_ON if plan.enabled else CONF_COMMAND_OFF, "1" if plan.enabled else "0")) if _domain(output_entity) not in SUPPORTED_SWITCH_DOMAINS else None),
            enabled=plan.enabled,
            wrote_enable=wrote_enable or wrote_output,
        )

    output_state = _state_or_error(hass, output_entity, "Numerischer Ausgang")
    desired_numeric = plan.numeric_value
    if desired_numeric is None:
        raise ActuatorError("Numerischer Verbraucher hat keinen berechneten Ausgangswert.")

    if plan.enabled is False:
        # Disable first to avoid a transient command increase. If a separate
        # enable exists, a numeric pause value outside the number entity range
        # can simply be skipped because the physical enable is already off.
        if enable_entity:
            wrote_enable = await _async_set_command(hass, enable_entity, False, load_data)

        if _numeric_in_range(desired_numeric, output_state):
            wrote_numeric = await _async_set_number(hass, output_entity, desired_numeric)
        elif not enable_entity:
            raise ActuatorError(
                "Sicherer Ausgangswert wird von der Entity nicht akzeptiert und keine "
                "separate Freigabe-Entity ist konfiguriert."
            )

        return AppliedCommand(
            target_kw=target_kw,
            numeric_value=(desired_numeric if _numeric_in_range(desired_numeric, output_state) else None),
            numeric_unit=plan.numeric_unit,
            enabled=False,
            wrote_numeric=wrote_numeric,
            wrote_enable=wrote_enable,
        )

    # PMAX invariant: positive targets must be representable exactly enough by
    # the configured HA entity. Never clamp up/down or silently disable here.
    if not _numeric_in_range(desired_numeric, output_state):
        minimum, maximum = _numeric_limits(output_state)
        raise ActuatorError(
            f"Berechneter Ausgangswert {desired_numeric:g} liegt außerhalb "
            f"des Entity-Bereichs [{minimum}, {maximum}]."
        )

    wrote_numeric = await _async_set_number(hass, output_entity, desired_numeric)

    if enable_entity:
        wrote_enable = await _async_set_command(hass, enable_entity, True, load_data)

    return AppliedCommand(
        target_kw=target_kw,
        numeric_value=desired_numeric,
        numeric_unit=plan.numeric_unit,
        enabled=True,
        wrote_numeric=wrote_numeric,
        wrote_enable=wrote_enable,
    )


async def async_apply_safe_state(
    hass: HomeAssistant,
    load_data: dict[str, Any],
) -> AppliedCommand:
    """Apply the load's configured zero-power / pause state."""

    return await async_apply_target(hass, load_data, 0.0)
