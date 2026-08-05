"""Force-spectroscopy foundation public surface (FS-F1).

Thirteen public capabilities over the modern segment-based ``ForceCurve``
model, with typed failures, immutable results and explicit orchestration.
"""

from __future__ import annotations

from spmkit.core.analysis.force_contact import (
    ContactPointCandidate,
    ContactPointResult,
    contact_point_ensemble,
    contact_point_piecewise,
    contact_point_ratio_of_variances,
    contact_point_threshold,
)
from spmkit.core.analysis.force_foundation_errors import (
    ForceFoundationError,
)
from spmkit.core.analysis.force_metrics import (
    ForceEventResult,
    ForceWorkResult,
    extract_force_events,
    integrate_force_work,
)
from spmkit.core.analysis.force_prepare import (
    ForcePreparationResult,
    prepare_force_curve,
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

__all__ = [
    "identify_force_segments",
    "calibrate_force_curve",
    "compute_tip_sample_separation",
    "fit_force_baseline",
    "correct_force_baseline",
    "contact_point_threshold",
    "contact_point_ratio_of_variances",
    "contact_point_piecewise",
    "contact_point_ensemble",
    "extract_force_events",
    "integrate_force_work",
    "score_force_curve_quality",
    "prepare_force_curve",
    "ForceSegmentationResult",
    "ForceCalibrationResult",
    "ForceBaselineResult",
    "ContactPointCandidate",
    "ContactPointResult",
    "ForceEventResult",
    "ForceWorkResult",
    "ForceCurveQualityResult",
    "ForcePreparationResult",
    "ForceFoundationError",
]
