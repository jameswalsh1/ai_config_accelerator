import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import candidates, config, drafts, generate, revisions, wizard
from app.settings import CORS_ORIGIN_REGEX

logger = logging.getLogger(__name__)


async def _check_database_readiness() -> None:
    """Ticket 15 — Startup readiness guard for CONFIG_SOURCE=database.

    When the application is configured to use the database as the config
    source, validate that the database has an active schema, at least one
    tool, and at least one language.  Log a clear warning (but do not
    crash) so operators notice immediately.
    """
    from app.settings import get_config_source_settings

    if get_config_source_settings().config_source != "database":
        return

    try:
        from sqlalchemy import func, select

        from app.db.models.language import Language
        from app.db.models.schema import ConfigSchema
        from app.db.models.tool import AITool
        from app.db.session import get_db_session

        async for session in get_db_session():
            schema_res = await session.execute(
                select(ConfigSchema).where(ConfigSchema.status == "active").limit(1)
            )
            active_schema = schema_res.scalar_one_or_none()
            if active_schema is None:
                logger.warning(
                    "CONFIG_SOURCE=database but no active schema found in the database. "
                    "Run: python -m app.commands.import_json_to_db"
                )
                return

            tool_count = (
                await session.execute(
                    select(func.count())
                    .select_from(AITool)
                    .where(AITool.is_active.is_(True))
                )
            ).scalar_one()
            lang_count = (
                await session.execute(
                    select(func.count())
                    .select_from(Language)
                    .where(Language.is_active.is_(True))
                )
            ).scalar_one()

            if tool_count == 0 or lang_count == 0:
                logger.warning(
                    "CONFIG_SOURCE=database but database has %d active tool(s) and "
                    "%d active language(s). Config resolution may fail. "
                    "Run: python -m app.commands.import_json_to_db",
                    tool_count,
                    lang_count,
                )
                return

            logger.info(
                "Database config ready: schema=%s, tools=%d, languages=%d",
                active_schema.schema_version,
                tool_count,
                lang_count,
            )
            break
    except Exception as exc:
        logger.warning(
            "CONFIG_SOURCE=database but database readiness check failed: %s. "
            "Config endpoints requiring the database will return errors.",
            exc,
        )


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    await _check_database_readiness()
    yield


app = FastAPI(title="AI Accelerator API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(wizard.router)
app.include_router(generate.router)
app.include_router(config.router)
app.include_router(drafts.router)
app.include_router(revisions.router)
app.include_router(candidates.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/config-db")
async def health_config_db() -> dict[str, Any]:
    """Ticket 23 — Database import status endpoint.

    Returns a summary of what has been imported into the database.
    Returns ``{"database_config_ready": false}`` when the DB is not
    reachable or when no active schema has been imported yet.
    """
    try:
        from sqlalchemy import select, func
        from app.db.session import get_db_session
        from app.db.models.schema import ConfigSchema
        from app.db.models.tool import AITool
        from app.db.models.language import Language
        from app.db.models.layer import ConfigLayer

        async for session in get_db_session():
            # Active schema
            schema_res = await session.execute(
                select(ConfigSchema).where(ConfigSchema.status == "active").limit(1)
            )
            active_schema = schema_res.scalar_one_or_none()

            if active_schema is None:
                return {"database_config_ready": False, "reason": "no active schema"}

            # Tool count
            tool_count_res = await session.execute(
                select(func.count()).select_from(AITool).where(AITool.is_active.is_(True))
            )
            tool_count: int = tool_count_res.scalar_one()

            # Language count
            lang_count_res = await session.execute(
                select(func.count()).select_from(Language).where(Language.is_active.is_(True))
            )
            lang_count: int = lang_count_res.scalar_one()

            # Layer counts by type
            layer_res = await session.execute(
                select(ConfigLayer.layer_type, func.count())
                .group_by(ConfigLayer.layer_type)
                .where(ConfigLayer.status == "active")
            )
            layers: dict[str, int] = {row[0]: row[1] for row in layer_res}

            break

        assert active_schema is not None
        return {
            "database_config_ready": True,
            "active_schema": active_schema.schema_version,
            "tools": tool_count,
            "languages": lang_count,
            "layers": {
                "tool": layers.get("tool", 0),
                "language": layers.get("language", 0),
                "combo": layers.get("combo", 0),
            },
        }
    except Exception:
        return {"database_config_ready": False, "reason": "database unavailable"}


@app.get("/health/db")
async def health_db() -> dict[str, str]:
    """Check database connectivity.

    Returns ``{"status": "ok", "database": "ok"}`` when the database is
    reachable, or ``{"status": "degraded", "database": "unavailable"}``
    when it is not.  Credentials are never included in the response.
    """
    try:
        from sqlalchemy import text
        from app.db.session import get_db_session

        async for session in get_db_session():
            await session.execute(text("SELECT 1"))
            break
        return {"status": "ok", "database": "ok"}
    except Exception:
        return {"status": "degraded", "database": "unavailable"}

