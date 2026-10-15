"""Diagnostic binary sensors for Power Manager."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import PowerManagerCoordinator, PowerManagerCoordinatorData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PowerManagerBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a Power Manager binary sensor."""

    value_fn: Callable[[PowerManagerCoordinatorData], bool | None]


def _result_bool(attribute: str) -> Callable[[PowerManagerCoordinatorData], bool | None]:
    """Safely return a ControllerResult boolean."""

    def value_fn(data: PowerManagerCoordinatorData) -> bool | None:
        if data.result is None:
            return None
        return bool(getattr(data.result, attribute))

    return value_fn


BINARY_SENSORS: tuple[PowerManagerBinarySensorDescription, ...] = (
    PowerManagerBinarySensorDescription(
        key="grid_measurement_healthy",
        translation_key="grid_measurement_healthy",
        value_fn=lambda data: data.grid_measurement_healthy,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PowerManagerBinarySensorDescription(
        key="fail_safe_active",
        translation_key="fail_safe_active",
        value_fn=lambda data: data.fail_safe_active,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PowerManagerBinarySensorDescription(
        key="output_healthy",
        translation_key="output_healthy",
        value_fn=lambda data: data.output_healthy,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PowerManagerBinarySensorDescription(
        key="peak_shaving_active",
        translation_key="peak_shaving_active",
        value_fn=_result_bool("peak_shaving_active"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PowerManagerBinarySensorDescription(
        key="surplus_active",
        translation_key="surplus_active",
        value_fn=_result_bool("surplus_active"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PowerManagerBinarySensorDescription(
        key="hard_grid_limit_exceeded",
        translation_key="hard_grid_limit_exceeded",
        value_fn=_result_bool("hard_limit_exceeded_now"),
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PowerManagerBinarySensorDescription(
        key="grid_limit_unachievable",
        translation_key="grid_limit_unachievable",
        value_fn=_result_bool("grid_limit_unachievable"),
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PowerManagerBinarySensorDescription(
        key="battery_soc_blocking_surplus",
        translation_key="battery_soc_blocking_surplus",
        value_fn=_result_bool("battery_soc_blocking_surplus"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[PowerManagerCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Power Manager binary sensors."""

    coordinator = entry.runtime_data
    async_add_entities(
        PowerManagerBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSORS
    )


class PowerManagerBinarySensor(
    CoordinatorEntity[PowerManagerCoordinator],
    BinarySensorEntity,
):
    """Representation of a Power Manager binary sensor."""

    _attr_has_entity_name = True
    entity_description: PowerManagerBinarySensorDescription

    def __init__(
        self,
        coordinator: PowerManagerCoordinator,
        entry: ConfigEntry,
        description: PowerManagerBinarySensorDescription,
    ) -> None:
        """Initialize binary sensor."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_translation_key = description.translation_key
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
        )

    @property
    def is_on(self) -> bool | None:
        """Return current diagnostic state."""

        data = self.coordinator.data
        if data is None:
            return None
        return self.entity_description.value_fn(data)
