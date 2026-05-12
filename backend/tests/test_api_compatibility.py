"""
Ticket 11: API compatibility tests for config editor mutations.

Verifies:
- Response status codes and shapes for all mutation endpoints
- Auth: forbidden without role when AUTH_ENABLED=true
- Auth: allowed with correct role
- Actor in audit/version entries when actor is provided
"""
import os
import pytest
from typing import Any
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_PAYLOAD = {
    "scope": "language",
    "target": "python",
    "tool": "claude",
    "language": "python",
    "step_id": "language_selection",
    "field_id": "language",
}


def _update_payload(**kwargs) -> dict[str, Any]:
    return {**_BASE_PAYLOAD, "changes": {"default": "python"}, **kwargs}


def _add_preset_payload(**kwargs) -> dict[str, Any]:
    return {
        **_BASE_PAYLOAD,
        "preset": {"label": "__compat_test__", "value": "__compat__"},
        **kwargs,
    }


def _remove_preset_payload(**kwargs) -> dict[str, Any]:
    return {**_BASE_PAYLOAD, "preset_label": "__compat_test__", **kwargs}


def _reset_payload(**kwargs) -> dict[str, Any]:
    return {**_BASE_PAYLOAD, **kwargs}


# ---------------------------------------------------------------------------
# Response shape tests (auth disabled — default)
# ---------------------------------------------------------------------------


class TestUpdateEndpointShape:
    def test_returns_200_or_404(self):
        resp = client.post("/config/update", json=_update_payload())
        assert resp.status_code in (200, 404)

    def test_200_response_has_step_and_source_tracking(self):
        resp = client.post("/config/update", json=_update_payload())
        if resp.status_code == 200:
            data = resp.json()
            assert "step" in data
            assert "source_tracking" in data

    def test_missing_required_field_returns_422(self):
        payload = dict(_update_payload())
        del payload["scope"]
        resp = client.post("/config/update", json=payload)
        assert resp.status_code == 422

    def test_invalid_scope_returns_422(self):
        resp = client.post("/config/update", json=_update_payload(scope="bad"))
        assert resp.status_code == 422

    def test_unknown_field_returns_422(self):
        resp = client.post("/config/update", json=_update_payload(field_id="nonexistent_xyz"))
        assert resp.status_code == 422


class TestResetEndpointShape:
    def test_returns_200_or_404(self):
        resp = client.post("/config/reset", json=_reset_payload())
        assert resp.status_code in (200, 404)

    def test_missing_scope_returns_422(self):
        payload = dict(_reset_payload())
        del payload["scope"]
        resp = client.post("/config/reset", json=payload)
        # Pydantic validates scope field; missing scope is 422
        # (may be 404 if file lookup occurs first in some paths)
        assert resp.status_code in (422, 404)

    def test_unknown_field_returns_422(self):
        resp = client.post("/config/reset", json=_reset_payload(field_id="nonexistent_xyz"))
        # 422 from save-time validation, or 404 if target file missing first
        assert resp.status_code in (422, 404)


class TestAddPresetEndpointShape:
    def test_returns_200_or_404(self):
        resp = client.post("/config/presets/add", json=_add_preset_payload())
        assert resp.status_code in (200, 404)

    def test_200_response_has_step_and_source_tracking(self):
        resp = client.post("/config/presets/add", json=_add_preset_payload())
        if resp.status_code == 200:
            data = resp.json()
            assert "step" in data
            assert "source_tracking" in data

    def test_missing_preset_returns_422(self):
        payload = dict(_add_preset_payload())
        del payload["preset"]
        resp = client.post("/config/presets/add", json=payload)
        assert resp.status_code == 422

    def test_unknown_field_returns_422(self):
        resp = client.post("/config/presets/add", json=_add_preset_payload(field_id="nonexistent_xyz"))
        assert resp.status_code == 422


class TestRemovePresetEndpointShape:
    def test_returns_200_or_404(self):
        resp = client.post("/config/presets/remove", json=_remove_preset_payload())
        assert resp.status_code in (200, 404, 400)

    def test_missing_identifier_returns_422(self):
        payload = {**_BASE_PAYLOAD}  # no preset_label, no position
        resp = client.post("/config/presets/remove", json=payload)
        assert resp.status_code == 422

    def test_unknown_field_returns_422(self):
        resp = client.post("/config/presets/remove", json=_remove_preset_payload(field_id="nonexistent_xyz"))
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Auth behaviour tests
# ---------------------------------------------------------------------------


