"""Exercise real schema backends with small HA selector/flow doubles."""

from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("backend", ["voluptuous", "probatio"])
def test_config_dialogs_work_with_both_home_assistant_schema_backends(backend):
    script = r'''
import asyncio
import importlib
import importlib.abc
import sys
from types import ModuleType, SimpleNamespace

backend = sys.argv[1]
if backend == "probatio":
    from probatio.compat import install_as_voluptuous
    install_as_voluptuous()
else:
    # HA 2026.8 does not supply Probatio. Also catch accidental direct imports
    # when it happens to be installed in the developer's test environment.
    class NoProbatio(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "probatio" or fullname.startswith("probatio."):
                raise ModuleNotFoundError("Probatio unavailable on HA 2026.8", name=fullname)
    sys.meta_path.insert(0, NoProbatio())

import voluptuous as vol

class Flow:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()
    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}
    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}
    def async_update_and_abort(self, entry, subentry, **kwargs):
        return {"type": "abort", **kwargs}

class Selector:
    def __init__(self, config=None):
        self.config = config
    def __call__(self, value):
        return value

selector_attrs = {name: Selector for name in (
    "BooleanSelector", "EntitySelector", "NumberSelector", "SelectSelector")}
selector_attrs.update({name: dict for name in (
    "EntitySelectorConfig", "NumberSelectorConfig", "SelectOptionDict", "SelectSelectorConfig")})
selector_attrs["NumberSelectorMode"] = SimpleNamespace(BOX="box")
modules = {
    "homeassistant": {},
    "homeassistant.config_entries": {"ConfigEntry": object, "ConfigFlow": Flow,
        "ConfigFlowResult": dict, "ConfigSubentryFlow": Flow, "OptionsFlow": Flow,
        "SubentryFlowResult": dict},
    "homeassistant.const": {"Platform": SimpleNamespace(SENSOR="sensor")},
    "homeassistant.core": {"callback": lambda fn: fn},
    "homeassistant.helpers": {},
    "homeassistant.helpers.selector": selector_attrs,
}
for name, attributes in modules.items():
    module = ModuleType(name)
    vars(module).update(attributes)
    sys.modules[name] = module

flow_module = importlib.import_module("custom_components.power_manager.config_flow")
assert flow_module.vol.Schema is vol.Schema
global_form = asyncio.run(flow_module.PowerManagerConfigFlow().async_step_user())
assert isinstance(global_form["data_schema"], vol.Schema)
global_data = global_form["data_schema"]({"grid_power_entity": "sensor.grid", "grid_limit_kw": 11})
assert global_data["grid_power_factor"] == "1"
assert global_data["surplus_strategy"] == "net_export"
missing_grid = global_form["data_schema"]({"grid_limit_kw": 11})
assert asyncio.run(flow_module.PowerManagerConfigFlow().async_step_user(missing_grid))["errors"]["grid_power_entity"] == "grid_entity_required"
bootstrap = {**missing_grid, "configure_points_first": True}
assert asyncio.run(flow_module.PowerManagerConfigFlow().async_step_user(bootstrap))["type"] == "create_entry"
created = asyncio.run(flow_module.PowerManagerConfigFlow().async_step_user(global_data))
assert created["type"] == "create_entry"
assert created["data"]["grid_power_factor"] == 1

load_flow = flow_module.PowerManagerLoadSubentryFlow()
load_flow._get_entry = lambda: SimpleNamespace(subentries={})
load_form = asyncio.run(load_flow.async_step_user())
load_data = load_form["data_schema"]({"load_name": "Heizstab", "load_type": "switch",
    "output_entity": "number.mode", "max_kw": 3, "command_on": "12", "command_off": "14"})
created_load = asyncio.run(load_flow.async_step_user(load_data))
assert created_load["type"] == "create_entry", created_load
assert created_load["data"]["command_on"] == "12"
assert created_load["data"]["command_off"] == "14"
assert created_load["data"]["min_kw"] == 3

subentry = SimpleNamespace(subentry_id="heater", data=created_load["data"])
load_flow._get_reconfigure_subentry = lambda: subentry
reconfigure = asyncio.run(load_flow.async_step_reconfigure())
assert isinstance(reconfigure["data_schema"], vol.Schema)
updated = reconfigure["data_schema"]({**load_data, "max_kw": 2})
assert asyncio.run(load_flow.async_step_reconfigure(updated))["data"]["max_kw"] == 2
point_class = flow_module.PowerManagerPointSubentryFlow
point_flow = point_class()
point_flow._get_entry = lambda: SimpleNamespace(subentries={})
base = asyncio.run(point_flow.async_step_user())
choice = base["data_schema"]({"name": "Wallbox Freigabe", "protocol": "mqtt", "kind": "switch"})
form = asyncio.run(point_flow.async_step_user(choice))
assert form["step_id"] == "mqtt"
data = form["data_schema"]({"state_topic": "wb/state", "command_topic": "wb/set", "command_on": "12", "command_off": "14"})
created = asyncio.run(point_flow.async_step_mqtt(data))
assert created["type"] == "create_entry", created
assert created["data"]["command_on"] == "12"
subentry = SimpleNamespace(subentry_id="wb", data=created["data"], subentry_type="point")
point_flow._get_reconfigure_subentry = lambda: subentry
base = asyncio.run(point_flow.async_step_reconfigure())
changed_kind = {**choice, "kind": "number"}
assert asyncio.run(point_flow.async_step_reconfigure(changed_kind))["errors"]["base"] == "point_type_immutable"
form = asyncio.run(point_flow.async_step_reconfigure(choice))
updated_data = form["data_schema"]({"command_topic": "wb/new", "command_on": "12", "command_off": "14"})
updated = asyncio.run(point_flow.async_step_mqtt(updated_data))
assert updated["type"] == "abort", updated
assert updated["data"]["state_topic"] == ""

point_flow = point_class()
point_flow._get_entry = lambda: SimpleNamespace(subentries={})
form = asyncio.run(point_flow.async_step_user({"name": "Netzzähler", "protocol": "modbus", "kind": "sensor"}))
data = form["data_schema"]({"host": "meter.local", "register_type": "input", "data_type": "int32", "address": 100})
created = asyncio.run(point_flow.async_step_modbus(data))
assert created["type"] == "create_entry", created
assert created["data"]["device_id"] == 1
invalid = asyncio.run(point_flow.async_step_modbus({**data, "address": 65535}))
assert invalid["errors"]["base"] == "invalid_point"
point_flow = point_class()
form = asyncio.run(point_flow.async_step_user({"name": "Output 2", "protocol": "modbus", "kind": "number"}))
other = {**created["data"], "name": "Output 1", "kind": "number", "register_type": "holding", "data_type": "float32", "address": 100}
point_flow._get_entry = lambda: SimpleNamespace(subentries={"other": SimpleNamespace(subentry_type="point", data=other)})
data = form["data_schema"]({"host": "meter.local", "data_type": "uint16", "address": 101})
assert asyncio.run(point_flow.async_step_modbus(data))["errors"]["base"] == "invalid_point"
print(backend + ": global, load and MQTT/Modbus create/reconfigure dialogs passed")
'''
    result = subprocess.run(
        [sys.executable, "-c", script, backend],
        cwd=Path(__file__).parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
