"""Force-curve preprocessing foundation (FS-F1).

Segment identification, calibration application, tip-sample separation and
baseline fit/correction for the modern segment-based ``ForceCurve`` model.

Scientific contract (frozen):

  * inputs are immutable; every result owns its storage;
  * calibration: raw deflection voltage (V) -> deflection (m) via InVOLS
    (m/V), then force (N) via the spring constant (N/m); already-calibrated
    segments pass through; explicit double calibration is rejected;
  * tip-sample separation: separation = height - deflection (SPMKit reader
    convention); no contact offset is applied here;
  * baseline: pre-contact region = the first 10% of the approach segment;
    linear model = offset + slope; robust = deterministic Huber IRLS;
  * typed failures instead of NaN-filled results.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from spmkit.core.analysis.calibration import (
    deflection_to_force,
    volts_to_deflection,
)
from spmkit.core.analysis.force_foundation_errors import (
    BASELINE_TOO_SHORT,
    INVALID_CALIBRATION,
    MISSING_CALIBRATION,
    MISSING_RETRACT,
    ForceFoundationError,
    require_finite,
)
from spmkit.core.models import Calibration, ForceCurve, ForceSegment

FloatArray = np.ndarray

#: Baseline region: fraction of the approach samples treated as pre-contact.
BASELINE_FRACTION = 0.10
MIN_BASELINE_POINTS = 10
MIN_BASELINE_POINTS_ROBUST = 12
HUBER_C = 1.345
HUBER_ITERATIONS = 10


@dataclass(frozen=True)
class ForceSegmentationResult:
    """Identified approach/retract sample indices of one curve."""

    approach_indices: tuple[int, ...]
    retract_indices: tuple[int, ...]
    turning_point_index: int
    pause_indices: tuple[int, ...] = ()
    method: str = "turning_point"
    diagnostics: dict[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ForceCalibrationResult:
    """Calibrated curve plus calibration provenance."""

    curve: ForceCurve
    input_units: str
    output_units: str
    invols: float | None
    spring_constant: float | None
    sign_convention: str
    source: str
    uncertainty: dict[str, float] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ForceBaselineResult:
    """Fitted baseline of a segment region."""

    segment: str
    sample_indices: tuple[int, ...]
    model: str
    intercept: float
    slope: float
    residual_rms: float
    robust_scale: float
    scope: str
    diagnostics: dict[str, object] = field(default_factory=dict)


def _primary_axis(segments: tuple[ForceSegment, ...]) -> tuple[ForceSegment, ...]:
    return segments


def identify_force_segments(
    curve: ForceCurve,
    *,
    method: str = "turning_point",
) -> ForceSegmentationResult:
    """Identify approach/retract sample indices of a force curve.

    Instrument-labelled segments are trusted when both ``extend`` and
    ``retract`` exist.  Otherwise the turning point is the index of the
    height extremum on the concatenated raw-height axis.  Samples are never
    reordered.
    """
    if method != "turning_point":
        raise ValueError(f"unknown segmentation method {method!r}")
    segments = curve.segments
    if not segments:
        raise ForceFoundationError(MISSING_RETRACT, "curve has no segments")
    warnings: list[str] = []
    total = sum(len(s) for s in segments)
    labels = [(s.segment_type, len(s)) for s in segments]
    types = [t for t, _n in labels]
    if "extend" in types and "retract" in types:
        # trusted instrument labels
        approach: list[int] = []
        retract: list[int] = []
        offset = 0
        pauses: list[int] = []
        for s in segments:
            idx = list(range(offset, offset + len(s)))
            if s.segment_type == "extend":
                approach.extend(idx)
            elif s.segment_type == "retract":
                retract.extend(idx)
            else:
                pauses.extend(idx)
            offset += len(s)
        turn = (approach[-1] if approach else 0) + (1 if approach else 0)
        if turn > total - 1:
            turn = total - 1
        return ForceSegmentationResult(
            approach_indices=tuple(approach),
            retract_indices=tuple(retract),
            turning_point_index=turn,
            pause_indices=tuple(pauses),
            method=method,
            diagnostics={"trusted_labels": True, "segment_types": types},
        )
    # inference on the concatenated raw height (turning point = height max)
    heights = np.concatenate([np.asarray(s.raw_height, dtype=np.float64) for s in segments])
    require_finite(heights, label="raw height")
    turn = int(np.argmax(heights))
    warnings.append("no instrument labels; turning point inferred from height maximum")
    return ForceSegmentationResult(
        approach_indices=tuple(range(turn + 1)),
        retract_indices=tuple(range(turn + 1, total)),
        turning_point_index=turn,
        method=method,
        diagnostics={"trusted_labels": False},
        warnings=tuple(warnings),
    )


def calibrate_force_curve(
    curve: ForceCurve,
    *,
    calibration: Calibration | None = None,
) -> ForceCalibrationResult:
    """Calibrate raw deflection voltage to force.

    ``raw_v`` -> ``deflection_m`` (x InVOLS, m/V) -> ``force_n`` (x spring
    constant, N/m).  Segments already in ``force_n`` pass through unchanged.
    An explicit calibration supplied for an already-calibrated curve is
    rejected as double calibration.  A missing calibration for raw segments
    raises ``MISSING_CALIBRATION``.
    """
    if not isinstance(curve, ForceCurve):
        raise TypeError("calibrate_force_curve requires a ForceCurve")
    cal = calibration if calibration is not None else curve.calibration
    invols: float | None
    k: float | None
    if cal is not None:
        invols = float(cal.invols)
        k = float(cal.spring_constant)
        if invols <= 0.0 or k <= 0.0:
            raise ForceFoundationError(
                INVALID_CALIBRATION, "calibration must have positive invols and k"
            )
    else:
        invols = None
        k = None
    new_segments: list[ForceSegment] = []
    warnings: list[str] = []
    needs_cal = any(s.state == "raw_v" for s in curve.segments)
    if needs_cal and (invols is None or k is None):
        raise ForceFoundationError(
            MISSING_CALIBRATION,
            "curve contains raw deflection segments but no calibration is available",
        )
    for s in curve.segments:
        if s.state == "raw_v":
            assert invols is not None and k is not None
            deflection = volts_to_deflection(np.asarray(s.raw_deflection), invols)
            force = deflection_to_force(deflection, k)
            new_segments.append(
                ForceSegment(
                    segment_type=s.segment_type,
                    direction=s.direction,
                    raw_height=s.raw_height,
                    raw_deflection=s.raw_deflection,
                    time=s.time,
                    cycle=s.cycle,
                    state="force_n",
                    deflection=deflection,
                    force=force,
                    separation=s.separation,
                    metadata=dict(s.metadata),
                )
            )
        elif s.state == "force_n":
            if calibration is not None:
                raise ForceFoundationError(
                    INVALID_CALIBRATION,
                    "curve is already calibrated; explicit calibration would double-apply",
                )
            new_segments.append(s)
        elif s.state == "deflection_m":
            if calibration is None and curve.calibration is None:
                raise ForceFoundationError(
                    MISSING_CALIBRATION, "deflection-calibrated segment needs a spring constant"
                )
            kk = k if k is not None else float(curve.calibration.spring_constant)  # type: ignore[union-attr]
            force = deflection_to_force(np.asarray(s.deflection), kk)
            new_segments.append(
                ForceSegment(
                    segment_type=s.segment_type,
                    direction=s.direction,
                    raw_height=s.raw_height,
                    raw_deflection=s.raw_deflection,
                    time=s.time,
                    cycle=s.cycle,
                    state="force_n",
                    deflection=s.deflection,
                    force=force,
                    separation=s.separation,
                    metadata=dict(s.metadata),
                )
            )
        else:
            warnings.append(f"segment state {s.state!r} left unchanged")
            new_segments.append(s)
    if cal is None:
        source = "curve metadata" if curve.calibration is not None else "none"
        invols_out = float(curve.calibration.invols) if curve.calibration is not None else None
        k_out = float(curve.calibration.spring_constant) if curve.calibration is not None else None
    else:
        source = "explicit"
        invols_out, k_out = invols, k
    new_curve = ForceCurve(
        segments=tuple(new_segments),
        calibration=curve.calibration,
        position=curve.position,
        index=curve.index,
        metadata=dict(curve.metadata),
    )
    return ForceCalibrationResult(
        curve=new_curve,
        input_units="V" if needs_cal else "N",
        output_units="N",
        invols=invols_out,
        spring_constant=k_out,
        sign_convention="positive deflection = cantilever bending toward sample",
        source=source,
        warnings=tuple(warnings),
    )


def compute_tip_sample_separation(curve: ForceCurve) -> ForceCurve:
    """Compute tip-sample separation = height - deflection for every segment.

    Requires calibrated deflection (``deflection_m`` or ``force_n`` with a
    spring constant).  Returns a new curve; the input is never mutated.  No
    contact offset is applied here.
    """
    new_segments: list[ForceSegment] = []
    for s in curve.segments:
        if s.separation is not None:
            new_segments.append(s)
            continue
        height = require_finite(np.asarray(s.raw_height, dtype=np.float64), label="height")
        if s.deflection is not None:
            deflection = require_finite(
                np.asarray(s.deflection, dtype=np.float64), label="deflection"
            )
        elif s.state == "force_n" and s.force is not None:
            cal = curve.calibration
            if cal is None:
                raise ForceFoundationError(
                    MISSING_CALIBRATION,
                    "force-calibrated segment without spring constant cannot " "recover deflection",
                )
            deflection = np.asarray(s.force, dtype=np.float64) / float(cal.spring_constant)
        else:
            raise ForceFoundationError(
                MISSING_CALIBRATION, "segment needs calibrated deflection to compute separation"
            )
        separation = height - deflection
        new_segments.append(
            ForceSegment(
                segment_type=s.segment_type,
                direction=s.direction,
                raw_height=s.raw_height,
                raw_deflection=s.raw_deflection,
                time=s.time,
                cycle=s.cycle,
                state=s.state,
                deflection=s.deflection,
                force=s.force,
                separation=separation,
                metadata=dict(s.metadata),
            )
        )
    return ForceCurve(
        segments=tuple(new_segments),
        calibration=curve.calibration,
        position=curve.position,
        index=curve.index,
        metadata=dict(curve.metadata),
    )


def _huber_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Deterministic Huber-IRLS linear fit (slope, intercept, scale)."""
    xm = x - float(np.mean(x))
    n = x.size
    slope = 0.0
    intercept = float(np.mean(y))
    scale = float(np.median(np.abs(y - intercept))) * 1.4826
    if scale <= 0.0:
        scale = float(np.std(y)) or 1.0
    for _ in range(HUBER_ITERATIONS):
        resid = y - (intercept + slope * xm)
        w = np.ones(n)
        z = np.abs(resid) / scale
        w[z > HUBER_C] = HUBER_C / z[z > HUBER_C]
        sw = np.sum(w)
        if sw <= 0.0:
            break
        np.sum(w * xm)
        sxx = np.sum(w * xm * xm)
        sxy = np.sum(w * xm * resid)
        if sxx <= 0.0:
            break
        delta = sxy / sxx
        slope = slope + delta
        intercept = intercept + float(np.mean(w * resid) / (sw / n))
        new_scale = float(np.median(np.abs(resid)) * 1.4826)
        if new_scale > 0.0:
            scale = new_scale
    return slope, intercept, scale


