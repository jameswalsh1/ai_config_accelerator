"""Phase 2-5 ORM models for the database-backed configuration domain.

Import all models here so Alembic autogenerate discovers them::

    from app.db.models import *  # noqa: F401, F403
"""

from app.db.models.tool import AITool
from app.db.models.language import Language
from app.db.models.schema import ConfigSchema, ConfigStep, ConfigField
from app.db.models.layer import (
    ConfigLayer,
    ConfigStepOverride,
    ConfigFieldMetadataOverride,
    ConfigFieldContentOverride,
)
from app.db.models.audit import ConfigAuditEvent, ConfigVersion
# Phase 4 models
from app.db.models.actor import ConfigActor
from app.db.models.revision import UserConfigRevision, UserConfigRevisionValue
from app.db.models.candidate import TemplateCandidate
# Phase 5 models
from app.db.models.visibility import VisibilityRule, VisibilityRuleOverride
from app.db.models.flow import WizardFlow, WizardFlowStep

__all__ = [
    "AITool",
    "Language",
    "ConfigSchema",
    "ConfigStep",
    "ConfigField",
    "ConfigLayer",
    "ConfigStepOverride",
    "ConfigFieldMetadataOverride",
    "ConfigFieldContentOverride",
    "ConfigAuditEvent",
    "ConfigVersion",
    # Phase 4
    "ConfigActor",
    "UserConfigRevision",
    "UserConfigRevisionValue",
    "TemplateCandidate",
    # Phase 5
    "VisibilityRule",
    "VisibilityRuleOverride",
    "WizardFlow",
    "WizardFlowStep",
]
