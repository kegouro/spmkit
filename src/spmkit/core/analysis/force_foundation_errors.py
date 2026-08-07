"""Shared typed failures and validation helpers for the SPMKit force
foundation (FS-F1).

The force foundation never returns NaN-filled pseudo-success: every failure
is a typed :class:`ForceFoundationError` carrying a machine-readable code.
"""

from __future__ import annotations

import numpy as np

#: Typed failure reasons (QC and raised errors share the same vocabulary).
MISSING_CALIBRATION = "MISSING_CALIBRATION"
INVALID_CALIBRATION = "INVALID_CALIBRATION"
MISSING_APPROACH = "MISSING_APPROACH"
MISSING_RETRACT = "MISSING_RETRACT"
NONFINITE_DATA = "NONFINITE_DATA"
NONMONOTONIC_COORDINATE = "NONMONOTONIC_COORDINATE"
BASELINE_TOO_SHORT = "BASELINE_TOO_SHORT"
BASELINE_UNSTABLE = "BASELINE_UNSTABLE"
CONTACT_NOT_FOUND = "CONTACT_NOT_FOUND"
CONTACT_METHOD_DISAGREEMENT = "CONTACT_METHOD_DISAGREEMENT"
SATURATED_SIGNAL = "SATURATED_SIGNAL"
EVENT_NOT_FOUND = "EVENT_NOT_FOUND"
INSUFFICIENT_OVERLAP = "INSUFFICIENT_OVERLAP"
FIT_NOT_ELIGIBLE = "FIT_NOT_ELIGIBLE"
MISSING_COORDINATE = "MISSING_COORDINATE"
INSUFFICIENT_SAMPLES = "INSUFFICIENT_SAMPLES"
LENGTH_MISMATCH = "LENGTH_MISMATCH"


class ForceFoundationError(ValueError):
    """Typed force-foundation failure with a machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def require_finite(values: np.ndarray, *, label: str) -> np.ndarray:
    """Validate a finite one-dimensional float64 array (copied)."""
    try:
        arr = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ForceFoundationError(NONFINITE_DATA, f"{label} must be array-compatible") from exc
    if arr.ndim != 1:
        raise ForceFoundationError(NONFINITE_DATA, f"{label} must be one-dimensional")
    if arr.size == 0:
        raise ForceFoundationError(NONFINITE_DATA, f"{label} must be non-empty")
    if not np.isfinite(arr).all():
        raise ForceFoundationError(NONFINITE_DATA, f"{label} must be finite")
    return arr.copy()


def require_monotone_increasing(values: np.ndarray, *, label: str, tol: float = 0.0) -> None:
    """Require a strictly monotone increasing coordinate (up to ``tol``)."""
    if np.any(np.diff(values) < tol):
        raise ForceFoundationError(
            NONMONOTONIC_COORDINATE, f"{label} must be monotonically increasing"
        )
