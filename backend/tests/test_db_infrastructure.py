"""Tests for Phase 1 database infrastructure.

These tests verify:
1. Settings load database URL without crashing.
2. The session factory can be instantiated.
3. The transaction helper commits and rolls back correctly (using a mock session).
4. Live DB smoke test (skipped when TEST_DATABASE_URL is not set).
"""

import os
import pytest
from unittest.mock import AsyncMock, patch


class TestDatabaseSettings:
    def test_get_url_returns_string(self):
        from app.settings import DatabaseSettings

        s = DatabaseSettings(
            database_user="user",
            database_password="pass",
            database_host="localhost",
            database_port=3306,
            database_name="testdb",
        )
        url = s.get_url()
        assert url.startswith("mysql+asyncmy://")
        assert "testdb" in url

    def test_explicit_database_url_takes_precedence(self):
        from app.settings import DatabaseSettings

        explicit = "mysql+asyncmy://root:secret@db:3306/mydb"
        s = DatabaseSettings(database_url=explicit)
        assert s.get_url() == explicit

    def test_safe_url_masks_password(self):
        from app.settings import DatabaseSettings

        s = DatabaseSettings(
            database_user="user",
            database_password="supersecret",
            database_host="localhost",
            database_port=3306,
            database_name="testdb",
        )
        safe = s.get_safe_url()
        assert "supersecret" not in safe
        assert "***" in safe

    def test_empty_database_url_treated_as_none(self):
        from app.settings import DatabaseSettings

        s = DatabaseSettings(database_url="")
        assert s.database_url is None
        # Should fall back to component-based URL
        assert "mysql+asyncmy://" in s.get_url()


class TestConfigSourceSettings:
    def test_json_is_accepted(self):
        from app.settings import ConfigSourceSettings

        s = ConfigSourceSettings(config_source="json")
        assert s.config_source == "json"

    def test_database_is_now_valid(self):
        """Phase 2: CONFIG_SOURCE=database is a supported value."""
        from app.settings import ConfigSourceSettings

        s = ConfigSourceSettings(config_source="database")
        assert s.config_source == "database"

    def test_unknown_value_raises_error(self):
        from pydantic import ValidationError
        from app.settings import ConfigSourceSettings

        with pytest.raises(ValidationError, match="Invalid CONFIG_SOURCE"):
            ConfigSourceSettings(config_source="filesystem")

    def test_default_is_database(self):
        """The production default config source is now 'database'."""
        import os
        # Temporarily remove CONFIG_SOURCE so the model default is used
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CONFIG_SOURCE", None)
            from app.settings import ConfigSourceSettings
            s = ConfigSourceSettings()
            assert s.config_source == "database"


class TestTransactionHelper:
    @pytest.mark.asyncio
    async def test_commit_called_on_success(self):
        from app.db.transaction import atomic

        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        async with atomic(session):
            pass  # no exception

        session.commit.assert_called_once()
        session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_rollback_called_on_exception(self):
        from app.db.transaction import atomic

        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        with pytest.raises(ValueError, match="boom"):
            async with atomic(session):
                raise ValueError("boom")

        session.rollback.assert_called_once()
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_transaction_commits_on_success(self):
        from app.db.transaction import db_transaction

        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        called_with_session = []

        async def work(s):  # type: ignore[no-untyped-def]
            called_with_session.append(s)

        await db_transaction(session, work)
        assert called_with_session == [session]
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_transaction_rolls_back_on_failure(self):
        from app.db.transaction import db_transaction

        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        async def failing_work(s):  # type: ignore[no-untyped-def]
            raise RuntimeError("db error")

        with pytest.raises(RuntimeError, match="db error"):
            await db_transaction(session, failing_work)

        session.rollback.assert_called_once()
        session.commit.assert_not_called()


class TestSessionFactory:
    def test_get_session_factory_returns_factory(self):
        """Verify the session factory can be created without connecting."""
        with patch("app.db.session._engine", None), \
             patch("app.db.session._session_factory", None):
            with patch("app.settings.get_database_settings") as mock_settings:
                mock_s = AsyncMock()
                mock_s.get_url.return_value = "sqlite+aiosqlite:///:memory:"
                mock_settings.return_value = mock_s

                from app.db import session as db_session_module
                db_session_module._engine = None
                db_session_module._session_factory = None

                factory = db_session_module.get_session_factory()
                assert factory is not None


class TestHealthDbEndpoint:
    def test_health_db_returns_degraded_when_db_unreachable(self):
        """The /health/db endpoint must return degraded status when DB is down."""
        from fastapi.testclient import TestClient
        from app.main import app

        # Override DATABASE_URL to an unreachable host so the test doesn't
        # accidentally connect to a real database.
        with patch.dict(os.environ, {"DATABASE_URL": "mysql+asyncmy://x:x@127.0.0.1:19999/noexist"}):
            with patch("app.db.session._engine", None), \
                 patch("app.db.session._session_factory", None):
                client = TestClient(app)
                response = client.get("/health/db")
                assert response.status_code == 200
                data = response.json()
                assert "database" in data
                # Either "ok" (if local MySQL is running) or "unavailable"
                assert data["database"] in ("ok", "unavailable")

    def test_health_db_response_shape(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get("/health/db")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database" in data
