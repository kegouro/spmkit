"""FS-F3 viscoelastic forward models and hereditary integrals.

Frozen equations (SI units).  Lumped models operate on normalized responses;
Lee-Radok and Ting are spherical-contact hereditary integrals.

Reduced modulus E* = E/(1-nu^2).  The spherical contact coefficient is
c = (4/3) sqrt(R) E*.

LEE-RADOK (monotonic loading only):
  F(t) = c * int_0^t E(t - t') d/dt' [delta(t')^1.5] dt'
  The contact radius a = sqrt(R*delta) must never decrease: delta must be
  monotone non-decreasing, else LEE_RADOK_NONMONOTONIC.

TING (loading + unloading, contact-time memory):
  loading  (t <= t_m): identical to Lee-Radok;
  unloading (t > t_m): F(t) = c * int_0^{t1(t)} E(t - t') d/dt' [delta(t')^1.5] dt'
  where t1(t) is the loading time with delta(t1) = delta(t) (the contact
  radius during unloading equals the loading radius at t1).  When the
  loading history cannot be reconstructed: TING_HISTORY_UNAVAILABLE.

Discrete quadrature (production): the Riemann-sum-in-increments rule
  F(t_i) = c * sum_{k<=i} E(t_i - t_k) * (delta_k^1.5 - delta_{k-1}^1.5)
with delta_{-1} = 0.  The independent oracle uses a different quadrature
(high-resolution substeps), so arithmetic order is cross-checked.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np

from spmkit.core.analysis.force_viscoelastic_errors import (
    INVALID_MODEL_PARAMETER,
    LEE_RADOK_NONMONOTONIC,
    PRONY_DUPLICATE_TAU,
    TING_HISTORY_UNAVAILABLE,
    ViscoelasticityError,
)


def reduced_modulus(young: float, poisson: float) -> float:
    """E* = E/(1 - nu^2)."""
    return young / (1.0 - poisson**2)


def spherical_coefficient(young: float, radius: float, poisson: float) -> float:
    """c = (4/3) sqrt(R) E*  (N/m^1.5)."""
    return (4.0 / 3.0) * math.sqrt(radius) * reduced_modulus(young, poisson)


# ---------------------------------------------------------------------------
# lumped forward responses
# ---------------------------------------------------------------------------


def forward_kelvin_voigt_compliance(t: np.ndarray, modulus: float,
                                    tau: float) -> np.ndarray:
    """J(t) = (1/E) (1 - exp(-t/tau)), tau = eta/E (retardation time)."""
    t = np.asarray(t, dtype=np.float64)
    if modulus <= 0.0 or tau <= 0.0:
        raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                   "Kelvin-Voigt: E > 0 and tau > 0 required")
    return (1.0 / modulus) * (1.0 - np.exp(-t / tau))


def forward_maxwell_modulus(t: np.ndarray, modulus: float, tau: float) -> np.ndarray:
    """E(t) = E exp(-t/tau), tau = eta/E (relaxation time)."""
    t = np.asarray(t, dtype=np.float64)
    if modulus <= 0.0 or tau <= 0.0:
        raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                   "Maxwell: E > 0 and tau > 0 required")
    return modulus * np.exp(-t / tau)


def forward_maxwell_normalized(t: np.ndarray, tau: float) -> np.ndarray:
    """n(t) = exp(-t/tau)."""
    t = np.asarray(t, dtype=np.float64)
    if tau <= 0.0:
        raise ViscoelasticityError(INVALID_MODEL_PARAMETER, "Maxwell: tau > 0 required")
    return np.exp(-t / tau)


def forward_sls_modulus(t: np.ndarray, modulus_0: float, modulus_inf: float,
                        tau_relax: float, *, _validate: bool = True) -> np.ndarray:
    """E(t) = E_inf + (E0 - E_inf) exp(-t/tau_relax).

    ``_validate`` is internal: the fit engine evaluates the raw formula
    during optimizer probing (which steps outside the feasible region) and
    validates the final parameters against this public contract instead.
    """
    t = np.asarray(t, dtype=np.float64)
    if _validate:
        if modulus_0 <= 0.0 or modulus_inf <= 0.0 or tau_relax <= 0.0:
            raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                       "SLS: E0 > 0, E_inf > 0, tau > 0 required")
        if modulus_inf > modulus_0:
            raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                       "SLS: E_inf must not exceed E0")
    return modulus_inf + (modulus_0 - modulus_inf) * np.exp(-t / tau_relax)


def forward_sls_compliance(t: np.ndarray, compliance_0: float,
                           compliance_inf: float, tau_retard: float, *,
                           _validate: bool = True) -> np.ndarray:
    """J(t) = J_inf - (J_inf - J0) exp(-t/tau_retard).

    ``_validate`` is internal: the fit engine evaluates the raw formula
    during optimizer probing and validates the final parameters against
    this public contract instead.
    """
    t = np.asarray(t, dtype=np.float64)
    if _validate:
        if compliance_0 <= 0.0 or compliance_inf <= 0.0 or tau_retard <= 0.0:
            raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                       "SLS creep: J0 > 0, J_inf > 0, tau > 0 required")
        if compliance_inf < compliance_0:
            raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                       "SLS creep: J_inf must not be below J0")
    return compliance_inf - (compliance_inf - compliance_0) * np.exp(-t / tau_retard)


def forward_generalized_maxwell_modulus(t: np.ndarray, modulus_inf: float,
                                        terms: np.ndarray) -> np.ndarray:
    """E(t) = E_inf + sum_i E_i exp(-t/tau_i).

    ``terms`` is an (n, 2) array of (E_i, tau_i) rows, ordered by ascending
    tau; E_i >= 0 and tau_i > 0 required; duplicate tau rejected.
    """
    t = np.asarray(t, dtype=np.float64)
    terms = np.asarray(terms, dtype=np.float64)
    if terms.ndim != 2 or terms.shape[1] != 2:
        raise ValueError("terms must be an (n, 2) array of (E_i, tau_i)")
    e_i, tau_i = terms[:, 0], terms[:, 1]
    if np.any(e_i < 0.0) or np.any(tau_i <= 0.0):
        raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                   "Prony: E_i >= 0 and tau_i > 0 required")
    if modulus_inf < 0.0:
        raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                   "Prony: E_inf >= 0 required")
    if tau_i.size > 1 and np.any(np.diff(tau_i) <= 0.0):
        raise ViscoelasticityError(
            PRONY_DUPLICATE_TAU,
            "Prony: tau_i must be strictly increasing (duplicates rejected)")
    out = np.full_like(t, float(modulus_inf), dtype=np.float64)
    for e, tau in zip(e_i, tau_i, strict=True):
        out = out + e * np.exp(-t / tau)
    return out


def forward_generalized_maxwell_normalized(t: np.ndarray, alpha: np.ndarray,
                                           tau: np.ndarray, *,
                                           _validate: bool = True) -> np.ndarray:
    """n(t) = 1 - sum(alpha) + sum(alpha_i exp(-t/tau_i)).

    alpha_i >= 0, sum(alpha) <= 1, tau_i > 0, strictly increasing tau.
    ``_validate`` is internal: the fit engine evaluates the raw formula
    during optimizer probing and validates the final parameters against
    this public contract instead.
    """
    t = np.asarray(t, dtype=np.float64)
    alpha = np.asarray(alpha, dtype=np.float64)
    tau = np.asarray(tau, dtype=np.float64)
    if _validate:
        if np.any(alpha < 0.0) or alpha.sum() > 1.0 + 1e-12:
            raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                       "Prony: alpha_i >= 0 and sum(alpha) <= 1 required")
        if np.any(tau <= 0.0):
            raise ViscoelasticityError(INVALID_MODEL_PARAMETER, "Prony: tau_i > 0 required")
        if tau.size > 1 and np.any(np.diff(tau) <= 0.0):
            raise ViscoelasticityError(PRONY_DUPLICATE_TAU,
                                       "Prony: tau_i must be strictly increasing")
    return 1.0 - float(alpha.sum()) + alpha @ np.exp(-t / tau[:, None])


def forward_power_law_modulus(t: np.ndarray, modulus_ref: float, alpha: float,
                              t_ref: float, modulus_inf: float = 0.0) -> np.ndarray:
    """E(t) = E_inf + E_ref (t/t_ref)^(-alpha), 0 < alpha < 1, t > 0.

    t = 0 is excluded (singularity); callers must start the response after
    the first positive relative time.
    """
    t = np.asarray(t, dtype=np.float64)
    if modulus_ref <= 0.0 or t_ref <= 0.0 or modulus_inf < 0.0:
        raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                   "power law: E_ref > 0, t_ref > 0, E_inf >= 0 required")
    if not (0.0 < alpha < 1.0):
        raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                   "power law: exponent alpha must be in (0, 1)")
    if np.any(t <= 0.0):
        raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                   "power law: t must be strictly positive (t=0 excluded)")
    return float(modulus_inf) + modulus_ref * np.power(t / t_ref, -alpha)


# ---------------------------------------------------------------------------
# SLS parameter conversions (relaxation <-> creep)
# ---------------------------------------------------------------------------


def sls_relaxation_to_creep(modulus_0: float, modulus_inf: float,
                            tau_relax: float) -> tuple[float, float, float]:
    """(J0, J_inf, tau_retard) from (E0, E_inf, tau_relax)."""
    if modulus_0 <= 0.0 or modulus_inf <= 0.0 or tau_relax <= 0.0 \
            or modulus_inf > modulus_0:
        raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                   "SLS conversion: 0 < E_inf <= E0, tau > 0 required")
    j0 = 1.0 / modulus_0
    j_inf = 1.0 / modulus_inf
    tau_ret = tau_relax * modulus_0 / modulus_inf
    return j0, j_inf, tau_ret


def sls_creep_to_relaxation(compliance_0: float, compliance_inf: float,
                            tau_retard: float) -> tuple[float, float, float]:
    """(E0, E_inf, tau_relax) from (J0, J_inf, tau_retard).

    tau_relax = tau_retard * E_inf / E0 = tau_retard * J0 / J_inf
    (the inverse of tau_retard = tau_relax * E0 / E_inf).
    """
    if compliance_0 <= 0.0 or compliance_inf <= 0.0 or tau_retard <= 0.0 \
            or compliance_inf < compliance_0:
        raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                   "SLS conversion: 0 < J0 <= J_inf, tau > 0 required")
    e0 = 1.0 / compliance_0
    e_inf = 1.0 / compliance_inf
    tau_rel = tau_retard * compliance_0 / compliance_inf
    return e0, e_inf, tau_rel


# ---------------------------------------------------------------------------
# hereditary integrals (production quadrature)
# ---------------------------------------------------------------------------


def _increment_quadrature(t: np.ndarray, delta: np.ndarray,
                          modulus_func: Callable[[np.ndarray], np.ndarray],
                          coefficient: float) -> np.ndarray:
    """Riemann-sum-in-increments:
    F(t_i) = c * sum_{k=0..i} E(t_i - t_k) * d(delta^1.5)_k
    where E is evaluated at the shifted arguments t_i - t_k (k ascending).
    """
    d15 = delta ** 1.5
    inc = np.empty_like(d15)
    inc[0] = d15[0]
    inc[1:] = np.diff(d15)
    n = t.size
    force = np.empty(n, dtype=np.float64)
    for i in range(n):
        args = t[i] - t[: i + 1]  # t_i, t_i - t_1, ..., 0 (descending)
        e_conv = np.asarray(modulus_func(args), dtype=np.float64)
        force[i] = coefficient * float(np.sum(e_conv * inc[: i + 1]))
    return force


def _modulus_grid(t: np.ndarray, modulus_params: dict[str, float],
                  model: str = "sls") -> np.ndarray:
    if model == "sls":
        return forward_sls_modulus(
            t, modulus_params["E0"], modulus_params["E_inf"], modulus_params["tau"])
    if model == "power_law":
        return forward_power_law_modulus(
            t, modulus_params["E_ref"], modulus_params["alpha"],
            modulus_params["t_ref"], modulus_params.get("E_inf", 0.0))
    raise ValueError(f"unknown modulus model {model!r}")


def lee_radok_force(t: np.ndarray, delta: np.ndarray, modulus_params: dict[str, float],
                    young: float, radius: float, poisson: float,
                    *, modulus_model: str = "sls") -> np.ndarray:
    """Lee-Radok spherical loading force (monotonic contact radius only)."""
    t = np.asarray(t, dtype=np.float64)
    delta = np.asarray(delta, dtype=np.float64)
    if t.ndim != 1 or t.size != delta.size or t.size == 0:
        raise ValueError("t and delta must be equal-length 1-D arrays")
    if np.any(np.diff(t) <= 0.0):
        raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                   "Lee-Radok: time must be strictly increasing")
    if np.any(np.diff(delta) < 0.0) or np.any(delta < 0.0):
        raise ViscoelasticityError(
            LEE_RADOK_NONMONOTONIC,
            "Lee-Radok requires a monotone non-decreasing indentation "
            "(contact radius must not decrease)")
    if delta[0] < 0.0:
        raise ViscoelasticityError(LEE_RADOK_NONMONOTONIC, "delta must be non-negative")
    modulus_func = lambda args: _modulus_grid(args, modulus_params, modulus_model)  # noqa: E731
    c = spherical_coefficient(young, radius, poisson)
    return _increment_quadrature(t, delta, modulus_func, c)


def ting_force(loading_t: np.ndarray, loading_delta: np.ndarray,
               unloading_t: np.ndarray, unloading_delta: np.ndarray,
               modulus_params: dict[str, float], young: float, radius: float,
               poisson: float, *, modulus_model: str = "sls") -> np.ndarray:
    """Ting spherical loading/unloading force with contact-time memory.

    Loading branch: Lee-Radok on the loading history.  Unloading branch:
    the integral runs over the loading history up to t1(t), the loading time
    with delta(t1) = delta(t).  When delta(t) exceeds the loading maximum or
    the loading history is missing, TING_HISTORY_UNAVAILABLE is raised.
    """
    loading_t = np.asarray(loading_t, dtype=np.float64)
    loading_delta = np.asarray(loading_delta, dtype=np.float64)
    unloading_t = np.asarray(unloading_t, dtype=np.float64)
    unloading_delta = np.asarray(unloading_delta, dtype=np.float64)
    for arr, label in ((loading_t, "loading_t"), (loading_delta, "loading_delta"),
                       (unloading_t, "unloading_t"), (unloading_delta, "unloading_delta")):
        if arr.ndim != 1 or arr.size == 0:
            raise ValueError(f"{label} must be a non-empty 1-D array")
    if loading_delta.size != loading_t.size or unloading_delta.size != unloading_t.size:
        raise ValueError("t/delta length mismatch")
    if np.any(np.diff(loading_t) <= 0.0) or np.any(np.diff(unloading_t) <= 0.0):
        raise ViscoelasticityError(INVALID_MODEL_PARAMETER,
                                   "Ting: time axes must be strictly increasing")
    if np.any(np.diff(loading_delta) < 0.0) or np.any(loading_delta < 0.0):
        raise ViscoelasticityError(
            LEE_RADOK_NONMONOTONIC,
            "Ting loading branch must be monotone non-decreasing")
    if unloading_t[0] < loading_t[-1]:
        raise ViscoelasticityError(
            TING_HISTORY_UNAVAILABLE,
            "Ting unloading must start at or after the loading branch end")
    c = spherical_coefficient(young, radius, poisson)
    modulus_func = lambda args: _modulus_grid(args, modulus_params, modulus_model)  # noqa: E731
    force_load = _increment_quadrature(loading_t, loading_delta, modulus_func, c)

    # contact-time memory: t1(t) solves delta_loading(t1) = delta_unloading(t)
    # on the monotone loading branch (inverted by interpolation)
    d_max = float(np.max(loading_delta))
    t1 = np.empty(unloading_t.size, dtype=np.float64)
    for i, d_u in enumerate(unloading_delta):
        if d_u > d_max + 1e-15 or d_u < 0.0:
            raise ViscoelasticityError(
                TING_HISTORY_UNAVAILABLE,
                f"unloading indentation {d_u:.3e} outside the loading history [0, {d_max:.3e}]")
        # the loading branch is monotone: invert delta(t1) = d_u
        if d_u <= float(loading_delta[0]):
            t1[i] = float(loading_t[0])
        else:
            idx = int(np.searchsorted(loading_delta, d_u, side="left"))
            idx = min(max(idx, 1), loading_delta.size - 1)
            t_a, t_b = float(loading_t[idx - 1]), float(loading_t[idx])
            d_a, d_b = float(loading_delta[idx - 1]), float(loading_delta[idx])
            if d_b <= d_a:
                t1[i] = t_b
            else:
                frac = (d_u - d_a) / (d_b - d_a)
                t1[i] = t_a + frac * (t_b - t_a)
    # unloading force: integral over the loading branch up to t1 with
    # E(t_u - t_k), k ascending over the loading times; the partial last
    # interval [t_k, t1] is included with the interpolated delta^1.5
    force_unload = np.empty(unloading_t.size, dtype=np.float64)
    d15 = loading_delta ** 1.5
    inc = np.empty_like(d15)
    inc[0] = d15[0]
    inc[1:] = np.diff(d15)
    for i, t_u in enumerate(unloading_t):
        t1v = t1[i]
        k = int(np.searchsorted(loading_t, t1v, side="right")) - 1
        k = min(max(k, 0), loading_t.size - 1)
        e_conv = _modulus_grid(t_u - loading_t[: k + 1], modulus_params, modulus_model)
        total = float(np.sum(e_conv * inc[: k + 1]))
        if t1v > loading_t[k] and k + 1 < loading_t.size:
            # partial interval [t_k, t1]: delta^1.5 interpolated at t1
            frac = (t1v - loading_t[k]) / (loading_t[k + 1] - loading_t[k])
            d15_t1 = d15[k] + frac * (d15[k + 1] - d15[k])
            total = total + float(_modulus_grid(
                np.array([t_u - loading_t[k]]), modulus_params, modulus_model)[0]) \
                * (d15_t1 - d15[k])
        force_unload[i] = c * total
    return np.concatenate([force_load, force_unload])
