"""Runtime operating-mode select for Power Manager."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import PowerManagerCoordinator
from .models import OperatingMode

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[PowerManagerCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Power Manager mode select."""

    async_add_entities([PowerManagerModeSelect(entry.runtime_data, entry)])


class PowerManagerModeSelect(
    CoordinatorEntity[PowerManagerCoordinator],
    SelectEntity,
):
    """Select NORMAL or SURPLUS controller mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "operating_mode"
    _attr_options = [OperatingMode.NORMAL.value, OperatingMode.SURPLUS.value]

    def __init__(
        self,
        coordinator: PowerManagerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize operating-mode select."""

        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_operating_mode"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
        )

    @property
    def current_option(self) -> str:
        """Return current controller mode."""

        return self.coordinator.operating_mode.value

    async def async_select_option(self, option: str) -> None:
        """Change controller mode."""

        await self.coordinator.async_set_operating_mode(OperatingMode(option))
