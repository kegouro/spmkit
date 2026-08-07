"""FS-F3 viscoelastic reliability: protocol/contact/window sensitivity."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from spmkit.core.analysis.force_foundation import ForcePreparationResult
from spmkit.core.analysis.force_time_protocol import (
    CreepResponseResult,
    RelaxationResponseResult,
    ViscoelasticProtocolResult,
    identify_viscoelastic_protocol,
)
from spmkit.core.analysis.force_viscoelastic_errors import (
    NO_VISCOELASTIC_FIT,
    ViscoelasticityError,
)
from spmkit.core.analysis.force_viscoelastic_fitting import (
    ViscoelasticFitResult,
    fit_standard_linear_solid,
)
from spmkit.core.models import ForceCurve


@dataclass(frozen=True)
class ViscoelasticSensitivityResult:
    """Raw evaluated multiverse; never collapsed into one interval."""

    configurations: tuple[dict[str, object], ...]
    parameter_multiverse: tuple[dict[str, float], ...]
    failures: tuple[tuple[dict[str, object], str], ...]
    dominant_sensitivity: str
    contact_sensitivity: float
    boundary_sensitivity: float
    window_sensitivity: float
    n_configurations: int
    n_skipped: int
    warnings: tuple[str, ...] = ()
    provenance: dict[str, object] = field(default_factory=dict)


def _sweep_sls_on_response(response: object,
                           fit_kwargs: dict) -> ViscoelasticFitResult | None:
    if not isinstance(response, (RelaxationResponseResult, CreepResponseResult)):
        return None
    try:
        return fit_standard_linear_solid(response, **fit_kwargs)
    except ViscoelasticityError:
        return None


def analyze_viscoelastic_sensitivity(
    curve: ForceCurve,
    prepared: ForcePreparationResult,
    *,
    protocol: ViscoelasticProtocolResult | None = None,
    contact_offsets: tuple[int, ...] = (-2, 0, 2),
    boundary_offsets: tuple[int, ...] = (-3, 0, 3),
    equilibrium_tail_fractions: tuple[float, ...] = (0.05, 0.1, 0.2),
    max_configurations: int = 96,
    tip_radius: float | None = None,
    poisson: float = 0.3,
) -> ViscoelasticSensitivityResult:
    """Deterministic multiverse over contact offset, hold-boundary offset
    and equilibrium-tail fraction for the SLS fit on the extracted response.

    Configurations are evaluated in deterministic order; failures are
    retained; the dominant sensitivity is the parameter spread relative to
    the median, classified by source (contact/boundary/window).
    """
    base_protocol = protocol if protocol is not None else identify_viscoelastic_protocol(curve)
    configs: list[dict[str, object]] = []
    params_out: list[dict[str, float]] = []
    failures: list[tuple[dict[str, object], str]] = []
    n_skipped = 0

    for c_off in contact_offsets:
        for b_off in boundary_offsets:
            for tail in equilibrium_tail_fractions:
                if len(configs) + len(failures) >= max_configurations:
                    n_skipped += 1
                    continue
                cfg: dict[str, object] = {
                    "contact_offset": c_off, "boundary_offset": b_off,
                    "equilibrium_tail_fraction": tail,
                }
                try:
                    zc = float(prepared.contact.selected.coordinate)
                    approach = prepared.curve.extend
                    if approach is None or approach.raw_height is None:
                        raise ViscoelasticityError(NO_VISCOELASTIC_FIT,
                                                   "no approach branch")
                    z = np.asarray(approach.raw_height, dtype=np.float64)
                    dz = float(np.mean(np.diff(z))) if z.size > 1 else 0.0
                    zc_shifted = zc + c_off * abs(dz)
                    # rebuild a prepared-like indentation by shifting the
                    # contact coordinate through the extraction helpers
                    sep = np.asarray(approach.separation, dtype=np.float64)
                    ind_shifted = sep - zc_shifted
                    reg = base_protocol.region("hold_displacement", "extend")
                    if reg is None:
                        reg = base_protocol.region("hold_force", "extend")
                    if reg is None:
                        raise ViscoelasticityError(NO_VISCOELASTIC_FIT,
                                                   "no hold region to sweep")
                    a, b = reg.start_index, reg.end_index + 1
                    a2 = min(max(a + b_off, 0), b - 2)
                    if approach.time is None:
                        raise ViscoelasticityError(NO_VISCOELASTIC_FIT,
                                                   "no time axis")
                    b2 = max(min(b + b_off, approach.time.size - 1), a2 + 2)
                    t_hold = np.asarray(approach.time, dtype=np.float64)[a2:b2]
                    ind_hold = ind_shifted[a2:b2]
                    f_hold = np.asarray(approach.force, dtype=np.float64)[a2:b2]
                    t0 = float(t_hold[0])
                    f0 = float(f_hold[0])
                    if f0 == 0.0 or t_hold.size < 3:
                        raise ViscoelasticityError(NO_VISCOELASTIC_FIT,
                                                   "degenerate hold response")
                    tail_n = max(1, int(round(t_hold.size * tail)))
                    eq = float(np.mean(f_hold[-tail_n:]))
                    n_hold = f_hold / f0
                    # build a lightweight relaxation response for the SLS fit
                    from spmkit.core.analysis.force_time_protocol import RelaxationResponseResult
                    resp = RelaxationResponseResult(
                        relative_time=t_hold - t0, indentation=ind_hold,
                        force=f_hold, normalized_force=n_hold,
                        hold_indices=np.arange(a2, b2), hold_start_time=t0,
                        force_at_hold_start=f0, equilibrium_force_estimate=eq,
                        warnings=(),
                    )
                    fit = fit_standard_linear_solid(
                        resp, tip_radius=tip_radius, poisson=poisson)
                    configs.append(cfg)
                    params_out.append(fit.parameters)
                except ViscoelasticityError as exc:
                    failures.append((cfg, exc.code))
    if not params_out:
        raise ViscoelasticityError(NO_VISCOELASTIC_FIT, "no multiverse configuration succeeded")

    keys = ("tau_relax", "a") if "a" in params_out[0] else ("tau_retard", "J0", "J_inf")
    medians = {k: float(np.median([p[k] for p in params_out])) for k in keys}
    spread = {k: (float(np.max([p[k] for p in params_out]))
                  - float(np.min([p[k] for p in params_out]))) / medians[k]
              for k in keys}
    dominant_key = max(spread, key=lambda k: float(spread[k])) \
        if any(spread.values()) else keys[0]
    # one-at-a-time source indices (relative to the baseline config)
    by_key: dict[tuple[int, int, float], dict[str, float]] = {}
    for cfg, params_i in zip(configs, params_out, strict=True):
        off_c = int(cfg["contact_offset"]) if isinstance(cfg["contact_offset"], int) else 0
        off_b = int(cfg["boundary_offset"]) if isinstance(cfg["boundary_offset"], int) else 0
        tail_c = float(cfg["equilibrium_tail_fraction"]) \
            if isinstance(cfg["equilibrium_tail_fraction"], (int, float)) else 0.0
        by_key[(off_c, off_b, tail_c)] = params_i
    base = by_key.get((0, 0, 0.1))
    contact_sens = boundary_sens = window_sens = 0.0
    if base is not None:
        med_b = base[dominant_key]
        for off in contact_offsets:
            p = by_key.get((off, 0, 0.1))
            if p:
                contact_sens = max(contact_sens,
                                   abs(p[dominant_key] - med_b) / abs(med_b))
        for off in boundary_offsets:
            p = by_key.get((0, off, 0.1))
            if p:
                boundary_sens = max(boundary_sens,
                                    abs(p[dominant_key] - med_b) / abs(med_b))
        for tail in equilibrium_tail_fractions:
            p = by_key.get((0, 0, tail))
            if p:
                window_sens = max(window_sens,
                                  abs(p[dominant_key] - med_b) / abs(med_b))
    threshold = 0.2
    if contact_sens > threshold:
        dominant = "contact"
    elif boundary_sens > threshold:
        dominant = "boundary"
    elif window_sens > threshold:
        dominant = "window"
    else:
        dominant = "none"
    return ViscoelasticSensitivityResult(
        configurations=tuple(configs), parameter_multiverse=tuple(params_out),
        failures=tuple(failures), dominant_sensitivity=dominant,
        contact_sensitivity=contact_sens, boundary_sensitivity=boundary_sens,
        window_sensitivity=window_sens, n_configurations=len(configs),
        n_skipped=n_skipped,
        provenance={"dominant_parameter": dominant_key, "threshold": threshold,
                    "model": "standard_linear_solid"})
