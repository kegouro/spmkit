"""Force-curve preparation orchestration (FS-F1).

``prepare_force_curve`` is explicit orchestration over the public Core
primitives; it duplicates no equations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from spmkit.core.analysis.force_contact import (
    ContactPointResult,
    contact_point_ensemble,
)
from spmkit.core.analysis.force_metrics import (
    ForceEventResult,
    ForceWorkResult,
    extract_force_events,
    integrate_force_work,
)
from spmkit.core.analysis.force_preprocessing import (
    ForceBaselineResult,
    ForceCalibrationResult,
    ForceSegmentationResult,
    calibrate_force_curve,
    compute_tip_sample_separation,
    correct_force_baseline,
    fit_force_baseline,
    identify_force_segments,
)
from spmkit.core.analysis.force_quality import (
    ForceCurveQualityResult,
    score_force_curve_quality,
)
from spmkit.core.models import Calibration, ForceCurve


@dataclass(frozen=True)
class ForcePreparationResult:
    """Complete prepared force curve with full provenance."""

    curve: ForceCurve
    segmentation: ForceSegmentationResult
    calibration: ForceCalibrationResult
    separation: ForceCurve
    baseline: ForceBaselineResult
    baseline_corrected: ForceCurve
    contact: ContactPointResult
    events: ForceEventResult
    work: ForceWorkResult
    quality: ForceCurveQualityResult
    provenance: dict[str, object] = field(default_factory=dict)


def prepare_force_curve(
    curve: ForceCurve,
    *,
    calibration: Calibration | None = None,
    baseline_model: str = "linear",
    contact_methods: tuple[str, ...] = ("threshold", "ratio_of_variances", "piecewise"),
    bootstrap_samples: int = 0,
) -> ForcePreparationResult:
    """Run the full force-foundation pipeline on one curve.

    Order: segments -> calibration -> tip-sample separation -> baseline fit
    -> baseline correction -> contact ensemble -> events -> work -> quality.
    """
    provenance: dict[str, object] = {}
    segmentation = identify_force_segments(curve)
    provenance["segmentation"] = {"method": segmentation.method}

    calibration_result = calibrate_force_curve(curve, calibration=calibration)
    calibrated = calibration_result.curve
    provenance["calibration"] = {
        "source": calibration_result.source,
        "invols": calibration_result.invols,
        "spring_constant": calibration_result.spring_constant,
    }

    separation_curve = compute_tip_sample_separation(calibrated)
    provenance["separation"] = {"convention": "height - deflection"}

    baseline = fit_force_baseline(separation_curve, model=baseline_model)
    corrected = correct_force_baseline(separation_curve, baseline, scope="all")
    provenance["baseline"] = {
        "model": baseline.model,
        "scope": baseline.scope,
        "intercept": baseline.intercept,
        "slope": baseline.slope,
    }

    # contact detection runs on the calibrated (uncorrected) curve: the
    # baseline-corrected near-zero noise is ill-conditioned for ROV and
    # piecewise estimators
    contact = contact_point_ensemble(
        separation_curve, methods=contact_methods, bootstrap_samples=bootstrap_samples
    )
    provenance["contact"] = {
        "methods": list(contact_methods),
        "selected_index": contact.selected.index,
        "agreement": contact.method_agreement,
        "bootstrap_samples": bootstrap_samples,
    }

    events = extract_force_events(corrected, contact)
    work = integrate_force_work(corrected, contact, domain="tip_position")
    provenance["events"] = {
        "snap_in_index": events.snap_in_index,
        "pull_off_index": events.pull_off_index,
    }
    provenance["work"] = {"domain": work.domain, "interpolation": work.interpolation}

    quality = score_force_curve_quality(
        corrected,
        segmentation=segmentation,
        baseline=baseline,
        contact=contact,
        events=events,
    )
    provenance["quality"] = {
        "summary_score": quality.summary_score,
        "failure_reasons": list(quality.failure_reasons),
        "eligible": quality.eligible,
    }
    provenance["pipeline"] = [
        "identify_force_segments",
        "calibrate_force_curve",
        "compute_tip_sample_separation",
        "fit_force_baseline",
        "correct_force_baseline",
        "contact_point_ensemble",
        "extract_force_events",
        "integrate_force_work",
        "score_force_curve_quality",
    ]
    return ForcePreparationResult(
        curve=corrected,
        segmentation=segmentation,
        calibration=calibration_result,
        separation=separation_curve,
        baseline=baseline,
        baseline_corrected=corrected,
        contact=contact,
        events=events,
        work=work,
        quality=quality,
        provenance=provenance,
    )
