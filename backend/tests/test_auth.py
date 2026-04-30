"""Tests for the auth service and route-level authorisation dependencies."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.testclient import TestClient

from app.services.auth import (
    AUTH_ENABLED,
    ROLE_AUDIT_VIEWER,
    ROLE_CONFIG_EDITOR,
    AuthUser,
    _extract_user,
    get_current_user,
    require_audit_viewer,
    require_config_editor,
)


# ---------------------------------------------------------------------------
# AuthUser
# ---------------------------------------------------------------------------

class TestAuthUser:
    def test_has_role_true(self):
        user = AuthUser(username="alice", roles=frozenset({"admin", "config_editor"}))
        assert user.has_role("config_editor") is True

    def test_has_role_false(self):
        user = AuthUser(username="alice", roles=frozenset({"admin"}))
        assert user.has_role("config_editor") is False

    def test_frozen(self):
        user = AuthUser(username="alice", roles=frozenset())
        with pytest.raises(AttributeError):
            user.username = "bob"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _extract_user — auth disabled (default)
# ---------------------------------------------------------------------------

class TestExtractUserDisabled:
    """When AUTH_ENABLED=false every request gets the anonymous user."""

    def test_returns_anonymous(self, _fake_request):
        with patch("app.services.auth.AUTH_ENABLED", False):
            user = _extract_user(_fake_request())
            assert user.username == "anonymous"
            assert user.roles == frozenset()

    def test_ignores_headers(self, _fake_request):
        with patch("app.services.auth.AUTH_ENABLED", False):
            user = _extract_user(
                _fake_request(headers={"x-auth-user": "alice", "x-auth-roles": "admin"})
            )
            assert user.username == "anonymous"


# ---------------------------------------------------------------------------
# _extract_user — auth enabled
# ---------------------------------------------------------------------------

class TestExtractUserEnabled:
    """When AUTH_ENABLED=true headers are required."""

    def test_valid_headers(self, _fake_request):
        with patch("app.services.auth.AUTH_ENABLED", True):
            user = _extract_user(
                _fake_request(headers={
                    "x-auth-user": "alice",
                    "x-auth-roles": "config_editor, audit_viewer",
                })
            )
            assert user.username == "alice"
            assert user.roles == frozenset({"config_editor", "audit_viewer"})

    def test_missing_user_header_raises_401(self, _fake_request):
        with patch("app.services.auth.AUTH_ENABLED", True):
            with pytest.raises(HTTPException) as exc_info:
                _extract_user(_fake_request())
            assert exc_info.value.status_code == 401

    def test_empty_user_header_raises_401(self, _fake_request):
        with patch("app.services.auth.AUTH_ENABLED", True):
            with pytest.raises(HTTPException) as exc_info:
                _extract_user(_fake_request(headers={"x-auth-user": "  "}))
            assert exc_info.value.status_code == 401

    def test_no_roles_header_gives_empty_roles(self, _fake_request):
        with patch("app.services.auth.AUTH_ENABLED", True):
            user = _extract_user(
                _fake_request(headers={"x-auth-user": "bob"})
            )
            assert user.username == "bob"
            assert user.roles == frozenset()

    def test_roles_trimmed(self, _fake_request):
        with patch("app.services.auth.AUTH_ENABLED", True):
            user = _extract_user(
                _fake_request(headers={
                    "x-auth-user": "carol",
                    "x-auth-roles": " admin ,  config_editor ,",
                })
            )
            assert user.roles == frozenset({"admin", "config_editor"})


# ---------------------------------------------------------------------------
# require_config_editor
# ---------------------------------------------------------------------------

class TestRequireConfigEditor:
    def test_passes_when_disabled(self):
        with patch("app.services.auth.AUTH_ENABLED", False):
            user = AuthUser(username="anonymous", roles=frozenset())
            assert require_config_editor(user) is user

    def test_passes_with_role(self):
        with patch("app.services.auth.AUTH_ENABLED", True):
            user = AuthUser(username="alice", roles=frozenset({ROLE_CONFIG_EDITOR}))
            assert require_config_editor(user) is user

    def test_rejects_without_role(self):
        with patch("app.services.auth.AUTH_ENABLED", True):
            user = AuthUser(username="bob", roles=frozenset({"other"}))
            with pytest.raises(HTTPException) as exc_info:
                require_config_editor(user)
            assert exc_info.value.status_code == 403
            assert ROLE_CONFIG_EDITOR in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# require_audit_viewer
# ---------------------------------------------------------------------------

class TestRequireAuditViewer:
    def test_passes_when_disabled(self):
        with patch("app.services.auth.AUTH_ENABLED", False):
            user = AuthUser(username="anonymous", roles=frozenset())
            assert require_audit_viewer(user) is user

    def test_passes_with_role(self):
        with patch("app.services.auth.AUTH_ENABLED", True):
            user = AuthUser(username="alice", roles=frozenset({ROLE_AUDIT_VIEWER}))
            assert require_audit_viewer(user) is user

    def test_rejects_without_role(self):
        with patch("app.services.auth.AUTH_ENABLED", True):
            user = AuthUser(username="bob", roles=frozenset({"config_editor"}))
            with pytest.raises(HTTPException) as exc_info:
                require_audit_viewer(user)
            assert exc_info.value.status_code == 403
            assert ROLE_AUDIT_VIEWER in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# Integration: routes reject when auth is enabled without correct role
# ---------------------------------------------------------------------------

class TestRouteIntegration:
    """Verify the dependencies are actually wired into routes."""

    def test_config_edit_rejects_without_role(self):
        from app.main import app

        with patch("app.services.auth.AUTH_ENABLED", True):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                "/config/tools",
                headers={"x-auth-user": "bob", "x-auth-roles": "audit_viewer"},
            )
            assert resp.status_code == 403

    def test_config_edit_allows_with_role(self):
        from app.main import app

        with patch("app.services.auth.AUTH_ENABLED", True):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                "/config/tools",
                headers={"x-auth-user": "alice", "x-auth-roles": "config_editor"},
            )
            assert resp.status_code == 200

    def test_audit_rejects_without_role(self):
        from app.main import app

        with patch("app.services.auth.AUTH_ENABLED", True):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                "/config/audit",
                headers={"x-auth-user": "bob", "x-auth-roles": "config_editor"},
            )
            assert resp.status_code == 403

    def test_audit_allows_with_role(self):
        from app.main import app

        with patch("app.services.auth.AUTH_ENABLED", True):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                "/config/audit",
                headers={"x-auth-user": "alice", "x-auth-roles": "audit_viewer"},
            )
            assert resp.status_code == 200

    def test_all_routes_open_when_disabled(self):
        from app.main import app

        with patch("app.services.auth.AUTH_ENABLED", False):
            client = TestClient(app, raise_server_exceptions=False)
            # No auth headers at all
            assert client.get("/config/tools").status_code == 200
            assert client.get("/config/audit").status_code == 200


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def _fake_request():
    """Build a minimal fake Request with controllable headers."""

    class FakeRequest:
        def __init__(self, headers: dict[str, str] | None = None):
            self.headers = headers or {}

    def _factory(headers: dict[str, str] | None = None) -> FakeRequest:
        return FakeRequest(headers=headers)  # type: ignore[return-value]

    return _factory
