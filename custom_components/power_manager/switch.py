"""Safety-gated live-control switch for Power Manager."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import PowerManagerCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[PowerManagerCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up live-control switch."""

    async_add_entities([PowerManagerLiveControlSwitch(entry.runtime_data, entry)])


class PowerManagerLiveControlSwitch(
    CoordinatorEntity[PowerManagerCoordinator],
    SwitchEntity,
):
    """Arm real actuator writes; defaults to off after every reload/restart."""

    _attr_has_entity_name = True
    _attr_translation_key = "live_control"

    def __init__(
        self,
        coordinator: PowerManagerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize live-control switch."""

        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_live_control"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
        )

    @property
    def is_on(self) -> bool:
        """Return whether real actuator writes are armed."""

        return self.coordinator.live_control_enabled

    async def async_turn_on(self, **kwargs) -> None:
        """Validate all actuators and arm live control."""

        await self.coordinator.async_enable_live_control()

    async def async_turn_off(self, **kwargs) -> None:
        """Send safe states once and disarm live control."""

        await self.coordinator.async_disable_live_control()
