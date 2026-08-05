"""Analytical lumped-model oracle for FS-F3 (independent of production).

Implements the frozen viscoelastic response equations from the literature
with no production imports.  The equations are deliberately written in a
different style (direct element-wise formulas) from the production module so
transcription errors cannot be shared.
"""

from __future__ import annotations

import math

import numpy as np


def reduced_modulus(young: float, poisson: float) -> float:
    return young / (1.0 - poisson ** 2)


def kv_compliance(time: np.ndarray, modulus: float, tau: float) -> np.ndarray:
    """Kelvin-Voigt creep: J(t) = (1 - exp(-t/tau)) / E."""
    t = np.asarray(time, dtype=float)
    return (1.0 - np.exp(-t / tau)) / modulus


def maxwell_relaxation(time: np.ndarray, modulus: float, tau: float) -> np.ndarray:
    """Maxwell relaxation modulus: E(t) = E * exp(-t/tau)."""
    t = np.asarray(time, dtype=float)
    return modulus * np.exp(-t / tau)


def maxwell_normalized(time: np.ndarray, tau: float) -> np.ndarray:
    t = np.asarray(time, dtype=float)
    return np.exp(-t / tau)


def sls_relaxation_modulus(time: np.ndarray, e0: float, e_inf: float,
                           tau: float) -> np.ndarray:
    """SLS: E(t) = E_inf + (E0 - E_inf) exp(-t/tau)."""
    t = np.asarray(time, dtype=float)
    return e_inf + (e0 - e_inf) * np.exp(-t / tau)


def sls_creep_compliance(time: np.ndarray, j0: float, j_inf: float,
                         tau: float) -> np.ndarray:
    """SLS creep: J(t) = J_inf - (J_inf - J0) exp(-t/tau)."""
    t = np.asarray(time, dtype=float)
    return j_inf - (j_inf - j0) * np.exp(-t / tau)


def prony_normalized(time: np.ndarray, alpha: np.ndarray, tau: np.ndarray) -> np.ndarray:
    """Prony normalized relaxation: n(t) = 1 - sum(alpha) + sum(alpha exp(-t/tau))."""
    t = np.asarray(time, dtype=float)
    out = np.full_like(t, 1.0 - float(np.sum(alpha)))
    for a, tau_i in zip(alpha, tau, strict=True):
        out = out + a * np.exp(-t / tau_i)
    return out


def power_law_modulus(time: np.ndarray, e_ref: float, alpha: float,
                      t_ref: float) -> np.ndarray:
    """E(t) = E_ref * (t/t_ref)^(-alpha)."""
    t = np.asarray(time, dtype=float)
    return e_ref * (t / t_ref) ** (-alpha)


def sls_relax_to_creep(e0: float, e_inf: float, tau_relax: float) -> tuple:
    return 1.0 / e0, 1.0 / e_inf, tau_relax * e0 / e_inf


def sls_creep_to_relax(j0: float, j_inf: float, tau_retard: float) -> tuple:
    return 1.0 / j0, 1.0 / j_inf, tau_retard * j_inf / j0


def spherical_coefficient(young: float, radius: float, poisson: float) -> float:
    return (4.0 / 3.0) * math.sqrt(radius) * reduced_modulus(young, poisson)