def fit_force_baseline(
    curve: ForceCurve,
    *,
    region: str = "pre_contact",
    model: str = "linear",
    robust: bool = False,
) -> ForceBaselineResult:
    """Fit the pre-contact baseline (offset + slope) of the approach.

    ``region="pre_contact"`` uses the first ``BASELINE_FRACTION`` (10%) of
    the approach samples.  ``model="linear"`` fits offset + slope;
    ``robust=True`` uses deterministic Huber IRLS.  Too few points raise
    ``BASELINE_TOO_SHORT``.
    """
    if region != "pre_contact":
        raise ValueError(f"unknown baseline region {region!r}")
    if model != "linear":
        raise ValueError(f"unknown baseline model {model!r}")
    approach = curve.extend or (curve.segments[0] if curve.segments else None)
    if approach is None:
        raise ForceFoundationError(MISSING_RETRACT, "no approach segment for baseline")
    if approach.force is None:
        raise ForceFoundationError(
            MISSING_CALIBRATION, "baseline requires a calibrated approach segment"
        )
    force = require_finite(np.asarray(approach.force, dtype=np.float64), label="approach force")
    z = require_finite(np.asarray(approach.raw_height, dtype=np.float64), label="height")
    n_base = max(MIN_BASELINE_POINTS, int(round(z.size * BASELINE_FRACTION)))
    n_base = min(n_base, z.size)
    if z.size < MIN_BASELINE_POINTS or n_base < 4:
        raise ForceFoundationError(BASELINE_TOO_SHORT, "pre-contact region too short")
    x = z[:n_base]
    y = force[:n_base]
    xm = float(np.mean(x))
    if robust:
        slope, intercept_centered, scale = _huber_fit(x, y)
        intercept = intercept_centered - slope * xm
    else:
        coeffs = np.polyfit(x - xm, y, 1)
        slope = float(coeffs[0])
        intercept = float(coeffs[1]) - slope * xm
        scale = float(np.std(y - (intercept + slope * x)))
    resid = y - (intercept + slope * x)
    rms = float(np.sqrt(np.mean(resid**2)))
    return ForceBaselineResult(
        segment="approach",
        sample_indices=tuple(range(n_base)),
        model=model,
        intercept=intercept,
        slope=slope,
        residual_rms=rms,
        robust_scale=scale,
        scope="all",
        diagnostics={"robust": robust, "n_points": n_base},
    )


