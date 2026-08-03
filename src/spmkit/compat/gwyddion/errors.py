"""Explicit errors for the static Gwyddion source-audit boundary."""

from __future__ import annotations


class GwyddionCompatibilityError(Exception):
    """Base error for conservative Gwyddion compatibility operations."""


class InvalidGwyddionSourceError(GwyddionCompatibilityError, TypeError):
    """Raised when a source audit does not receive source text."""


class UnsupportedGwyddionProfileError(GwyddionCompatibilityError, ValueError):
    """Raised when no explicit compatibility profile exists for a version."""
