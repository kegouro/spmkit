"""Declarative and metamorphic oracle for FS-F3 (independent of production).

Metamorphic relations that any correct implementation must satisfy:
units, time scaling, parameter scaling, monotonicity and limiting cases.
"""

from __future__ import annotations

import math

import numpy as np
from oracle_viscoelastic_lumped import (
    kv_compliance,
    maxwell_normalized,
    power_law_modulus,
    prony_normalized,
    sls_creep_compliance,
    sls_relaxation_modulus,
)


def kv_scales_with_inverse_modulus(E1: float, E2: float, t: np.ndarray,
                                   tau: float) -> bool:
    """J(t; E1) / J(t; E2) = E2 / E1 (compliance scales with 1/E)."""
    j1 = kv_compliance(t, E1, tau)
    j2 = kv_compliance(t, E2, tau)
    return bool(np.allclose(j1 / j2, E2 / E1, rtol=1e-12))


def maxwell_time_scaling(t: np.ndarray, tau: float, scale: float) -> bool:
    """n(t; tau) = n(t/scale; tau/scale) (time-scaling invariance)."""
    left = maxwell_normalized(t, tau)
    right = maxwell_normalized(t / scale, tau / scale)
    return bool(np.allclose(left, right, rtol=1e-12))


def sls_relaxation_monotone_decreasing(t: np.ndarray, e0: float, e_inf: float,
                                       tau: float) -> bool:
    """SLS relaxation modulus is non-increasing and bounded by [E_inf, E0]."""
    e = sls_relaxation_modulus(t, e0, e_inf, tau)
    return bool(np.all(np.diff(e) <= 1e-12)) and bool(np.all(e >= e_inf - 1e-12)) \
        and bool(np.all(e <= e0 + 1e-12))


def sls_creep_monotone_increasing(t: np.ndarray, j0: float, j_inf: float,
                                  tau: float) -> bool:
    """SLS creep compliance is non-decreasing and bounded by [J0, J_inf]."""
    j = sls_creep_compliance(t, j0, j_inf, tau)
    return bool(np.all(np.diff(j) >= -1e-12)) and bool(np.all(j >= j0 - 1e-12)) \
        and bool(np.all(j <= j_inf + 1e-12))


def prony_limits(t: np.ndarray, alpha: np.ndarray, tau: np.ndarray) -> bool:
    """n(0) = 1 and n(inf) = 1 - sum(alpha) (equilibrium)."""
    n0 = prony_normalized(np.array([0.0]), alpha, tau)
    n_inf = prony_normalized(np.array([50.0 * float(np.max(tau))]), alpha, tau)
    return bool(abs(float(n0[0]) - 1.0) < 1e-12) \
        and bool(abs(float(n_inf[0]) - (1.0 - float(np.sum(alpha)))) < 1e-6)


def power_law_scaling(t: np.ndarray, e_ref: float, alpha: float,
                      t_ref: float) -> bool:
    """E(scale*t) / E(t) = scale^(-alpha) (self-similarity)."""
    e1 = power_law_modulus(t, e_ref, alpha, t_ref)
    e2 = power_law_modulus(2.0 * t, e_ref, alpha, t_ref)
    return bool(np.allclose(e2 / e1, 2.0 ** (-alpha), rtol=1e-12))


def kv_instantaneous_zero(time: np.ndarray, modulus: float, tau: float) -> bool:
    """Kelvin-Voigt: J(0) = 0 (no instantaneous compliance)."""
    return bool(abs(float(kv_compliance(np.array([0.0]), modulus, tau)[0])) < 1e-15)


def maxwell_no_equilibrium(time: np.ndarray, modulus: float, tau: float) -> bool:
    """Maxwell: the modulus decays to zero (fluid, no equilibrium)."""
    return bool(float(maxwell_normalized(np.array([1e6 * tau]), tau)[0]) < 1e-6)


def sls_equilibrium_ratio(e0: float, e_inf: float, tau: float,
                          t_long: float) -> bool:
    """SLS approaches E_inf at long times."""
    e = sls_relaxation_modulus(np.array([t_long]), e0, e_inf, tau)
    return bool(abs(float(e[0]) - e_inf) / e0 < 1e-6)


def hertz_elastic_limit(young: float, radius: float, poisson: float,
                        delta: float) -> float:
    """Elastic limit reference: F = (4/3) sqrt(R) E* delta^1.5."""
    return (4.0 / 3.0) * math.sqrt(radius) * young / (1.0 - poisson**2) * delta**1.5
