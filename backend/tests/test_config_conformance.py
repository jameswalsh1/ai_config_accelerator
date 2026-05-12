"""
Production config conformance tests.

These tests scan the ``tests/wizard_configs/`` directory and validate
every file found there.  When a new language or tool is added, it is
automatically picked up and validated — no test changes required.

The tests check:
- JSON schema compliance (structure)
- Override reference integrity (all field_id / step_id refs point to real schema entries)
- Composable config loading (each tool × language combination resolves without error)
- File generation (each tool produces non-empty output)
"""

import json
from pathlib import Path
from typing import Any, cast

import pytest

from app.services.config_validator import (
    validate_language_override,
    validate_tool_override,
    validate_combo_override,
    validate_wizard_schema,
    validate_override_references,
)
from app.services.config_loader_composable import load_composable_config
from app.services.file_generator import generate_files
from app.models.wizard import WizardConfig

# ── Discovery helpers ────────────────────────────────────────────────────────

_PROD_DATA_DIR = Path(__file__).parent / "wizard_configs"


def _discover_json_files(subdir: str) -> list[Path]:
    """Return all .json files under a subdirectory of production data."""
    d = _PROD_DATA_DIR / subdir
    if not d.exists():
        return []
    return sorted(p for p in d.glob("*.json") if not p.name.endswith(".backup"))


