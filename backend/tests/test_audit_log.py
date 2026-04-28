"""
Tests for the Audit Log Service (audit_log.py) and GET /config/audit endpoint.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.services.audit_log import (
    append_audit_entry,
    read_audit_log,
    build_audit_entry,
    LOG_PATH,
)
from app.services.config_persistence import save_config

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_audit_log(tmp_path, monkeypatch):
    """
    Redirect audit log writes to a temp file for every test.
    Prevents tests from writing to or reading from the real audit.jsonl.
    """
    tmp_log = tmp_path / "audit.jsonl"
    monkeypatch.setattr("app.services.audit_log.LOG_PATH", tmp_log)
    # Also patch within config_persistence's lazy import scope
    yield tmp_log


# ---------------------------------------------------------------------------
# Unit: append_audit_entry / read_audit_log
# ---------------------------------------------------------------------------


class TestAppendAndRead:
    def test_append_creates_file(self, isolated_audit_log):
        append_audit_entry({"event": "test"})
        assert isolated_audit_log.exists()

    def test_appended_entry_is_readable(self, isolated_audit_log):
        entry = {"timestamp": "2026-01-01T00:00:00Z", "action": "update", "scope": "language",
                 "target": "python", "file": "test.json", "actor": "system",
                 "diff_summary": "no changes", "diff": {}}
        append_audit_entry(entry)
        result = read_audit_log()
        assert result["total"] == 1
        assert result["entries"][0]["target"] == "python"

    def test_multiple_entries_returned_newest_first(self, isolated_audit_log):
        for i in range(3):
            append_audit_entry({"n": i})
        result = read_audit_log()
        assert result["total"] == 3
        # newest-first means last-appended is index 0
        assert result["entries"][0]["n"] == 2
        assert result["entries"][2]["n"] == 0

    def test_empty_log_returns_empty(self, isolated_audit_log):
        result = read_audit_log()
        assert result == {"entries": [], "total": 0}

    def test_missing_log_returns_empty(self, isolated_audit_log):
        # isolated_audit_log was never created
        result = read_audit_log()
        assert result == {"entries": [], "total": 0}

    def test_limit_paginates(self, isolated_audit_log):
        for i in range(10):
            append_audit_entry({"n": i})
        result = read_audit_log(limit=3)
        assert len(result["entries"]) == 3
        assert result["total"] == 10

    def test_offset_skips_entries(self, isolated_audit_log):
        for i in range(5):
            append_audit_entry({"n": i})
        result = read_audit_log(limit=10, offset=2)
        assert len(result["entries"]) == 3
        assert result["entries"][0]["n"] == 2  # newest-first, skipped 4 and 3

    def test_filter_by_scope(self, isolated_audit_log):
        append_audit_entry({"scope": "language", "target": "python"})
        append_audit_entry({"scope": "tool", "target": "claude"})
        result = read_audit_log(scope="language")
        assert result["total"] == 1
        assert result["entries"][0]["scope"] == "language"

    def test_filter_by_target(self, isolated_audit_log):
        append_audit_entry({"scope": "language", "target": "python"})
        append_audit_entry({"scope": "language", "target": "java"})
        result = read_audit_log(target="java")
        assert result["total"] == 1
        assert result["entries"][0]["target"] == "java"

    def test_malformed_line_is_skipped(self, isolated_audit_log):
        isolated_audit_log.write_text("NOT JSON\n{\"n\": 1}\n", encoding="utf-8")
        result = read_audit_log()
        assert result["total"] == 1
        assert result["entries"][0]["n"] == 1


# ---------------------------------------------------------------------------
# Unit: build_audit_entry
# ---------------------------------------------------------------------------


class TestBuildAuditEntry:
    def test_action_is_create_for_new_file(self, tmp_path):
        path = tmp_path / "languages" / "haskell.json"
        after = {"language_id": "haskell"}
        entry = build_audit_entry(file_path=path, before_data=None, after_data=after)
        assert entry["action"] == "create"

    def test_action_is_update_for_existing_file(self, tmp_path):
        path = tmp_path / "languages" / "python.json"
        entry = build_audit_entry(
            file_path=path,
            before_data={"language_id": "python"},
            after_data={"language_id": "python", "version": "2.0"},
        )
        assert entry["action"] == "update"

    def test_scope_inferred_from_path(self, tmp_path):
        path = tmp_path / "languages" / "python.json"
        entry = build_audit_entry(file_path=path, before_data=None, after_data={})
        assert entry["scope"] == "language"

    def test_scope_from_context_overrides_path(self, tmp_path):
        path = tmp_path / "languages" / "python.json"
        entry = build_audit_entry(
            file_path=path, before_data=None, after_data={},
            context={"scope": "tool", "target": "claude"}
        )
        assert entry["scope"] == "tool"
        assert entry["target"] == "claude"

    def test_target_inferred_from_file_stem(self, tmp_path):
        path = tmp_path / "tools" / "copilot.json"
        entry = build_audit_entry(file_path=path, before_data=None, after_data={})
        assert entry["target"] == "copilot"

    def test_entry_has_all_required_fields(self, tmp_path):
        path = tmp_path / "languages" / "python.json"
        entry = build_audit_entry(file_path=path, before_data=None, after_data={})
        for field in ("timestamp", "action", "scope", "target", "file", "actor", "diff_summary", "diff"):
            assert field in entry, f"Missing field: {field}"

    def test_actor_defaults_to_system(self, tmp_path):
        path = tmp_path / "languages" / "python.json"
        entry = build_audit_entry(file_path=path, before_data=None, after_data={})
        assert entry["actor"] == "system"

    def test_actor_from_context(self, tmp_path):
        path = tmp_path / "languages" / "python.json"
        entry = build_audit_entry(
            file_path=path, before_data=None, after_data={},
            context={"actor": "alice@example.com"}
        )
        assert entry["actor"] == "alice@example.com"

    def test_entry_is_json_serialisable(self, tmp_path):
        path = tmp_path / "languages" / "python.json"
        entry = build_audit_entry(file_path=path, before_data=None, after_data={"key": "value"})
        # Should not raise
        json.dumps(entry)


# ---------------------------------------------------------------------------
# Integration: save_config emits an audit entry
# ---------------------------------------------------------------------------


class TestSaveConfigEmitsAudit:
    def test_new_file_creates_audit_entry(self, tmp_path, isolated_audit_log):
        config_file = tmp_path / "languages" / "rust.json"
        data = {
            "language_id": "rust",
            "metadata_overrides": [{"field_id": "step.field", "default": "cargo"}],
        }
        save_config(config_file, data, validate=False, create_backup=False)

        result = read_audit_log()
        assert result["total"] == 1
        entry = result["entries"][0]
        assert entry["action"] == "create"
        assert entry["actor"] == "system"

    def test_update_creates_audit_entry(self, tmp_path, isolated_audit_log):
        config_file = tmp_path / "languages" / "rust.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        original = {"language_id": "rust", "version": "1.0"}
        config_file.write_text(json.dumps(original))

        updated = {"language_id": "rust", "version": "2.0"}
        save_config(config_file, updated, validate=False, create_backup=False)

        result = read_audit_log()
        assert result["total"] == 1
        assert result["entries"][0]["action"] == "update"

    def test_context_scope_target_in_entry(self, tmp_path, isolated_audit_log):
        config_file = tmp_path / "test.json"
        save_config(
            config_file,
            {"language_id": "rust"},
            validate=False,
            create_backup=False,
            context={"scope": "language", "target": "rust"},
        )
        result = read_audit_log()
        entry = result["entries"][0]
        assert entry["scope"] == "language"
        assert entry["target"] == "rust"

    def test_audit_failure_does_not_block_save(self, tmp_path, isolated_audit_log):
        config_file = tmp_path / "languages" / "kotlin.json"
        data = {"language_id": "kotlin", "metadata_overrides": []}

        with patch("app.services.audit_log.append_audit_entry", side_effect=OSError("disk full")):
            # Must complete without raising despite audit failure
            save_config(config_file, data, validate=False, create_backup=False)

        assert config_file.exists()
        saved = json.loads(config_file.read_text())
        assert saved["language_id"] == "kotlin"


# ---------------------------------------------------------------------------
# API: GET /config/audit
# ---------------------------------------------------------------------------


class TestAuditEndpoint:
    def test_returns_200(self):
        response = client.get("/config/audit")
        assert response.status_code == 200

    def test_returns_expected_shape(self):
        response = client.get("/config/audit")
        data = response.json()
        assert "entries" in data
        assert "total" in data
        assert isinstance(data["entries"], list)
        assert isinstance(data["total"], int)

    def test_limit_query_param(self):
        response = client.get("/config/audit?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["entries"]) <= 5

    def test_scope_filter(self):
        response = client.get("/config/audit?scope=language")
        assert response.status_code == 200
        data = response.json()
        for entry in data["entries"]:
            assert entry.get("scope") == "language"

    def test_invalid_limit_rejected(self):
        response = client.get("/config/audit?limit=0")
        assert response.status_code == 422

    def test_limit_above_500_rejected(self):
        response = client.get("/config/audit?limit=501")
        assert response.status_code == 422
