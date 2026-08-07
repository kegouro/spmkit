"""Force-curve quality scoring foundation (FS-F1).

Typed failure reasons beside a summary score; the score never replaces the
component diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from spmkit.core.analysis.force_contact import ContactPointResult
from spmkit.core.analysis.force_foundation_errors import (
    BASELINE_UNSTABLE,
    CONTACT_METHOD_DISAGREEMENT,
    EVENT_NOT_FOUND,
    INVALID_CALIBRATION,
    MISSING_APPROACH,
    MISSING_CALIBRATION,
    MISSING_RETRACT,
    NONFINITE_DATA,
    NONMONOTONIC_COORDINATE,
    SATURATED_SIGNAL,
)
from spmkit.core.analysis.force_metrics import ForceEventResult
from spmkit.core.analysis.force_preprocessing import (
    ForceBaselineResult,
    ForceSegmentationResult,
)
from spmkit.core.models import ForceCurve


@dataclass(frozen=True)
class ForceCurveQualityResult:
    """Quality assessment with typed failure reasons and a summary score."""

    components: dict[str, object]
    summary_score: float
    failure_reasons: tuple[str, ...]
    eligible: bool
    warnings: tuple[str, ...] = ()


def score_force_curve_quality(
    curve: ForceCurve,
    *,
    segmentation: ForceSegmentationResult | None = None,
    baseline: ForceBaselineResult | None = None,
    contact: ContactPointResult | None = None,
    events: ForceEventResult | None = None,
) -> ForceCurveQualityResult:
    """Score curve quality from explicit components.

    The summary score counts passed component checks over the total;
    failure reasons are always explicit and typed.
    """
    reasons: list[str] = []
    components: dict[str, object] = {}
    passed = 0
    total = 0

    def check(name: str, ok: bool, reason: str | None = None) -> None:
        nonlocal passed, total
        total += 1
        if ok:
            passed += 1
            components[name] = "pass"
        else:
            components[name] = reason or "fail"
            if reason:
                reasons.append(reason)

    if not curve.segments:
        check("has_segments", False, MISSING_APPROACH)
        return ForceCurveQualityResult(
            components=components, summary_score=0.0, failure_reasons=tuple(reasons), eligible=False
        )

    approach = curve.extend
    retract = curve.retract
    check("has_approach", approach is not None, MISSING_APPROACH)
    check("has_retract", retract is not None, MISSING_RETRACT)

    all_finite = True
    for s in curve.segments:
        for arr, _label in (
            (s.raw_height, "height"),
            (s.raw_deflection, "deflection"),
            (s.force, "force"),
            (s.separation, "separation"),
        ):
            if arr is not None and not np.isfinite(arr).all():
                all_finite = False
                reasons.append(NONFINITE_DATA)
                components["finite"] = NONFINITE_DATA
                break
    if all_finite:
        components["finite"] = "pass"
        passed += 1
    total += 1

    if approach is not None:
        z = np.asarray(approach.raw_height, dtype=np.float64)
        if z.size and np.any(np.diff(z) < 0):
            check("monotone_coordinate", False, NONMONOTONIC_COORDINATE)
        else:
            check("monotone_coordinate", True)

    if approach is not None and approach.force is None:
        check("calibration", False, MISSING_CALIBRATION)
    else:
        check("calibration", True)
    if curve.calibration is not None and (
        curve.calibration.invols <= 0.0 or curve.calibration.spring_constant <= 0.0
    ):
        check("calibration_valid", False, INVALID_CALIBRATION)
    else:
        check("calibration_valid", True)

    if approach is not None and approach.force is not None:
        f = np.asarray(approach.force, dtype=np.float64)
        # clipping plateau: >= 3 consecutive samples pinned at |max force|
        if f.size:
            peak = float(np.max(np.abs(f)))
            # a genuine clipping plateau pins samples at the exact limit;
            # rounding noise near zero never produces exact equality
            pinned = (f == peak) | (f == -peak) if peak > 0 else np.zeros(f.size, dtype=bool)
            end_plateau = 0
            for flag in pinned[::-1]:
                end_plateau = end_plateau + 1 if flag else 0
                if end_plateau >= 3:
                    break
            pinned_fraction = float(np.mean(pinned))
            clipped = end_plateau >= 3 and 0.01 <= pinned_fraction < 0.8
            check("saturation", not clipped, SATURATED_SIGNAL)
        else:
            check("saturation", True)
    else:
        check("saturation", False, MISSING_CALIBRATION)

    if baseline is not None:
        rms = baseline.residual_rms
        baseline_ok = rms >= 0.0 and rms < float("inf")
        check("baseline_stable", baseline_ok, BASELINE_UNSTABLE)
    else:
        check("baseline_stable", False, BASELINE_UNSTABLE)

    if contact is not None:
        if contact.method_agreement < 2:
            check("contact_agreement", False, CONTACT_METHOD_DISAGREEMENT)
        else:
            check("contact_agreement", True)
    else:
        check("contact_agreement", False, "CONTACT_NOT_FOUND")

    if events is not None:
        if not events.valid:
            check("events_valid", False, EVENT_NOT_FOUND)
        else:
            check("events_valid", True)
    else:
        check("events_valid", True)

    eligible = (
        approach is not None
        and retract is not None
        and "MISSING_CALIBRATION" not in reasons
        and "INVALID_CALIBRATION" not in reasons
        and "NONFINITE_DATA" not in reasons
        and "NONMONOTONIC_COORDINATE" not in reasons
        and "CONTACT_NOT_FOUND" not in reasons
        and "CONTACT_METHOD_DISAGREEMENT" not in reasons
    )
    if not eligible and "FIT_NOT_ELIGIBLE" not in reasons:
        # FIT_NOT_ELIGIBLE is reported when any blocking condition exists
        pass
    if not eligible:
        reasons.append("FIT_NOT_ELIGIBLE")
    score = passed / total if total else 0.0
    return ForceCurveQualityResult(
        components=components,
        summary_score=score,
        failure_reasons=tuple(dict.fromkeys(reasons)),
        eligible=eligible,
    )