def _load_json(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return cast(dict[str, Any], json.load(f))


def _load_schema() -> dict[str, Any]:
    return _load_json(_PROD_DATA_DIR / "schema.json")


# ── Parametrised IDs ─────────────────────────────────────────────────────────

_language_files = _discover_json_files("languages")
_tool_files = _discover_json_files("tools")
_override_files = _discover_json_files("overrides")

_language_ids = [p.stem for p in _language_files]
_tool_ids = [p.stem for p in _tool_files]


# ── Schema validation ────────────────────────────────────────────────────────

class TestBaseSchemaConformance:
    """The base schema.json itself must be valid."""

    def test_schema_exists(self):
        assert (_PROD_DATA_DIR / "schema.json").exists(), "schema.json is missing"

    def test_schema_is_valid(self):
        data = _load_schema()
        validate_wizard_schema(data)

    def test_schema_has_steps(self):
        data = _load_schema()
        assert len(data.get("steps", [])) > 0, "schema.json must define at least one step"

    def test_every_step_has_id_and_title(self):
        data = _load_schema()
        for step in data["steps"]:
            assert "id" in step, f"Step missing 'id': {step}"
            assert "title" in step, f"Step {step.get('id')} missing 'title'"

    def test_every_step_has_at_least_one_field(self):
        data = _load_schema()
        for step in data["steps"]:
            fields = step.get("fields", [])
            assert len(fields) > 0, f"Step '{step['id']}' has no fields"


# ── Language conformance ─────────────────────────────────────────────────────

@pytest.mark.parametrize("lang_file", _language_files, ids=_language_ids)
class TestLanguageConformance:
    """Every language override file must conform to the standard."""

    def test_valid_json(self, lang_file: Path):
        """File must be parseable JSON."""
        _load_json(lang_file)

    def test_schema_valid(self, lang_file: Path):
        """File must pass the language override JSON schema."""
        data = _load_json(lang_file)
        validate_language_override(data)

    def test_has_language_id(self, lang_file: Path):
        """File must declare a language_id."""
        data = _load_json(lang_file)
        lid = data.get("language_id")
        assert lid, f"{lang_file.name} missing language_id"

    def test_language_id_matches_filename(self, lang_file: Path):
        """language_id must match the filename (without .json)."""
        data = _load_json(lang_file)
        assert data["language_id"] == lang_file.stem, (
            f"language_id '{data['language_id']}' does not match filename '{lang_file.stem}'"
        )

    def test_override_references_are_valid(self, lang_file: Path):
        """Every field_id and step_id must reference a real schema entry."""
        schema = _load_schema()
        data = _load_json(lang_file)
        warnings = validate_override_references(schema, data, lang_file.name)
        assert not warnings, "\n".join(warnings)

    def test_presets_have_label_and_value(self, lang_file: Path):
        """Every preset in field_overrides must have label and value."""
        data = _load_json(lang_file)
        for fo in data.get("field_overrides", []):
            for key in ("merge_presets", "replace_presets_with"):
                for preset in fo.get(key, []):
                    assert "label" in preset, (
                        f"{lang_file.name} field_override '{fo['field_id']}': preset missing 'label'"
                    )
                    assert "value" in preset, (
                        f"{lang_file.name} field_override '{fo['field_id']}': "
                        f"preset '{preset.get('label')}' missing 'value'"
                    )

    def test_metadata_overrides_use_valid_editability(self, lang_file: Path):
        """Editability values must be one of the allowed enum values."""
        data = _load_json(lang_file)
        allowed = {"free", "locked", "suggested", "defaulted"}
        for mo in data.get("metadata_overrides", []):
            edit = mo.get("editability")
            if edit is not None:
                assert edit in allowed, (
                    f"{lang_file.name} metadata_override '{mo['field_id']}': "
                    f"invalid editability '{edit}'"
                )


# ── Tool conformance ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("tool_file", _tool_files, ids=_tool_ids)
class TestToolConformance:
    """Every tool override file must conform to the standard."""

    def test_valid_json(self, tool_file: Path):
        _load_json(tool_file)

    def test_schema_valid(self, tool_file: Path):
        data = _load_json(tool_file)
        validate_tool_override(data)

    def test_has_tool_id(self, tool_file: Path):
        data = _load_json(tool_file)
        tid = data.get("tool_id")
        assert tid, f"{tool_file.name} missing tool_id"

    def test_tool_id_matches_filename(self, tool_file: Path):
        data = _load_json(tool_file)
        assert data["tool_id"] == tool_file.stem, (
            f"tool_id '{data['tool_id']}' does not match filename '{tool_file.stem}'"
        )

    def test_override_references_are_valid(self, tool_file: Path):
        schema = _load_schema()
        data = _load_json(tool_file)
        warnings = validate_override_references(schema, data, tool_file.name)
        assert not warnings, "\n".join(warnings)

    def test_presets_have_label_and_value(self, tool_file: Path):
        data = _load_json(tool_file)
        for fo in data.get("field_overrides", []):
            for key in ("merge_presets", "replace_presets_with"):
                for preset in fo.get(key, []):
                    assert "label" in preset, (
                        f"{tool_file.name} field_override '{fo['field_id']}': preset missing 'label'"
                    )
                    assert "value" in preset, (
                        f"{tool_file.name} field_override '{fo['field_id']}': "
                        f"preset '{preset.get('label')}' missing 'value'"
                    )

    def test_metadata_overrides_use_valid_editability(self, tool_file: Path):
        data = _load_json(tool_file)
        allowed = {"free", "locked", "suggested", "defaulted"}
        for mo in data.get("metadata_overrides", []):
            edit = mo.get("editability")
            if edit is not None:
                assert edit in allowed, (
                    f"{tool_file.name} metadata_override '{mo['field_id']}': "
                    f"invalid editability '{edit}'"
                )


# ── Override (combo) conformance ─────────────────────────────────────────────

@pytest.mark.parametrize(
    "override_file",
    _override_files,
    ids=[p.stem for p in _override_files],
)
class TestOverrideConformance:
    """Every tool+language combo override file must conform."""

    def test_schema_valid(self, override_file: Path):
        data = _load_json(override_file)
        validate_combo_override(data)

    def test_override_references_are_valid(self, override_file: Path):
        schema = _load_schema()
        data = _load_json(override_file)
        warnings = validate_override_references(schema, data, override_file.name)
        assert not warnings, "\n".join(warnings)


# ── Cross-cutting: composable loading ────────────────────────────────────────

_tool_language_combos = [
    (tool, lang)
    for tool in _tool_ids
    for lang in _language_ids
]


@pytest.mark.parametrize("tool,language", _tool_language_combos, ids=[f"{t}+{l}" for t, l in _tool_language_combos])
class TestComposableLoading:
    """Every tool × language combination must resolve without error."""

    def test_loads_without_error(self, tool: str, language: str):
        config = load_composable_config(tool, language)
        assert config is not None
        assert config.get("id") == tool

    def test_has_steps(self, tool: str, language: str):
        config = load_composable_config(tool, language)
        assert len(config.get("steps", [])) > 0

    def test_every_field_has_id_and_type(self, tool: str, language: str):
        config = load_composable_config(tool, language)
        for step in config["steps"]:
            for field in step.get("fields", []):
                assert "id" in field, f"Field in step '{step['id']}' missing 'id'"
                assert "type" in field, f"Field '{field.get('id')}' in step '{step['id']}' missing 'type'"


# ── Cross-cutting: file generation ───────────────────────────────────────────

@pytest.mark.parametrize("tool", _tool_ids)
class TestFileGeneration:
    """Every tool must generate at least one non-empty output file."""

    def test_generates_files(self, tool: str):
        raw = load_composable_config(tool, _language_ids[0] if _language_ids else "python")
        config = WizardConfig(**raw)
        files = generate_files(config, {})
        assert len(files) > 0, f"Tool '{tool}' generated no output files"

    def test_all_files_non_empty(self, tool: str):
        raw = load_composable_config(tool, _language_ids[0] if _language_ids else "python")
        config = WizardConfig(**raw)
        files = generate_files(config, {})
        for path, content in files.items():
            assert content.strip(), f"Tool '{tool}' generated empty file: {path}"
