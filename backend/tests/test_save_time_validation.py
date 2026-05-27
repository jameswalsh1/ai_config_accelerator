"""Tests for Ticket 9: Save-time validation of field and step references."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.config_validator import (
    SchemaValidationError,
    validate_field_id_exists,
    validate_step_id_exists,
)

client = TestClient(app)


class TestValidateStepIdExists:
    def test_valid_step_id_does_not_raise(self):
        # language_selection is a known step in schema.json
        validate_step_id_exists("language_selection")

    def test_invalid_step_id_raises(self):
        with pytest.raises(SchemaValidationError) as exc:
            validate_step_id_exists("nonexistent_step_xyz_abc")
        assert "nonexistent_step_xyz_abc" in str(exc.value)

    def test_error_lists_valid_step_ids(self):
        with pytest.raises(SchemaValidationError) as exc:
            validate_step_id_exists("bogus")
        assert "language_selection" in str(exc.value)


class TestValidateFieldIdExists:
    def test_valid_step_and_field_does_not_raise(self):
        validate_field_id_exists("language_selection", "language")

    def test_invalid_step_raises(self):
        with pytest.raises(SchemaValidationError) as exc:
            validate_field_id_exists("bogus_step", "language")
        assert "bogus_step" in str(exc.value)

    def test_invalid_field_raises(self):
        with pytest.raises(SchemaValidationError) as exc:
            validate_field_id_exists("language_selection", "nonexistent_field_xyz")
        assert "nonexistent_field_xyz" in str(exc.value)

    def test_error_for_invalid_field_lists_valid_fields(self):
        with pytest.raises(SchemaValidationError) as exc:
            validate_field_id_exists("language_selection", "bogus")
        assert "language_selection." in str(exc.value)


class TestUpdateEndpointSaveTimeValidation:
    """POST /config/update rejects unknown step/field references."""

    def test_invalid_step_id_returns_422(self):
        resp = client.post("/config/update", json={
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "nonexistent_step_xyz",
            "field_id": "language",
            "changes": {"default": "typescript"},
        })
        assert resp.status_code == 422
        assert "nonexistent_step_xyz" in resp.json()["detail"]

    def test_invalid_field_id_returns_422(self):
        resp = client.post("/config/update", json={
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "nonexistent_field_xyz",
            "changes": {"default": "typescript"},
        })
        assert resp.status_code == 422
        assert "nonexistent_field_xyz" in resp.json()["detail"]

    def test_valid_step_and_field_accepted(self):
        resp = client.post("/config/update", json={
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "language",
            "changes": {"default": "python"},
        })
        # Expect success or 404 (target not found), but NOT 422
        assert resp.status_code != 422


class TestAddPresetEndpointSaveTimeValidation:
    """POST /config/presets/add rejects unknown step/field references."""

    def test_invalid_step_id_returns_422(self):
        resp = client.post("/config/presets/add", json={
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "nonexistent_step_xyz",
            "field_id": "language",
            "preset": {"label": "Test", "value": "test"},
        })
        assert resp.status_code == 422

    def test_invalid_field_id_returns_422(self):
        resp = client.post("/config/presets/add", json={
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "nonexistent_field_xyz",
            "preset": {"label": "Test", "value": "test"},
        })
        assert resp.status_code == 422


class TestRemovePresetEndpointSaveTimeValidation:
    """POST /config/presets/remove rejects unknown step/field references."""

    def test_invalid_step_id_returns_422(self):
        resp = client.post("/config/presets/remove", json={
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "nonexistent_step_xyz",
            "field_id": "language",
            "preset_label": "Test",
        })
        assert resp.status_code == 422

    def test_invalid_field_id_returns_422(self):
        resp = client.post("/config/presets/remove", json={
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "nonexistent_field_xyz",
            "preset_label": "Test",
        })
        assert resp.status_code == 422
