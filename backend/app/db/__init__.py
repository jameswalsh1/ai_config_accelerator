"""Database package for the AI Accelerator backend.

Phase 1 — infrastructure only. No application tables yet.

Submodules
----------
base       SQLAlchemy declarative base and shared metadata.
session    Async engine and session factory.
deps       FastAPI dependency for injecting database sessions.
mixins     Reusable audit column mixin for future models.
transaction  Async transaction context-manager helper.
"""
