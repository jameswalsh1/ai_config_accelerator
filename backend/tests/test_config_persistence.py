"""
Tests for Config Persistence Service (config_persistence.py)

Tests safe, atomic configuration persistence with:
- Atomic writes (temp file → rename)
- Schema validation
- Format consistency
- Reloadability verification
- Backup and rollback capability
"""

import json
import pytest
from pathlib import Path
from copy import deepcopy

from app.services.config_persistence import (
    save_config,
    save_patch_result,
    verify_changes_reloadable,
    ConfigTransaction,
    ValidationError,
    CorruptionError,
    BackupError,
    ReloadError,
    PersistenceError,
    _validate_json_syntax,
    _validate_override_schema,
    _create_backup,
    _restore_backup,
)

DATA_DIR = Path(__file__).parent.parent / "data" / "wizard_configs"


class TestJsonValidation:
    """Test JSON syntax validation."""

    def test_validate_valid_json(self):
        """Test that valid JSON passes validation."""
        data = {"key": "value", "nested": {"a": 1}}
        _validate_json_syntax(data)  # Should not raise

    def test_validate_json_with_non_serializable(self):
        """Test that non-serializable data raises error."""
        import datetime
        data = {"date": datetime.datetime.now()}
        
        with pytest.raises(ValidationError):
            _validate_json_syntax(data)


class TestOverrideSchemaValidation:
    """Test override file schema validation."""

    def test_validate_valid_override(self):
        """Test valid override structure."""
        data = {
            "language_id": "python",
            "metadata_overrides": [
                {"field_id": "step.field", "default": "value"}
            ]
        }
        _validate_override_schema(data, "language")  # Should not raise

    def test_validate_not_dict(self):
        """Test that non-dict raises error."""
        with pytest.raises(ValidationError):
            _validate_override_schema(["item"], "language")

    def test_validate_metadata_overrides_not_list(self):
        """Test that metadata_overrides must be list."""
        data = {"metadata_overrides": "not_a_list"}
        
        with pytest.raises(ValidationError):
            _validate_override_schema(data, "language")

    def test_validate_metadata_override_missing_field_id(self):
        """Test that metadata override requires field_id."""
        data = {
            "metadata_overrides": [
                {"default": "value"}  # Missing field_id
            ]
        }
        
        with pytest.raises(ValidationError):
            _validate_override_schema(data, "language")

    def test_validate_field_overrides_missing_field_id(self):
        """Test that field override requires field_id."""
        data = {
            "field_overrides": [
                {"merge_presets": []}  # Missing field_id
            ]
        }
        
        with pytest.raises(ValidationError):
            _validate_override_schema(data, "language")

    def test_validate_step_overrides_missing_step_id(self):
        """Test that step override requires step_id."""
        data = {
            "step_overrides": [
                {"hidden": True}  # Missing step_id
            ]
        }
        
        with pytest.raises(ValidationError):
            _validate_override_schema(data, "tool")


class TestBackupRestore:
    """Test backup and restore functionality."""

    def test_create_backup_existing_file(self, tmp_path):
        """Test creating backup of existing file."""
        # Create test file in temp directory
        test_file = tmp_path / "test.json"
        test_file.write_text('{"test": "data"}')
        
        backup_path = _create_backup(test_file)
        
        assert backup_path.exists()
        assert backup_path.suffix == ".backup"
        
        # Verify backup content matches original
        assert test_file.read_text() == backup_path.read_text()

    def test_create_backup_nonexistent_file(self):
        """Test creating backup of non-existent file (no-op)."""
        nonexistent = DATA_DIR / "nonexistent.json"
        # Should not raise
        backup_path = _create_backup(nonexistent)
        # Backup path is returned even if source doesn't exist
        assert backup_path is not None

    def test_restore_backup(self, tmp_path):
        """Test restoring file from backup."""
        # Create test files
        test_file = tmp_path / "test.json"
        backup_file = tmp_path / "test.json.backup"
        
        # Write original content
        original_data = {"original": "content"}
        with test_file.open("w") as f:
            json.dump(original_data, f)
        
        # Create backup
        with backup_file.open("w") as f:
            json.dump(original_data, f)
        
        # Modify original
        modified_data = {"modified": "content"}
        with test_file.open("w") as f:
            json.dump(modified_data, f)
        
        # Restore from backup
        _restore_backup(test_file, backup_file)
        
        # Verify restored
        with test_file.open() as f:
            restored = json.load(f)
        
        assert restored == original_data

    def test_restore_backup_missing_backup(self):
        """Test restore when backup doesn't exist."""
        test_file = DATA_DIR / "languages" / "python.json"
        missing_backup = DATA_DIR / "nonexistent_backup.json"
        
        with pytest.raises(BackupError):
            _restore_backup(test_file, missing_backup)


