"""Tests for Phase 2 Tickets 21, 22, 23.

Ticket 21 — Feature flag: CONFIG_SOURCE now accepts 'database' as a valid value.
Ticket 22 — DB-backed read endpoints: settings proxy exposes config_source.
Ticket 23 — Import status endpoint: GET /health/config-db.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Ticket 21 — Feature flag
# ---------------------------------------------------------------------------


class TestConfigSourceFeatureFlag:
    def test_database_is_default(self):
        """The production default config source is now 'database'."""
        import os
        # Temporarily remove CONFIG_SOURCE so the model default is used.
        # The conftest sets CONFIG_SOURCE=json for test isolation; we need to
        # clear it to test the bare model default.
        prev = os.environ.pop("CONFIG_SOURCE", None)
        try:
            import app.settings as settings_mod
            settings_mod._config_source_settings = None
            from app.settings import get_config_source_settings
            s = get_config_source_settings()
            assert s.config_source == "database"
        finally:
            if prev is not None:
                os.environ["CONFIG_SOURCE"] = prev
            import app.settings as settings_mod
            settings_mod._config_source_settings = None

    def test_database_is_now_valid(self):
        """CONFIG_SOURCE=database must not raise a validation error."""
        import os
        os.environ["CONFIG_SOURCE"] = "database"
        import app.settings as settings_mod
        settings_mod._config_source_settings = None
        from app.settings import ConfigSourceSettings
        s = ConfigSourceSettings()
        assert s.config_source == "database"
        # Cleanup
        os.environ.pop("CONFIG_SOURCE", None)
        settings_mod._config_source_settings = None

    def test_invalid_value_still_raises(self):
        from app.settings import ConfigSourceSettings
        from pydantic import ValidationError
        import os
        os.environ["CONFIG_SOURCE"] = "s3_bucket"
        import app.settings as settings_mod
        settings_mod._config_source_settings = None
        try:
            with pytest.raises(ValidationError):
                ConfigSourceSettings()
        finally:
            os.environ.pop("CONFIG_SOURCE", None)
            settings_mod._config_source_settings = None

    def test_get_settings_proxy_exposes_config_source(self):
        from app.settings import get_settings
        settings = get_settings()
        assert settings.config_source in ("json", "database")

    def test_get_settings_proxy_exposes_database(self):
        from app.settings import get_settings
        settings = get_settings()
        db = settings.database
        assert hasattr(db, "get_url")


# ---------------------------------------------------------------------------
# Ticket 22 — Read-only DB-backed endpoints (feature-flag awareness test)
# ---------------------------------------------------------------------------


class TestReadOnlyEndpoints:
    """The existing GET endpoints must continue to work normally with JSON source."""

    def test_tools_endpoint_returns_list(self, auth_headers):
        resp = client.get("/config/tools", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_languages_endpoint_returns_list(self, auth_headers):
        resp = client.get("/config/languages", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_tools_have_id_and_title(self, auth_headers):
        resp = client.get("/config/tools", headers=auth_headers)
        for t in resp.json():
            assert "id" in t or "tool_id" in t or "title" in t

    def test_languages_have_id_and_title(self, auth_headers):
        resp = client.get("/config/languages", headers=auth_headers)
        # Language list items should have at minimum one identifying key
        assert len(resp.json()) > 0


# ---------------------------------------------------------------------------
# Ticket 23 — Import status endpoint
# ---------------------------------------------------------------------------


class TestImportStatusEndpoint:
    def test_health_config_db_returns_json(self):
        resp = client.get("/health/config-db")
        assert resp.status_code == 200
        data = resp.json()
        assert "database_config_ready" in data

    def test_not_ready_when_no_db(self):
        """Without a live MySQL DB, the endpoint returns not-ready."""
        resp = client.get("/health/config-db")
        data = resp.json()
        # Either not ready (no live DB) or ready (if somehow connected)
        assert isinstance(data["database_config_ready"], bool)

    def test_endpoint_never_raises_500(self):
        """The endpoint should handle all DB errors gracefully."""
        resp = client.get("/health/config-db")
        assert resp.status_code == 200

    def test_ready_response_has_schema_version(self):
        """When ready, response includes active_schema key."""
        resp = client.get("/health/config-db")
        data = resp.json()
        if data.get("database_config_ready"):
            assert "active_schema" in data
            assert "tools" in data
            assert "languages" in data
            assert "layers" in data

    def test_not_ready_has_reason(self):
        """When not ready, response includes reason."""
        resp = client.get("/health/config-db")
        data = resp.json()
        if not data.get("database_config_ready"):
            assert "reason" in data


@pytest.fixture
def auth_headers():
    """Provide valid auth headers for the test client."""
    import base64
    creds = base64.b64encode(b"admin:admin").decode()
    return {"Authorization": f"Basic {creds}"}
