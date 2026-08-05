"""Contact-point estimation foundation (FS-F1).

Four public estimators over the approach segment of a calibrated curve:

  * threshold: baseline mean + k*sigma crossing with persistence;
  * ratio of variances (Gavara 2016): variance-after/variance-before;
  * piecewise: value-continuous baseline/contact polynomial fit;
  * ensemble: robust combination with explicit disagreement and optional
    deterministic bootstrap.

All estimators return typed candidates; failures are never hidden.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from spmkit.core.analysis.force_foundation_errors import (
    BASELINE_TOO_SHORT,
    CONTACT_METHOD_DISAGREEMENT,
    CONTACT_NOT_FOUND,
    MISSING_CALIBRATION,
    MISSING_RETRACT,
    ForceFoundationError,
    require_finite,
)
from spmkit.core.models import ForceCurve

#: Contact-search lower bound: first 10% of approach samples.
SEARCH_START_FRACTION = 0.10
SEARCH_END_FRACTION = 0.90
THRESHOLD_PERSISTENCE = 3
ROV_DEFAULT_WINDOW = 20
ENSEMBLE_SEED = 0
BOOTSTRAP_SAMPLES_DEFAULT = 200


@dataclass(frozen=True)
class ContactPointCandidate:
    """One contact estimate from one method."""

    method: str
    index: int
    coordinate: float
    score: float
    valid: bool
    failure_reason: str | None = None
    diagnostics: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ContactPointResult:
    """Ensemble contact result with explicit disagreement."""

    selected: ContactPointCandidate
    candidates: tuple[ContactPointCandidate, ...]
    method_agreement: int
    spread_samples: int
    spread_coordinate: float
    bootstrap_interval: tuple[float, float] | None
    warnings: tuple[str, ...] = ()


def _approach_data(curve: ForceCurve, label: str) -> tuple[np.ndarray, np.ndarray]:
    approach = curve.extend or (curve.segments[0] if curve.segments else None)
    if approach is None:
        raise ForceFoundationError(MISSING_RETRACT, f"{label}: no approach segment")
    if approach.force is None:
        raise ForceFoundationError(
            MISSING_CALIBRATION, f"{label}: approach segment is not calibrated"
        )
    force = require_finite(np.asarray(approach.force, dtype=np.float64), label="force")
    z = require_finite(np.asarray(approach.raw_height, dtype=np.float64), label="height")
    if force.size != z.size:
        raise ForceFoundationError(CONTACT_NOT_FOUND, "height/force length mismatch")
    return z, force


def contact_point_threshold(
    curve: ForceCurve,
    *,
    threshold_sigma: float = 5.0,
) -> ContactPointCandidate:
    """Baseline-relative threshold contact (first persistent crossing).

    Baseline mean/scale come from the first 10% of the approach.  The
    crossing must persist for ``THRESHOLD_PERSISTENCE`` consecutive samples.
    """
    z, force = _approach_data(curve, "contact_point_threshold")
    if threshold_sigma <= 0.0:
        raise ValueError("threshold_sigma must be positive")
    n_base = max(4, int(round(z.size * SEARCH_START_FRACTION)))
    if z.size < 12 or n_base >= z.size - 2:
        raise ForceFoundationError(BASELINE_TOO_SHORT, "baseline region too short")
    base = force[:n_base]
    mean = float(np.mean(base))
    scale = float(np.std(base))
    if scale <= 0.0:
        # relative epsilon so a noiseless baseline still yields a finite
        # threshold (SI-scale safe; never an absolute 1.0)
        scale = 1e-15 * max(1.0, float(np.max(np.abs(force))))
    level = mean + threshold_sigma * scale
    above = force > level
    run = 0
    for i in range(n_base, z.size):
        run = run + 1 if above[i] else 0
        if run >= THRESHOLD_PERSISTENCE:
            idx = i - THRESHOLD_PERSISTENCE + 1
            return ContactPointCandidate(
                method="threshold",
                index=idx,
                coordinate=float(z[idx]),
                score=float((force[idx] - mean) / scale),
                valid=True,
                diagnostics={
                    "baseline_mean": mean,
                    "baseline_scale": scale,
                    "level": level,
                    "persistence": THRESHOLD_PERSISTENCE,
                },
            )
    return ContactPointCandidate(
        method="threshold",
        index=-1,
        coordinate=float(z[-1]),
        score=0.0,
        valid=False,
        failure_reason=CONTACT_NOT_FOUND,
        diagnostics={"baseline_mean": mean, "baseline_scale": scale, "level": level},
    )


def contact_point_ratio_of_variances(
    curve: ForceCurve,
    *,
    window: int = ROV_DEFAULT_WINDOW,
) -> ContactPointCandidate:
    """Gavara ratio-of-variances contact (variance after / before)."""
    z, force = _approach_data(curve, "contact_point_ratio_of_variances")
    if window < 3:
        raise ValueError("window must be >= 3")
    n = force.size
    if n < 2 * window + 1:
        raise ForceFoundationError(CONTACT_NOT_FOUND, "curve too short for ROV window")
    eps = 1e-12 * float(np.max(force**2)) + 1e-300
    best_i, best_r = -1, -1.0
    # first index with maximal ratio (earliest tie)
    for i in range(window, n - window):
        var_before = float(np.var(force[i - window : i]))
        var_after = float(np.var(force[i : i + window]))
        r = var_after / (var_before + eps)
        if r > best_r:
            best_r, best_i = r, i
    if best_i < 0 or best_r < 2.0:
        # a genuine variance jump requires the after/before ratio to at
        # least double; flat curves yield ratios near 1
        return ContactPointCandidate(
            method="ratio_of_variances",
            index=-1,
            coordinate=float(z[-1]),
            score=best_r,
            valid=False,
            failure_reason=CONTACT_NOT_FOUND,
            diagnostics={"window": window, "best_ratio": best_r},
        )
    return ContactPointCandidate(
        method="ratio_of_variances",
        index=best_i,
        coordinate=float(z[best_i]),
        score=best_r,
        valid=True,
        diagnostics={"window": window},
    )


def _piecewise_residual(
    z: np.ndarray, force: np.ndarray, split: int, baseline_order: int, contact_order: int
) -> float:
    """Value-continuous piecewise fit residual for a candidate split."""
    n = z.size
    if split < 2 or n - split < 3:
        return float("inf")
    xb = z[:split] - float(z[split])
    xc = z[split:] - float(z[split])
    b_deg = min(baseline_order, split - 1)
    c_deg = min(contact_order, n - split - 1)
    cb = np.polyfit(xb, force[:split], b_deg)
    cc = np.polyfit(xc, force[split:], c_deg)
    # continuity: value of baseline at split == value of contact at split
    vb = float(np.polyval(cb, 0.0))
    vc = float(np.polyval(cc, 0.0))
    shift = vb - vc
    cc = cc.copy()
    cc[-1] = cc[-1] + shift
    resid_b = force[:split] - np.polyval(cb, xb)
    resid_c = force[split:] - np.polyval(cc, xc)
    return float(np.sum(resid_b**2) + np.sum(resid_c**2))


def contact_point_piecewise(
    curve: ForceCurve,
    *,
    baseline_order: int = 1,
    contact_order: int = 2,
) -> ContactPointCandidate:
    """Value-continuous piecewise contact (baseline vs contact polynomial)."""
    z, force = _approach_data(curve, "contact_point_piecewise")
    if baseline_order < 0 or contact_order < 0:
        raise ValueError("orders must be non-negative")
    n = z.size
    lo = max(3, int(round(n * SEARCH_START_FRACTION)))
    hi = min(n - 4, int(round(n * SEARCH_END_FRACTION)))
    if hi <= lo:
        raise ForceFoundationError(CONTACT_NOT_FOUND, "search grid too small")
    best_i, best_res = lo, float("inf")
    for split in range(lo, hi + 1):
        res = _piecewise_residual(z, force, split, baseline_order, contact_order)
        if res < best_res:
            best_res, best_i = res, split
    # null model: a single polynomial over the whole curve; a flat curve
    # cannot be improved by any piecewise split
    deg = max(baseline_order, contact_order)
    xc_all = z - float(z[0])
    if n > deg + 1:
        coeffs = np.polyfit(xc_all, force, deg)
        null_res = float(np.sum((force - np.polyval(coeffs, xc_all)) ** 2))
    else:
        null_res = 0.0
    # a meaningful improvement must exceed the rounding floor of the
    # signal itself; perfectly flat curves cannot pass
    f_scale = float(np.max(np.abs(force)))
    floor = (1e-12 * f_scale) ** 2 * n if f_scale > 0 else 0.0
    improved = null_res > floor and best_res < 0.5 * null_res
    if not improved:
        return ContactPointCandidate(
            method="piecewise",
            index=-1,
            coordinate=float(z[-1]),
            score=float(best_res),
            valid=False,
            failure_reason=CONTACT_NOT_FOUND,
            diagnostics={"baseline_order": baseline_order, "contact_order": contact_order},
        )
    return ContactPointCandidate(
        method="piecewise",
        index=best_i,
        coordinate=float(z[best_i]),
        score=float(best_res),
        valid=True,
        diagnostics={"baseline_order": baseline_order, "contact_order": contact_order},
    )


def _bootstrap_median(
    curve: ForceCurve, methods: tuple[str, ...], samples: int, seed: int
) -> tuple[float, float]:
    """Deterministic bootstrap of the ensemble median (indices)."""
    z, force = _approach_data(curve, "contact_point_ensemble")
    rng = np.random.default_rng(seed)
    medians: list[float] = []
    for _ in range(samples):
        idx = rng.integers(0, force.size, size=force.size)
        sub = force[idx]
        zs = z[idx]
        est = []
        for method in methods:
            if method == "threshold":
                n_base = max(4, int(round(zs.size * SEARCH_START_FRACTION)))
                mean = float(np.mean(sub[:n_base]))
                scale = float(np.std(sub[:n_base])) or 1.0
                above = sub > mean + 5.0 * scale
                hits = np.flatnonzero(above[n_base:])
                if hits.size:
                    est.append(float(n_base + int(hits[0])))
            elif method == "ratio_of_variances":
                w = min(ROV_DEFAULT_WINDOW, zs.size // 3)
                if zs.size >= 2 * w + 1:
                    best_r = -1.0
                    for i in range(w, zs.size - w):
                        r = float(np.var(sub[i : i + w])) / (float(np.var(sub[i - w : i])) + 1e-300)
                        if r > best_r:
                            best_r, best_i = r, i
                    est.append(float(best_i))
            elif method == "piecewise":
                lo = max(3, zs.size // 10)
                hi = zs.size - 4
                if hi > lo:
                    best_split: int = lo
                    best_res = float("inf")
                    for split in range(lo, hi + 1):
                        res = _piecewise_residual(zs, sub, split, 1, 2)
                        if res < best_res:
                            best_res, best_split = res, split
                    est.append(float(best_split))
        if est:
            medians.append(float(np.median(est)))
    if not medians:
        return (float("nan"), float("nan"))
    pct_lo = float(np.percentile(medians, 2.5))
    pct_hi = float(np.percentile(medians, 97.5))
    return pct_lo, pct_hi


def contact_point_ensemble(
    curve: ForceCurve,
    *,
    methods: tuple[str, ...] = ("threshold", "ratio_of_variances", "piecewise"),
    bootstrap_samples: int = 0,
) -> ContactPointResult:
    """Combine contact methods; robust location = median of valid indices."""
    candidates: list[ContactPointCandidate] = []
    for method in methods:
        if method == "threshold":
            candidates.append(contact_point_threshold(curve))
        elif method == "ratio_of_variances":
            candidates.append(contact_point_ratio_of_variances(curve))
        elif method == "piecewise":
            candidates.append(contact_point_piecewise(curve))
        else:
            raise ValueError(f"unknown contact method {method!r}")
    valid = [c for c in candidates if c.valid]
    if len(valid) < 2:
        reasons = [c.failure_reason for c in candidates if not c.valid]
        raise ForceFoundationError(
            CONTACT_METHOD_DISAGREEMENT,
            f"insufficient agreeing contact methods ({len(valid)} valid; {reasons})",
        )
    indices = sorted(c.index for c in valid)
    median_idx = int(round(float(np.median(indices))))
    spread_idx = indices[-1] - indices[0]
    z, _force = _approach_data(curve, "contact_point_ensemble")
    spread_coord = float(z[indices[-1]] - z[indices[0]])
    selected = ContactPointCandidate(
        method="ensemble",
        index=median_idx,
        coordinate=float(z[median_idx]),
        score=float(np.median([c.score for c in valid])),
        valid=True,
        diagnostics={"valid_methods": [c.method for c in valid]},
    )
    bootstrap = None
    if bootstrap_samples > 0:
        lo, hi = _bootstrap_median(
            curve, tuple(c.method for c in valid), bootstrap_samples, ENSEMBLE_SEED
        )
        if not np.isnan(lo):
            bootstrap = (
                float(z[int(round(lo))]) if 0 <= int(round(lo)) < z.size else lo,
                float(z[int(round(hi))]) if 0 <= int(round(hi)) < z.size else hi,
            )
    warnings: tuple[str, ...] = ()
    if len(valid) < len(methods):
        warnings = (f"{len(methods) - len(valid)} method(s) failed",)
    return ContactPointResult(
        selected=selected,
        candidates=tuple(candidates),
        method_agreement=len(valid),
        spread_samples=spread_idx,
        spread_coordinate=spread_coord,
        bootstrap_interval=bootstrap,
        warnings=warnings,
    )
