"""FS-F3 force-volume viscoelasticity mapping (deterministic, bounded)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from spmkit.core.analysis.force_foundation import prepare_force_curve
from spmkit.core.analysis.force_time_protocol import (
    extract_stress_relaxation,
    identify_viscoelastic_protocol,
)
from spmkit.core.analysis.force_viscoelastic_errors import (
    ViscoelasticityError,
)
from spmkit.core.analysis.force_viscoelastic_fitting import (
    fit_standard_linear_solid,
)
from spmkit.core.models import ForceVolume


@dataclass(frozen=True)
class ForceVolumeViscoelasticityResult:
    """Per-curve viscoelastic maps with an explicit failed mask."""

    modulus_0_map: np.ndarray
    modulus_inf_map: np.ndarray
    viscosity_map: np.ndarray
    relaxation_time_map: np.ndarray
    model_map: np.ndarray
    ambiguity_map: np.ndarray
    sensitivity_map: np.ndarray
    protocol_map: np.ndarray
    failed_mask: np.ndarray
    provenance: dict[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


def fit_force_volume_viscoelasticity(
    volume: ForceVolume,
    *,
    tip_radius: float | None = None,
    poisson: float = 0.3,
    min_hold_points: int = 5,
) -> ForceVolumeViscoelasticityResult:
    """Apply identify -> prepare -> extract -> SLS fit to every curve.

    Failed curves stay explicitly masked; nothing is silently dropped.
    Viscosity = E0 * tau_relax * (1 - a) is reported as an SLS-dashpot
    estimate (documented model quantity, not a certified material value).
    """
    n = volume.n_curves
    modulus_0 = np.full(n, np.nan)
    modulus_inf = np.full(n, np.nan)
    viscosity = np.full(n, np.nan)
    tau_map = np.full(n, np.nan)
    model_map = np.full(n, "", dtype=object)
    ambiguity_map = np.zeros(n, dtype=bool)
    sensitivity_map = np.full(n, np.nan)
    protocol_map = np.full(n, "", dtype=object)
    failed = np.zeros(n, dtype=bool)
    failed_reasons: dict[int, str] = {}
    for i in range(n):
        curve = volume.curve(i)
        try:
            protocol = identify_viscoelastic_protocol(curve, min_hold_points=min_hold_points)
            prepared = prepare_force_curve(curve)
            response = extract_stress_relaxation(prepared, protocol)
            fit = fit_standard_linear_solid(response, tip_radius=tip_radius,
                                            poisson=poisson)
            e0 = fit.parameters.get("E0", np.nan)
            e_inf = fit.parameters.get("E_inf", np.nan)
            tau = fit.parameters.get("tau_relax", np.nan)
            modulus_0[i] = e0
            modulus_inf[i] = e_inf
            tau_map[i] = tau
            viscosity[i] = e0 * tau * fit.parameters.get("a", 0.0) if np.isfinite(e0) else np.nan
            model_map[i] = fit.model
            protocol_map[i] = protocol.protocol_type
            ambiguity_map[i] = protocol.ambiguity
            sensitivity_map[i] = fit.condition_number if np.isfinite(fit.condition_number) \
                else np.nan
        except ViscoelasticityError as exc:
            failed[i] = True
            failed_reasons[i] = exc.code
        except Exception as exc:  # noqa: BLE001 - recorded per-curve failure
            failed[i] = True
            failed_reasons[i] = type(exc).__name__
    provenance: dict[str, object] = {
        "pipeline": ["identify_viscoelastic_protocol", "prepare_force_curve",
                     "extract_stress_relaxation", "fit_standard_linear_solid"],
        "tip_radius": tip_radius, "poisson": poisson, "n_curves": n,
        "n_failed": int(failed.sum()), "failed_reasons": failed_reasons,
        "deterministic": True,
    }
    return ForceVolumeViscoelasticityResult(
        modulus_0_map=modulus_0, modulus_inf_map=modulus_inf,
        viscosity_map=viscosity, relaxation_time_map=tau_map, model_map=model_map,
        ambiguity_map=ambiguity_map, sensitivity_map=sensitivity_map,
        protocol_map=protocol_map, failed_mask=failed, provenance=provenance)
