"""Manual power demand entities for individually configured consumers."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_LOAD_NAME, SUBENTRY_TYPE_LOAD
from .coordinator import PowerManagerCoordinator
from .load_config import normalize_load_data

PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    from .point_entity import add_point_entities
    add_point_entities(entry, "number", async_add_entities)
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type == SUBENTRY_TYPE_LOAD:
            async_add_entities([PowerManagerManualPower(entry.runtime_data, entry, subentry_id)], config_subentry_id=subentry_id)


class PowerManagerManualPower(CoordinatorEntity[PowerManagerCoordinator], NumberEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "manual_power"
    _attr_native_unit_of_measurement = "kW"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0.0
    _attr_native_step = 0.01

    def __init__(self, coordinator, entry, subentry_id):
        super().__init__(coordinator)
        self._subentry_id = subentry_id
        data = normalize_load_data(dict(entry.subentries[subentry_id].data))
        self._attr_unique_id = f"{entry.entry_id}_{subentry_id}_manual_power"
        self._attr_native_max_value = data["max_kw"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}:{subentry_id}")}, name=data[CONF_LOAD_NAME],
        )

    @property
    def native_value(self):
        return self.coordinator.manual_control(self._subentry_id).power_kw

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_manual_power(self._subentry_id, value)
