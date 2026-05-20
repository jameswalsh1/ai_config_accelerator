"""Tests for the Phase 5A visibility rule evaluation engine."""
from __future__ import annotations

from typing import Any

import pytest

from app.services.visibility_engine import (
    VisibilityResult,
    _evaluate_condition,
    _resolve_field_value,
    evaluate_rules_from_list,
)


# ---------------------------------------------------------------------------
# _evaluate_condition
# ---------------------------------------------------------------------------


class TestEvaluateCondition:
    def test_equals_match(self):
        assert _evaluate_condition("equals", "python", "python") is True

    def test_equals_no_match(self):
        assert _evaluate_condition("equals", "java", "python") is False

    def test_not_equals_match(self):
        assert _evaluate_condition("not_equals", "java", "python") is True

    def test_not_equals_no_match(self):
        assert _evaluate_condition("not_equals", "python", "python") is False

    def test_in_match(self):
        assert _evaluate_condition("in", "python", ["python", "java"]) is True

    def test_in_no_match(self):
        assert _evaluate_condition("in", "ruby", ["python", "java"]) is False

    def test_in_non_list_rule_value(self):
        # rule_value is not a list → condition is never met
        assert _evaluate_condition("in", "python", "python") is False

    def test_not_in_match(self):
        assert _evaluate_condition("not_in", "ruby", ["python", "java"]) is True

    def test_not_in_no_match(self):
        assert _evaluate_condition("not_in", "python", ["python", "java"]) is False

    def test_not_in_non_list_rule_value(self):
        # rule_value is not a list → always True (value cannot be "in" a non-list)
        assert _evaluate_condition("not_in", "python", "python") is True

    def test_is_empty_none(self):
        assert _evaluate_condition("is_empty", None, None) is True

    def test_is_empty_empty_string(self):
        assert _evaluate_condition("is_empty", "", None) is True

    def test_is_empty_empty_list(self):
        assert _evaluate_condition("is_empty", [], None) is True

    def test_is_empty_non_empty(self):
        assert _evaluate_condition("is_empty", "value", None) is False

    def test_is_not_empty_with_value(self):
        assert _evaluate_condition("is_not_empty", "value", None) is True

    def test_is_not_empty_with_none(self):
        assert _evaluate_condition("is_not_empty", None, None) is False

    def test_unknown_operator_returns_false(self):
        assert _evaluate_condition("unknown_op", "value", "value") is False


# ---------------------------------------------------------------------------
# _resolve_field_value
# ---------------------------------------------------------------------------


class TestResolveFieldValue:
    def test_resolves_step_dot_field(self):
        answers = {"setup": {"language": "python"}}
        assert _resolve_field_value("setup.language", answers) == "python"

    def test_missing_step_returns_none(self):
        answers: dict[str, Any] = {}
        assert _resolve_field_value("setup.language", answers) is None

    def test_missing_field_returns_none(self):
        answers: dict[str, Any] = {"setup": {}}
        assert _resolve_field_value("setup.language", answers) is None

    def test_invalid_path_no_dot_returns_none(self):
        answers = {"setup": {"language": "python"}}
        assert _resolve_field_value("setup_language", answers) is None


# ---------------------------------------------------------------------------
# evaluate_rules_from_list
# ---------------------------------------------------------------------------


class TestEvaluateRulesFromList:
    def _rule(self, **kwargs) -> dict[str, Any]:
        defaults = {
            "id": 1,
            "target_type": "step",
            "target_step_key": "advanced",
            "target_field_path": None,
            "depends_on_field_path": "setup.language",
            "operator": "equals",
            "value_json": "python",
            "action": "show",
            "priority": 0,
        }
        return {**defaults, **kwargs}

    def test_show_action_condition_met(self):
        rules = [self._rule()]
        answers = {"setup": {"language": "python"}}
        result = evaluate_rules_from_list(rules, answers)
        assert result.steps["advanced"] is True
        assert result.rules_evaluated == 1

    def test_show_action_condition_not_met(self):
        rules = [self._rule()]
        answers = {"setup": {"language": "java"}}
        result = evaluate_rules_from_list(rules, answers)
        assert result.steps["advanced"] is False

    def test_hide_action_condition_met(self):
        rules = [self._rule(action="hide")]
        answers = {"setup": {"language": "python"}}
        result = evaluate_rules_from_list(rules, answers)
        assert result.steps["advanced"] is False

    def test_hide_action_condition_not_met(self):
        rules = [self._rule(action="hide")]
        answers = {"setup": {"language": "java"}}
        result = evaluate_rules_from_list(rules, answers)
        assert result.steps["advanced"] is True

    def test_disabled_rule_is_skipped(self):
        rules = [self._rule(id=42)]
        answers = {"setup": {"language": "python"}}
        result = evaluate_rules_from_list(rules, answers, disabled_rule_ids={42})
        assert "advanced" not in result.steps
        assert result.rules_evaluated == 0

    def test_override_value_replaces_rule_value(self):
        rules = [self._rule(id=10, value_json="python")]
        # Override changes comparison value to "java"
        answers = {"setup": {"language": "java"}}
        result = evaluate_rules_from_list(rules, answers, override_values={10: "java"})
        assert result.steps["advanced"] is True

    def test_field_target_type(self):
        rules = [self._rule(
            target_type="field",
            target_step_key="setup",
            target_field_path="setup.docker_file",
            action="show",
        )]
        answers = {"setup": {"language": "python"}}
        result = evaluate_rules_from_list(rules, answers)
        assert result.fields["setup.docker_file"] is True

    def test_higher_priority_rule_wins(self):
        # Low priority: hide advanced when language=python
        rule_low = self._rule(id=1, action="hide", priority=0)
        # High priority: show advanced when language=python
        rule_high = self._rule(id=2, action="show", priority=10)
        answers = {"setup": {"language": "python"}}
        result = evaluate_rules_from_list([rule_low, rule_high], answers)
        assert result.steps["advanced"] is True  # high priority wins

    def test_empty_rules_returns_empty_result(self):
        result = evaluate_rules_from_list([], {})
        assert result.steps == {}
        assert result.fields == {}
        assert result.rules_evaluated == 0

    def test_to_dict(self):
        rules = [self._rule()]
        answers = {"setup": {"language": "python"}}
        result = evaluate_rules_from_list(rules, answers)
        d = result.to_dict()
        assert "steps" in d
        assert "fields" in d
        assert "rules_evaluated" in d
