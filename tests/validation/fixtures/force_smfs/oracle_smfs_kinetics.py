"""Independent kinetic and survival oracle for FS-F4 (no production imports).

Bell-Evans and DHS likelihoods are evaluated by direct quadrature; the
Kaplan-Meier estimator is implemented independently (product-limit with the
same events-before-censors tie order, expressed differently).
"""

from __future__ import annotations

import math

import numpy as np

KB = 1.380649e-23


def bell_evans_pdf(F: np.ndarray, r: float | np.ndarray, k0: float, xb: float,
                   T: float) -> np.ndarray:
    """p(F) = k(F)/r exp(-k0 kBT/(r xb)(exp(F xb/kBT)-1))."""
    kt = KB * T
    y = F * xb / kt
    return (k0 * np.exp(y) / r
            * np.exp(-k0 * kt / (r * xb) * (np.exp(y) - 1.0)))


def bell_evans_nll(rates: np.ndarray, forces: np.ndarray, k0: float, xb: float,
                   T: float) -> float:
    vals = bell_evans_pdf(forces, rates, k0, xb, T)
    return -float(np.sum(np.log(np.maximum(vals, 1e-300))))


def dhs_rate(F: float, k0: float, xb: float, dg: float, nu: float, T: float) -> float:
    kt = KB * T
    z = 1.0 - nu * F * xb / dg
    if z <= 0.0:
        return float("inf")
    return k0 * z ** (1.0 / nu - 1.0) * math.exp(dg * (1.0 - z ** (1.0 / nu)) / kt)


def dhs_pdf(F: np.ndarray, r: float, k0: float, xb: float, dg: float, nu: float,
            T: float) -> np.ndarray:
    """p(F) = k(F)/r exp(-(1/r) int_0^F k(f) df); integral by Romberg-style
    adaptive refinement (independent of the production trapezoid grid)."""
    out = np.empty(F.size, dtype=float)
    for i, fi in enumerate(F):
        grid = np.linspace(0.0, float(fi), 513)
        kv = np.array([dhs_rate(float(g), k0, xb, dg, nu, T) for g in grid])
        # Simpson 1/3 rule
        h = grid[1] - grid[0]
        integral = (kv[0] + kv[-1] + 4.0 * np.sum(kv[1:-1:2])
                    + 2.0 * np.sum(kv[2:-2:2])) * h / 3.0
        kf = dhs_rate(float(fi), k0, xb, dg, nu, T)
        out[i] = kf / r * math.exp(-integral / r)
    return out


def kaplan_meier(lifetimes: np.ndarray, censored: np.ndarray) -> tuple:
    """Independent product-limit estimator (events before censors at ties)."""
    lt = np.asarray(lifetimes, dtype=float)
    ce = np.asarray(censored, dtype=float)
    order = np.lexsort((ce, lt))
    lt_s, ce_s = lt[order], ce[order]
    times: list[float] = []
    surv: list[float] = []
    at_risk: list[int] = []
    n_total = lt_s.size
    n = n_total
    s = 1.0
    i = 0
    while i < n_total:
        t_i = lt_s[i]
        n_events = 0
        j = i
        while j < n_total and lt_s[j] == t_i and ce_s[j] == 0.0:
            n_events += 1
            j += 1
        if n_events:
            s *= (1.0 - n_events / n)
            times.append(t_i)
            surv.append(s)
            at_risk.append(n)
            n -= n_events
        while j < n_total and lt_s[j] == t_i:
            n -= 1
            j += 1
        i = j
    return (np.asarray(times), np.asarray(surv), np.asarray(at_risk, dtype=int))