def correct_force_baseline(
    curve: ForceCurve,
    baseline: ForceBaselineResult,
    *,
    scope: str = "all",
) -> ForceCurve:
    """Subtract the fitted baseline (offset + slope over height).

    ``scope="all"`` corrects every segment; ``"baseline"`` only the
    pre-contact region samples; ``"approach"`` only the approach segment.
    The slope term changes the data: the caller is warned via the baseline
    ``scope`` field and this docstring.
    """
    if scope not in ("all", "baseline", "approach"):
        raise ValueError(f"unknown correction scope {scope!r}")
    approach = curve.extend or curve.segments[0]
    if approach is None or approach.force is None:
        raise ForceFoundationError(MISSING_RETRACT, "no calibrated approach segment")
    new_segments: list[ForceSegment] = []
    for s in curve.segments:
        if s.force is None:
            new_segments.append(s)
            continue
        z = np.asarray(s.raw_height, dtype=np.float64)
        force = np.asarray(s.force, dtype=np.float64)
        baseline_line = baseline.intercept + baseline.slope * z
        corrected = force - baseline_line
        if scope == "baseline":
            corrected = force.copy()
            idx = baseline.sample_indices
            corrected[: len(idx)] = force[: len(idx)] - baseline_line[: len(idx)]
        new_segments.append(
            ForceSegment(
                segment_type=s.segment_type,
                direction=s.direction,
                raw_height=s.raw_height,
                raw_deflection=s.raw_deflection,
                time=s.time,
                cycle=s.cycle,
                state=s.state,
                deflection=s.deflection,
                force=corrected,
                separation=s.separation,
                metadata=dict(s.metadata),
            )
        )
    return ForceCurve(
        segments=tuple(new_segments),
        calibration=curve.calibration,
        position=curve.position,
        index=curve.index,
        metadata=dict(curve.metadata),
    )
