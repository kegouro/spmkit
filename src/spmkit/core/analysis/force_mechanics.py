"""FS-F2 public surface: contact mechanics, fit reliability, volume mapping."""

from __future__ import annotations

from spmkit.core.analysis.contact_mechanics import (
    ContactMechanicsFitResult,
    ModelComparisonResult,
    compare_contact_models,
    fit_dmt,
    fit_flat_punch,
    fit_hertz_sphere,
    fit_jkr,
    fit_sneddon_cone,
    forward_model,
)
from spmkit.core.analysis.force_fit_reliability import (
    BootstrapForceFitResult,
    ForceFitDiagnosticResult,
    ForceFitSensitivityResult,
    analyze_force_fit_sensitivity,
    bootstrap_force_fit,
    diagnose_force_fit,
)
from spmkit.core.analysis.force_indentation import (
    FitWindowResult,
    IndentationResult,
    compute_indentation,
    select_contact_fit_window,
)
from spmkit.core.analysis.force_mechanics_errors import (
    ForceMechanicsError,
)
from spmkit.core.analysis.force_volume_mechanics import (
    ForceVolumeMechanicsResult,
    fit_force_volume_mechanics,
)

__all__ = [
    "compute_indentation",
    "select_contact_fit_window",
    "fit_hertz_sphere",
    "fit_sneddon_cone",
    "fit_flat_punch",
    "fit_dmt",
    "fit_jkr",
    "compare_contact_models",
    "forward_model",
    "analyze_force_fit_sensitivity",
    "bootstrap_force_fit",
    "diagnose_force_fit",
    "fit_force_volume_mechanics",
    "IndentationResult",
    "FitWindowResult",
    "ContactMechanicsFitResult",
    "ModelComparisonResult",
    "ForceFitSensitivityResult",
    "BootstrapForceFitResult",
    "ForceFitDiagnosticResult",
    "ForceVolumeMechanicsResult",
    "ForceMechanicsError",
]
