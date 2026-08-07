"""Analytical oracle for FS-F2 mechanical phantoms (independent of production).

Forward equations, reduced modulus, limiting relations and exact clean
recovery targets.  No production imports.
"""

from __future__ import annotations

import math

import numpy as np


def reduced_modulus(young: float, poisson: float) -> float:
    return young / (1.0 - poisson ** 2)


def forward_hertz(delta: np.ndarray, est: float, radius: float) -> np.ndarray:
    return (4.0 / 3.0) * est * math.sqrt(radius) * np.asarray(delta, float) ** 1.5


def forward_sneddon(delta: np.ndarray, est: float, alpha: float) -> np.ndarray:
    return (2.0 * math.tan(alpha) / math.pi) * est * np.asarray(delta, float) ** 2.0


def forward_punch(delta: np.ndarray, est: float, radius: float) -> np.ndarray:
    return 2.0 * est * radius * np.asarray(delta, float)


def forward_dmt(delta: np.ndarray, est: float, radius: float,
                f_adh: float) -> np.ndarray:
    return forward_hertz(delta, est, radius) - f_adh


def forward_jkr(delta: np.ndarray, est: float, radius: float,
                work: float) -> np.ndarray:
    # monotone loading branch parametrized by the contact radius a:
    # delta(a) = a^2/R - sqrt(2*pi*w*a/E*), increasing for a >= a0 with
    # a0 = (2*pi*w*R^2/E*)^(1/3); the parametric range is derived from the
    # requested delta range (no a_max parameter)
    d = np.asarray(delta, float)
    dmax = float(np.max(d)) if d.size else 0.0
    if dmax <= 0.0:
        return np.zeros_like(d)
    c = math.sqrt(2.0 * math.pi * work / est)
    a0 = (2.0 * math.pi * work * radius**2 / est) ** (1.0 / 3.0) if work > 0.0 else 0.0
    a_lo = max(a0, 1e-12)
    a_hi = a_lo
    while a_hi**2 / radius - c * math.sqrt(a_hi) < dmax:
        a_hi *= 2.0
    a = np.linspace(a_lo, a_hi, 4096)
    dd = a**2 / radius - c * np.sqrt(a)
    f = 4.0 * est * a**3 / (3.0 * radius) - np.sqrt(8.0 * math.pi * work * est * a**3)
    return np.interp(d, dd, f, left=0.0, right=float(f[-1]))


def expected_E_from_hertz_coefficient(coeff: float, radius: float,
                                      poisson: float) -> float:
    """E = coeff * 3/4 / sqrt(R) * (1 - nu^2)."""
    return coeff * 0.75 / math.sqrt(radius) * (1.0 - poisson ** 2)


def modulus_scaling_relation(E1: float, E2: float, R: float,
                             delta: np.ndarray, poisson: float) -> bool:
    """F(E2)/F(E1) = E2/E1 for the same geometry."""
    est1 = reduced_modulus(E1, poisson)
    est2 = reduced_modulus(E2, poisson)
    f1 = forward_hertz(delta, est1, R)
    f2 = forward_hertz(delta, est2, R)
    return bool(np.allclose(f2 / f1, est2 / est1, rtol=1e-12))


def radius_modulus_tradeoff(delta: np.ndarray, R1: float, R2: float,
                            E: float, poisson: float) -> bool:
    """F(R2) / F(R1) = sqrt(R2/R1)."""
    f1 = forward_hertz(delta, reduced_modulus(E, poisson), R1)
    f2 = forward_hertz(delta, reduced_modulus(E, poisson), R2)
    return bool(np.allclose(f2 / f1, math.sqrt(R2 / R1), rtol=1e-12))


def angle_modulus_scaling(delta: np.ndarray, a1: float, a2: float,
                          E: float, poisson: float) -> bool:
    """Cone force scales with tan(alpha)."""
    est = reduced_modulus(E, poisson)
    f1 = forward_sneddon(delta, est, a1)
    f2 = forward_sneddon(delta, est, a2)
    return bool(np.allclose(f2 / f1, math.tan(a2) / math.tan(a1), rtol=1e-12))


def dmt_hertz_limit(delta: np.ndarray, est: float, radius: float) -> bool:
    """DMT with F_adh = 0 reduces exactly to Hertz."""
    return bool(np.allclose(forward_dmt(delta, est, radius, 0.0),
                            forward_hertz(delta, est, radius), rtol=0.0))


def jkr_hertz_limit(delta: np.ndarray, est: float, radius: float) -> bool:
    """JKR with w = 0 reduces to Hertz (parametric branch)."""
    return bool(np.allclose(forward_jkr(delta, est, radius, 0.0),
                            forward_hertz(delta, est, radius), rtol=1e-9))
