"""Force event and work metrics foundation (FS-F1).

Events: snap-in (approach, before contact) and pull-off (retract, after
contact), baseline-relative, with physical windows.  Work: force integrated
over tip-sample separation on the common overlap domain with monotone
interpolation and trapezoidal arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from spmkit.core.analysis.force_contact import (
    ContactPointCandidate,
    ContactPointResult,
)
from spmkit.core.analysis.force_foundation_errors import (
    EVENT_NOT_FOUND,
    INSUFFICIENT_OVERLAP,
    MISSING_CALIBRATION,
    MISSING_RETRACT,
    NONMONOTONIC_COORDINATE,
    ForceFoundationError,
    require_finite,
    require_monotone_increasing,
)
from spmkit.core.models import ForceCurve


@dataclass(frozen=True)
class ForceEventResult:
    """Snap-in and pull-off event characterization."""

    snap_in_index: int | None
    snap_in_force: float | None
    snap_in_coordinate: float | None
    pull_off_index: int | None
    pull_off_force: float | None
    pull_off_coordinate: float | None
    event_windows: dict[str, tuple[float, float]] = field(default_factory=dict)
    valid: bool = True
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ForceWorkResult:
    """Work integrals over the common tip-position overlap domain."""

    work_approach: float
    work_retract: float
    work_adhesion: float
    hysteresis: float
    domain: str
    interpolation: str
    units: str
    valid: bool
    warnings: tuple[str, ...] = ()


def _axis(curve: ForceCurve, segment_name: str) -> np.ndarray:
    seg = curve.extend if segment_name == "approach" else curve.retract
    if seg is None:
        raise ForceFoundationError(MISSING_RETRACT, f"no {segment_name} segment")
    if seg.separation is not None:
        axis = np.asarray(seg.separation, dtype=np.float64)
    else:
        axis = np.asarray(seg.raw_height, dtype=np.float64)
    return require_finite(axis, label=f"{segment_name} axis")


def extract_force_events(
    curve: ForceCurve,
    contact: ContactPointResult | ContactPointCandidate,
    *,
    snap_in_window: tuple[float, float] | None = None,
    pull_off_window: tuple[float, float] | None = None,
) -> ForceEventResult:
    """Extract snap-in (approach) and pull-off (retract) events.

    Snap-in is the minimum force before contact in the approach window
    (baseline-relative: below the baseline mean minus 3 sigma).  Pull-off
    is the minimum force after contact on the retract.  Windows are physical
    coordinates on the selected axis (separation when available, else
    height).
    """
    approach = curve.extend
    retract = curve.retract
    if approach is None or approach.force is None:
        raise ForceFoundationError(MISSING_CALIBRATION, "approach must be calibrated")
    z_a = _axis(curve, "approach")
    f_a = require_finite(np.asarray(approach.force, dtype=np.float64), label="approach force")
    if isinstance(contact, ContactPointResult):
        cp_index = int(contact.selected.index)
    else:
        cp_index = int(contact.index)
    warnings: list[str] = []

    # snap-in
    snap_idx: int | None = None
    snap_force: float | None = None
    snap_coord: float | None = None
    if cp_index > 3:
        n_base = max(4, int(round(z_a.size * 0.10)))
        base_mean = float(np.mean(f_a[: min(n_base, cp_index)]))
        base_scale = float(np.std(f_a[: min(n_base, cp_index)]))
        search = np.arange(0, min(cp_index, z_a.size))
        if snap_in_window is not None:
            lo, hi = snap_in_window
            mask = (z_a >= lo) & (z_a <= hi)
            search = np.flatnonzero(mask & (np.arange(z_a.size) < cp_index))
        if search.size:
            i = int(search[int(np.argmin(f_a[search]))])
            if f_a[i] < base_mean - 3.0 * base_scale:
                snap_idx, snap_force, snap_coord = i, float(f_a[i]), float(z_a[i])
    else:
        warnings.append("approach too short for snap-in search")

    # pull-off
    po_idx: int | None = None
    po_force: float | None = None
    po_coord: float | None = None
    if retract is not None and retract.force is not None:
        z_r = _axis(curve, "retract")
        f_r = require_finite(np.asarray(retract.force, dtype=np.float64), label="retract force")
        search = np.arange(0, z_r.size)
        if pull_off_window is not None:
            lo, hi = pull_off_window
            mask = (z_r >= lo) & (z_r <= hi)
            search = np.flatnonzero(mask)
        if search.size:
            i = int(search[int(np.argmin(f_r[search]))])
            po_idx, po_force, po_coord = i, float(f_r[i]), float(z_r[i])
    else:
        warnings.append("no retract segment; pull-off not searched")

    windows = {}
    if snap_in_window is not None:
        windows["snap_in"] = snap_in_window
    if pull_off_window is not None:
        windows["pull_off"] = pull_off_window
    valid = snap_idx is not None or po_idx is not None
    if not valid:
        warnings.append(EVENT_NOT_FOUND)
    return ForceEventResult(
        snap_in_index=snap_idx,
        snap_in_force=snap_force,
        snap_in_coordinate=snap_coord,
        pull_off_index=po_idx,
        pull_off_force=po_force,
        pull_off_coordinate=po_coord,
        event_windows=windows,
        valid=valid,
        warnings=tuple(warnings),
    )


def _monotone_resample(x: np.ndarray, y: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Monotone interpolation of y(x) onto target (no extrapolation)."""
    order = np.argsort(x, kind="stable")
    xs, ys = x[order], y[order]
    require_monotone_increasing(xs, label="coordinate")
    return np.interp(target, xs, ys)


