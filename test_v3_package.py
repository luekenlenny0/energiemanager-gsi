import json
from pathlib import Path

from custom_components.power_manager.const import VERSION

ROOT = Path(__file__).parent
COMPONENT = ROOT / "custom_components" / "power_manager"


def _json(relative: str):
    return json.loads((COMPONENT / relative).read_text(encoding="utf-8"))


def test_manifest_and_runtime_version_match_v3():
    manifest = _json("manifest.json")
    assert manifest["version"] == "3.1.0"
    assert VERSION == manifest["version"]


def test_manifest_has_no_external_python_requirements():
    manifest = _json("manifest.json")
    assert manifest["requirements"] == []


def test_all_translation_json_files_parse():
    _json("strings.json")
    _json("translations/en.json")
    _json("translations/de.json")


def test_english_reconfigure_load_form_has_all_add_form_fields():
    data = _json("strings.json")["config_subentries"]["load"]["step"]
    assert data["reconfigure"]["data"] == data["user"]["data"]
    assert data["reconfigure"]["data_description"] == data["user"]["data_description"]


def test_german_reconfigure_load_form_has_all_add_form_fields():
    data = _json("translations/de.json")["config_subentries"]["load"]["step"]
    assert data["reconfigure"]["data"] == data["user"]["data"]
    assert data["reconfigure"]["data_description"] == data["user"]["data_description"]


def test_selector_translations_cover_runtime_options():
    selectors = _json("strings.json")["selector"]
    assert set(selectors["load_type"]["options"]) == {"modulating", "switch", "evse"}
    assert set(selectors["battery_soc_scale"]["options"]) == {"percent", "fraction"}
    assert "output_unit" not in selectors


def test_component_has_no_exam_simulator_address_or_participant_topic_hardcoded():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in COMPONENT.rglob("*")
        if path.suffix in {".py", ".json"}
    )
    assert "192.168.1.37" not in source
    assert "sim/t01" not in source


def test_live_control_is_documented_as_a_runtime_safety_gate():
    strings = _json("strings.json")
    assert "live_control" in strings["entity"]["switch"]
    assert "fail_safe_active" in strings["entity"]["binary_sensor"]


def test_generic_entity_selector_omits_none_domain_filter():
    source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
    assert 'if domain is not None:' in source
    assert 'config["domain"] = domain' in source
    assert '_optional_marker(CONF_OUTPUT_ENTITY, values): _entity_selector()' in source
    assert 'domain=["switch", "input_boolean"]' in source


def test_coordinator_load_diagnostic_age_is_wired_to_diagnostic_not_core_model():
    source = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")
    controllable_block = source[source.index("load = ControllableLoad("):source.index("loads.append(load)")]
    diagnostic_block = source[source.index("diagnostics[subentry_id] = LoadDiagnostic("):source.index("return loads, diagnostics")]
    assert "actual_measurement_age_s=" not in controllable_block
    assert "actual_measurement_age_s=actual_age_s" in diagnostic_block


def test_load_reconfigure_uses_parent_entry_accessor():
    source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
    reconfigure_block = source[source.index("async def async_step_reconfigure"):source.index("return self.async_show_form", source.index("async def async_step_reconfigure"))]
    assert "self._get_entry()" in reconfigure_block
    assert "self._get_reconfigure_entry()" not in reconfigure_block


def test_surplus_mode_auto_returns_to_normal_at_reserve_soc():
    source = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")
    assert "battery_soc <= surplus_min_battery_soc" in source
    assert "self.operating_mode = OperatingMode.NORMAL" in source


def test_surplus_core_uses_pv_as_raw_budget():
    source = (COMPONENT / "controller.py").read_text(encoding="utf-8")
    surplus_block = source[source.index("# V3.0.6:"):source.index("battery_soc_blocking_surplus", source.index("# V3.0.6:"))]
    assert "inputs.pv_kw" in surplus_block
    assert "controlled_power_for_calculation_kw\n            - inputs.grid_kw" not in surplus_block


def test_manifest_classifies_power_manager_as_hub():
    manifest = _json("manifest.json")
    assert manifest["integration_type"] == "hub"


def test_manifest_declares_frontend_dependencies():
    manifest = _json("manifest.json")
    assert set(manifest["dependencies"]) == {"frontend", "http"}


def test_dashboard_card_is_packaged_and_registered():
    card = COMPONENT / "frontend" / "power-manager-card.js"
    assert card.is_file()
    source = card.read_text(encoding="utf-8")
    assert 'customElements.define("power-manager-card"' in source
    assert 'type: "power-manager-card"' in source
    assert 'config/entity_registry/list' in source


def test_backend_serves_and_loads_dashboard_card():
    source = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    assert "StaticPathConfig" in source
    assert "frontend.add_extra_js_url" in source
    assert "power-manager-card.js" in source


def test_load_target_sensor_exposes_dashboard_metadata():
    source = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
    for attribute in (
        '"load_name"',
        '"priority"',
        '"min_kw"',
        '"max_kw"',
        '"peak_shaving_enabled"',
        '"surplus_enabled"',
        '"requested_kw"',
        '"actual_kw"',
    ):
        assert attribute in source