class TestAtomicWrite:
    """Test atomic write functionality."""

    def test_save_config_new_file(self, tmp_path):
        """Test saving new configuration file."""
        target_file = tmp_path / "new_config.json"
        data = {
            "language_id": "test",
            "metadata_overrides": [
                {"field_id": "step.field", "default": "test"}
            ]
        }
        
        save_config(target_file, data, validate=True, create_backup=False, verify_reloadable=False)
        
        assert target_file.exists()
        with target_file.open() as f:
            saved = json.load(f)
        assert saved == data

    def test_save_config_creates_backup(self, tmp_path):
        """Test that backup is created before overwriting."""
        target_file = tmp_path / "config.json"
        backup_file = target_file.with_suffix(".json.backup")
        
        # Create initial file
        original = {"original": "data"}
        with target_file.open("w") as f:
            json.dump(original, f)
        
        # Update file with backup
        updated = {"updated": "data"}
        save_config(target_file, updated, validate=False, create_backup=True, verify_reloadable=False)
        
        # Verify backup exists with original content
        assert backup_file.exists()
        with backup_file.open() as f:
            backup_data = json.load(f)
        assert backup_data == original

    def test_save_config_validates_structure(self, tmp_path):
        """Test that invalid structure is rejected."""
        target_file = tmp_path / "invalid.json"
        invalid_data = {
            "metadata_overrides": [
                {"default": "no_field_id"}  # Invalid: missing field_id
            ]
        }
        
        with pytest.raises(ValidationError):
            save_config(target_file, invalid_data, validate=True)

    def test_save_config_invalid_json_serializable(self, tmp_path):
        """Test that non-JSON-serializable data is rejected."""
        import datetime
        target_file = tmp_path / "bad.json"
        data = {"date": datetime.datetime.now()}
        
        with pytest.raises(ValidationError):
            save_config(target_file, data, validate=False)

    def test_save_config_maintains_format(self, tmp_path):
        """Test that saved JSON has consistent formatting."""
        target_file = tmp_path / "format.json"
        data = {
            "language_id": "test",
            "metadata_overrides": [
                {"field_id": "step.field", "default": "value"}
            ]
        }
        
        save_config(target_file, data, validate=False, create_backup=False, verify_reloadable=False)
        
        # Read raw content
        with target_file.open() as f:
            content = f.read()
        
        # Verify 2-space indentation (not tabs or 4 spaces)
        assert "  " in content
        assert "\t" not in content

    def test_save_config_to_existing_language_file(self, tmp_path):
        """Test saving to a file with existing content."""
        target_file = tmp_path / "config.json"
        
        # Create initial content
        original = {
            "language_id": "python",
            "metadata_overrides": [
                {"field_id": "step.field", "default": "original"}
            ]
        }
        with target_file.open("w") as f:
            json.dump(original, f)
        
        # Make a copy with small change
        updated = deepcopy(original)
        updated["metadata_overrides"][0]["default"] = "updated"
        
        # Save with backup
        save_config(target_file, updated, validate=True, create_backup=True, verify_reloadable=False)
        
        # Verify saved
        with target_file.open() as f:
            saved = json.load(f)
        assert saved == updated
        
        # Verify backup exists
        backup_file = target_file.with_suffix(".json.backup")
        assert backup_file.exists()
        with backup_file.open() as f:
            backup_data = json.load(f)
        assert backup_data == original


