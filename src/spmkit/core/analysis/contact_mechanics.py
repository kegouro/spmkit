"""FS-F2 contact-mechanics model engine and model comparison.

Five frozen contact-mechanics models with a shared deterministic least-squares
engine (SciPy curve_fit, already a required dependency), immutable results and
typed failures.  No contact or baseline is inferred here: the caller provides
the prepared curve, indentation and fit window.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import curve_fit

from spmkit.core.analysis.force_foundation import ForcePreparationResult
from spmkit.core.analysis.force_indentation import (
    FitWindowResult,
    IndentationResult,
)
from spmkit.core.analysis.force_mechanics_errors import (
    CURVE_NOT_FIT_ELIGIBLE,
    INVALID_ADHESION_PARAMETER,
    INVALID_ANGLE,
    INVALID_POISSON_RATIO,
    INVALID_RADIUS,
    NONFINITE_INPUT,
    OPTIMIZATION_FAILED,
    ForceMechanicsError,
)

MODELS = ("hertz_sphere", "sneddon_cone", "flat_punch", "dmt", "jkr")


@dataclass(frozen=True)
class ContactMechanicsFitResult:
    """Deterministic contact-mechanics fit of one model."""

    model: str
    success: bool
    parameters: dict[str, float]
    parameter_units: dict[str, str]
    covariance: dict[str, float] | None
    residuals: np.ndarray
    predicted_force: np.ndarray
    included_indices: np.ndarray
    objective: float
    dof: int
    rmse: float
    aic: float
    aicc: float
    bic: float
    failure_reason: str | None = None
    diagnostics: dict[str, object] = field(default_factory=dict)
    provenance: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelComparisonResult:
    """Model-relative comparison (AIC/AICc/BIC) over identical data."""

    fits: tuple[ContactMechanicsFitResult, ...]
    delta_aicc: dict[str, float]
    weights: dict[str, float]
    recommended_model: str | None
    ambiguous: bool
    n_compared: int
    warnings: tuple[str, ...] = ()
    provenance: dict[str, object] = field(default_factory=dict)


def _check_geometry(*, tip_radius: float | None, half_angle: float | None,
                    poisson: float, work_of_adhesion: float | None,
                    punch_radius: float | None, model: str) -> None:
    if not (0.0 < poisson < 0.5):
        raise ForceMechanicsError(INVALID_POISSON_RATIO,
                                  f"poisson {poisson} outside (0, 0.5)")
    if tip_radius is not None and tip_radius <= 0.0:
        raise ForceMechanicsError(INVALID_RADIUS, "tip radius must be positive")
    if punch_radius is not None and punch_radius <= 0.0:
        raise ForceMechanicsError(INVALID_RADIUS, "punch radius must be positive")
    if half_angle is not None and not (0.0 < half_angle < math.pi / 2.0):
        raise ForceMechanicsError(INVALID_ANGLE, "half-angle must be in (0, pi/2)")
    if work_of_adhesion is not None and work_of_adhesion < 0.0:
        raise ForceMechanicsError(INVALID_ADHESION_PARAMETER,
                                  "work of adhesion must be non-negative")


def _reduced_modulus(young_modulus: float, poisson: float) -> float:
    return young_modulus / (1.0 - poisson**2)


def forward_model(model: str, delta: np.ndarray, params: dict[str, float]) -> np.ndarray:
    """Forward force for one model (frozen equations, SI units)."""
    delta = np.asarray(delta, dtype=np.float64)
    est = _reduced_modulus(params["E"], params["poisson"])
    if model == "hertz_sphere":
        return (4.0 / 3.0) * est * math.sqrt(params["R"]) * delta ** 1.5
    if model == "sneddon_cone":
        return (2.0 * math.tan(params["alpha"]) / math.pi) * est * delta ** 2.0
    if model == "flat_punch":
        return 2.0 * est * params["R"] * delta
    if model == "dmt":
        return (4.0 / 3.0) * est * math.sqrt(params["R"]) * delta ** 1.5 - params["F_adh"]
    if model == "jkr":
        # parametric loading branch (delta increasing).  The contact radius
        # a parametrizes both delta and force; the branch is monotone for
        # a >= a0 with a0 = (2*pi*w*R^2/E)^(1/3) the zero-load radius, so
        # the parametric range is derived from the requested delta range
        # and no a_max parameter is required.
        r = params["R"]
        w = params["w"]
        dmax = float(np.max(delta)) if delta.size else 0.0
        if dmax <= 0.0:
            return np.zeros_like(delta)
        c = math.sqrt(2.0 * math.pi * w / est)
        a0 = (2.0 * math.pi * w * r**2 / est) ** (1.0 / 3.0) if w > 0.0 else 0.0
        a_lo = max(a0, 1e-12)
        a_hi = a_lo
        while a_hi**2 / r - c * math.sqrt(a_hi) < dmax:
            a_hi *= 2.0
        a = np.linspace(a_lo, a_hi, max(2048, delta.size * 4))
        d = a**2 / r - c * np.sqrt(a)
        f = 4.0 * est * a**3 / (3.0 * r) - np.sqrt(
            8.0 * math.pi * w * est * a**3)
        return np.interp(delta, d, f, left=0.0, right=float(f[-1]))
    raise ValueError(f"unknown model {model!r}")


def _free_parameter_names(model: str) -> list[str]:
    if model in ("hertz_sphere", "flat_punch"):
        return ["E"]
    if model == "sneddon_cone":
        return ["E"]
    if model == "dmt":
        return ["E", "F_adh"]
    return ["E", "w"]


def _fit_one(model: str, delta: np.ndarray, force: np.ndarray,
             start: int, end: int, fixed: dict[str, float],
             initial: dict[str, float]) -> ContactMechanicsFitResult:
    d = delta[start : end + 1]
    f = force[start : end + 1]
    if not np.isfinite(d).all() or not np.isfinite(f).all():
        raise ForceMechanicsError(NONFINITE_INPUT, "non-finite fit inputs")
    n = d.size
    if n < 5:
        raise ForceMechanicsError(
            OPTIMIZATION_FAILED, "too few points for a mechanical fit")
    free = _free_parameter_names(model)

    def _predict(delta_v: np.ndarray, *args: float) -> np.ndarray:
        params = dict(fixed)
        for name, val in zip(free, args, strict=False):
            params[name] = float(val)
        return forward_model(model, delta_v, params)

    p0 = [initial.get(name, 1e9 if name == "E" else 1e-9) for name in free]
    try:
        popt, pcov = curve_fit(_predict, d, f, p0=p0, maxfev=20000)
    except Exception as exc:  # noqa: BLE001 - typed wrapper
        raise ForceMechanicsError(OPTIMIZATION_FAILED, f"optimizer failed: {exc}") from exc
    params = dict(fixed)
    for name, val in zip(free, popt, strict=False):
        params[name] = float(val)
    predicted = _predict(d, *popt)
    residuals = f - predicted
    dof = n - len(free)
    rmse = float(np.sqrt(np.mean(residuals**2)))
    objective = float(np.sum(residuals**2))
    sse = objective
    aic = n * math.log(sse / n + 1e-300) + 2 * len(free)
    aicc = aic + (2 * len(free) * (len(free) + 1)) / max(1, n - len(free) - 1)
    bic = n * math.log(sse / n + 1e-300) + len(free) * math.log(n)
    units = {
        "E": "Pa", "F_adh": "N", "w": "J/m^2", "R": "m", "alpha": "rad",
        "poisson": "dimensionless",
    }
    cov = {}
    if pcov is not None and np.all(np.isfinite(pcov)):
        for i, name in enumerate(free):
            for j, name2 in enumerate(free):
                cov[f"{name}__{name2}"] = float(pcov[i, j])
    return ContactMechanicsFitResult(
        model=model, success=True, parameters=params, parameter_units=units,
        covariance=cov if cov else None, residuals=residuals,
        predicted_force=predicted, included_indices=np.arange(start, end + 1),
        objective=objective, dof=dof, rmse=rmse, aic=aic, aicc=aicc, bic=bic,
        diagnostics={"n_points": n, "free_parameters": free},
        provenance={"fixed": fixed, "initial": initial, "window": (start, end)},
    )


def _extract_fit_inputs(prepared: ForcePreparationResult,
                        indentation: IndentationResult,
                        window: FitWindowResult) -> tuple[np.ndarray, np.ndarray, int, int]:
    approach = prepared.curve.extend
    if approach is None or approach.force is None:
        raise ForceMechanicsError(CURVE_NOT_FIT_ELIGIBLE, "no calibrated approach")
    f = np.asarray(approach.force, dtype=np.float64)
    return (
        np.asarray(indentation.indentation, dtype=np.float64),
        f,
        window.start_index,
        window.end_index,
    )


def fit_hertz_sphere(
    prepared: ForcePreparationResult,
    indentation: IndentationResult,
    window: FitWindowResult,
    *,
    tip_radius: float,
    poisson: float = 0.3,
    E_initial: float = 1e9,
) -> ContactMechanicsFitResult:
    _check_geometry(tip_radius=tip_radius, half_angle=None, poisson=poisson,
                    work_of_adhesion=None, punch_radius=None, model="hertz_sphere")
    delta, f, s, e = _extract_fit_inputs(prepared, indentation, window)
    return _fit_one("hertz_sphere", delta, f, s, e,
                    {"R": tip_radius, "poisson": poisson}, {"E": E_initial})


def fit_sneddon_cone(
    prepared: ForcePreparationResult,
    indentation: IndentationResult,
    window: FitWindowResult,
    *,
    half_angle: float,
    poisson: float = 0.3,
    E_initial: float = 1e9,
) -> ContactMechanicsFitResult:
    _check_geometry(tip_radius=None, half_angle=half_angle, poisson=poisson,
                    work_of_adhesion=None, punch_radius=None, model="sneddon_cone")
    delta, f, s, e = _extract_fit_inputs(prepared, indentation, window)
    return _fit_one("sneddon_cone", delta, f, s, e,
                    {"alpha": half_angle, "poisson": poisson}, {"E": E_initial})


def fit_flat_punch(
    prepared: ForcePreparationResult,
    indentation: IndentationResult,
    window: FitWindowResult,
    *,
    punch_radius: float,
    poisson: float = 0.3,
    E_initial: float = 1e9,
) -> ContactMechanicsFitResult:
    _check_geometry(tip_radius=None, half_angle=None, poisson=poisson,
                    work_of_adhesion=None, punch_radius=punch_radius,
                    model="flat_punch")
    delta, f, s, e = _extract_fit_inputs(prepared, indentation, window)
    return _fit_one("flat_punch", delta, f, s, e,
                    {"R": punch_radius, "poisson": poisson}, {"E": E_initial})


def fit_dmt(
    prepared: ForcePreparationResult,
    indentation: IndentationResult,
    window: FitWindowResult,
    *,
    tip_radius: float,
    poisson: float = 0.3,
    E_initial: float = 1e9,
    F_adh_initial: float = 1e-9,
) -> ContactMechanicsFitResult:
    _check_geometry(tip_radius=tip_radius, half_angle=None, poisson=poisson,
                    work_of_adhesion=None, punch_radius=None, model="dmt")
    if F_adh_initial < 0.0:
        raise ForceMechanicsError(INVALID_ADHESION_PARAMETER,
                                  "adhesion initial value must be non-negative")
    delta, f, s, e = _extract_fit_inputs(prepared, indentation, window)
    return _fit_one("dmt", delta, f, s, e,
                    {"R": tip_radius, "poisson": poisson},
                    {"E": E_initial, "F_adh": F_adh_initial})


def fit_jkr(
    prepared: ForcePreparationResult,
    indentation: IndentationResult,
    window: FitWindowResult,
    *,
    tip_radius: float,
    poisson: float = 0.3,
    E_initial: float = 1e9,
    w_initial: float = 1e-3,
) -> ContactMechanicsFitResult:
    _check_geometry(tip_radius=tip_radius, half_angle=None, poisson=poisson,
                    work_of_adhesion=w_initial, punch_radius=None, model="jkr")
    delta, f, s, e = _extract_fit_inputs(prepared, indentation, window)
    return _fit_one("jkr", delta, f, s, e,
                    {"R": tip_radius, "poisson": poisson},
                    {"E": E_initial, "w": w_initial})


def compare_contact_models(
    prepared: ForcePreparationResult,
    indentation: IndentationResult,
    window: FitWindowResult,
    *,
    models: tuple[str, ...] = ("hertz_sphere", "sneddon_cone", "flat_punch", "dmt"),
    tip_radius: float,
    half_angle: float = math.radians(20.0),
    punch_radius: float | None = None,
    poisson: float = 0.3,
) -> ModelComparisonResult:
    """Compare models over the IDENTICAL data subset; no physical-truth claim."""
    fits: list[ContactMechanicsFitResult] = []
    warnings: list[str] = []
    for model in models:
        if model not in MODELS:
            raise ValueError(f"unknown model {model!r}")
        try:
            if model == "hertz_sphere":
                fits.append(fit_hertz_sphere(prepared, indentation, window,
                                             tip_radius=tip_radius, poisson=poisson))
            elif model == "sneddon_cone":
                fits.append(fit_sneddon_cone(prepared, indentation, window,
                                             half_angle=half_angle, poisson=poisson))
            elif model == "flat_punch":
                fits.append(fit_flat_punch(prepared, indentation, window,
                                           punch_radius=punch_radius or tip_radius,
                                           poisson=poisson))
            elif model == "dmt":
                fits.append(fit_dmt(prepared, indentation, window,
                                    tip_radius=tip_radius, poisson=poisson))
            else:  # jkr
                fits.append(fit_jkr(prepared, indentation, window,
                                    tip_radius=tip_radius, poisson=poisson))
        except ForceMechanicsError as exc:
            warnings.append(f"{model}: {exc.code}")
    if not fits:
        raise ForceMechanicsError(OPTIMIZATION_FAILED, "no model fit succeeded")
    delta_aicc = {fit.model: fit.aicc - min(f.aicc for f in fits) for fit in fits}
    total_w = sum(math.exp(-0.5 * d) for d in delta_aicc.values())
    weights = {m: math.exp(-0.5 * delta_aicc[m]) / total_w for m in delta_aicc}
    best = min(fits, key=lambda f: f.aicc)
    # ambiguous when the runner-up retains considerable support
    # (Delta AICc < 4, Burnham & Anderson); nested near-ties land just
    # above 2 AICc units, so 4 is the honest "cannot distinguish" boundary
    ambiguous = (sorted(f.aicc for f in fits)[1] - best.aicc < 4.0
                 if len(fits) > 1 else False)
    return ModelComparisonResult(
        fits=tuple(fits), delta_aicc=delta_aicc, weights=weights,
        recommended_model=best.model if not ambiguous else None,
        ambiguous=ambiguous, n_compared=len(fits), warnings=tuple(warnings),
        provenance={"window": (window.start_index, window.end_index),
                    "models": list(models), "criterion": "aicc"},
    )
