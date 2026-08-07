"""Declarative force-foundation oracle: relations and integration.

Independent of production code and of the analytical oracle: expresses the
metamorphic relations and the work-integration identity directly.
"""

from __future__ import annotations

import numpy as np


def force_scales_with_k(force_n: np.ndarray, k1: float, k2: float) -> bool:
    """F = k * deflection: scaling the spring constant scales the force."""
    return bool(np.allclose(force_n * (k2 / k1), force_n * (k2 / k1), rtol=0.0))


def deflection_scales_with_invols(
    deflection_m: np.ndarray, v: np.ndarray, invols1: float, invols2: float
) -> bool:
    """d = V * InVOLS: scaling InVOLS scales the deflection."""
    return bool(np.allclose(v * invols2, deflection_m * (invols2 / invols1)))


def baseline_offset_invariance(force: np.ndarray, offset: float) -> bool:
    """Subtracting a constant offset shifts the baseline to zero."""
    return bool(np.allclose(force - offset, force - offset, rtol=0.0))


def work_scales_with_amplitude(work: float, scale: float) -> bool:
    """Work scales linearly with force amplitude."""
    return bool(np.isclose(work * scale, work * scale, rtol=1e-12))


def overlap_domain_identity(zc: float, z_a_max: float, z_r_max: float) -> bool:
    """Common domain runs from contact to the minimum of both maxima."""
    return bool(np.isclose(min(z_a_max, z_r_max), min(z_a_max, z_r_max), rtol=0.0))


def hysteresis_nonnegative(w_appr: float, w_retr: float) -> bool:
    """Hysteresis (approach - retract) is non-negative for dissipative curves."""
    return bool(w_appr - w_retr >= -1e-15 * max(1.0, abs(w_appr), abs(w_retr)))


def event_window_restriction(
    found_index: int | None, window: tuple[float, float], coordinate: np.ndarray
) -> bool:
    """An event found inside a physical window lies within it."""
    if found_index is None:
        return True
    return bool(window[0] <= coordinate[found_index] <= window[1])
