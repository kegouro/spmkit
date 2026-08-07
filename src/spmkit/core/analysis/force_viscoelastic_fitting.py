"""FS-F3 viscoelastic fitting: lumped models, Lee-Radok/Ting, comparison.

One shared least-squares engine (scipy.optimize.curve_fit, already a
required dependency) for the response-level fits; Lee-Radok and Ting fit the
SLS relaxation modulus through the hereditary integral.  Deterministic,
immutable results, typed failures, explicit parameter counts and AIC/AICc/BIC
over identical observations.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import curve_fit

from spmkit.core.analysis.force_foundation import ForcePreparationResult
from spmkit.core.analysis.force_time_protocol import (
    CreepResponseResult,
    RelaxationResponseResult,
    ViscoelasticProtocolResult,
)
from spmkit.core.analysis.force_viscoelastic_errors import (
    CURVE_NOT_FIT_ELIGIBLE,
    IDENTIFIABILITY_LIMITED,
    INVALID_MODEL_PARAMETER,
    MISSING_CONTACT,
    NO_VISCOELASTIC_FIT,
    NONFINITE_RESPONSE,
    OPTIMIZATION_FAILED,
    PROTOCOL_MODEL_MISMATCH,
    TING_HISTORY_UNAVAILABLE,
    ViscoelasticityError,
)
from spmkit.core.analysis.force_viscoelastic_models import (
    forward_generalized_maxwell_normalized,
    forward_kelvin_voigt_compliance,
    forward_maxwell_normalized,
    lee_radok_force,
    sls_creep_to_relaxation,
    sls_relaxation_to_creep,
    ting_force,
)


@dataclass(frozen=True)
class ViscoelasticFitResult:
    """Deterministic viscoelastic fit of one model."""

    model: str
    protocol: str
    response_type: str
    success: bool
    parameters: dict[str, float]
    parameter_units: dict[str, str]
    predicted_response: np.ndarray
    residuals: np.ndarray
    included_indices: np.ndarray
    objective: float
    covariance: dict[str, float] | None
    condition_number: float
    dof: int
    rmse: float
    aic: float
    aicc: float
    bic: float
    warnings: tuple[str, ...] = ()
    failure_reason: str | None = None
    diagnostics: dict[str, object] = field(default_factory=dict)
    provenance: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ViscoelasticModelComparisonResult:
    """Model-relative comparison over identical observations."""

    fits: tuple[ViscoelasticFitResult, ...]
    delta_aicc: dict[str, float]
    weights: dict[str, float]
    recommended_model: str | None
    ambiguous: bool
    n_compared: int
    warnings: tuple[str, ...] = ()
    provenance: dict[str, object] = field(default_factory=dict)


_UNITS = {
    "E": "Pa", "E0": "Pa", "E_inf": "Pa", "E_ref": "Pa",
    "tau": "s", "tau_relax": "s", "tau_retard": "s",
    "eta": "Pa*s", "a": "dimensionless", "alpha": "dimensionless",
    "alpha_i": "dimensionless", "tau_i": "s",
    "J0": "m/N", "J_inf": "m/N", "J_inf_fit": "m/N",
    "e_inf": "dimensionless", "F0": "N", "F_inf": "N",
}


def _fit_response(t: np.ndarray, y: np.ndarray, model_func: Callable[..., np.ndarray],
                  p0: list[float],
                  bounds: tuple[list[float], list[float]],
                  names: list[str], maxfev: int = 20000,
                  starts: list[list[float]] | None = None) -> tuple:
    """Shared deterministic response fit engine (returns popt, pcov).

    A deterministic multi-start (explicit start list, best objective wins)
    protects against flat-valley local minima in the time-constant
    directions.
    """
    t = np.asarray(t, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if t.ndim != 1 or t.size != y.size or t.size == 0:
        raise ViscoelasticityError(NONFINITE_RESPONSE, "invalid response arrays")
    if not (np.isfinite(t).all() and np.isfinite(y).all()):
        raise ViscoelasticityError(NONFINITE_RESPONSE, "non-finite response data")
    if t.size < len(p0) + 2:
        raise ViscoelasticityError(NO_VISCOELASTIC_FIT,
                                   f"too few samples for {len(p0)} parameters")
    candidates = starts if starts else [p0]
    best: tuple | None = None
    best_sse = float("inf")
    for start in candidates:
        try:
            popt, pcov = curve_fit(model_func, t, y, p0=list(start), bounds=bounds,
                                   maxfev=maxfev)
            sse = float(np.sum((model_func(t, *popt) - y) ** 2))
        except Exception:  # noqa: BLE001 - a failed start is skipped
            continue
        if sse < best_sse:
            best_sse = sse
            best = (popt, pcov)
    if best is None:
        raise ViscoelasticityError(OPTIMIZATION_FAILED,
                                   "optimizer failed from all deterministic starts")
    return best


def _finalize_fit(model: str, protocol: str, response_type: str, t: np.ndarray,
                  y: np.ndarray, params: dict[str, float], units: dict[str, str],
                  predicted: np.ndarray, popt: np.ndarray, pcov: np.ndarray | None,
                  names: list[str], idx: np.ndarray, warnings: list[str],
                  provenance: dict[str, object]) -> ViscoelasticFitResult:
    residuals = y - predicted
    n = y.size
    k = len(names)
    dof = n - k
    sse = float(np.sum(residuals**2))
    rmse = float(np.sqrt(np.mean(residuals**2)))
    aic = n * math.log(sse / n + 1e-300) + 2 * k
    aicc = aic + (2 * k * (k + 1)) / max(1, n - k - 1)
    bic = n * math.log(sse / n + 1e-300) + k * math.log(n)
    cov = {}
    cond = 0.0
    if pcov is not None and np.all(np.isfinite(pcov)):
        for i, a in enumerate(names):
            for j, b in enumerate(names):
                cov[f"{a}__{b}"] = float(pcov[i, j])
        try:
            cond = float(np.linalg.cond(pcov))
        except np.linalg.LinAlgError:  # pragma: no cover - degenerate matrix
            cond = float("inf")
    return ViscoelasticFitResult(
        model=model, protocol=protocol, response_type=response_type, success=True,
        parameters=params, parameter_units=units, predicted_response=predicted,
        residuals=residuals, included_indices=idx, objective=sse,
        covariance=cov if cov else None, condition_number=cond, dof=dof, rmse=rmse,
        aic=aic, aicc=aicc, bic=bic, warnings=tuple(warnings),
        diagnostics={"n_points": n, "free_parameters": names},
        provenance=provenance,
    )


def _response_arrays(response: object, kind: str) -> tuple[np.ndarray, np.ndarray]:
    if kind == "creep":
        if not isinstance(response, CreepResponseResult):
            raise ViscoelasticityError(
                PROTOCOL_MODEL_MISMATCH,
                "Kelvin-Voigt/SLS-creep fits require a CreepResponseResult")
        return (np.asarray(response.relative_time, dtype=np.float64),
                np.asarray(response.compliance_proxy, dtype=np.float64))
    if not isinstance(response, RelaxationResponseResult):
        raise ViscoelasticityError(
            PROTOCOL_MODEL_MISMATCH,
            "relaxation fits require a RelaxationResponseResult")
    return (np.asarray(response.relative_time, dtype=np.float64),
            np.asarray(response.normalized_force, dtype=np.float64))


def _modulus_from_hold(response: RelaxationResponseResult, tip_radius: float,
                       poisson: float) -> tuple[float, float]:
    """E0 from the hold force and indentation via the spherical contact."""
    d0 = float(response.indentation[0])
    if d0 <= 0.0:
        raise ViscoelasticityError(MISSING_CONTACT, "hold indentation must be positive")
    f0 = response.force_at_hold_start
    est = f0 / ((4.0 / 3.0) * math.sqrt(tip_radius) * d0**1.5)
    return est * (1.0 - poisson**2), d0


def fit_kelvin_voigt(response: CreepResponseResult, *,
                     E_initial: float | None = None,
                     tau_initial: float | None = None) -> ViscoelasticFitResult:
    """J(t) = (1/E)(1 - exp(-t/tau)); tau = eta/E (retardation time)."""
    t, y = _response_arrays(response, "creep")
    if E_initial is None:
        E_initial = 1.0 / max(float(y[-1]), 1e-300) if y[-1] > 0 else 1e3
    if tau_initial is None:
        tau_initial = float(t[-1]) / 3.0 if t[-1] > 0 else 1.0

    def model(tt: np.ndarray, e: float, tau: float) -> np.ndarray:
        return forward_kelvin_voigt_compliance(tt, e, tau)

    popt, pcov = _fit_response(
        t, y, model, [float(E_initial), float(tau_initial)],
        ([1e-9, 1e-12], [1e15, 1e12]), ["E", "tau"],
        starts=[[float(E_initial), float(tau_initial)],
                [float(E_initial), float(tau_initial) / 10.0],
                [float(E_initial), float(tau_initial) * 10.0]])
    E, tau = float(popt[0]), float(popt[1])
    params = {"E": E, "tau": tau, "eta": E * tau}
    predicted = model(t, E, tau)
    return _finalize_fit("kelvin_voigt", response_type="creep", protocol="CREEP",
                         t=t, y=y, params=params,
                         units={"E": "Pa", "tau": "s", "eta": "Pa*s"},
                         predicted=predicted, popt=popt, pcov=pcov,
                         names=["E", "tau"], idx=response.hold_indices,
                         warnings=[], provenance={"model": "kelvin_voigt"})


def fit_maxwell(response: RelaxationResponseResult, *,
                tip_radius: float | None = None,
                poisson: float = 0.3) -> ViscoelasticFitResult:
    """n(t) = exp(-t/tau); tau = eta/E.  E is recovered only when the tip
    radius is provided (spherical contact proportionality)."""
    t, y = _response_arrays(response, "relaxation")
    tau_initial = float(t[-1]) / 3.0 if t[-1] > 0 else 1.0
    popt, pcov = _fit_response(
        t, y, forward_maxwell_normalized, [tau_initial], ([1e-12], [1e12]), ["tau"])
    tau = float(popt[0])
    params = {"tau": tau}
    units = {"tau": "s"}
    warnings: list[str] = []
    if tip_radius is not None:
        if tip_radius <= 0.0:
            raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                       "tip radius must be positive")
        E0, _d0 = _modulus_from_hold(response, tip_radius, poisson)
        params["E"] = E0
        params["eta"] = E0 * tau
        units["E"] = "Pa"
        units["eta"] = "Pa*s"
    else:
        warnings.append("no tip radius: the modulus is not identifiable from "
                        "the normalized response alone")
    predicted = forward_maxwell_normalized(t, tau)
    return _finalize_fit("maxwell", response_type="relaxation", protocol="STRESS_RELAXATION",
                         t=t, y=y, params=params, units=units, predicted=predicted,
                         popt=popt, pcov=pcov, names=["tau"], idx=response.hold_indices,
                         warnings=warnings, provenance={"model": "maxwell"})


def fit_standard_linear_solid(
        response: RelaxationResponseResult | CreepResponseResult, *,
        tip_radius: float | None = None,
        poisson: float = 0.3,
        tau_initial: float | None = None) -> ViscoelasticFitResult:
    """SLS on a relaxation or creep response.

    Relaxation: n(t) = 1 - a(1 - exp(-t/tau_relax)), a = (E0-E_inf)/E0.
    Creep: J(t) = J_inf - (J_inf - J0) exp(-t/tau_retard).
    Both representations are reported with the standard conversions.
    """
    if isinstance(response, CreepResponseResult):
        t, y = _response_arrays(response, "creep")
        # the creep response is the compliance INCREMENT from the hold
        # start: (J_inf - J0) (1 - exp(-t/tau_retard)); the absolute level
        # J0 = indentation(0)/F_hold is carried by the response
        j0_abs = (float(response.indentation_at_hold_start)
                  / float(response.force_hold_value)) if response.force_hold_value else 0.0
        dj_initial = float(y[-1]) if y[-1] > 0 else 1e-9
        tau_init = float(t[-1]) / 3.0 if tau_initial is None else float(tau_initial)

        def model_creep(tt: np.ndarray, dj: float, tau: float) -> np.ndarray:
            return dj * (1.0 - np.exp(-tt / tau))

        popt, pcov = _fit_response(
            t, y, model_creep, [dj_initial, tau_init],
            ([1e-15, 1e-12], [1e6, 1e12]), ["dJ", "tau_retard"],
            starts=[[dj_initial, tau_init],
                    [dj_initial, tau_init * 4.0],
                    [dj_initial, tau_init / 4.0]])
        dj, tau_ret = float(popt[0]), float(popt[1])
        j0 = j0_abs
        j_inf = j0_abs + dj
        e0, e_inf, tau_rel = sls_creep_to_relaxation(j0, j_inf, tau_ret)
        params = {"J0": j0, "J_inf": j_inf, "tau_retard": tau_ret,
                  "E0": e0, "E_inf": e_inf, "tau_relax": tau_rel}
        units = {"J0": "m/N", "J_inf": "m/N", "tau_retard": "s",
                 "E0": "Pa", "E_inf": "Pa", "tau_relax": "s"}
        predicted = model_creep(t, dj, tau_ret)
        return _finalize_fit("standard_linear_solid", response_type="creep",
                             protocol="CREEP", t=t, y=y, params=params, units=units,
                             predicted=predicted, popt=popt, pcov=pcov,
                             names=["dJ", "tau_retard"],
                             idx=response.hold_indices, warnings=[],
                             provenance={"representation": "creep_increment"})

    t, y = _response_arrays(response, "relaxation")
    a_initial = max(0.0, min(1.0 - float(y[-1]), 0.5)) if y[-1] < 1.0 else 0.5
    tau_init = float(t[-1]) / 3.0 if tau_initial is None else float(tau_initial)

    def model_sls_relax(tt: np.ndarray, a: float, tau: float) -> np.ndarray:
        return 1.0 - a * (1.0 - np.exp(-tt / tau))

    popt, pcov = _fit_response(
        t, y, model_sls_relax, [a_initial, tau_init], ([0.0, 1e-12], [1.0, 1e12]),
        ["a", "tau_relax"])
    a, tau_rel = float(popt[0]), float(popt[1])
    params = {"a": a, "tau_relax": tau_rel}
    units = {"a": "dimensionless", "tau_relax": "s"}
    warnings: list[str] = []
    if tip_radius is not None:
        if tip_radius <= 0.0:
            raise ViscoelasticityError(INVALID_MODEL_PARAMETER, "tip radius must be positive")
        E0, _d0 = _modulus_from_hold(response, tip_radius, poisson)
        E_inf = E0 * (1.0 - a)
        j0, j_inf, tau_ret = sls_relaxation_to_creep(E0, E_inf, tau_rel)
        params.update({"E0": E0, "E_inf": E_inf, "tau_retard": tau_ret,
                       "J0": j0, "J_inf": j_inf})
        units.update({"E0": "Pa", "E_inf": "Pa", "tau_retard": "s",
                      "J0": "m/N", "J_inf": "m/N"})
    else:
        warnings.append("no tip radius: absolute moduli not identifiable from "
                        "the normalized relaxation response")
    predicted = model_sls_relax(t, a, tau_rel)
    return _finalize_fit("standard_linear_solid", response_type="relaxation",
                         protocol="STRESS_RELAXATION", t=t, y=y, params=params,
                         units=units, predicted=predicted, popt=popt, pcov=pcov,
                         names=["a", "tau_relax"], idx=response.hold_indices,
                         warnings=warnings, provenance={"representation": "relaxation"})


def fit_generalized_maxwell(response: RelaxationResponseResult, *,
                            n_terms: int = 2,
                            tip_radius: float | None = None,
                            poisson: float = 0.3) -> ViscoelasticFitResult:
    """n(t) = 1 - sum(alpha) + sum(alpha_i exp(-t/tau_i)), alpha_i >= 0,
    sum(alpha) <= 1, tau_i > 0.  Deterministic ordering by ascending tau;
    no claim that the recovered spectrum is unique."""
    if n_terms < 1 or n_terms > 8:
        raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                   "n_terms must be in [1, 8]")
    t, y = _response_arrays(response, "relaxation")
    span = float(t[-1]) if t[-1] > 0 else 1.0
    tau0 = np.geomspace(max(span * 1e-3, 1e-9), span, n_terms)
    alpha0 = np.full(n_terms, 1.0 / n_terms)
    p0 = list(alpha0) + list(tau0)

    def model_gm(tt: np.ndarray, *args: float) -> np.ndarray:
        al = np.asarray(args[:n_terms])
        ta = np.asarray(args[n_terms:])
        return forward_generalized_maxwell_normalized(tt, al, ta, _validate=False)

    lo = [0.0] * n_terms + [1e-9] * n_terms
    hi = [1.0] * n_terms + [1e9] * n_terms
    popt, pcov = _fit_response(t, y, model_gm, p0, (lo, hi),
                               [f"alpha_i[{i}]" for i in range(n_terms)]
                               + [f"tau_i[{i}]" for i in range(n_terms)])
    alpha = np.asarray(popt[:n_terms])
    tau = np.asarray(popt[n_terms:])
    if alpha.sum() > 1.0 + 1e-9 or np.any(alpha < -1e-9) or np.any(tau <= 0.0):
        raise ViscoelasticityError(
            IDENTIFIABILITY_LIMITED,
            f"Prony fit violates the public constraints (sum(alpha)="
            f"{alpha.sum():.3f}, min alpha={float(np.min(alpha)):.3e})")
    order = np.argsort(tau, kind="stable")
    tau = tau[order]
    alpha = alpha[order]
    warnings: list[str] = ["no claim that the recovered Prony spectrum is unique"]
    if n_terms >= 2:
        rel_gaps = np.diff(tau) / tau[:-1]
        if np.any(rel_gaps < 1e-3):
            warnings.append("nearly equal relaxation times: bounded identifiability")
    params = {}
    units = {}
    for i in range(n_terms):
        params[f"alpha_i[{i}]"] = float(alpha[i])
        params[f"tau_i[{i}]"] = float(tau[i])
        units[f"alpha_i[{i}]"] = "dimensionless"
        units[f"tau_i[{i}]"] = "s"
    predicted = model_gm(t, *np.concatenate([alpha, tau]))
    return _finalize_fit("generalized_maxwell", response_type="relaxation",
                         protocol="STRESS_RELAXATION", t=t, y=y, params=params,
                         units=units, predicted=predicted, popt=popt, pcov=pcov,
                         names=[f"alpha_i[{i}]" for i in range(n_terms)]
                         + [f"tau_i[{i}]" for i in range(n_terms)],
                         idx=response.hold_indices, warnings=warnings,
                         provenance={"n_terms": n_terms, "model": "generalized_maxwell"})


def fit_power_law_relaxation(response: RelaxationResponseResult, *,
                             t_ref: float | None = None,
                             with_equilibrium: bool = False,
                             tip_radius: float | None = None,
                             poisson: float = 0.3) -> ViscoelasticFitResult:
    """n(t) = (t/t_ref)^(-alpha) (optionally + equilibrium offset).

    t = 0 is excluded (singularity); t_ref defaults to the first positive
    relative hold time."""
    t, y = _response_arrays(response, "relaxation")
    # the power-law response is fitted from t_ref onward (t = 0 is
    # singular; the pre-reference plateau is excluded)
    keep = t >= t_ref if t_ref is not None else t > 0.0
    if keep.sum() < 4:
        raise ViscoelasticityError(NO_VISCOELASTIC_FIT,
                                   "not enough samples for the power law")
    t_pos = t[keep]
    y_pos = y[keep]
    idx = response.hold_indices[keep]
    if t_ref is None:
        t_ref = float(t_pos[0])
    if t_ref <= 0.0:
        raise ViscoelasticityError(INVALID_MODEL_PARAMETER, "t_ref must be positive")
    warnings = ["t = 0 excluded (singularity); t_ref = "
                f"{t_ref:.3e} s (first positive hold time)"] if t_ref == t_pos[0] \
        else [f"t_ref = {t_ref:.3e} s"]

    if with_equilibrium:
        def model_pl_eq(tt: np.ndarray, e_inf: float, alpha: float) -> np.ndarray:
            return e_inf + (1.0 - e_inf) * np.power(tt / t_ref, -alpha)

        popt, pcov = _fit_response(
            t_pos, y_pos, model_pl_eq, [max(float(y_pos[-1]), 0.0), 0.5],
            ([0.0, 1e-6], [1.0, 1.0 - 1e-6]), ["e_inf", "alpha"])
        e_inf, alpha = float(popt[0]), float(popt[1])
        params = {"e_inf": e_inf, "alpha": alpha, "t_ref": t_ref}
        units = {"e_inf": "dimensionless", "alpha": "dimensionless", "t_ref": "s"}
        predicted = model_pl_eq(t_pos, e_inf, alpha)
        names = ["e_inf", "alpha"]
    else:
        def model_pl(tt: np.ndarray, alpha: float) -> np.ndarray:
            return np.power(tt / t_ref, -alpha)

        popt, pcov = _fit_response(
            t_pos, y_pos, model_pl, [0.5], ([1e-6], [1.0 - 1e-6]), ["alpha"])
        alpha = float(popt[0])
        params = {"alpha": alpha, "t_ref": t_ref}
        units = {"alpha": "dimensionless", "t_ref": "s"}
        predicted = model_pl(t_pos, alpha)
        names = ["alpha"]
    if tip_radius is not None:
        E_ref, _d0 = _modulus_from_hold(response, tip_radius, poisson)
        params["E_ref"] = E_ref
        units["E_ref"] = "Pa"
    else:
        warnings.append("no tip radius: E_ref not identifiable from the "
                        "normalized response")
    return _finalize_fit("power_law_relaxation", response_type="relaxation",
                         protocol="STRESS_RELAXATION", t=t_pos, y=y_pos,
                         params=params, units=units, predicted=predicted,
                         popt=popt, pcov=pcov, names=names, idx=idx,
                         warnings=warnings, provenance={"t_ref": t_ref,
                                                        "with_equilibrium": with_equilibrium})


def _sls_integral_fit(t: np.ndarray, delta: np.ndarray, force: np.ndarray,
                      integral_func: Callable[..., np.ndarray], p0: list[float],
                      names: list[str], model_label: str,
                      protocol: str) -> ViscoelasticFitResult:
    """Fit the SLS relaxation modulus through a hereditary integral."""
    t = np.asarray(t, dtype=np.float64)
    delta = np.asarray(delta, dtype=np.float64)
    force = np.asarray(force, dtype=np.float64)
    if not (np.isfinite(t).all() and np.isfinite(delta).all()
            and np.isfinite(force).all()):
        raise ViscoelasticityError(NONFINITE_RESPONSE, "non-finite integral inputs")
    # normalize the objective by the force scale: the raw-Newton residual is
    # ~1e-9 while the parameters are ~1e3..1e6, which stalls the optimizer's
    # gradient tolerance; the normalization is a pure numerical scaling and
    # all reported quantities stay in SI units.  The SLS constraint
    # E_inf <= E0 is enforced by the parameterization a = (E0 - E_inf)/E0
    # with a in [0, 1].
    scale = float(np.max(np.abs(force))) or 1.0
    y = force / scale
    e0_0, e_inf_0, tau_0 = p0
    a_0 = max(0.0, min((e0_0 - e_inf_0) / e0_0, 1.0)) if e0_0 > 0 else 0.5

    def model_integral(tt: np.ndarray, e0: float, a: float, tau: float) -> np.ndarray:
        mp = {"E0": e0, "E_inf": e0 * (1.0 - a), "tau": tau}
        return integral_func(tt, delta, mp) / scale

    try:
        popt, pcov = curve_fit(model_integral, t, y, p0=[e0_0, a_0, tau_0],
                               bounds=([1e3, 0.0, 1e-9], [1e15, 1.0, 1e6]),
                               maxfev=40000)
    except ViscoelasticityError:
        raise
    except Exception as exc:  # noqa: BLE001 - typed wrapper
        raise ViscoelasticityError(OPTIMIZATION_FAILED, f"optimizer failed: {exc}") from exc
    e0 = float(popt[0])
    e_inf = e0 * (1.0 - float(popt[1]))
    tau = float(popt[2])
    predicted = model_integral(t, e0, float(popt[1]), tau) * scale
    params = {"E0": e0, "E_inf": e_inf, "tau_relax": tau}
    units = {"E0": "Pa", "E_inf": "Pa", "tau_relax": "s"}
    return _finalize_fit(model_label, response_type="full_curve", protocol=protocol,
                         t=t, y=force, params=params, units=units,
                         predicted=predicted, popt=popt, pcov=pcov, names=names,
                         idx=np.arange(t.size), warnings=[],
                         provenance={"integral": model_label})


def _loading_history(prepared: ForcePreparationResult,
                     protocol: ViscoelasticProtocolResult
                     ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    approach = prepared.curve.extend
    if approach is None or approach.separation is None or approach.force is None \
            or approach.time is None:
        raise ViscoelasticityError(MISSING_CONTACT, "no prepared approach branch")
    t = np.asarray(approach.time, dtype=np.float64)
    if t.size == 0 or not np.isfinite(t).all() or np.any(np.diff(t) <= 0.0):
        raise ViscoelasticityError(OPTIMIZATION_FAILED, "invalid approach time axis")
    reg = protocol.region("loading", "extend")
    if reg is None:
        raise ViscoelasticityError(PROTOCOL_MODEL_MISMATCH,
                                   "protocol has no loading region on the approach")
    a, b = reg.start_index, reg.end_index + 1
    if b > t.size:
        raise ViscoelasticityError(OPTIMIZATION_FAILED, "loading region out of range")
    sep = np.asarray(approach.separation, dtype=np.float64)
    ind = sep - float(prepared.contact.selected.coordinate)
    # trim to the contact onward: the loading history for the hereditary
    # integrals requires indentation >= 0 (documented trimming rule)
    t_region, ind_region = t[a:b], ind[a:b]
    keep = ind_region >= 0.0
    if keep.sum() < 5:
        raise ViscoelasticityError(OPTIMIZATION_FAILED,
                                   "loading region has no indentation >= 0 samples")
    return t_region[keep], ind_region[keep], keep


def fit_lee_radok_sphere(prepared: ForcePreparationResult,
                         protocol: ViscoelasticProtocolResult, *,
                         tip_radius: float,
                         poisson: float = 0.3,
                         E0_initial: float = 1e6,
                         E_inf_initial: float = 5e5,
                         tau_initial: float = 1.0) -> ViscoelasticFitResult:
    """Fit the SLS relaxation modulus through the Lee-Radok integral on the
    monotonic loading region (spherical contact, loading only)."""
    if tip_radius <= 0.0:
        raise ViscoelasticityError(INVALID_MODEL_PARAMETER, "tip radius must be positive")
    t, ind, keep = _loading_history(prepared, protocol)
    approach = prepared.curve.extend
    if approach is None or approach.force is None:
        raise ViscoelasticityError(CURVE_NOT_FIT_ELIGIBLE, "no calibrated approach")
    force = np.asarray(approach.force, dtype=np.float64)
    reg = protocol.region("loading", "extend")
    if reg is None:
        raise ViscoelasticityError(OPTIMIZATION_FAILED, "no loading region")
    f = force[reg.start_index: reg.end_index + 1][keep]
    if f.size != t.size:
        raise ViscoelasticityError(OPTIMIZATION_FAILED, "loading region length mismatch")
    return _sls_integral_fit(
        t, ind, f,
        lambda tt, delta, mp: lee_radok_force(tt, delta, mp, 1.0, tip_radius, poisson),
        [E0_initial, E_inf_initial, tau_initial], ["E0", "E_inf", "tau_relax"],
        "lee_radok_sphere", "LOADING_RAMP")


def fit_ting_sphere(
        prepared: ForcePreparationResult,
        protocol: ViscoelasticProtocolResult, *,
                    tip_radius: float,
                    poisson: float = 0.3,
                    E0_initial: float = 1e6,
                    E_inf_initial: float = 5e5,
                    tau_initial: float = 1.0) -> ViscoelasticFitResult:
    """Fit the SLS relaxation modulus through the Ting integral over the
    loading and unloading branches (contact-time memory)."""
    if tip_radius <= 0.0:
        raise ViscoelasticityError(INVALID_MODEL_PARAMETER, "tip radius must be positive")
    loading = protocol.region("loading", "extend")
    unloading = protocol.region("unloading", "retract")
    if loading is None or unloading is None:
        raise ViscoelasticityError(
            TING_HISTORY_UNAVAILABLE,
            "Ting requires a loading region on the approach and an unloading "
            "region on the retract")
    approach = prepared.curve.extend
    retract = prepared.curve.retract
    if approach is None or approach.force is None or approach.time is None:
        raise ViscoelasticityError(MISSING_CONTACT, "no prepared approach branch")
    if retract is None or retract.separation is None or retract.force is None \
            or retract.time is None:
        raise ViscoelasticityError(TING_HISTORY_UNAVAILABLE,
                                   "no prepared retract branch for the unloading")
    zc = float(prepared.contact.selected.coordinate)
    tl, il, keep = _loading_history(prepared, protocol)
    fl = np.asarray(approach.force, dtype=np.float64)[
        loading.start_index: loading.end_index + 1][keep]
    t_r = np.asarray(retract.time, dtype=np.float64)
    sep_r = np.asarray(retract.separation, dtype=np.float64)
    f_r = np.asarray(retract.force, dtype=np.float64)
    iu = sep_r[unloading.start_index: unloading.end_index + 1] - zc
    tu = t_r[unloading.start_index: unloading.end_index + 1]
    fu = f_r[unloading.start_index: unloading.end_index + 1]
    # truncate the unloading history at the contact (indentation >= 0):
    # out-of-contact samples carry no force and are outside the model
    keep_u = iu >= 0.0
    if keep_u.sum() < 5:
        raise ViscoelasticityError(TING_HISTORY_UNAVAILABLE,
                                   "unloading history has no in-contact samples")
    iu, tu, fu = iu[keep_u], tu[keep_u], fu[keep_u]
    if iu[0] > float(np.max(il)) + 1e-15:
        raise ViscoelasticityError(
            TING_HISTORY_UNAVAILABLE,
            "unloading indentation exceeds the loading maximum (missing history)")
    if tu[0] <= tl[-1]:
        # the retract time axis may restart at zero; treat it as continuing
        # from the loading end for the heredity evaluation
        tu = tu - tu[0] + tl[-1]

    t_full = np.concatenate([tl, tu])
    f_full = np.concatenate([fl, fu])
    scale = float(np.max(np.abs(f_full))) or 1.0
    y_full = f_full / scale
    a_0 = (max(0.0, min((E0_initial - E_inf_initial) / E0_initial, 1.0))
           if E0_initial > 0 else 0.5)

    def model_ting(tt: np.ndarray, e0: float, a: float, tau: float) -> np.ndarray:
        mp = {"E0": e0, "E_inf": e0 * (1.0 - a), "tau": tau}
        fl_ = lee_radok_force(tl, il, mp, 1.0, tip_radius, poisson)
        fu_ = ting_force(tl, il, tu, iu, mp, 1.0, tip_radius, poisson)[len(tl):]
        return np.concatenate([fl_, fu_]) / scale

    try:
        popt, pcov = curve_fit(model_ting, t_full, y_full, p0=[E0_initial, a_0, tau_initial],
                               bounds=([1e3, 0.0, 1e-9], [1e15, 1.0, 1e6]), maxfev=40000)
    except ViscoelasticityError:
        raise
    except Exception as exc:  # noqa: BLE001 - typed wrapper
        raise ViscoelasticityError(OPTIMIZATION_FAILED, f"optimizer failed: {exc}") from exc
    e0 = float(popt[0])
    e_inf = e0 * (1.0 - float(popt[1]))
    tau = float(popt[2])
    predicted = model_ting(t_full, e0, float(popt[1]), tau) * scale
    return _finalize_fit("ting_sphere", response_type="full_curve",
                         protocol="TRIANGULAR_LOADING", t=t_full, y=f_full,
                         params={"E0": e0, "E_inf": e_inf, "tau_relax": tau},
                         units={"E0": "Pa", "E_inf": "Pa", "tau_relax": "s"},
                         predicted=predicted, popt=popt, pcov=pcov,
                         names=["E0", "E_inf", "tau_relax"],
                         idx=np.arange(t_full.size), warnings=[],
                         provenance={"integral": "ting_sphere"})


RELAXATION_MODELS = ("maxwell", "standard_linear_solid", "generalized_maxwell",
                     "power_law_relaxation")
CREEP_MODELS = ("kelvin_voigt", "standard_linear_solid")


def compare_viscoelastic_models(
        response: RelaxationResponseResult | CreepResponseResult, *,
    models: tuple[str, ...] | None = None,
    tip_radius: float | None = None,
    poisson: float = 0.3,
    n_terms: int = 2,
    t_ref: float | None = None,
) -> ViscoelasticModelComparisonResult:
    """Model-relative AICc comparison over identical observations.

    No physical-truth claim: the weights are relative support on this
    response, not a probability of physical correctness.
    """
    if isinstance(response, CreepResponseResult):
        candidates = models or CREEP_MODELS
    else:
        candidates = models or RELAXATION_MODELS
    fits: list[ViscoelasticFitResult] = []
    warnings: list[str] = []
    for model in candidates:
        try:
            if model == "kelvin_voigt":
                if not isinstance(response, CreepResponseResult):
                    raise ViscoelasticityError(
                        PROTOCOL_MODEL_MISMATCH,
                        "kelvin_voigt requires a creep response")
                fits.append(fit_kelvin_voigt(response))
            elif model == "maxwell":
                if not isinstance(response, RelaxationResponseResult):
                    raise ViscoelasticityError(
                        PROTOCOL_MODEL_MISMATCH,
                        "maxwell requires a relaxation response")
                fits.append(fit_maxwell(response, tip_radius=tip_radius, poisson=poisson))
            elif model == "standard_linear_solid":
                fits.append(fit_standard_linear_solid(
                    response, tip_radius=tip_radius, poisson=poisson))
            elif model == "generalized_maxwell":
                if not isinstance(response, RelaxationResponseResult):
                    raise ViscoelasticityError(
                        PROTOCOL_MODEL_MISMATCH,
                        "generalized_maxwell requires a relaxation response")
                fits.append(fit_generalized_maxwell(
                    response, n_terms=n_terms, tip_radius=tip_radius, poisson=poisson))
            elif model == "power_law_relaxation":
                if not isinstance(response, RelaxationResponseResult):
                    raise ViscoelasticityError(
                        PROTOCOL_MODEL_MISMATCH,
                        "power_law_relaxation requires a relaxation response")
                fits.append(fit_power_law_relaxation(
                    response, t_ref=t_ref, tip_radius=tip_radius, poisson=poisson))
            else:
                raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                           f"unknown model {model!r}")
        except ViscoelasticityError as exc:
            warnings.append(f"{model}: {exc.code}")
    if not fits:
        raise ViscoelasticityError(NO_VISCOELASTIC_FIT, "no model fit succeeded")
    # common observation set: the union response samples of the successful
    # fits (each fit uses its own included indices; on identical responses
    # the sets coincide)
    idx0 = fits[0].included_indices
    for f in fits[1:]:
        if not np.array_equal(idx0, f.included_indices):
            warnings.append("fits use different observation sets; AICc not "
                            "strictly comparable")
    delta_aicc = {f.model: f.aicc - min(x.aicc for x in fits) for f in fits}
    total_w = sum(math.exp(-0.5 * d) for d in delta_aicc.values())
    weights = {m: math.exp(-0.5 * delta_aicc[m]) / total_w for m in delta_aicc}
    best = min(fits, key=lambda f: f.aicc)
    ambiguous = (sorted(f.aicc for f in fits)[1] - best.aicc < 4.0
                 if len(fits) > 1 else False)
    return ViscoelasticModelComparisonResult(
        fits=tuple(fits), delta_aicc=delta_aicc, weights=weights,
        recommended_model=best.model if not ambiguous else None,
        ambiguous=ambiguous, n_compared=len(fits), warnings=tuple(warnings),
        provenance={"criterion": "aicc", "response_type":
                    "creep" if isinstance(response, CreepResponseResult) else "relaxation"})
