"""FS-F2 fit reliability: sensitivity multiverse, bootstrap, diagnostics."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from spmkit.core.analysis.contact_mechanics import (
    ContactMechanicsFitResult,
    fit_hertz_sphere,
)
from spmkit.core.analysis.force_foundation import ForcePreparationResult
from spmkit.core.analysis.force_indentation import (
    FitWindowResult,
    IndentationResult,
)
from spmkit.core.analysis.force_mechanics_errors import (
    BOOTSTRAP_INSUFFICIENT_SUCCESS,
    CONTACT_SENSITIVITY_HIGH,
    CURVE_NOT_FIT_ELIGIBLE,
    ForceMechanicsError,
)


@dataclass(frozen=True)
class ForceFitSensitivityResult:
    """Raw evaluated multiverse; never collapsed into one interval."""

    configurations: tuple[dict[str, object], ...]
    parameter_multiverse: tuple[dict[str, float], ...]
    failures: tuple[tuple[dict[str, object], str], ...]
    stability_ranges: dict[str, tuple[float, float]]
    robust_medians: dict[str, float]
    dominant_sensitivity: str
    n_configurations: int
    n_skipped: int
    warnings: tuple[str, ...] = ()
    contact_sensitivity: float = 0.0
    window_sensitivity: float = 0.0


@dataclass(frozen=True)
class BootstrapForceFitResult:
    """Deterministic residual bootstrap of one model fit."""

    seed: int
    strategy: str
    samples: int
    n_success: int
    parameter_samples: tuple[dict[str, float], ...]
    percentile_intervals: dict[str, tuple[float, float]]
    bias_estimate: dict[str, float]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ForceFitDiagnosticResult:
    """Explicit diagnostics; the summary status is a policy, not a
    validated probability."""

    fit_eligible: bool
    residual_rms: float
    residual_autocorrelation_proxy: float
    residual_curvature_proxy: float
    parameter_bound_hits: tuple[str, ...]
    condition_metric: float
    parameter_correlation_max: float
    contact_sensitivity: float
    window_sensitivity: float
    bootstrap_success_fraction: float | None
    model_ambiguous: bool
    failure_reasons: tuple[str, ...]
    summary_status: str
    warnings: tuple[str, ...] = ()


def _recompute_indentation(prepared: ForcePreparationResult,
                           contact_offset: int) -> IndentationResult:
    """Recompute indentation with a shifted contact (no curve mutation)."""
    import numpy as np

    # reuse the contact coordinate from provenance and shift by sample spacing
    approach = prepared.curve.extend
    if approach is None or approach.separation is None or approach.raw_height is None:
        raise ForceMechanicsError(CURVE_NOT_FIT_ELIGIBLE, "no approach branch")
    sep = np.asarray(approach.separation, dtype=np.float64)
    zc = prepared.contact.selected.coordinate
    z = np.asarray(approach.raw_height, dtype=np.float64)
    dz = float(np.mean(np.diff(z))) if z.size > 1 else 0.0
    zc_shifted = zc + contact_offset * abs(dz)
    # same convention as compute_indentation: indentation = separation -
    # contact coordinate (the height at the contact)
    ind = sep - zc_shifted
    return IndentationResult(
        indentation=ind, contact_index=prepared.contact.selected.index + contact_offset,
        contact_coordinate=zc_shifted, separation=sep, valid=ind >= 0.0,
        provenance={"shifted_contact": True, "offset": contact_offset},
    )


def analyze_force_fit_sensitivity(
    prepared: ForcePreparationResult,
    *,
    contact_offsets: tuple[int, ...] = (-3, -1, 0, 1, 3),
    fit_window_variants: tuple[float, ...] = (0.0, 0.05),
    baseline_variants: tuple[str, ...] = ("linear",),
    models: tuple[str, ...] = ("hertz_sphere",),
    max_configurations: int = 512,
    tip_radius: float = 10e-9,
    poisson: float = 0.3,
) -> ForceFitSensitivityResult:
    """Deterministic sensitivity multiverse over contact/window/baseline."""
    from spmkit.core.analysis.force_indentation import select_contact_fit_window

    n_skipped = 0
    configs: list[dict[str, object]] = []
    params_out: list[dict[str, float]] = []
    keys_out: list[tuple[int, float]] = []
    failures: list[tuple[dict[str, object], str]] = []
    for off in contact_offsets:
        if len(configs) + len(failures) >= max_configurations:
            n_skipped += 1
            continue
        ind = _recompute_indentation(prepared, off)
        ind_max = float(np.max(ind.indentation)) if ind.indentation.size else 0.0
        for wfrac in fit_window_variants:
            if len(configs) + len(failures) >= max_configurations:
                n_skipped += 1
                continue
            # window variants are FRACTIONS of the indentation range
            bound = float(wfrac) * ind_max
            try:
                window = select_contact_fit_window(prepared, ind,
                                                   min_indentation=bound,
                                                   min_points=10)
                fit = fit_hertz_sphere(prepared, ind, window,
                                       tip_radius=tip_radius, poisson=poisson)
                config = {"contact_offset": off, "window_lower": bound,
                          "window_lower_fraction": float(wfrac),
                          "baseline": "linear", "model": "hertz_sphere"}
                configs.append(config)
                params_out.append(fit.parameters)
                keys_out.append((int(off), float(wfrac)))
            except ForceMechanicsError as exc:
                failures.append(({"contact_offset": off, "window_lower": bound,
                                  "window_lower_fraction": float(wfrac),
                                  "baseline": "linear", "model": "hertz_sphere"},
                                 exc.code))
    if not params_out:
        raise ForceMechanicsError(CONTACT_SENSITIVITY_HIGH,
                                  "no multiverse configuration succeeded")
    e_values = np.array([p["E"] for p in params_out])
    lo, hi = float(np.percentile(e_values, 5)), float(np.percentile(e_values, 95))
    # one-at-a-time sensitivity indices relative to the baseline
    # configuration (contact offset 0, window lower fraction 0.0)
    by_key: dict[tuple[int, float], float] = {}
    for key, p in zip(keys_out, params_out, strict=True):
        by_key[key] = p["E"]
    base = by_key.get((0, 0.0))
    if base:
        contact_E = [by_key[(off, 0.0)] for off in contact_offsets if (off, 0.0) in by_key]
        window_E = [by_key[(0, wf)] for wf in fit_window_variants if (0, wf) in by_key]
        contact_sens = (float(max(abs(e - base) for e in contact_E)) / abs(base)
                        if contact_E else 0.0)
        window_sens = (float(max(abs(e - base) for e in window_E)) / abs(base)
                       if window_E else 0.0)
    else:
        spread = float((np.max(e_values) - np.min(e_values)) / np.median(e_values))
        contact_sens = window_sens = spread
    if contact_sens > 0.2:
        dominant = "contact"
    elif window_sens > 0.2:
        dominant = "window"
    else:
        dominant = "none"
    return ForceFitSensitivityResult(
        configurations=tuple(configs), parameter_multiverse=tuple(params_out),
        failures=tuple(failures), stability_ranges={"E": (lo, hi)},
        robust_medians={"E": float(np.median(e_values))},
        dominant_sensitivity=dominant, n_configurations=len(configs),
        n_skipped=n_skipped, contact_sensitivity=contact_sens,
        window_sensitivity=window_sens,
    )


def bootstrap_force_fit(
    spec: tuple[ForcePreparationResult, IndentationResult, FitWindowResult, str],
    *,
    samples: int = 500,
    seed: int = 0,
    strategy: str = "residual",
    tip_radius: float = 10e-9,
    poisson: float = 0.3,
    min_success_fraction: float = 0.5,
) -> BootstrapForceFitResult:
    """Deterministic residual bootstrap of a hertz fit specification."""
    if strategy not in ("residual", "block_residual"):
        raise ValueError(f"unknown bootstrap strategy {strategy!r}")
    prepared, ind, window, _model = spec
    base_fit = fit_hertz_sphere(prepared, ind, window,
                                tip_radius=tip_radius, poisson=poisson)
    residuals = base_fit.residuals
    rng = np.random.default_rng(seed)
    samples_out: list[dict[str, float]] = []
    approach = prepared.curve.extend
    if approach is None or approach.force is None:
        raise ForceMechanicsError(CURVE_NOT_FIT_ELIGIBLE, "no calibrated approach")
    d = np.asarray(ind.indentation, dtype=np.float64)
    f = np.asarray(approach.force, dtype=np.float64)
    idx = np.arange(window.start_index, window.end_index + 1)
    block = 5 if strategy == "block_residual" else 1
    # block strategy: permute whole blocks; when the window length is not a
    # multiple of the block size, the permuted blocks are cyclically
    # repeated to exactly fill the window (deterministic, no reshape crash)
    if block > 1:
        n_full = (residuals.size // block) * block
        blocks = residuals[:n_full].reshape(-1, block) if n_full else residuals.reshape(1, -1)
    for _ in range(samples):
        if block > 1:
            perm = rng.permutation(blocks).reshape(-1)
            if perm.size < idx.size:
                reps = int(np.ceil(idx.size / perm.size))
                res_perm = np.tile(perm, reps)[: idx.size]
            else:
                res_perm = perm[: idx.size]
        else:
            res_perm = rng.permutation(residuals)
        # the bootstrap force is the fitted window force plus permuted
        # residuals, written back into the full-length force array so the
        # refit window slices align
        f_boot_full = f.copy()
        f_boot_full[idx] = base_fit.predicted_force + res_perm[: idx.size]
        try:
            from spmkit.core.analysis.contact_mechanics import _fit_one

            boot = _fit_one("hertz_sphere", d, f_boot_full, window.start_index,
                            window.end_index, {"R": tip_radius, "poisson": poisson},
                            {"E": base_fit.parameters["E"]})
            samples_out.append(boot.parameters)
        except ForceMechanicsError:
            continue
    if not 0.0 <= min_success_fraction <= 1.0:
        raise ForceMechanicsError(BOOTSTRAP_INSUFFICIENT_SUCCESS,
                                  "min_success_fraction must be in [0, 1]")
    if len(samples_out) < min_success_fraction * samples:
        raise ForceMechanicsError(BOOTSTRAP_INSUFFICIENT_SUCCESS,
                                  f"only {len(samples_out)}/{samples} replicates succeeded")
    e_vals = np.array([p["E"] for p in samples_out])
    intervals = {
        "E": (float(np.percentile(e_vals, 2.5)), float(np.percentile(e_vals, 97.5)))}
    bias = {"E": float(np.mean(e_vals) - base_fit.parameters["E"])}
    return BootstrapForceFitResult(
        seed=seed, strategy=strategy, samples=samples, n_success=len(samples_out),
        parameter_samples=tuple(samples_out), percentile_intervals=intervals,
        bias_estimate=bias,
    )


def diagnose_force_fit(
    fit: ContactMechanicsFitResult,
    *,
    sensitivity: ForceFitSensitivityResult | None = None,
    bootstrap: BootstrapForceFitResult | None = None,
) -> ForceFitDiagnosticResult:
    """Explicit diagnostics; summary status is a policy, not a probability."""
    residuals = np.asarray(fit.residuals, dtype=np.float64)
    n = residuals.size
    rms = float(np.sqrt(np.mean(residuals**2)))
    ac = 0.0
    if n > 2:
        r = residuals - np.mean(residuals)
        denom = np.sum(r**2)
        ac = float(np.sum(r[:-1] * r[1:]) / denom) if denom > 0 else 0.0
    curvature = 0.0
    if n > 3:
        x = np.arange(n, dtype=float)
        c = np.polyfit(x, residuals, 2)
        curvature = float(abs(c[0]))
    bound_hits: tuple[str, ...] = ()
    # covariance conditioning and parameter correlation from the fit
    # covariance matrix (scale-invariant condition number)
    condition_metric = 0.0
    parameter_correlation_max = 0.0
    cov = fit.covariance
    if cov:
        names = sorted({k.split("__")[0] for k in cov})
        if names:
            m = np.array([[cov.get(f"{i}__{j}", 0.0) for j in names] for i in names])
            if np.all(np.isfinite(m)) and np.linalg.matrix_rank(m) == len(names):
                condition_metric = float(np.linalg.cond(m))
            if len(names) >= 2:
                corrs = []
                for i in range(len(names)):
                    for j in range(i + 1, len(names)):
                        den = math.sqrt(m[i, i] * m[j, j])
                        if den > 0.0:
                            corrs.append(abs(m[i, j]) / den)
                parameter_correlation_max = max(corrs) if corrs else 0.0
    reasons: list[str] = []
    if sensitivity is not None and sensitivity.dominant_sensitivity == "contact":
        reasons.append("CONTACT_SENSITIVITY_HIGH")
    if sensitivity is not None and sensitivity.dominant_sensitivity == "window":
        reasons.append("WINDOW_SENSITIVITY_HIGH")
    amb = bool(fit.diagnostics.get("ambiguous", False))
    eligible = not reasons and fit.success
    summary = "ok" if eligible else "review"
    return ForceFitDiagnosticResult(
        fit_eligible=eligible, residual_rms=rms,
        residual_autocorrelation_proxy=ac, residual_curvature_proxy=curvature,
        parameter_bound_hits=bound_hits, condition_metric=condition_metric,
        parameter_correlation_max=parameter_correlation_max,
        contact_sensitivity=(sensitivity.contact_sensitivity
                             if sensitivity is not None else 0.0),
        window_sensitivity=(sensitivity.window_sensitivity
                            if sensitivity is not None else 0.0),
        bootstrap_success_fraction=(bootstrap.n_success / bootstrap.samples
                                    if bootstrap is not None else None),
        model_ambiguous=amb, failure_reasons=tuple(reasons), summary_status=summary,
    )
