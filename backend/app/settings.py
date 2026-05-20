import os
import ssl
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

    # SSL — set DB_SSL_CA to the path of the CA certificate file for full
    # verification (recommended for Azure Database for MySQL).  Set
    # DB_SSL_MODE=REQUIRED to enforce encryption without cert verification.
    db_ssl_ca: str | None = None
    db_ssl_mode: str = "DISABLED"

    # Connection pool — tune these for the Azure MySQL SKU in use.
    db_pool_size: int = 10
    db_pool_max_overflow: int = 20
    db_pool_recycle: int = 1800  # seconds; avoids stale connections on Azure

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

    def get_connect_args(self) -> dict:
        """Return SSL connect_args for the async engine.

        - DB_SSL_CA set: full certificate verification using the supplied CA file.
        - DB_SSL_MODE=REQUIRED/VERIFY_CA/VERIFY_IDENTITY (no CA file): TLS
          required but without CA verification — still encrypts traffic.
        - Default (DISABLED): no SSL; suitable for local development only.
        """
        if self.db_ssl_ca:
            ctx = ssl.create_default_context(cafile=self.db_ssl_ca)
            return {"ssl": ctx}
        if self.db_ssl_mode.upper() in ("REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY"):
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return {"ssl": ctx}
        return {}

    def get_safe_url(self) -> str:
        """Return the connection URL with the password replaced by *** — safe to log."""
        url = self.get_url()
        if self.database_password and self.database_password in url:
            return url.replace(self.database_password, "***")
        return url


class ConfigSourceSettings(BaseSettings):
    """Controls which backend the config system reads from.

    The only supported value is ``database`` — configuration is read from
    the relational database.
    """

    config_source: str = "database"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("config_source", mode="before")
    @classmethod
    def _validate_source(cls, v: str) -> str:
        allowed = {"database"}
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

