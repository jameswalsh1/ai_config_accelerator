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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
