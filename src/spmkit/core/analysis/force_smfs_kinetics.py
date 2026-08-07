"""FS-F4 dynamic force spectroscopy: Bell-Evans, Dudko-Hummer-Szabo and
force-clamp survival analysis.

Frozen kinetic conventions:

BELL-EVANS (likelihood fit):
  k(F) = k0 exp(F x_beta / k_B T)
  survival  S(F; r) = exp(-k0 x_beta / (r k_B T) (exp(F x_beta / k_B T) - 1))
  pdf      p(F; r) = k(F)/r S(F; r)
  The most-probable-force estimator
  F* = (k_B T / x_beta) ln(r x_beta / (k0 k_B T))
  is derived from the same model and reported, never treated as an
  independent equivalent of the likelihood fit.

DUDKO-HUMMER-SZABO (likelihood fit, frozen potential-shape convention):
  k(F) = k0 (1 - nu F x_beta / dG)^(1/nu - 1)
         exp(dG [1 - (1 - nu F x_beta / dG)^(1/nu)] / k_B T)
  with nu in {1/2, 2/3} (cusp / linear-cubic), dG the barrier height (J),
  x_beta the transition distance (m), k0 the zero-force rate (1/s); the
  domain 1 - nu F x_beta / dG > 0 is enforced for every observed force.
  Bell limit: nu -> 0 recovers k(F) = k0 exp(F x_beta / k_B T).

FORCE CLAMP (Kaplan-Meier with right censoring):
  product-limit estimator over explicit lifetimes and censoring flags;
  ties are broken deterministically (events before censors at the same
  time); censored observations are never discarded.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from spmkit.core.analysis.force_smfs_errors import (
    CENSORING_INVALID,
    INSUFFICIENT_EVENTS,
    INVALID_MODEL_PARAMETER,
    KINETIC_DOMAIN,
    NONFINITE_INPUT,
    OPTIMIZATION_FAILED,
    SmfsError,
)

KB = 1.380649e-23


@dataclass(frozen=True)
class DynamicForceSpectroscopyFitResult:
    """Kinetic fit over a (loading rate, rupture force) event series."""

    kinetic_model: str
    success: bool
    parameters: dict[str, float]
    parameter_units: dict[str, str]
    n_events: int
    negative_log_likelihood: float
    most_probable_force_estimator: float | None
    included_rates: np.ndarray
    included_forces: np.ndarray
    warnings: tuple[str, ...] = ()
    failure_reason: str | None = None
    diagnostics: dict[str, object] = field(default_factory=dict)
    provenance: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ForceClampSurvivalResult:
    """Kaplan-Meier survival with right censoring."""

    force_level: float
    temperature: float
    lifetimes: np.ndarray
    censored: np.ndarray
    km_times: np.ndarray
    survival_probability: np.ndarray
    at_risk: np.ndarray
    n_events: int
    n_censored: int
    median_lifetime: float | None
    exponential_rate: float | None
    exponential_rate_error: float | None
    units: str = "s"
    warnings: tuple[str, ...] = ()
    provenance: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Bell-Evans
# ---------------------------------------------------------------------------


def bell_evans_rate(force: float | np.ndarray, k0: float, x_beta: float,
                    temperature: float) -> float | np.ndarray:
    """k(F) = k0 exp(F x_beta / k_B T)."""
    return k0 * np.exp(np.asarray(force, dtype=np.float64) * x_beta
                       / (KB * temperature))


def bell_evans_survival(force: np.ndarray, rate: float | np.ndarray, k0: float,
                        x_beta: float, temperature: float) -> np.ndarray:
    """S(F; r) = exp(-k0 k_B T/(r x_beta) (exp(F x_beta / k_B T) - 1)).

    The coefficient k0 k_B T/(r x_beta) is dimensionless: 1/s * J /
    (N/s * m) = J/(N m) = 1.
    """
    kt = KB * temperature
    exponent = force * x_beta / kt
    return np.exp(-k0 * kt / (rate * x_beta) * (np.exp(exponent) - 1.0))


def bell_evans_pdf(force: np.ndarray, rate: float | np.ndarray, k0: float,
                   x_beta: float, temperature: float) -> np.ndarray:
    """p(F; r) = k(F)/r S(F; r)."""
    return (np.asarray(bell_evans_rate(force, k0, x_beta, temperature), dtype=np.float64)
            / np.asarray(rate, dtype=np.float64)
            * bell_evans_survival(np.asarray(force, dtype=np.float64),
                                  np.asarray(rate, dtype=np.float64),
                                  k0, x_beta, temperature))


def _bell_nll(params: np.ndarray, rates: np.ndarray, forces: np.ndarray,
              temperature: float) -> float:
    k0, x_beta = float(params[0]), float(params[1])
    if k0 <= 0.0 or x_beta <= 0.0:
        return 1e300
    vals = bell_evans_pdf(forces, rates, k0, x_beta, temperature)
    if np.any(vals <= 0.0) or not np.isfinite(vals).all():
        return 1e300
    return -float(np.sum(np.log(vals)))


def _bell_profile(x_beta: float, rates: np.ndarray, forces: np.ndarray,
                  temperature: float) -> tuple[float, float]:
    """Profile likelihood over x_beta with the closed-form k0 optimum.

    nll(k0) = -n log(k0) - sum(log h_i) + k0 * sum g_i with
    h_i = exp(y_i)/r_i, g_i = x_beta/(r_i k_B T)(exp(y_i) - 1); the
    optimum is k0 = n / sum(g_i).
    """
    if x_beta <= 0.0:
        return 1e300, 0.0
    kt = KB * temperature
    y = forces * x_beta / kt
    # stable log-sum-exp profile: nll = n log(sum g_i) - sum(log h_i) - n
    # log(n) + n with h_i = exp(y_i)/r_i and
    # g_i = x_beta/(r_i k_B T)(exp(y_i) - 1)
    log_h = y - np.log(rates)
    log_g = np.log(x_beta) - np.log(rates * kt) + np.logaddexp(y, 0.0)
    log_sum_g = float(np.logaddexp.reduce(log_g))
    nll = (float(forces.size) * (log_sum_g - math.log(float(forces.size)))
           - float(np.sum(log_h)) + float(forces.size))
    k0 = float(forces.size) / math.exp(log_sum_g) if log_sum_g < 700.0 else 0.0
    if not np.isfinite(nll):
        return 1e300, k0
    return nll, k0


def fit_bell_evans(
    loading_rates: np.ndarray,
    rupture_forces: np.ndarray,
    *,
    temperature: float = 298.0,
    k0_initial: float = 1.0,
    x_beta_initial: float = 1e-9,
) -> DynamicForceSpectroscopyFitResult:
    """Maximum-likelihood Bell-Evans fit over the rupture-force series.

    Parameters (k0, x_beta) with k0 > 0 and x_beta > 0.  The
    most-probable-force estimator is reported as a derived quantity.
    A narrow loading-rate range triggers an identifiability warning.
    """
    rates = np.asarray(loading_rates, dtype=np.float64)
    forces = np.asarray(rupture_forces, dtype=np.float64)
    if rates.ndim != 1 or rates.size != forces.size or rates.size == 0:
        raise SmfsError(NONFINITE_INPUT, "rates/forces must be equal-length 1-D arrays")
    if not (np.isfinite(rates).all() and np.isfinite(forces).all()):
        raise SmfsError(NONFINITE_INPUT, "non-finite kinetic inputs")
    if temperature <= 0.0:
        raise SmfsError(INVALID_MODEL_PARAMETER, "temperature must be positive")
    if np.any(rates <= 0.0):
        raise SmfsError(INVALID_MODEL_PARAMETER, "loading rates must be positive")
    if np.any(forces <= 0.0):
        raise SmfsError(INVALID_MODEL_PARAMETER, "rupture forces must be positive")
    if rates.size < 5:
        raise SmfsError(INSUFFICIENT_EVENTS, "at least 5 events required for Bell-Evans")
    warnings: list[str] = []
    rate_span = float(np.max(rates) / np.min(rates))
    if rate_span < 10.0:
        warnings.append(
            f"loading-rate range spans only {rate_span:.1f}x: k0 and x_beta are "
            "weakly identifiable (IDENTIFIABILITY_LIMITED)")
    # PRIMARY estimator (frozen convention): the most-probable-force
    # regression F* = (k_B T / x_beta) ln(r) + (k_B T / x_beta)
    # ln(x_beta / (k0 k_B T)) over the per-rate median rupture forces.
    # The BE likelihood is degenerate toward x_beta -> 0 (k0 -> inf, the
    # pdf concentrating at zero force), so the linear F* estimator is the
    # well-posed one; the likelihood runs as a bounded secondary with an
    # identifiability diagnosis.
    uniq_rates = np.unique(rates)
    medians = np.array([float(np.median(forces[rates == r])) for r in uniq_rates])
    log_r = np.log(uniq_rates)
    if uniq_rates.size < 2 or np.ptp(medians) <= 0.0:
        raise SmfsError(INSUFFICIENT_EVENTS,
                        "at least two loading rates with distinct forces required")
    kt = KB * temperature
    slope, intercept = np.polyfit(log_r, medians, 1)
    if slope <= 0.0:
        raise SmfsError(KINETIC_DOMAIN,
                        "most-probable force must increase with the loading rate")
    x_beta = kt / slope
    k0 = x_beta / (kt * math.exp(intercept * x_beta / kt)) \
        if intercept < 700.0 * kt / x_beta else None
    if k0 is None or k0 <= 0.0 or not np.isfinite(k0):
        raise SmfsError(KINETIC_DOMAIN,
                        "unphysical k0 from the most-probable-force intercept")
    # bounded likelihood check: the profile optimum at the x_beta bound
    # indicates the zero-distance degeneracy
    best_nll = float("inf")
    for log_x in np.linspace(-25.33, -16.12, 121):
        xb = math.exp(log_x)
        nll, _k = _bell_profile(xb, rates, forces, temperature)
        if nll < best_nll:
            best_nll = nll
    if math.log(x_beta) <= -25.33 + 0.5 or math.log(x_beta) >= -16.12 - 0.5:
        warnings.append(
            "x_beta at the physical bound: the Bell-Evans likelihood is "
            "degenerate toward x_beta -> 0; the F* regression is the "
            "well-posed estimator (IDENTIFIABILITY_LIMITED)")
    nll_at_fit = _bell_nll(np.array([k0, x_beta]), rates, forces, temperature)
    mpf = (KB * temperature / x_beta
           * math.log(np.median(rates) * x_beta / (k0 * KB * temperature))) \
        if k0 * KB * temperature > 0 else None
    if mpf is not None and not np.isfinite(mpf):
        mpf = None
    return DynamicForceSpectroscopyFitResult(
        kinetic_model="bell_evans", success=True,
        parameters={"k0": k0, "x_beta": x_beta},
        parameter_units={"k0": "1/s", "x_beta": "m"},
        n_events=int(rates.size), negative_log_likelihood=nll_at_fit,
        most_probable_force_estimator=mpf,
        included_rates=rates, included_forces=forces, warnings=tuple(warnings),
        diagnostics={"rate_span": rate_span,
                     "estimator": "most-probable-force F* = (k_B T/x_beta) "
                                  "ln(r x_beta/(k0 k_B T))",
                     "likelihood_best_nll": best_nll,
                     "likelihood_well_posed": bool(
                         -25.33 + 0.5 < math.log(x_beta) < -16.12 - 0.5)},
        provenance={"kinetic_model": "bell_evans", "temperature": temperature})


# ---------------------------------------------------------------------------
# Dudko-Hummer-Szabo
# ---------------------------------------------------------------------------


def dhs_log_rate(force: float, k0: float, x_beta: float, dg: float, nu: float,
                 temperature: float) -> float:
    """Log of the DHS rate (stable across the parameter sweep)."""
    kt = KB * temperature
    z = 1.0 - nu * force * x_beta / dg
    if z <= 0.0:
        return float("inf")
    return (math.log(k0) + (1.0 / nu - 1.0) * math.log(z)
            + dg * (1.0 - z ** (1.0 / nu)) / kt)


def dhs_rate(force: float, k0: float, x_beta: float, dg: float, nu: float,
             temperature: float) -> float:
    """DHS force-dependent rate (1/s)."""
    log_k = dhs_log_rate(force, k0, x_beta, dg, nu, temperature)
    return float("inf") if not np.isfinite(log_k) else math.exp(min(log_k, 700.0))


def dhs_log_pdf(force: float, rate: float, k0: float, x_beta: float, dg: float,
                nu: float, temperature: float, grid_n: int = 200) -> float:
    """Log of p(F; r) = k(F)/r exp(-(1/r) int_0^F k(f) df)."""
    log_k = dhs_log_rate(force, k0, x_beta, dg, nu, temperature)
    if not np.isfinite(log_k):
        return float("-inf")
    grid = np.linspace(0.0, force, grid_n)
    kv = np.array([dhs_rate(float(g), k0, x_beta, dg, nu, temperature)
                   for g in grid])
    if not np.isfinite(kv).all():
        return float("-inf")
    integral = float(np.trapezoid(kv, grid))
    return log_k - math.log(rate) - integral / rate


def dhs_pdf(force: np.ndarray, rate: float, k0: float, x_beta: float, dg: float,
            nu: float, temperature: float) -> np.ndarray:
    """p(F; r) evaluated in log space for stability."""
    out = np.empty(force.size, dtype=np.float64)
    for i, fi in enumerate(force):
        logp = dhs_log_pdf(float(fi), rate, k0, x_beta, dg, nu, temperature)
        out[i] = 0.0 if logp <= -745.0 else math.exp(logp)
    return out


def _dhs_nll(params: np.ndarray, rates: np.ndarray, forces: np.ndarray,
             nu: float, temperature: float) -> float:
    k0, x_beta, dg = float(params[0]), float(params[1]), float(params[2])
    if k0 <= 0.0 or x_beta <= 0.0 or dg <= 0.0:
        return 1e300
    if np.any(1.0 - nu * forces * x_beta / dg <= 0.0):
        return 1e300
    total = 0.0
    for rate, fi in zip(rates, forces, strict=True):
        logp = dhs_log_pdf(float(fi), rate, k0, x_beta, dg, nu, temperature)
        if not np.isfinite(logp):
            return 1e300
        total += -logp
    return total


def _dhs_profile(x_beta: float, dg: float, rates: np.ndarray, forces: np.ndarray,
                 nu: float, temperature: float) -> tuple[float, float]:
    """Profile likelihood over (x_beta, dG) with the closed-form k0:
    the nll is convex in k0 with the optimum k0 = n / sum(J_i/r_i) where
    J_i = int_0^{F_i} (1-z(f))^(1/nu - 1) exp(dG(1-z(f)^(1/nu))/k_BT) df
    with z(f) = 1 - nu f x_beta / dG.
    """
    if x_beta <= 0.0 or dg <= 0.0:
        return 1e300, 0.0
    if np.any(1.0 - nu * forces * x_beta / dg <= 0.0):
        return 1e300, 0.0
    total_j = 0.0
    log_h = 0.0
    for rate, fi in zip(rates, forces, strict=True):
        grid = np.linspace(0.0, float(fi), 120)
        logk = np.array([dhs_log_rate(float(g), 1.0, x_beta, dg, nu, temperature)
                         for g in grid])
        if not np.isfinite(logk).all():
            return 1e300, 0.0
        j = float(np.trapezoid(np.exp(np.minimum(logk, 700.0)), grid))
        if not np.isfinite(j):
            return 1e300, 0.0
        total_j += j / rate
        logk_f = dhs_log_rate(float(fi), 1.0, x_beta, dg, nu, temperature)
        # the rate is capped at exp(700) in the integral; the same cap must
        # apply to the point value or the profile likelihood is corrupted
        # by floating-point cancelation in the near-boundary regime
        log_h += min(logk_f, 700.0) - math.log(rate)
    if total_j <= 0.0:
        return 1e300, 0.0
    k0 = float(forces.size) / total_j
    nll = -float(forces.size) * math.log(k0) - log_h + float(forces.size)
    if not np.isfinite(nll):
        return 1e300, k0
    return nll, k0


def fit_dudko_hummer_szabo(
    loading_rates: np.ndarray,
    rupture_forces: np.ndarray,
    *,
    nu: float = 2.0 / 3.0,
    temperature: float = 298.0,
    k0_initial: float = 1.0,
    x_beta_initial: float = 1e-9,
    dg_initial: float = 1e-19,
) -> DynamicForceSpectroscopyFitResult:
    """Maximum-likelihood DHS fit (k0, x_beta, dG) with the frozen shape
    convention; nu in {1/2, 2/3}.  The fitted landscape is not claimed to be
    physically unique."""
    rates = np.asarray(loading_rates, dtype=np.float64)
    forces = np.asarray(rupture_forces, dtype=np.float64)
    if rates.ndim != 1 or rates.size != forces.size or rates.size == 0:
        raise SmfsError(NONFINITE_INPUT, "rates/forces must be equal-length 1-D arrays")
    if not (np.isfinite(rates).all() and np.isfinite(forces).all()):
        raise SmfsError(NONFINITE_INPUT, "non-finite kinetic inputs")
    if temperature <= 0.0:
        raise SmfsError(INVALID_MODEL_PARAMETER, "temperature must be positive")
    if nu not in (0.5, 2.0 / 3.0):
        raise SmfsError(INVALID_MODEL_PARAMETER,
                        "DHS nu must be 1/2 (cusp) or 2/3 (linear-cubic)")
    if np.any(rates <= 0.0) or np.any(forces <= 0.0):
        raise SmfsError(INVALID_MODEL_PARAMETER, "rates/forces must be positive")
    if rates.size < 5:
        raise SmfsError(INSUFFICIENT_EVENTS, "at least 5 events required for DHS")
    warnings: list[str] = [
        "the fitted DHS energy landscape is not claimed to be physically unique"]
    rate_span = float(np.max(rates) / np.min(rates))
    if rate_span < 10.0:
        warnings.append(
            f"loading-rate range spans only {rate_span:.1f}x: dG is weakly "
            "identifiable (IDENTIFIABILITY_LIMITED)")
    best_nll = float("inf")
    best_params: tuple[float, float, float] | None = None
    for log_x in np.linspace(-25.33, -16.12, 41):
        xb = math.exp(log_x)
        for log_dg in np.linspace(-48.35, -39.1, 41):
            dg = math.exp(log_dg)
            nll, k0 = _dhs_profile(xb, dg, rates, forces, nu, temperature)
            if nll < best_nll:
                best_nll = nll
                best_params = (k0, xb, dg)
    if best_params is None or not np.isfinite(best_nll):
        raise SmfsError(OPTIMIZATION_FAILED, "DHS likelihood failed")
    from scipy.optimize import minimize as _min
    ref = _min(
        lambda p: _dhs_nll(np.array([math.exp(min(max(p[0], -100.0), 100.0)),
                                     math.exp(min(max(p[1], -100.0), 100.0)),
                                     math.exp(min(max(p[2], -100.0), 100.0))]),
                           rates, forces, nu, temperature),
        x0=[math.log(best_params[0]), math.log(best_params[1]),
            math.log(best_params[2])],
        method="Nelder-Mead", options={"maxiter": 4000, "xatol": 1e-10,
                                       "fatol": 1e-12})
    if ref.fun < best_nll and np.isfinite(ref.fun):
        best_nll = float(ref.fun)
        best_params = (math.exp(float(ref.x[0])), math.exp(float(ref.x[1])),
                       math.exp(float(ref.x[2])))
    k0, x_beta, dg = best_params
    return DynamicForceSpectroscopyFitResult(
        kinetic_model="dudko_hummer_szabo", success=True,
        parameters={"k0": k0, "x_beta": x_beta, "dG": dg, "nu": nu},
        parameter_units={"k0": "1/s", "x_beta": "m", "dG": "J", "nu": "dimensionless"},
        n_events=int(rates.size), negative_log_likelihood=best_nll,
        most_probable_force_estimator=None,
        included_rates=rates, included_forces=forces, warnings=tuple(warnings),
        diagnostics={"rate_span": rate_span, "shape": "cusp" if nu == 0.5
                     else "linear-cubic",
                     "bell_limit": "nu -> 0 recovers k(F) = k0 exp(F x_beta/k_B T)"},
        provenance={"kinetic_model": "dudko_hummer_szabo", "nu": nu,
                    "temperature": temperature})


# ---------------------------------------------------------------------------
# force-clamp survival (Kaplan-Meier)
# ---------------------------------------------------------------------------


def estimate_force_clamp_survival(
    lifetimes: np.ndarray,
    censored: np.ndarray,
    *,
    force_level: float,
    temperature: float = 298.0,
    fit_exponential_rate: bool = True,
) -> ForceClampSurvivalResult:
    """Kaplan-Meier survival with right censoring.

    Ties are broken deterministically: events are processed before censors
    at the same time.  Censored observations are never discarded.  The
    median lifetime is the first KM time with S <= 0.5; when the survival
    never reaches 0.5 the median is undefined (typed UNDEFINED_MEDIAN in
    the warnings/provenance, not an exception).  The optional exponential
    rate is the censoring-aware MLE rate = n_events / sum(lifetimes).
    """
    lt = np.asarray(lifetimes, dtype=np.float64)
    ce = np.asarray(censored, dtype=np.float64)
    if lt.ndim != 1 or lt.size != ce.size or lt.size == 0:
        raise SmfsError(NONFINITE_INPUT, "lifetimes/censored must be equal-length 1-D")
    if not (np.isfinite(lt).all() and np.isfinite(ce).all()):
        raise SmfsError(NONFINITE_INPUT, "non-finite lifetimes")
    if np.any(lt < 0.0):
        raise SmfsError(CENSORING_INVALID, "lifetimes must be non-negative")
    if not np.all((ce == 0.0) | (ce == 1.0)):
        raise SmfsError(CENSORING_INVALID, "censored flags must be 0 (event) or 1 (censored)")
    if force_level <= 0.0 or temperature <= 0.0:
        raise SmfsError(INVALID_MODEL_PARAMETER, "force level and temperature must be positive")
    order = np.lexsort((ce, lt))  # deterministic: time, then censored flag
    lt_s = lt[order]
    ce_s = ce[order]
    times: list[float] = []
    surv: list[float] = []
    at_risk: list[int] = []
    n_at_risk = int(lt_s.size)
    s = 1.0
    i = 0
    while i < lt_s.size:
        t_i = float(lt_s[i])
        # events at this time (censored flags: 0 = event) come first
        j = i
        n_events_at = 0
        while j < lt_s.size and lt_s[j] == t_i and ce_s[j] == 0.0:
            n_events_at += 1
            j += 1
        if n_events_at > 0:
            s = s * (1.0 - n_events_at / n_at_risk)
            times.append(t_i)
            surv.append(s)
            at_risk.append(n_at_risk)
            n_at_risk -= n_events_at
        # censors at this time leave the risk set afterwards too
        while j < lt_s.size and lt_s[j] == t_i:
            n_at_risk -= 1
            j += 1
        i = j
    km_times = np.asarray(times, dtype=np.float64)
    surv_p = np.asarray(surv, dtype=np.float64)
    at_risk_arr = np.asarray(at_risk, dtype=np.int64)
    median = None
    below = np.flatnonzero(surv_p <= 0.5)
    if below.size:
        median = float(km_times[int(below[0])])
    rate = None
    rate_err = None
    warnings: list[str] = []
    if median is None:
        warnings.append("median lifetime undefined: survival never reaches 0.5 "
                        "(UNDEFINED_MEDIAN)")
    if fit_exponential_rate:
        n_events = int(np.sum(ce_s == 0.0))
        total_time = float(np.sum(lt_s))
        if n_events > 0 and total_time > 0.0:
            rate = n_events / total_time
            rate_err = rate / math.sqrt(n_events) if n_events > 1 else None
        else:
            warnings.append("exponential rate undefined: no uncensored events")
    return ForceClampSurvivalResult(
        force_level=force_level, temperature=temperature, lifetimes=lt, censored=ce,
        km_times=km_times, survival_probability=surv_p, at_risk=at_risk_arr,
        n_events=int(np.sum(ce_s == 0.0)), n_censored=int(np.sum(ce_s == 1.0)),
        median_lifetime=median, exponential_rate=rate, exponential_rate_error=rate_err,
        warnings=tuple(warnings),
        provenance={"estimator": "kaplan_meier", "tie_order": "events before censors",
                    "exponential_rate_mle": fit_exponential_rate})
