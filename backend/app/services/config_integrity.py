"""Post-import integrity checks for dangling step_key / field_path references.

Detects references that point to non-existent steps or fields after a schema
import or field/step rename/delete.  Should be invoked after any schema mutation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.flow import WizardFlowStep
from app.db.models.schema import ConfigField, ConfigSchema, ConfigStep
from app.db.models.visibility import VisibilityRule


@dataclass
class IntegrityIssue:
    """A single dangling reference."""

    table: str
    column: str
    row_id: int
    value: str
    message: str


@dataclass
class IntegrityReport:
    """Result of an integrity check."""

    issues: list[IntegrityIssue] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.issues) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_clean": self.is_clean,
            "issue_count": len(self.issues),
            "issues": [
                {
                    "table": i.table,
                    "column": i.column,
                    "row_id": i.row_id,
                    "value": i.value,
                    "message": i.message,
                }
                for i in self.issues
            ],
        }


async def check_dangling_references(
    session: AsyncSession,
    schema_id: int | None = None,
) -> IntegrityReport:
    """Check for dangling step_key and field_path references.

    If ``schema_id`` is provided, checks are scoped to that schema.
    Otherwise, checks against the active schema.

    Checks performed:
    - visibility_rule.target_step_key → config_step.step_key
    - visibility_rule.depends_on_field_path → config_field.field_path
    - visibility_rule.target_field_path → config_field.field_path
    - wizard_flow_step.step_key → config_step.step_key
    """
    report = IntegrityReport()

    # Resolve schema
    if schema_id is None:
        schema_res = await session.execute(
            select(ConfigSchema.id).where(ConfigSchema.status == "active").limit(1)
        )
        row = schema_res.scalar_one_or_none()
        if row is None:
            return report
        schema_id = row

    # Collect valid step keys and field paths for this schema
    step_res = await session.execute(
        select(ConfigStep.step_key).where(ConfigStep.schema_id == schema_id)
    )
    valid_step_keys: set[str] = {r[0] for r in step_res}

    field_res = await session.execute(
        select(ConfigField.field_path).where(ConfigField.schema_id == schema_id)
    )
    valid_field_paths: set[str] = {r[0] for r in field_res}

    # Check visibility rules scoped to this schema
    rule_res = await session.execute(
        select(VisibilityRule).where(VisibilityRule.schema_id == schema_id)
    )
    for rule in rule_res.scalars().all():
        if rule.target_step_key not in valid_step_keys:
            report.issues.append(IntegrityIssue(
                table="visibility_rule",
                column="target_step_key",
                row_id=rule.id,
                value=rule.target_step_key,
                message=f"Step key '{rule.target_step_key}' does not exist in schema {schema_id}",
            ))
        if rule.target_field_path and rule.target_field_path not in valid_field_paths:
            report.issues.append(IntegrityIssue(
                table="visibility_rule",
                column="target_field_path",
                row_id=rule.id,
                value=rule.target_field_path,
                message=f"Field path '{rule.target_field_path}' does not exist in schema {schema_id}",
            ))
        if rule.depends_on_field_path not in valid_field_paths:
            report.issues.append(IntegrityIssue(
                table="visibility_rule",
                column="depends_on_field_path",
                row_id=rule.id,
                value=rule.depends_on_field_path,
                message=f"Field path '{rule.depends_on_field_path}' does not exist in schema {schema_id}",
            ))

    # Check wizard flow steps (not scoped to schema — flows reference by key)
    flow_step_res = await session.execute(select(WizardFlowStep))
    for fs in flow_step_res.scalars().all():
        if fs.step_key not in valid_step_keys:
            report.issues.append(IntegrityIssue(
                table="wizard_flow_step",
                column="step_key",
                row_id=fs.id,
                value=fs.step_key,
                message=f"Step key '{fs.step_key}' does not exist in schema {schema_id}",
            ))

    return report
