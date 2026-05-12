"""Phase 5A — Visibility rule evaluation engine.

Evaluates conditional visibility rules against current user answers
to determine which steps and fields should be visible.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.layer import ConfigLayer
from app.db.models.visibility import VisibilityRule, VisibilityRuleOverride


# ---------------------------------------------------------------------------
# Rule evaluation
# ---------------------------------------------------------------------------


def _evaluate_condition(
    operator: str,
    field_value: Any,
    rule_value: Any,
) -> bool:
    """Evaluate a single condition operator against an answer value."""
    if operator == "equals":
        return bool(field_value == rule_value)
    if operator == "not_equals":
        return bool(field_value != rule_value)
    if operator == "in":
        if isinstance(rule_value, list):
            return field_value in rule_value
        return False
    if operator == "not_in":
        if isinstance(rule_value, list):
            return field_value not in rule_value
        return True
    if operator == "is_empty":
        return (
            field_value is None
            or field_value == ""
            or (isinstance(field_value, list) and len(field_value) == 0)
        )
    if operator == "is_not_empty":
        return not (
            field_value is None
            or field_value == ""
            or (isinstance(field_value, list) and len(field_value) == 0)
        )
    return False


def _resolve_field_value(
    depends_on_field_path: str,
    answers: dict[str, dict[str, Any]],
) -> Any:
    """Resolve the current value of a field from the answers dict.

    Field path format: ``step_key.field_key`` (dot-separated).
    """
    parts = depends_on_field_path.split(".", 1)
    if len(parts) != 2:
        return None
    step_key, field_key = parts
    return answers.get(step_key, {}).get(field_key)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class VisibilityResult:
    """Result of evaluating visibility rules."""

    def __init__(self) -> None:
        self.steps: dict[str, bool] = {}  # step_key → visible
        self.fields: dict[str, bool] = {}  # field_path → visible
        self.rules_evaluated: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": self.steps,
            "fields": self.fields,
            "rules_evaluated": self.rules_evaluated,
        }


def evaluate_rules_from_list(
    rules: list[dict[str, Any]],
    answers: dict[str, dict[str, Any]],
    disabled_rule_ids: set[int] | None = None,
    override_values: dict[int, Any] | None = None,
) -> VisibilityResult:
    """Evaluate visibility rules against the provided answers.

    Parameters
    ----------
    rules:
        List of rule dicts (from DB or JSON seed).
    answers:
        Current wizard answers: {step_key: {field_key: value}}.
    disabled_rule_ids:
        Set of rule IDs to skip (from layer overrides).
    override_values:
        Rule ID → replacement comparison value.

    Returns
    -------
    VisibilityResult with computed visibility map.
    """
    disabled = disabled_rule_ids or set()
    overrides = override_values or {}
    result = VisibilityResult()

    # Sort rules by priority (higher = evaluated later = wins)
    sorted_rules = sorted(rules, key=lambda r: r.get("priority", 0))

    for rule in sorted_rules:
        rule_id = rule.get("id")
        if rule_id is not None and rule_id in disabled:
            continue

        result.rules_evaluated += 1
        depends_on = rule["depends_on_field_path"]
        field_value = _resolve_field_value(depends_on, answers)

        compare_value = overrides.get(rule_id) if rule_id in overrides else rule.get("value_json")
        operator = rule.get("operator", "equals")
        action = rule.get("action", "show")
        target_type = rule["target_type"]
        target_step_key = rule["target_step_key"]
        target_field_path = rule.get("target_field_path")

        condition_met = _evaluate_condition(operator, field_value, compare_value)

        # Determine visibility
        if action == "show":
            visible = condition_met
        else:  # hide
            visible = not condition_met

        if target_type == "step":
            result.steps[target_step_key] = visible
        elif target_type == "field" and target_field_path:
            result.fields[target_field_path] = visible

    return result


async def evaluate_visibility(
    session: AsyncSession,
    schema_id: int,
    answers: dict[str, dict[str, Any]],
    layer_ids: list[int] | None = None,
) -> VisibilityResult:
    """Evaluate all visibility rules for a schema against provided answers.

    Loads rules and any layer overrides from the database.
    """
    # Load all rules for this schema
    res = await session.execute(
        select(VisibilityRule)
        .where(VisibilityRule.schema_id == schema_id)
        .order_by(VisibilityRule.priority)
    )
    db_rules = list(res.scalars().all())

    # Load overrides for active layers
    disabled_ids: set[int] = set()
    override_values: dict[int, Any] = {}

    if layer_ids:
        override_res = await session.execute(
            select(VisibilityRuleOverride).where(
                VisibilityRuleOverride.layer_id.in_(layer_ids)
            )
        )
        for ovr in override_res.scalars().all():
            if ovr.is_disabled:
                disabled_ids.add(ovr.rule_id)
            if ovr.override_value_json is not None:
                override_values[ovr.rule_id] = ovr.override_value_json

    # Convert to dicts for the evaluator
    rules = [
        {
            "id": r.id,
            "target_type": r.target_type,
            "target_step_key": r.target_step_key,
            "target_field_path": r.target_field_path,
            "depends_on_field_path": r.depends_on_field_path,
            "operator": r.operator,
            "value_json": r.value_json,
            "action": r.action,
            "priority": r.priority,
        }
        for r in db_rules
    ]

    return evaluate_rules_from_list(rules, answers, disabled_ids, override_values)


async def get_visibility_rules_for_config(
    session: AsyncSession,
    schema_id: int,
    layer_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Return all visibility rules for a schema (for client-side evaluation).

    Rules marked as disabled by layer overrides are excluded.
    """
    res = await session.execute(
        select(VisibilityRule)
        .where(VisibilityRule.schema_id == schema_id)
        .order_by(VisibilityRule.priority)
    )
    db_rules = list(res.scalars().all())

    disabled_ids: set[int] = set()
    override_values: dict[int, Any] = {}

    if layer_ids:
        override_res = await session.execute(
            select(VisibilityRuleOverride).where(
                VisibilityRuleOverride.layer_id.in_(layer_ids)
            )
        )
        for ovr in override_res.scalars().all():
            if ovr.is_disabled:
                disabled_ids.add(ovr.rule_id)
            if ovr.override_value_json is not None:
                override_values[ovr.rule_id] = ovr.override_value_json

    rules: list[dict[str, Any]] = []
    for r in db_rules:
        if r.id in disabled_ids:
            continue
        rule_dict: dict[str, Any] = {
            "id": r.id,
            "target_type": r.target_type,
            "target_step_key": r.target_step_key,
            "depends_on_field_path": r.depends_on_field_path,
            "operator": r.operator,
            "value": override_values.get(r.id, r.value_json),
            "action": r.action,
            "priority": r.priority,
        }
        if r.target_field_path:
            rule_dict["target_field_path"] = r.target_field_path
        rules.append(rule_dict)

    return rules
