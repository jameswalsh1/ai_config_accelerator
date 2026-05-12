"""Tests for Phase 2 ORM model definitions (Tickets 1-9).

These tests verify the model structure without a live database.
Live-DB integration tests are in test_db_infrastructure.py.
"""
import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.base import Base
from app.db.models import (
    AITool,
    Language,
    ConfigSchema,
    ConfigStep,
    ConfigField,
    ConfigLayer,
    ConfigStepOverride,
    ConfigFieldMetadataOverride,
    ConfigFieldContentOverride,
    ConfigAuditEvent,
    ConfigVersion,
)
from app.db.models.layer import LAYER_TYPE_VALUES, LAYER_STATUS_VALUES, MERGE_MODE_VALUES, EDITABILITY_VALUES

# ---------------------------------------------------------------------------
# Async SQLite fixture for in-process model tests
# ---------------------------------------------------------------------------

from sqlalchemy.pool import StaticPool

DATABASE_URL = "sqlite+aiosqlite:///file:test_phase2_models_db?mode=memory&cache=shared&uri=true"


@pytest.fixture(scope="module")
async def engine():
    eng = create_async_engine(DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()


# ---------------------------------------------------------------------------
# Ticket 1: AITool and Language
# ---------------------------------------------------------------------------

class TestAIToolModel:
    async def test_create_tool(self, session):
        tool = AITool(tool_key="claude", title="Claude Code", description="Anthropic Claude")
        session.add(tool)
        await session.flush()
        assert tool.id is not None
        assert tool.tool_key == "claude"
        assert tool.is_active is True

    async def test_tool_key_required(self, session):
        """tool_key column exists on the model."""
        mapper = sa_inspect(AITool)
        col_names = [c.key for c in mapper.columns]
        assert "tool_key" in col_names

    async def test_audit_columns_present(self, session):
        mapper = sa_inspect(AITool)
        col_names = [c.key for c in mapper.columns]
        for col in ("created_at", "updated_at", "created_by", "updated_by"):
            assert col in col_names

    async def test_unique_tool_key_enforced(self, session):
        from sqlalchemy.exc import IntegrityError
        session.add(AITool(tool_key="copilot", title="Copilot"))
        await session.flush()
        session.add(AITool(tool_key="copilot", title="Copilot Duplicate"))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    async def test_create_multiple_tools(self, session):
        tools = [
            AITool(tool_key="claude_t", title="Claude"),
            AITool(tool_key="copilot_t", title="Copilot"),
            AITool(tool_key="cursor_t", title="Cursor"),
        ]
        session.add_all(tools)
        await session.flush()
        assert all(t.id is not None for t in tools)


class TestLanguageModel:
    async def test_create_language(self, session):
        lang = Language(language_key="python", title="Python")
        session.add(lang)
        await session.flush()
        assert lang.id is not None
        assert lang.is_active is True

    async def test_unique_language_key_enforced(self, session):
        from sqlalchemy.exc import IntegrityError
        session.add(Language(language_key="java_dup", title="Java"))
        await session.flush()
        session.add(Language(language_key="java_dup", title="Java Again"))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    async def test_inactive_language(self, session):
        lang = Language(language_key="legacy_lang", title="Legacy", is_active=False)
        session.add(lang)
        await session.flush()
        assert lang.is_active is False


# ---------------------------------------------------------------------------
# Ticket 2: ConfigSchema
# ---------------------------------------------------------------------------

class TestConfigSchemaModel:
    async def test_create_schema(self, session):
        schema = ConfigSchema(schema_version="2.0", description="Canonical schema", status="active")
        session.add(schema)
        await session.flush()
        assert schema.id is not None
        assert schema.status == "active"

    async def test_schema_with_checksum(self, session):
        schema = ConfigSchema(
            schema_version="2.1",
            source_checksum="abc123",
            source_path="app/data/wizard_configs/schema.json",
        )
        session.add(schema)
        await session.flush()
        assert schema.source_checksum == "abc123"


# ---------------------------------------------------------------------------
# Ticket 3: ConfigStep
# ---------------------------------------------------------------------------

class TestConfigStepModel:
    async def test_create_step(self, session):
        schema = ConfigSchema(schema_version="3.0", status="active")
        session.add(schema)
        await session.flush()

        step = ConfigStep(
            schema_id=schema.id,
            step_key="language_selection",
            title="Language Selection",
            position=0,
        )
        session.add(step)
        await session.flush()
        assert step.id is not None
        assert step.position == 0

    async def test_step_ordering(self, session):
        schema = ConfigSchema(schema_version="3.1", status="draft")
        session.add(schema)
        await session.flush()

        steps = [
            ConfigStep(schema_id=schema.id, step_key=f"step_{i}", title=f"Step {i}", position=i)
            for i in range(3)
        ]
        session.add_all(steps)
        await session.flush()
        positions = [s.position for s in steps]
        assert positions == [0, 1, 2]

    async def test_unique_step_key_per_schema(self, session):
        from sqlalchemy.exc import IntegrityError
        schema = ConfigSchema(schema_version="3.2", status="draft")
        session.add(schema)
        await session.flush()

        session.add(ConfigStep(schema_id=schema.id, step_key="dup_step", title="A"))
        await session.flush()
        session.add(ConfigStep(schema_id=schema.id, step_key="dup_step", title="B"))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


# ---------------------------------------------------------------------------
# Ticket 4: ConfigField
# ---------------------------------------------------------------------------

class TestConfigFieldModel:
    async def test_create_top_level_field(self, session):
        schema = ConfigSchema(schema_version="4.0", status="active")
        session.add(schema)
        await session.flush()

        step = ConfigStep(schema_id=schema.id, step_key="lang_step", title="Lang", position=0)
        session.add(step)
        await session.flush()

        field = ConfigField(
            schema_id=schema.id,
            step_id=step.id,
            field_key="language",
            field_path="lang_step.language",
            field_type="select",
            label="Language",
            position=0,
        )
        session.add(field)
        await session.flush()
        assert field.id is not None
        assert field.parent_field_id is None

    async def test_create_nested_field(self, session):
        schema = ConfigSchema(schema_version="4.1", status="active")
        session.add(schema)
        await session.flush()

        step = ConfigStep(schema_id=schema.id, step_key="rule_step", title="Rules", position=0)
        session.add(step)
        await session.flush()

        parent = ConfigField(
            schema_id=schema.id,
            step_id=step.id,
            field_key="rules",
            field_path="rule_step.rules",
            field_type="repeatable_group",
            label="Rules",
            position=0,
        )
        session.add(parent)
        await session.flush()

        child = ConfigField(
            schema_id=schema.id,
            step_id=step.id,
            parent_field_id=parent.id,
            field_key="rule_file_name",
            field_path="rule_step.rules.rule_file_name",
            field_type="text",
            label="Rule File Name",
            position=0,
        )
        session.add(child)
        await session.flush()
        assert child.parent_field_id == parent.id

    async def test_json_columns_accept_various_types(self, session):
        schema = ConfigSchema(schema_version="4.2", status="draft")
        session.add(schema)
        await session.flush()

        step = ConfigStep(schema_id=schema.id, step_key="js_step", title="JS", position=0)
        session.add(step)
        await session.flush()

        field = ConfigField(
            schema_id=schema.id,
            step_id=step.id,
            field_key="multi",
            field_path="js_step.multi",
            field_type="select",
            label="Multi",
            position=0,
            default_value_json="typescript",
            options_json=[{"value": "ts", "label": "TypeScript"}],
            presets_json=[{"label": "TS Preset", "value": "ts"}],
        )
        session.add(field)
        await session.flush()
        assert field.default_value_json == "typescript"
        assert isinstance(field.options_json, list)


# ---------------------------------------------------------------------------
# Ticket 5: ConfigLayer
# ---------------------------------------------------------------------------

class TestConfigLayerModel:
    async def test_create_tool_layer(self, session):
        tool = AITool(tool_key="layer_test_tool", title="Layer Test Tool")
        session.add(tool)
        await session.flush()

        layer = ConfigLayer(
            layer_type="tool",
            layer_key="tool:layer_test_tool",
            tool_id=tool.id,
            version="1",
            status="active",
        )
        session.add(layer)
        await session.flush()
        assert layer.id is not None
        assert layer.layer_type == "tool"

    async def test_create_language_layer(self, session):
        lang = Language(language_key="layer_python", title="Python")
        session.add(lang)
        await session.flush()

        layer = ConfigLayer(
            layer_type="language",
            layer_key="language:layer_python",
            language_id=lang.id,
            version="1",
        )
        session.add(layer)
        await session.flush()
        assert layer.layer_type == "language"

    async def test_create_combo_layer(self, session):
        tool = AITool(tool_key="combo_claude", title="Claude")
        lang = Language(language_key="combo_python", title="Python")
        session.add_all([tool, lang])
        await session.flush()

        layer = ConfigLayer(
            layer_type="combo",
            layer_key="combo:combo_claude+combo_python",
            tool_id=tool.id,
            language_id=lang.id,
            version="1",
        )
        session.add(layer)
        await session.flush()
        assert layer.layer_type == "combo"

    async def test_layer_type_values_constant(self):
        assert "tool" in LAYER_TYPE_VALUES
        assert "language" in LAYER_TYPE_VALUES
        assert "combo" in LAYER_TYPE_VALUES


# ---------------------------------------------------------------------------
# Ticket 6: ConfigStepOverride
# ---------------------------------------------------------------------------

class TestConfigStepOverrideModel:
    async def test_step_override_hidden(self, session):
        # Create prerequisites
        tool = AITool(tool_key="so_tool", title="SO Tool")
        schema = ConfigSchema(schema_version="6.0", status="active")
        session.add_all([tool, schema])
        await session.flush()

        step = ConfigStep(schema_id=schema.id, step_key="so_step", title="SO", position=0)
        layer = ConfigLayer(layer_type="tool", layer_key="tool:so_tool", tool_id=tool.id, version="1")
        session.add_all([step, layer])
        await session.flush()

        override = ConfigStepOverride(layer_id=layer.id, step_id=step.id, hidden=True)
        session.add(override)
        await session.flush()
        assert override.hidden is True

    async def test_step_override_title(self, session):
        tool = AITool(tool_key="so_title_tool", title="SO Title Tool")
        schema = ConfigSchema(schema_version="6.1", status="draft")
        session.add_all([tool, schema])
        await session.flush()

        step = ConfigStep(schema_id=schema.id, step_key="so_title_step", title="Original", position=0)
        layer = ConfigLayer(
            layer_type="tool", layer_key="tool:so_title_tool", tool_id=tool.id, version="1"
        )
        session.add_all([step, layer])
        await session.flush()

        override = ConfigStepOverride(
            layer_id=layer.id, step_id=step.id, title_override="Overridden Title"
        )
        session.add(override)
        await session.flush()
        assert override.title_override == "Overridden Title"

    async def test_unique_layer_step_enforced(self, session):
        from sqlalchemy.exc import IntegrityError
        tool = AITool(tool_key="so_dup_tool", title="SO Dup")
        schema = ConfigSchema(schema_version="6.2", status="draft")
        session.add_all([tool, schema])
        await session.flush()

        step = ConfigStep(schema_id=schema.id, step_key="so_dup_step", title="Dup", position=0)
        layer = ConfigLayer(
            layer_type="tool", layer_key="tool:so_dup_tool", tool_id=tool.id, version="1"
        )
        session.add_all([step, layer])
        await session.flush()

        session.add(ConfigStepOverride(layer_id=layer.id, step_id=step.id, hidden=True))
        await session.flush()
        session.add(ConfigStepOverride(layer_id=layer.id, step_id=step.id, hidden=False))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


# ---------------------------------------------------------------------------
# Ticket 7: ConfigFieldMetadataOverride
# ---------------------------------------------------------------------------

class TestConfigFieldMetadataOverrideModel:
    async def _make_prerequisites(self, session, suffix: str):
        tool = AITool(tool_key=f"fmo_tool_{suffix}", title="FMO Tool")
        schema = ConfigSchema(schema_version=f"7.{suffix}", status="active")
        session.add_all([tool, schema])
        await session.flush()

        step = ConfigStep(schema_id=schema.id, step_key=f"fmo_step_{suffix}", title="FMO", position=0)
        layer = ConfigLayer(
            layer_type="tool", layer_key=f"tool:fmo_tool_{suffix}", tool_id=tool.id, version="1"
        )
        session.add_all([step, layer])
        await session.flush()

        field = ConfigField(
            schema_id=schema.id,
            step_id=step.id,
            field_key="fmo_field",
            field_path=f"fmo_step_{suffix}.fmo_field",
            field_type="text",
            label="FMO Field",
            position=0,
        )
        session.add(field)
        await session.flush()
        return layer, field

    async def test_string_default(self, session):
        layer, field = await self._make_prerequisites(session, "str")
        o = ConfigFieldMetadataOverride(layer_id=layer.id, field_id=field.id, default_value_json="python")
        session.add(o)
        await session.flush()
        assert o.default_value_json == "python"

    async def test_bool_default(self, session):
        layer, field = await self._make_prerequisites(session, "bool")
        o = ConfigFieldMetadataOverride(layer_id=layer.id, field_id=field.id, default_value_json=True)
        session.add(o)
        await session.flush()
        assert o.default_value_json is True

    async def test_list_default(self, session):
        layer, field = await self._make_prerequisites(session, "list")
        o = ConfigFieldMetadataOverride(layer_id=layer.id, field_id=field.id, default_value_json=["a", "b"])
        session.add(o)
        await session.flush()
        assert o.default_value_json == ["a", "b"]

    async def test_null_default(self, session):
        layer, field = await self._make_prerequisites(session, "null")
        o = ConfigFieldMetadataOverride(layer_id=layer.id, field_id=field.id, default_value_json=None)
        session.add(o)
        await session.flush()
        assert o.default_value_json is None

    async def test_locked_editability(self, session):
        layer, field = await self._make_prerequisites(session, "lock")
        o = ConfigFieldMetadataOverride(layer_id=layer.id, field_id=field.id, editability="locked")
        session.add(o)
        await session.flush()
        assert o.editability == "locked"

    async def test_hidden_override(self, session):
        layer, field = await self._make_prerequisites(session, "hid")
        o = ConfigFieldMetadataOverride(layer_id=layer.id, field_id=field.id, hidden=True)
        session.add(o)
        await session.flush()
        assert o.hidden is True

    async def test_editability_values_constant(self):
        assert "free" in EDITABILITY_VALUES
        assert "locked" in EDITABILITY_VALUES


# ---------------------------------------------------------------------------
# Ticket 8: ConfigFieldContentOverride
# ---------------------------------------------------------------------------

class TestConfigFieldContentOverrideModel:
    async def _make_prerequisites(self, session, suffix: str):
        tool = AITool(tool_key=f"fco_tool_{suffix}", title="FCO Tool")
        schema = ConfigSchema(schema_version=f"8.{suffix}", status="active")
        session.add_all([tool, schema])
        await session.flush()

        step = ConfigStep(schema_id=schema.id, step_key=f"fco_step_{suffix}", title="FCO", position=0)
        layer = ConfigLayer(
            layer_type="tool", layer_key=f"tool:fco_tool_{suffix}", tool_id=tool.id, version="1"
        )
        session.add_all([step, layer])
        await session.flush()

        field = ConfigField(
            schema_id=schema.id,
            step_id=step.id,
            field_key="fco_field",
            field_path=f"fco_step_{suffix}.fco_field",
            field_type="select",
            label="FCO Field",
            position=0,
        )
        session.add(field)
        await session.flush()
        return layer, field

    async def test_replace_options(self, session):
        layer, field = await self._make_prerequisites(session, "ro")
        o = ConfigFieldContentOverride(
            layer_id=layer.id, field_id=field.id,
            replace_options_with_json=[{"value": "x", "label": "X"}],
        )
        session.add(o)
        await session.flush()
        assert o.replace_options_with_json[0]["value"] == "x"

    async def test_merge_presets(self, session):
        layer, field = await self._make_prerequisites(session, "mp")
        o = ConfigFieldContentOverride(
            layer_id=layer.id, field_id=field.id,
            merge_presets_json=[{"label": "Test", "value": "test"}],
            merge_mode="merge_by_label",
        )
        session.add(o)
        await session.flush()
        assert o.merge_mode == "merge_by_label"

    async def test_preset_files(self, session):
        layer, field = await self._make_prerequisites(session, "pf")
        o = ConfigFieldContentOverride(
            layer_id=layer.id, field_id=field.id,
            preset_files_to_add_json=["shared/python_presets.json"],
        )
        session.add(o)
        await session.flush()
        assert "shared/python_presets.json" in o.preset_files_to_add_json

    async def test_merge_mode_values_constant(self):
        assert "append" in MERGE_MODE_VALUES
        assert "merge_by_label" in MERGE_MODE_VALUES
        assert "replace" in MERGE_MODE_VALUES


# ---------------------------------------------------------------------------
# Ticket 9: ConfigAuditEvent and ConfigVersion
# ---------------------------------------------------------------------------

class TestAuditAndVersionModels:
    async def test_insert_audit_event(self, session):
        event = ConfigAuditEvent(
            actor="alice",
            action="update_field",
            scope="language",
            target_key="python",
            summary="Changed default",
        )
        session.add(event)
        await session.flush()
        assert event.id is not None
        assert event.actor == "alice"

    async def test_audit_with_before_after(self, session):
        event = ConfigAuditEvent(
            actor="system",
            action="import",
            before_json={"default": "old"},
            after_json={"default": "new"},
        )
        session.add(event)
        await session.flush()
        assert event.before_json == {"default": "old"}

    async def test_insert_version(self, session):
        ver = ConfigVersion(
            scope="language",
            target_key="python",
            version_number=1,
            actor="bob",
            summary="First version",
            data_json={"language_id": "python"},
        )
        session.add(ver)
        await session.flush()
        assert ver.id is not None
        assert ver.version_number == 1

    async def test_unique_version_number_enforced(self, session):
        from sqlalchemy.exc import IntegrityError
        session.add(ConfigVersion(scope="tool", target_key="claude_ver", version_number=1, actor="sys"))
        await session.flush()
        session.add(ConfigVersion(scope="tool", target_key="claude_ver", version_number=1, actor="sys"))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    async def test_query_versions_by_scope_target(self, session):
        from sqlalchemy import select
        for i in range(3):
            session.add(ConfigVersion(
                scope="language",
                target_key="ts_ver",
                version_number=i + 1,
                actor="system",
            ))
        await session.flush()

        stmt = select(ConfigVersion).where(
            ConfigVersion.scope == "language",
            ConfigVersion.target_key == "ts_ver",
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        assert len(rows) == 3
