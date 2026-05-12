import os
from pydantic import field_validator
from pydantic_settings import BaseSettings


def _build_cors_regex() -> str:
    """Build CORS origin regex from environment.

    In production set ALLOWED_ORIGIN to your domain, e.g. https://example.com
    Multiple origins can be separated by commas.
    Falls back to localhost-only when not set.
    """
    raw = os.getenv("ALLOWED_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()]

    if not origins:
        return r"http://localhost(:\d+)?"

    escaped = [o.replace(".", r"\.").replace("://", r"://") for o in origins]
    return "^(" + "|".join(escaped) + ")$"


CORS_ORIGIN_REGEX: str = _build_cors_regex()


class DatabaseSettings(BaseSettings):
    """Database connection settings.

    The DATABASE_URL environment variable takes precedence. If it is not
    set, individual component variables are used to build the URL.

    Sensitive values are never logged — only the sanitised URL (with
    password replaced by ***) is safe to log.
    """

    database_url: str | None = None
    database_host: str = "localhost"
    database_port: int = 3306
    database_name: str = "ai_config_wizard"
    database_user: str = "ai_config_user"
    database_password: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("database_url", mode="before")
    @classmethod
    def _database_url_not_empty(cls, v: str | None) -> str | None:
        if v == "":
            return None
        return v

    def get_url(self) -> str:
        """Return the fully-qualified async MySQL URL."""
        if self.database_url:
            return self.database_url
        return (
            f"mysql+asyncmy://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )

    def get_safe_url(self) -> str:
        """Return the connection URL with the password replaced by *** — safe to log."""
        url = self.get_url()
        if self.database_password and self.database_password in url:
            return url.replace(self.database_password, "***")
        return url


class ConfigSourceSettings(BaseSettings):
    """Controls which backend the config system reads from.

    Allowed values:
      - ``json``     — read from JSON files on disk (default)
      - ``database`` — read from the relational database (Phase 2)
    """

    config_source: str = "database"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("config_source", mode="before")
    @classmethod
    def _validate_source(cls, v: str) -> str:
        allowed = {"json", "database"}
        if v not in allowed:
            raise ValueError(
                f"Invalid CONFIG_SOURCE '{v}'. Allowed values: {', '.join(sorted(allowed))}"
            )
        return v


# Module-level singletons — evaluated lazily so tests can patch env before import.
_db_settings: DatabaseSettings | None = None
_config_source_settings: ConfigSourceSettings | None = None


def get_database_settings() -> DatabaseSettings:
    global _db_settings
    if _db_settings is None:
        _db_settings = DatabaseSettings()
    return _db_settings


def get_config_source_settings() -> ConfigSourceSettings:
    global _config_source_settings
    if _config_source_settings is None:
        _config_source_settings = ConfigSourceSettings()
    return _config_source_settings


class _SettingsProxy:
    """Thin proxy so ``get_settings().database.url`` works in the import command."""

    @property
    def database(self) -> DatabaseSettings:
        return get_database_settings()

    @property
    def config_source(self) -> str:
        return get_config_source_settings().config_source


def get_settings() -> _SettingsProxy:  # noqa: D401
    """Return a proxy exposing ``database`` and ``config_source`` attributes."""
    return _SettingsProxy()

