"""
Authentication and authorisation service.

Gated behind the ``AUTH_ENABLED`` environment variable.  When the variable
is unset or ``"false"`` (the default), every request is allowed through
unconditionally — no headers are inspected.

When ``AUTH_ENABLED=true``, the service expects an upstream reverse-proxy
(e.g. an LDAP-integrated gateway) to inject trusted headers:

    X-Auth-User   – the authenticated username
    X-Auth-Roles  – comma-separated list of role names

Two roles govern access:

    config_editor  – may use the Config Wizard (read + write)
    audit_viewer   – may view the Audit Log and version history

These are implemented as thin FastAPI dependencies so that routers
remain free of business logic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "false").lower() == "true"

ROLE_CONFIG_EDITOR = "config_editor"
ROLE_AUDIT_VIEWER = "audit_viewer"


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AuthUser:
    """Represents the identity extracted from trusted proxy headers."""

    username: str
    roles: frozenset[str]

    def has_role(self, role: str) -> bool:
        return role in self.roles


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_ANONYMOUS = AuthUser(username="anonymous", roles=frozenset())


def _extract_user(request: Request) -> AuthUser:
    """Pull identity from proxy-injected headers.

    Returns the anonymous user when auth is disabled.
    """
    if not AUTH_ENABLED:
        return _ANONYMOUS

    username = request.headers.get("x-auth-user", "").strip()
    if not username:
        raise HTTPException(status_code=401, detail="Missing X-Auth-User header")

    raw_roles = request.headers.get("x-auth-roles", "")
    roles = frozenset(r.strip() for r in raw_roles.split(",") if r.strip())
    return AuthUser(username=username, roles=roles)


# ---------------------------------------------------------------------------
# Public FastAPI dependencies
# ---------------------------------------------------------------------------

def get_current_user(request: Request) -> AuthUser:
    """Dependency that extracts the current user from the request.

    When ``AUTH_ENABLED=false`` (default) this always returns an
    anonymous user with no role checks.
    """
    return _extract_user(request)


def require_config_editor(
    user: AuthUser = Depends(get_current_user),
) -> AuthUser:
    """Dependency that enforces the ``config_editor`` role.

    Attach to any route that reads or writes wizard configuration.
    No-op when auth is disabled.
    """
    if AUTH_ENABLED and not user.has_role(ROLE_CONFIG_EDITOR):
        raise HTTPException(
            status_code=403,
            detail=f"Role '{ROLE_CONFIG_EDITOR}' required",
        )
    return user


def require_audit_viewer(
    user: AuthUser = Depends(get_current_user),
) -> AuthUser:
    """Dependency that enforces the ``audit_viewer`` role.

    Attach to any route that reads the audit log or version history.
    No-op when auth is disabled.
    """
    if AUTH_ENABLED and not user.has_role(ROLE_AUDIT_VIEWER):
        raise HTTPException(
            status_code=403,
            detail=f"Role '{ROLE_AUDIT_VIEWER}' required",
        )
    return user
