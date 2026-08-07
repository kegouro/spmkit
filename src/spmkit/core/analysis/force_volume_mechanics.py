"""FS-F2 force-volume mechanics mapping (deterministic, bounded)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from spmkit.core.analysis.contact_mechanics import (
    compare_contact_models,
)
from spmkit.core.analysis.force_foundation import prepare_force_curve
from spmkit.core.analysis.force_indentation import (
    compute_indentation,
    select_contact_fit_window,
)
from spmkit.core.analysis.force_mechanics_errors import (
    ForceMechanicsError,
)
from spmkit.core.models import ForceVolume


@dataclass(frozen=True)
class ForceVolumeMechanicsResult:
    """Per-curve mechanics maps with explicit failed-curve masks."""

    modulus_map: np.ndarray
    adhesion_map: np.ndarray | None
    model_map: np.ndarray
    failed_mask: np.ndarray
    quality_map: np.ndarray
    provenance: dict[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


def fit_force_volume_mechanics(
    volume: ForceVolume,
    *,
    tip_radius: float = 10e-9,
    poisson: float = 0.3,
    half_angle: float = 0.3490658503988659,
    models: tuple[str, ...] = ("hertz_sphere", "dmt"),
    min_points: int = 20,
) -> ForceVolumeMechanicsResult:
    """Apply the FS-F1 preparation + FS-F2 mechanics stack to every curve.

    Failed curves remain masked; no curve is silently dropped.
    """
    n = volume.n_curves
    modulus_map = np.full(n, np.nan)
    adhesion_map = np.full(n, np.nan)
    model_map = np.full(n, "", dtype=object)
    failed_mask = np.zeros(n, dtype=bool)
    quality_map = np.zeros(n, dtype=bool)
    failed_reasons: dict[int, str] = {}
    provenance: dict[str, object] = {}
    for i in range(n):
        try:
            prepared = prepare_force_curve(volume.curve(i))
            ind = compute_indentation(prepared)
            window = select_contact_fit_window(prepared, ind, min_points=min_points)
            cmp = compare_contact_models(prepared, ind, window, models=models,
                                         tip_radius=tip_radius, poisson=poisson,
                                         half_angle=half_angle)
            best = next(f for f in cmp.fits if f.model == (cmp.recommended_model
                                                           or cmp.fits[0].model))
            modulus_map[i] = best.parameters.get("E", np.nan)
            if "F_adh" in best.parameters:
                adhesion_map[i] = best.parameters["F_adh"]
            model_map[i] = best.model
            quality_map[i] = prepared.quality.eligible
        except ForceMechanicsError as exc:
            failed_mask[i] = True
            failed_reasons[i] = exc.code
        except Exception as exc:  # noqa: BLE001 - recorded per-curve failure
            failed_mask[i] = True
            failed_reasons[i] = type(exc).__name__
    provenance = {
        "pipeline": ["prepare_force_curve", "compute_indentation",
                     "select_contact_fit_window", "compare_contact_models"],
        "tip_radius": tip_radius, "poisson": poisson, "half_angle": half_angle,
        "models": list(models), "n_curves": n,
        "n_failed": int(failed_mask.sum()),
        "failed_reasons": failed_reasons,
        "deterministic": True,
    }
    return ForceVolumeMechanicsResult(
        modulus_map=modulus_map, adhesion_map=adhesion_map, model_map=model_map,
        failed_mask=failed_mask, quality_map=quality_map, provenance=provenance,
    )