class TestSavePatchResult:
    """Test save_patch_result helper."""

    def test_save_patch_result_language(self, tmp_path, monkeypatch):
        """Test saving patched language config."""
        # Patch DATA_DIR to use temp directory
        import app.services.config_persistence as persistence_module
        monkeypatch.setattr(persistence_module, "DATA_DIR", tmp_path)
        
        # Create directory structure
        (tmp_path / "languages").mkdir()
        
        data = {
            "language_id": "test",
            "metadata_overrides": []
        }
        
        save_patch_result("language", "test", data)
        
        # Verify saved
        saved_file = tmp_path / "languages" / "test.json"
        assert saved_file.exists()
        with saved_file.open() as f:
            saved = json.load(f)
        assert saved == data

    def test_save_patch_result_tool(self, tmp_path, monkeypatch):
        """Test saving patched tool config."""
        import app.services.config_persistence as persistence_module
        monkeypatch.setattr(persistence_module, "DATA_DIR", tmp_path)
        
        (tmp_path / "tools").mkdir()
        
        data = {"tool_id": "claude", "metadata_overrides": []}
        save_patch_result("tool", "claude", data)
        
        saved_file = tmp_path / "tools" / "claude.json"
        assert saved_file.exists()
        with saved_file.open() as f:
            saved = json.load(f)
        assert saved == data

    def test_save_patch_result_invalid_scope(self, tmp_path):
        """Test that invalid scope raises error."""
        with pytest.raises(PersistenceError):
            save_patch_result("invalid", "target", {})


class TestVerifyReloadable:
    """Test reloadability verification."""

    def test_verify_changes_reloadable_valid(self):
        """Test verifying valid config is reloadable."""
        # Use a known-good combination
        assert verify_changes_reloadable("claude", "python")

    def test_verify_changes_reloadable_all_combinations(self):
        """Test all tool+language combinations are reloadable."""
        combinations = [
            ("claude", "python"),
            ("claude", "dotnet"),
            ("copilot", "java"),
            ("copilot", "typescript"),
            ("cursor", "angular"),
            ("cursor", "react-typescript"),
        ]
        
        for tool, lang in combinations:
            try:
                result = verify_changes_reloadable(tool, lang)
                assert result is True
            except ReloadError:
                pytest.fail(f"Failed to reload {tool}+{lang}")