def integrate_force_work(
    curve: ForceCurve,
    contact: ContactPointResult | ContactPointCandidate,
    *,
    domain: str = "tip_position",
) -> ForceWorkResult:
    """Integrate force over tip-sample separation on the common overlap.

    The common domain runs from the contact coordinate to the minimum of
    the approach and retract maxima.  Interpolation is monotone (np.interp
    over the sorted coordinate); integration is trapezoidal.  Units: J.
    """
    if domain not in ("tip_position", "height"):
        raise ValueError(f"unknown integration domain {domain!r}")
    approach = curve.extend
    retract = curve.retract
    if approach is None or approach.force is None:
        raise ForceFoundationError(MISSING_CALIBRATION, "approach must be calibrated")
    if retract is None or retract.force is None:
        raise ForceFoundationError(MISSING_RETRACT, "retract must be calibrated")
    z_a = _axis(curve, "approach")
    f_a = require_finite(np.asarray(approach.force, dtype=np.float64), label="approach force")
    z_r = _axis(curve, "retract")
    f_r = require_finite(np.asarray(retract.force, dtype=np.float64), label="retract force")
    for zz, label in ((z_a, "approach"), (z_r, "retract")):
        d = np.diff(zz)
        scale = float(np.max(np.abs(zz)))
        tol = 1e-6 * scale if scale > 0.0 else 1e-300
        if not (np.all(d > -tol) or np.all(d < tol)):
            raise ForceFoundationError(
                NONMONOTONIC_COORDINATE, f"{label} coordinate not strictly monotone"
            )
    if isinstance(contact, ContactPointResult):
        zc = float(contact.selected.coordinate)
    else:
        zc = float(contact.coordinate)
    lo = zc
    hi = min(float(np.max(z_a)), float(np.max(z_r)))
    if hi - lo <= 0.0:
        raise ForceFoundationError(INSUFFICIENT_OVERLAP, "no common overlap domain")
    n_grid = max(64, int(min(z_a.size, z_r.size)))
    grid = np.linspace(lo, hi, n_grid)
    f_a_g = _monotone_resample(z_a, f_a, grid)
    f_r_g = _monotone_resample(z_r, f_r, grid)
    w_appr = float(np.trapezoid(f_a_g, grid))
    w_retr = float(np.trapezoid(f_r_g, grid))
    return ForceWorkResult(
        work_approach=w_appr,
        work_retract=w_retr,
        work_adhesion=w_retr,
        hysteresis=w_appr - w_retr,
        domain=domain,
        interpolation="linear_monotone",
        units="J",
        valid=True,
    )