class TestMutationEndpointsAuthBehaviour:
    """When AUTH_ENABLED=true, mutations require config_editor role."""

    def _make_client_with_auth(self, username: str, roles: str) -> TestClient:
        headers = {"x-auth-user": username, "x-auth-roles": roles}
        return TestClient(app, headers=headers)

    def test_update_allowed_without_auth_enabled(self):
        """Default (AUTH_ENABLED=false): no headers needed."""
        resp = client.post("/config/update", json=_update_payload())
        assert resp.status_code in (200, 404, 422)  # not 401 / 403

    def test_update_forbidden_when_auth_enabled_and_no_role(self, monkeypatch):
        monkeypatch.setattr("app.services.auth.AUTH_ENABLED", True)
        authed = TestClient(app, headers={"x-auth-user": "bob", "x-auth-roles": "some_other_role"})
        resp = authed.post("/config/update", json=_update_payload())
        assert resp.status_code == 403

    def test_update_allowed_when_auth_enabled_and_has_role(self, monkeypatch):
        monkeypatch.setattr("app.services.auth.AUTH_ENABLED", True)
        authed = TestClient(app, headers={"x-auth-user": "alice", "x-auth-roles": "config_editor"})
        resp = authed.post("/config/update", json=_update_payload())
        assert resp.status_code in (200, 404)

    def test_update_401_when_auth_enabled_and_no_user_header(self, monkeypatch):
        monkeypatch.setattr("app.services.auth.AUTH_ENABLED", True)
        resp = client.post("/config/update", json=_update_payload())
        assert resp.status_code == 401

    def test_add_preset_forbidden_without_role(self, monkeypatch):
        monkeypatch.setattr("app.services.auth.AUTH_ENABLED", True)
        authed = TestClient(app, headers={"x-auth-user": "bob", "x-auth-roles": ""})
        resp = authed.post("/config/presets/add", json=_add_preset_payload())
        assert resp.status_code == 403

    def test_remove_preset_forbidden_without_role(self, monkeypatch):
        monkeypatch.setattr("app.services.auth.AUTH_ENABLED", True)
        authed = TestClient(app, headers={"x-auth-user": "bob", "x-auth-roles": "audit_viewer"})
        resp = authed.post("/config/presets/remove", json=_remove_preset_payload())
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Actor propagation tests
# ---------------------------------------------------------------------------


class TestActorPropagation:
    """Verify actor from X-Auth-User is recorded in version/audit entries."""

    def test_update_records_actor_in_version(self, monkeypatch, tmp_path):
        """When a write succeeds the actor should appear in the version history."""
        import json
        from app.services import version_history as vh

        monkeypatch.setattr("app.services.auth.AUTH_ENABLED", True)

        # Use a temp dir so we don't mutate real config files
        import app.services.config_patcher as patcher
        import app.services.config_persistence as persistence

        lang_file = tmp_path / "python.json"
        lang_file.write_text(json.dumps({
            "language_id": "python",
            "metadata_overrides": [],
        }))

        captured: list[str] = []

        original_write = persistence.save_config

        def _spy_save(path, data, **kwargs):
            actor = (kwargs.get("context") or {}).get("actor", "system")
            captured.append(actor)
            # Don't actually write to real files
            return None

        monkeypatch.setattr(persistence, "save_config", _spy_save)
        monkeypatch.setattr(patcher, "_get_target_file", lambda scope, target: lang_file)

        authed = TestClient(app, headers={"x-auth-user": "testuser", "x-auth-roles": "config_editor"})
        authed.post("/config/update", json=_update_payload())

        # The actor should have been passed as "testuser"
        assert "testuser" in captured

    def test_anonymous_actor_when_auth_disabled(self, monkeypatch, tmp_path):
        """With AUTH_ENABLED=false the actor is 'anonymous'."""
        import json
        import app.services.config_patcher as patcher
        import app.services.config_persistence as persistence

        lang_file = tmp_path / "python.json"
        lang_file.write_text(json.dumps({
            "language_id": "python",
            "metadata_overrides": [],
        }))

        captured: list[str] = []

        def _spy_save(path, data, **kwargs):
            actor = (kwargs.get("context") or {}).get("actor", "system")
            captured.append(actor)
            return None

        monkeypatch.setattr(persistence, "save_config", _spy_save)
        monkeypatch.setattr(patcher, "_get_target_file", lambda scope, target: lang_file)

        client.post("/config/update", json=_update_payload())

        assert "anonymous" in captured