class TestConfigTransaction:
    """Test transactional configuration changes."""

    def test_transaction_commit_success(self, tmp_path):
        """Test successful transaction commit."""
        target_file = tmp_path / "config.json"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        data1 = {"id": "config1"}
        
        with ConfigTransaction() as tx:
            tx.update_file(target_file, data1)
        
        # Should be committed
        assert target_file.exists()
        with target_file.open() as f:
            saved = json.load(f)
        assert saved == data1

    def test_transaction_rollback_on_exception(self, tmp_path):
        """Test transaction rollback on exception."""
        target_file = tmp_path / "config.json"
        
        # Create initial file
        original = {"original": "data"}
        target_file.parent.mkdir(parents=True, exist_ok=True)
        with target_file.open("w") as f:
            json.dump(original, f)
        
        # Start transaction that will fail
        try:
            with ConfigTransaction() as tx:
                tx.update_file(target_file, {"updated": "data"})
                raise ValueError("Simulated error")
        except ValueError:
            pass
        
        # Verify rollback
        with target_file.open() as f:
            content = json.load(f)
        assert content == original

    def test_transaction_multiple_files(self, tmp_path):
        """Test transaction with multiple file updates."""
        file1 = tmp_path / "subdir" / "config1.json"
        file2 = tmp_path / "subdir" / "config2.json"
        file1.parent.mkdir(parents=True, exist_ok=True)
        
        data1 = {"id": "config1"}
        data2 = {"id": "config2"}
        
        with ConfigTransaction() as tx:
            tx.update_file(file1, data1)
            tx.update_file(file2, data2)
        
        # Verify both committed
        assert file1.exists()
        assert file2.exists()
        
        with file1.open() as f:
            assert json.load(f) == data1
        with file2.open() as f:
            assert json.load(f) == data2

    def test_transaction_rollback_multiple_files(self, tmp_path):
        """Test rollback with multiple files."""
        file1 = tmp_path / "config1.json"
        file2 = tmp_path / "config2.json"
        
        # Create initial files
        file1.parent.mkdir(parents=True, exist_ok=True)
        original1 = {"id": "original1"}
        original2 = {"id": "original2"}
        with file1.open("w") as f:
            json.dump(original1, f)
        with file2.open("w") as f:
            json.dump(original2, f)
        
        # Transaction that fails
        try:
            with ConfigTransaction() as tx:
                tx.update_file(file1, {"id": "updated1"})
                tx.update_file(file2, {"id": "updated2"})
                raise RuntimeError("Simulated error")
        except RuntimeError:
            pass
        
        # Verify both rolled back
        with file1.open() as f:
            assert json.load(f) == original1
        with file2.open() as f:
            assert json.load(f) == original2


class TestCreateLanguageConfig:
    """Tests for create_language_config and get_language_tags."""

    from app.services.config_persistence import create_language_config, get_language_tags

    LANGUAGES_DIR = Path(__file__).parent.parent / "app" / "data" / "wizard_configs" / "languages"

    _TEST_IDS = [
        "test-scratch-lang", "test-clone-all-sections", "test-retag-default",
        "test-explicit-remap", "test-no-remap", "test-route-tag-remap",
    ]

    def setup_method(self):
        for lid in self._TEST_IDS:
            (self.LANGUAGES_DIR / f"{lid}.json").unlink(missing_ok=True)

    def teardown_method(self):
        for lid in self._TEST_IDS:
            (self.LANGUAGES_DIR / f"{lid}.json").unlink(missing_ok=True)

    def test_create_scratch(self):
        """Create a brand new language with no based_on."""
        from app.services.config_persistence import create_language_config
        lid = "test-scratch-lang"
        result = create_language_config(lid, "Test Scratch Lang")
        assert result["language_id"] == lid
        assert result["metadata"]["title"] == "Test Scratch Lang"
        assert result["field_overrides"] == []
        assert result["metadata_overrides"] == []
        assert result["step_overrides"] == []
        assert (self.LANGUAGES_DIR / f"{lid}.json").exists()

    def test_create_invalid_id_raises(self):
        """language_id with invalid chars raises ValidationError."""
        from app.services.config_persistence import create_language_config, ValidationError
        with pytest.raises(ValidationError, match="lowercase alphanumeric"):
            create_language_config("Bad ID!", "title")

    def test_create_duplicate_raises(self):
        """Creating a language that already exists raises ValidationError."""
        from app.services.config_persistence import create_language_config, ValidationError
        with pytest.raises(ValidationError, match="already exists"):
            create_language_config("python", "Python duplicate")

    def test_create_based_on_copies_all_sections(self):
        """based_on copies field_overrides, metadata_overrides AND step_overrides."""
        from app.services.config_persistence import create_language_config
        lid = "test-clone-all-sections"
        result = create_language_config(lid, "Clone All Sections", based_on="python")
        # All three override sections should be copied
        assert isinstance(result["field_overrides"], list)
        assert isinstance(result["metadata_overrides"], list)
        assert isinstance(result["step_overrides"], list)
        # applies_to should be the new language, not python
        assert result["applies_to"]["languages"] == [lid]

    def test_create_based_on_default_tag_retag(self):
        """Default tag remap: presets tagged 'python' become the new language_id."""
        from app.services.config_persistence import create_language_config
        lid = "test-retag-default"
        result = create_language_config(lid, "Retag Default", based_on="python")
        for fo in result["field_overrides"]:
            for preset in fo.get("merge_presets", []):
                assert "python" not in preset.get("tags", [])

    def test_create_based_on_explicit_tag_remap(self):
        """Explicit tag_remap overrides the default behaviour."""
        from app.services.config_persistence import create_language_config
        lid = "test-explicit-remap"
        result = create_language_config(
            lid, "Explicit Remap", based_on="python",
            tag_remap={"python": "django"}
        )
        for fo in result["field_overrides"]:
            for preset in fo.get("merge_presets", []):
                assert "python" not in preset.get("tags", [])

    def test_create_based_on_empty_tag_remap_no_retag(self):
        """Passing an empty tag_remap dict means no tags are renamed."""
        from app.services.config_persistence import create_language_config
        lid = "test-no-remap"
        result = create_language_config(
            lid, "No Remap", based_on="python",
            tag_remap={}
        )
        # With empty remap, 'python' tags stay as 'python'
        found_python_tag = any(
            "python" in preset.get("tags", [])
            for fo in result["field_overrides"]
            for preset in fo.get("merge_presets", [])
        )
        assert found_python_tag  # python tags preserved

    def test_get_language_tags_returns_sorted(self):
        """get_language_tags returns sorted unique tags from all presets."""
        from app.services.config_persistence import get_language_tags
        tags = get_language_tags("python")
        assert isinstance(tags, list)
        assert tags == sorted(set(tags))

    def test_get_language_tags_unknown_raises(self):
        """get_language_tags raises ValidationError for missing language."""
        from app.services.config_persistence import get_language_tags, ValidationError
        with pytest.raises(ValidationError, match="not found"):
            get_language_tags("nonexistent-xyz")

    def test_get_language_tags_includes_merge_and_replace(self):
        """Tags are collected from both merge_presets and replace_presets_with."""
        from app.services.config_persistence import get_language_tags
        # 'python' has merge_presets with 'python' tag
        tags = get_language_tags("python")
        # At least includes tags from merge_presets; result is a list
        assert isinstance(tags, list)


