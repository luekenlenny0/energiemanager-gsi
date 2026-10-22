"""Run integration setup/unload against small public HA API doubles."""

import asyncio
import importlib
import sys
from types import ModuleType, SimpleNamespace


def test_setup_registers_panel_and_unload_sends_safe_state_before_closing_io(monkeypatch):
    events = []
    async def register_panel(hass, **kwargs):
        events.append(("panel", kwargs))
    async def static_paths(paths):
        events.append(("static", paths))
    async def forward(entry, platforms):
        assert entry.runtime_data.direct_io.points == {}
        events.append(("platforms", platforms))
    async def unload(entry, platforms):
        events.append(("unload", platforms))
        return True
    class Coordinator:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
        async def async_refresh(self):
            events.append(("refresh", None))
        def async_start_tracking(self):
            events.append(("tracking", None))
        async def async_shutdown(self):
            assert not self.direct_io.stopped
            events.append(("safe_state", None))
    class Entry:
        title = "Energiemanager GSI"
        entry_id = "entry"
        subentries = {}
        def async_on_unload(self, fn):
            pass
        def add_update_listener(self, fn):
            return lambda: None
    modules = {
        "homeassistant": {}, "homeassistant.core": {"callback": lambda fn: fn},
        "homeassistant.exceptions": {"HomeAssistantError": RuntimeError},
        "homeassistant.components": {},
        "homeassistant.components.frontend": {
            "add_extra_js_url": lambda hass,url: events.append(("js", url)),
            "remove_extra_js_url": lambda hass,url: events.append(("remove_js", url)),
            "async_remove_panel": lambda hass,path: events.append(("remove_panel", path)),
        },
        "homeassistant.components.panel_custom": {"async_register_panel": register_panel},
        "homeassistant.components.http": {"StaticPathConfig": lambda *args,**kwargs: (args,kwargs)},
        "homeassistant.const": {"Platform": SimpleNamespace(SENSOR="sensor", BINARY_SENSOR="binary_sensor", SELECT="select", SWITCH="switch", NUMBER="number")},
        "custom_components.power_manager.coordinator": {"PowerManagerCoordinator": Coordinator},
    }
    for name, attrs in modules.items():
        module = ModuleType(name)
        vars(module).update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.delitem(sys.modules, "custom_components.power_manager.direct_io", raising=False)
    integration = importlib.import_module("custom_components.power_manager")
    hass = SimpleNamespace(data={}, http=SimpleNamespace(async_register_static_paths=static_paths),
        config_entries=SimpleNamespace(async_forward_entry_setups=forward, async_unload_platforms=unload))
    entry = Entry()
    async def exercise():
        assert await integration.async_setup_entry(hass, entry)
        kwargs = next(value for key,value in events if key == "panel")
        assert kwargs["sidebar_title"] == "Energiemanager GSI"
        assert kwargs["sidebar_icon"] == "mdi:home-lightning-bolt"
        assert kwargs["frontend_url_path"] == "energiemanager-gsi"
        assert kwargs["module_url"].endswith("energiemanager-gsi-panel.js?v=3.4.0")
        assert kwargs["config"]["entry_id"] == entry.entry_id
        assert await integration.async_unload_entry(hass, entry)
        assert entry.runtime_data.direct_io.stopped
        assert [key for key,value in events].index("safe_state") < [key for key,value in events].index("remove_panel")
        # A reload can register the same path again; static paths stay registered.
        assert await integration.async_setup_entry(hass, entry)
        assert sum(key == "static" for key,value in events) == 1
        assert sum(key == "panel" for key,value in events) == 2
        assert await integration.async_unload_entry(hass, entry)
    asyncio.run(exercise())
