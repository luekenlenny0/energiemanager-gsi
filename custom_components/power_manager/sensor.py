"""Diagnostic sensors for Power Manager."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_BATTERY_POWER_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_LOAD_NAME,
    CONF_PV_POWER_ENTITY,
    DOMAIN,
    NAME,
    SUBENTRY_TYPE_LOAD,
)
from .coordinator import (
    LoadDiagnostic,
    PowerManagerCoordinator,
    PowerManagerCoordinatorData,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PowerManagerSensorDescription(SensorEntityDescription):
    """Describe a Power Manager global sensor."""

    value_fn: Callable[[PowerManagerCoordinatorData], StateType]
    required_config_key: str | None = None


def _result_value(attribute: str) -> Callable[[PowerManagerCoordinatorData], StateType]:
    """Safely return a ControllerResult attribute."""

    def value_fn(data: PowerManagerCoordinatorData) -> StateType:
        if data.result is None:
            return None
        return getattr(data.result, attribute)

    return value_fn


def _input_value(attribute: str) -> Callable[[PowerManagerCoordinatorData], StateType]:
    """Safely return a ControllerInputs attribute."""

    def value_fn(data: PowerManagerCoordinatorData) -> StateType:
        if data.inputs is None:
            return None
        return getattr(data.inputs, attribute)

    return value_fn


POWER_SENSOR_OPTIONS = {
    "device_class": SensorDeviceClass.POWER,
    "native_unit_of_measurement": UnitOfPower.KILO_WATT,
    "state_class": SensorStateClass.MEASUREMENT,
    "entity_category": EntityCategory.DIAGNOSTIC,
}

SENSORS: tuple[PowerManagerSensorDescription, ...] = (
    PowerManagerSensorDescription(
        key="grid_power",
        translation_key="grid_power",
        value_fn=lambda data: data.grid_power_kw,
        **POWER_SENSOR_OPTIONS,
    ),
    PowerManagerSensorDescription(
        key="grid_measurement_age",
        translation_key="grid_measurement_age",
        value_fn=lambda data: data.grid_measurement_age_s,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PowerManagerSensorDescription(
        key="fail_safe_reason",
        translation_key="fail_safe_reason",
        value_fn=lambda data: data.fail_safe_reason or "none",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PowerManagerSensorDescription(
        key="last_output_error",
        translation_key="last_output_error",
        value_fn=lambda data: data.last_output_error or "none",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PowerManagerSensorDescription(
        key="configured_load_count",
        translation_key="configured_load_count",
        value_fn=lambda data: len(data.loads),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PowerManagerSensorDescription(
        key="pv_power",
        translation_key="pv_power",
        value_fn=_input_value("pv_kw"),
        required_config_key=CONF_PV_POWER_ENTITY,
        **POWER_SENSOR_OPTIONS,
    ),
    PowerManagerSensorDescription(
        key="battery_power",
        translation_key="battery_power",
        value_fn=_input_value("battery_kw"),
        required_config_key=CONF_BATTERY_POWER_ENTITY,
        **POWER_SENSOR_OPTIONS,
    ),
    PowerManagerSensorDescription(
        key="battery_soc",
        translation_key="battery_soc",
        value_fn=_input_value("battery_soc"),
        required_config_key=CONF_BATTERY_SOC_ENTITY,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PowerManagerSensorDescription(
        key="effective_grid_limit",
        translation_key="effective_grid_limit",
        value_fn=_result_value("effective_grid_limit_kw"),
        **POWER_SENSOR_OPTIONS,
    ),
    PowerManagerSensorDescription(
        key="base_load",
        translation_key="base_load",
        value_fn=_result_value("base_load_kw"),
        **POWER_SENSOR_OPTIONS,
    ),
    PowerManagerSensorDescription(
        key="peak_budget",
        translation_key="peak_budget",
        value_fn=_result_value("peak_budget_kw"),
        **POWER_SENSOR_OPTIONS,
    ),
    PowerManagerSensorDescription(
        key="raw_surplus_budget",
        translation_key="raw_surplus_budget",
        value_fn=_result_value("raw_surplus_budget_kw"),
        **POWER_SENSOR_OPTIONS,
    ),
    PowerManagerSensorDescription(
        key="surplus_budget",
        translation_key="surplus_budget",
        value_fn=_result_value("surplus_budget_kw"),
        **POWER_SENSOR_OPTIONS,
    ),
    PowerManagerSensorDescription(
        key="available_budget",
        translation_key="available_budget",
        value_fn=_result_value("available_budget_kw"),
        **POWER_SENSOR_OPTIONS,
    ),
    PowerManagerSensorDescription(
        key="unused_budget",
        translation_key="unused_budget",
        value_fn=_result_value("unused_budget_kw"),
        **POWER_SENSOR_OPTIONS,
    ),
    PowerManagerSensorDescription(
        key="projected_grid_power",
        translation_key="projected_grid_power",
        value_fn=_result_value("projected_grid_kw"),
        **POWER_SENSOR_OPTIONS,
    ),
    PowerManagerSensorDescription(
        key="grid_headroom",
        translation_key="grid_headroom",
        value_fn=_result_value("grid_headroom_kw"),
        **POWER_SENSOR_OPTIONS,
    ),
    PowerManagerSensorDescription(
        key="total_requested_power",
        translation_key="total_requested_power",
        value_fn=_result_value("total_requested_kw"),
        **POWER_SENSOR_OPTIONS,
    ),
    PowerManagerSensorDescription(
        key="total_target_power",
        translation_key="total_target_power",
        value_fn=_result_value("total_target_kw"),
        **POWER_SENSOR_OPTIONS,
    ),
    PowerManagerSensorDescription(
        key="measured_controlled_power",
        translation_key="measured_controlled_power",
        value_fn=_result_value("measured_controlled_power_kw"),
        **POWER_SENSOR_OPTIONS,
    ),
    PowerManagerSensorDescription(
        key="estimated_controlled_power",
        translation_key="estimated_controlled_power",
        value_fn=_result_value("estimated_controlled_power_kw"),
        **POWER_SENSOR_OPTIONS,
    ),
    PowerManagerSensorDescription(
        key="battery_discharge",
        translation_key="battery_discharge",
        value_fn=_result_value("battery_discharge_kw"),
        **POWER_SENSOR_OPTIONS,
    ),
    PowerManagerSensorDescription(
        key="active_load_count",
        translation_key="active_load_count",
        value_fn=_result_value("active_load_count"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PowerManagerSensorDescription(
        key="limited_load_count",
        translation_key="limited_load_count",
        value_fn=_result_value("limited_load_count"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PowerManagerSensorDescription(
        key="settling_load_count",
        translation_key="settling_load_count",
        value_fn=_result_value("settling_load_count"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[PowerManagerCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Power Manager sensors."""

    coordinator = entry.runtime_data

    global_sensors = [
        PowerManagerSensor(coordinator, entry, description)
        for description in SENSORS
        if description.required_config_key is None
        or coordinator.settings.get(description.required_config_key)
    ]
    async_add_entities(global_sensors)

    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_LOAD:
            continue
        async_add_entities(
            [PowerManagerLoadTargetSensor(coordinator, entry, subentry_id)],
            config_subentry_id=subentry_id,
        )


