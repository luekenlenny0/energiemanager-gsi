import json
from pathlib import Path

from custom_components.power_manager.const import VERSION

ROOT = Path(__file__).parent
COMPONENT = ROOT / "custom_components" / "power_manager"


def _json(relative: str):
    return json.loads((COMPONENT / relative).read_text(encoding="utf-8"))


def test_manifest_and_runtime_version_match_v3():
    manifest = _json("manifest.json")
    assert manifest["version"] == "3.0.0"
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
    assert set(selectors["output_unit"]["options"]) == {"auto", "W", "kW", "MW"}


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