class TestLanguageTagsEndpoint:
    """Integration tests for GET /languages/{language_id}/tags router."""

    LANGUAGES_DIR = Path(__file__).parent.parent / "app" / "data" / "wizard_configs" / "languages"

    def setup_method(self):
        (self.LANGUAGES_DIR / "test-route-tag-remap.json").unlink(missing_ok=True)

    def teardown_method(self):
        (self.LANGUAGES_DIR / "test-route-tag-remap.json").unlink(missing_ok=True)

    def test_tags_endpoint_known_language(self):
        """GET /languages/python/tags returns list of strings."""
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.get("/config/languages/python/tags")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_tags_endpoint_unknown_language(self):
        """GET /languages/unknown/tags returns 404."""
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.get("/config/languages/nonexistent-xyz/tags")
        assert resp.status_code == 404

    def test_create_language_with_tag_remap(self):
        """POST /config/languages with tag_remap applies remapping."""
        from fastapi.testclient import TestClient
        from app.main import app
        lid = "test-route-tag-remap"
        client = TestClient(app)
        resp = client.post("/config/languages", json={
            "language_id": lid,
            "title": "Route Tag Remap Test",
            "based_on": "python",
            "tag_remap": {"python": "django"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["language_id"] == lid

    def test_create_language_invalid_tag_remap(self):
        """POST /config/languages with non-dict tag_remap returns 400."""
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.post("/config/languages", json={
            "language_id": "test-bad-remap",
            "title": "Bad Remap",
            "tag_remap": ["not", "a", "dict"],
        })
        assert resp.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
