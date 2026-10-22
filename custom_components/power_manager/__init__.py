"""Power Manager integration for Home Assistant."""

from __future__ import annotations

from contextlib import suppress
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import PowerManagerCoordinator

    type PowerManagerConfigEntry = ConfigEntry[PowerManagerCoordinator]

_LOGGER = logging.getLogger(__name__)

_FRONTEND_URL_BASE = "/power_manager_frontend"
_FRONTEND_STATIC_REGISTERED = "frontend_static_registered"


async def _async_update_listener(
    hass: HomeAssistant,
    entry: PowerManagerConfigEntry,
) -> None:
    """Reload after global options or load subentries change."""

    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerManagerConfigEntry,
) -> bool:
    """Set up Power Manager from a config entry."""

    from homeassistant.components import frontend
    from homeassistant.components.http import StaticPathConfig
    from homeassistant.const import Platform

    from .const import DOMAIN, VERSION
    from .coordinator import PowerManagerCoordinator

    domain_data = hass.data.setdefault(DOMAIN, {})
    frontend_dir = Path(__file__).parent / "frontend"
    module_url = f"{_FRONTEND_URL_BASE}/power-manager-card.js?v={VERSION}"

    if not domain_data.get(_FRONTEND_STATIC_REGISTERED):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    _FRONTEND_URL_BASE,
                    str(frontend_dir),
                    cache_headers=True,
                )
            ]
        )
        domain_data[_FRONTEND_STATIC_REGISTERED] = True

    frontend.add_extra_js_url(hass, module_url)

    coordinator = PowerManagerCoordinator(hass=hass, config_entry=entry)

    # Load the integration even if a critical source is currently unavailable.
    # The coordinator exposes that condition as fail-safe instead of preventing
    # the user from opening the integration and fixing its configuration.
    await coordinator.async_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(
        entry,
        [
            Platform.SENSOR,
            Platform.BINARY_SENSOR,
            Platform.SELECT,
            Platform.SWITCH,
            Platform.NUMBER,
        ],
    )

    coordinator.async_start_tracking()
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: PowerManagerConfigEntry,
) -> bool:
    """Unload Power Manager and best-effort put live outputs into safe state."""

    from homeassistant.components import frontend
    from homeassistant.const import Platform

    from .const import VERSION

    coordinator = entry.runtime_data
    await coordinator.async_shutdown()

    with suppress(KeyError):
        frontend.remove_extra_js_url(
            hass,
            f"{_FRONTEND_URL_BASE}/power-manager-card.js?v={VERSION}",
        )

    return await hass.config_entries.async_unload_platforms(
        entry,
        [
            Platform.SENSOR,
            Platform.BINARY_SENSOR,
            Platform.SELECT,
            Platform.SWITCH,
            Platform.NUMBER,
        ],
    )


async def async_migrate_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Migrate older Power Manager config entries to the V3 schema."""

    from .const import (
        CONF_BATTERY_SOC_SCALE,
        DEFAULT_BATTERY_SOC_SCALE,
    )

    if entry.version > 4:
        _LOGGER.error(
            "Cannot migrate Power Manager config entry from newer version %s",
            entry.version,
        )
        return False

    if entry.version < 4:
        new_data = dict(entry.data)
        new_data.setdefault(CONF_BATTERY_SOC_SCALE, DEFAULT_BATTERY_SOC_SCALE)
        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            version=4,
            minor_version=0,
        )
        _LOGGER.info("Migrated Power Manager config entry to version 4")

    return True
