import json
from pathlib import Path

ROOT = Path(__file__).parent
COMPONENT = ROOT / "custom_components" / "power_manager"


def test_hacs_json_exists_and_renders_readme():
    data = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert data["name"] == "Power Manager"
    assert data["render_readme"] is True
    assert (ROOT / "LICENSE").is_file()
    assert (COMPONENT / "brand" / "icon.png").is_file()


def test_manifest_contains_hacs_required_metadata_keys():
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    for key in (
        "domain",
        "documentation",
        "issue_tracker",
        "codeowners",
        "name",
        "version",
    ):
        assert key in manifest
    assert manifest["iot_class"] == "calculated"


def test_repository_contains_hacs_and_hassfest_workflow():
    workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    assert "hacs/action@main" in workflow
    assert "home-assistant/actions/hassfest@master" in workflow
    assert "category: integration" in workflow


def test_hacs_setup_helper_exists():
    assert (ROOT / "prepare_hacs_repo.py").is_file()
    assert (ROOT / "HACS_SETUP.md").is_file()
