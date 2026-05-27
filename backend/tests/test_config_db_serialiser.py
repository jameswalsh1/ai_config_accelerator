"""Tests for Phase 2 Ticket 10 — DB serialisation helpers.

Uses in-memory SQLite (aiosqlite) to create real ORM rows and then asserts
that the serialisation functions produce the expected dict shapes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.db.base import Base
from app.db.models.schema import ConfigField, ConfigSchema, ConfigStep
from app.services.config_db_serialiser import (
    apply_field_content_override_to_dict,
    apply_field_metadata_override_to_dict,
    apply_step_overrides_to_dict,
    field_to_dict,
    schema_to_config_dict,
    step_to_dict,
    _build_field_tree,
)

from sqlalchemy.pool import StaticPool

DATABASE_URL = "sqlite+aiosqlite:///file:test_config_db_serialiser_db?mode=memory&cache=shared&uri=true"

NOW = datetime.now(tz=timezone.utc)


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
# Helpers
# ---------------------------------------------------------------------------

def _schema(version: str, **kwargs: Any) -> ConfigSchema:
    return ConfigSchema(
        schema_version=version,
        description="",
        status="active",
        created_at=NOW,
        updated_at=NOW,
        **kwargs,
    )


def _step(schema_id: int, key: str, position: int = 0, **kwargs: Any) -> ConfigStep:
    return ConfigStep(
        schema_id=schema_id,
        step_key=key,
        title=key.replace("_", " ").title(),
        position=position,
        output_file=f"{key}.md",
        output_format="text",
        hidden=False,
        created_at=NOW,
        updated_at=NOW,
        **kwargs,
    )


def _field(
    schema_id: int,
    step_id: int,
    key: str,
    field_path: str,
    position: int = 0,
    field_type: str = "text",
    parent_field_id: int | None = None,
    **kwargs: Any,
) -> ConfigField:
    return ConfigField(
        schema_id=schema_id,
        step_id=step_id,
        field_key=key,
        field_path=field_path,
        field_type=field_type,
        label=key.replace("_", " ").title(),
        position=position,
        required=False,
        editability="free",
        render=True,
        hidden=False,
        frontmatter=False,
        parent_field_id=parent_field_id,
        created_at=NOW,
        updated_at=NOW,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# field_to_dict
# ---------------------------------------------------------------------------

class TestFieldToDict:
    async def test_minimal_field(self, session):
        schema = _schema("ft.1")
        session.add(schema)
        await session.flush()

        step = _step(schema.id, "step_a")
        session.add(step)
        await session.flush()

        f = _field(schema.id, step.id, "my_field", "step_a.my_field")
        session.add(f)
        await session.flush()

        d = field_to_dict(f)
        assert d["id"] == "my_field"
        assert d["type"] == "text"
        assert d["label"] == "My Field"
        assert d["required"] is False
        assert d["render"] is True
        assert d["editability"] == "free"

    async def test_json_columns_passthrough(self, session):
        schema = _schema("ft.2")
        session.add(schema)
        await session.flush()

        step = _step(schema.id, "step_b")
        session.add(step)
        await session.flush()

        options = [{"value": "ts", "label": "TypeScript"}]
        f = _field(
            schema.id, step.id, "lang", "step_b.lang",
            field_type="select",
            default_value_json="ts",
            options_json=options,
            presets_json=[{"label": "TS", "value": "ts"}],
        )
        session.add(f)
        await session.flush()

        d = field_to_dict(f)
        assert d["default"] == "ts"
        assert d["options"] == options
        assert d["presets"][0]["label"] == "TS"

    async def test_nested_children_included(self, session):
        schema = _schema("ft.3")
        session.add(schema)
        await session.flush()

        step = _step(schema.id, "step_c")
        session.add(step)
        await session.flush()

        parent = _field(schema.id, step.id, "rules", "step_c.rules", field_type="repeatable_group")
        session.add(parent)
        await session.flush()

        child_dict = {"id": "rule_file", "type": "text", "label": "Rule File"}
        d = field_to_dict(parent, children=[child_dict])
        assert d["fields"] == [child_dict]

    async def test_no_children_no_fields_key(self, session):
        schema = _schema("ft.4")
        session.add(schema)
        await session.flush()

        step = _step(schema.id, "step_d")
        session.add(step)
        await session.flush()

        f = _field(schema.id, step.id, "simple", "step_d.simple")
        session.add(f)
        await session.flush()

        d = field_to_dict(f)
        assert "fields" not in d

    async def test_description_and_placeholder_optional(self, session):
        schema = _schema("ft.5")
        session.add(schema)
        await session.flush()

        step = _step(schema.id, "step_e")
        session.add(step)
        await session.flush()

        f = _field(
            schema.id, step.id, "desc_f", "step_e.desc_f",
            description="A description",
            placeholder="Enter value",
        )
        session.add(f)
        await session.flush()

        d = field_to_dict(f)
        assert d["description"] == "A description"
        assert d["placeholder"] == "Enter value"


# ---------------------------------------------------------------------------
# _build_field_tree
# ---------------------------------------------------------------------------

class TestBuildFieldTree:
    async def test_top_level_only(self, session):
        schema = _schema("tree.1")
        session.add(schema)
        await session.flush()

        step = _step(schema.id, "tree_step")
        session.add(step)
        await session.flush()

        f1 = _field(schema.id, step.id, "a", "tree_step.a", position=0)
        f2 = _field(schema.id, step.id, "b", "tree_step.b", position=1)
        session.add_all([f1, f2])
        await session.flush()

        tree = _build_field_tree([f1, f2], parent_id=None)
        assert [t["id"] for t in tree] == ["a", "b"]

    async def test_nested_tree(self, session):
        schema = _schema("tree.2")
        session.add(schema)
        await session.flush()

        step = _step(schema.id, "nested_step")
        session.add(step)
        await session.flush()

        parent = _field(schema.id, step.id, "group", "nested_step.group", field_type="repeatable_group")
        session.add(parent)
        await session.flush()

        child = _field(
            schema.id, step.id, "name", "nested_step.group.name",
            parent_field_id=parent.id,
        )
        session.add(child)
        await session.flush()

        tree = _build_field_tree([parent, child], parent_id=None)
        assert len(tree) == 1
        assert tree[0]["id"] == "group"
        assert tree[0]["fields"][0]["id"] == "name"


# ---------------------------------------------------------------------------
# step_to_dict
# ---------------------------------------------------------------------------

class TestStepToDict:
    async def test_basic_step(self, session):
        schema = _schema("sd.1")
        session.add(schema)
        await session.flush()

        step = _step(schema.id, "lang_select", description="Pick language")
        session.add(step)
        await session.flush()

        f = _field(schema.id, step.id, "language", "lang_select.language", field_type="select")
        session.add(f)
        await session.flush()

        d = step_to_dict(step, [f])
        assert d["id"] == "lang_select"
        assert d["output_file"] == "lang_select.md"
        assert d["description"] == "Pick language"
        assert len(d["fields"]) == 1
        assert d["fields"][0]["id"] == "language"

    async def test_hidden_step(self, session):
        schema = _schema("sd.2")
        session.add(schema)
        await session.flush()

        step = _step(schema.id, "hidden_step")
        step.hidden = True
        session.add(step)
        await session.flush()

        d = step_to_dict(step, [])
        assert d["hidden"] is True

    async def test_supported_surfaces_json(self, session):
        schema = _schema("sd.3")
        session.add(schema)
        await session.flush()

        step = _step(schema.id, "surf_step")
        step.supported_surfaces_json = ["vscode", "claude"]
        session.add(step)
        await session.flush()

        d = step_to_dict(step, [])
        assert d["supported_surfaces"] == ["vscode", "claude"]


# ---------------------------------------------------------------------------
# schema_to_config_dict
# ---------------------------------------------------------------------------

class TestSchemaToConfigDict:
    async def test_full_config_structure(self, session):
        schema = _schema("full.1")
        schema.description = "Full schema test"
        session.add(schema)
        await session.flush()

        steps = [
            _step(schema.id, "step_one", position=0),
            _step(schema.id, "step_two", position=1),
        ]
        session.add_all(steps)
        await session.flush()

        fields_by_step: dict[int, list[ConfigField]] = {}
        for step in steps:
            f = _field(schema.id, step.id, "f1", f"{step.step_key}.f1")
            session.add(f)
            await session.flush()
            fields_by_step[step.id] = [f]

        d = schema_to_config_dict(schema, steps, fields_by_step)
        assert d["schema_version"] == "full.1"
        assert d["description"] == "Full schema test"
        assert len(d["steps"]) == 2
        assert d["steps"][0]["id"] == "step_one"
        assert d["steps"][1]["id"] == "step_two"

    async def test_empty_steps(self, session):
        schema = _schema("empty.1")
        session.add(schema)
        await session.flush()

        d = schema_to_config_dict(schema, [], {})
        assert d["steps"] == []


# ---------------------------------------------------------------------------
# apply_step_overrides_to_dict
# ---------------------------------------------------------------------------

class TestApplyStepOverrides:
    def test_hide_step(self):
        step = {"id": "s", "title": "S", "hidden": False}
        result = apply_step_overrides_to_dict(step, [{"hidden": True}])
        assert result["hidden"] is True

    def test_title_override(self):
        step = {"id": "s", "title": "Original"}
        result = apply_step_overrides_to_dict(step, [{"title_override": "New Title"}])
        assert result["title"] == "New Title"

    def test_multiple_overrides_last_wins(self):
        step = {"id": "s", "title": "Original", "hidden": False}
        overrides = [
            {"title_override": "First Override"},
            {"title_override": "Second Override"},
        ]
        result = apply_step_overrides_to_dict(step, overrides)
        assert result["title"] == "Second Override"

    def test_no_overrides_unchanged(self):
        step = {"id": "s", "title": "Original"}
        result = apply_step_overrides_to_dict(step, [])
        assert result == step

    def test_original_not_mutated(self):
        step = {"id": "s", "title": "Original", "hidden": False}
        apply_step_overrides_to_dict(step, [{"hidden": True}])
        assert step["hidden"] is False


# ---------------------------------------------------------------------------
# apply_field_metadata_override_to_dict
# ---------------------------------------------------------------------------

class TestApplyFieldMetadataOverride:
    def test_default_value_set(self):
        field = {"id": "f", "editability": "free"}
        result = apply_field_metadata_override_to_dict(
            field, {"default_value_json": "python"}, "tool:claude"
        )
        assert result["default"] == "python"

    def test_editability_locked(self):
        field = {"id": "f", "editability": "free"}
        result = apply_field_metadata_override_to_dict(
            field, {"editability": "locked"}, "tool:claude"
        )
        assert result["editability"] == "locked"

    def test_required_override(self):
        field = {"id": "f", "required": False}
        result = apply_field_metadata_override_to_dict(
            field, {"required": True}, "tool:claude"
        )
        assert result["required"] is True

    def test_hidden_override(self):
        field = {"id": "f", "hidden": False}
        result = apply_field_metadata_override_to_dict(
            field, {"hidden": True}, "language:python"
        )
        assert result["hidden"] is True

    def test_override_source_set(self):
        field = {"id": "f"}
        result = apply_field_metadata_override_to_dict(
            field, {"editability": "suggested"}, "tool:cursor"
        )
        assert result["override_source"] == "tool:cursor"

    def test_override_source_not_overwritten(self):
        """First layer that sets override_source wins."""
        field = {"id": "f", "override_source": "tool:claude"}
        result = apply_field_metadata_override_to_dict(
            field, {"editability": "suggested"}, "language:python"
        )
        assert result["override_source"] == "tool:claude"


# ---------------------------------------------------------------------------
# apply_field_content_override_to_dict
# ---------------------------------------------------------------------------

class TestApplyFieldContentOverride:
    def test_replace_options(self):
        field = {"id": "f", "options": [{"value": "old", "label": "Old"}]}
        result = apply_field_content_override_to_dict(
            field,
            {"replace_options_with_json": [{"value": "new", "label": "New"}]},
            "tool:claude",
        )
        assert len(result["options"]) == 1
        assert result["options"][0]["value"] == "new"

    def test_merge_options_appended(self):
        field = {"id": "f", "options": [{"value": "a", "label": "A"}]}
        result = apply_field_content_override_to_dict(
            field,
            {"merge_options_json": [{"value": "b", "label": "B"}], "merge_mode": "append"},
            "language:python",
        )
        assert len(result["options"]) == 2

    def test_replace_presets(self):
        field = {"id": "f", "presets": [{"label": "Old", "value": "old"}]}
        result = apply_field_content_override_to_dict(
            field,
            {"replace_presets_with_json": [{"label": "New", "value": "new"}]},
            "tool:claude",
        )
        assert result["presets"][0]["label"] == "New"

    def test_merge_presets_append(self):
        field = {"id": "f", "presets": [{"label": "A", "value": "a"}]}
        result = apply_field_content_override_to_dict(
            field,
            {"merge_presets_json": [{"label": "B", "value": "b"}], "merge_mode": "append"},
            "tool:claude",
        )
        assert len(result["presets"]) == 2

    def test_merge_presets_merge_by_label(self):
        field = {"id": "f", "presets": [{"label": "A", "value": "old"}]}
        result = apply_field_content_override_to_dict(
            field,
            {
                "merge_presets_json": [{"label": "A", "value": "new"}, {"label": "B", "value": "b"}],
                "merge_mode": "merge_by_label",
            },
            "tool:claude",
        )
        assert len(result["presets"]) == 2
        assert result["presets"][0]["value"] == "new"

    def test_preset_files_appended(self):
        field = {"id": "f", "preset_files": ["existing.json"]}
        result = apply_field_content_override_to_dict(
            field,
            {"preset_files_to_add_json": ["new.json"]},
            "language:ts",
        )
        assert "existing.json" in result["preset_files"]
        assert "new.json" in result["preset_files"]

    def test_preset_files_no_existing(self):
        field = {"id": "f"}
        result = apply_field_content_override_to_dict(
            field,
            {"preset_files_to_add_json": ["new.json"]},
            "language:ts",
        )
        assert result["preset_files"] == ["new.json"]