class PowerManagerSensor(
    CoordinatorEntity[PowerManagerCoordinator],
    SensorEntity,
):
    """Representation of a global Power Manager sensor."""

    _attr_has_entity_name = True
    entity_description: PowerManagerSensorDescription

    def __init__(
        self,
        coordinator: PowerManagerCoordinator,
        entry: ConfigEntry,
        description: PowerManagerSensorDescription,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_translation_key = description.translation_key
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
        )

    @property
    def native_value(self) -> StateType:
        """Return current diagnostic value."""

        data = self.coordinator.data
        if data is None:
            return None
        return self.entity_description.value_fn(data)


class PowerManagerLoadTargetSensor(
    CoordinatorEntity[PowerManagerCoordinator],
    SensorEntity,
):
    """Calculated target power and runtime details for one load subentry."""

    _attr_has_entity_name = True
    _attr_translation_key = "load_target_power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: PowerManagerCoordinator,
        entry: ConfigEntry,
        subentry_id: str,
    ) -> None:
        """Initialize a load target sensor."""

        super().__init__(coordinator)
        self._subentry_id = subentry_id
        subentry = entry.subentries[subentry_id]
        load_name = str(subentry.data.get(CONF_LOAD_NAME, subentry.title))
        self._attr_unique_id = f"{entry.entry_id}_{subentry_id}_target_power"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}:{subentry_id}")},
            name=load_name,
        )

    def _load(self) -> LoadDiagnostic | None:
        """Return current load diagnostic."""

        data = self.coordinator.data
        if data is None:
            return None
        return data.loads.get(self._subentry_id)

    @property
    def native_value(self) -> float | None:
        """Return calculated target power in kW."""

        load = self._load()
        return None if load is None else load.calculated_target_kw

    @property
    def extra_state_attributes(self) -> dict[str, StateType]:
        """Expose useful per-load runtime diagnostics."""

        load = self._load()
        if load is None:
            return {}

        return {
            "requested_kw": load.requested_kw,
            "actual_kw": load.actual_kw,
            "actual_measurement_age_s": load.actual_measurement_age_s,
            "available": load.available,
            "commanded_target_kw": load.commanded_target_kw,
            "output_entity": load.output_entity,
            "enable_entity": load.enable_entity,
            "command_value": load.command_value,
            "command_unit": load.command_unit,
            "command_enabled": load.command_enabled,
            "input_error": load.input_error,
            "command_error": load.command_error,
        }
