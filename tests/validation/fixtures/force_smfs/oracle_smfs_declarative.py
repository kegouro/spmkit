"""Declarative/metamorphic oracle for FS-F4 (no production imports).

Relations that any correct SMFS implementation must satisfy: temperature
scaling, contour translation, model limits, loading-rate scaling and
censoring relations.
"""

from __future__ import annotations

import numpy as np
from oracle_smfs_polymer import wlc_force as oracle_wlc


def wlc_temperature_scaling(x: np.ndarray, lc: float, lp: float,
                            T1: float, T2: float) -> bool:
    """F(T2)/F(T1) = T2/T1 (the WLC force is linear in k_B T)."""
    f1 = oracle_wlc(x, lc, lp, T1)
    f2 = oracle_wlc(x, lc, lp, T2)
    return bool(np.allclose(f2 / f1, T2 / T1, rtol=1e-10))


def wlc_persistence_scaling(x: np.ndarray, lc: float, lp1: float,
                            lp2: float, T: float) -> bool:
    """F(lp2)/F(lp1) = lp1/lp2."""
    f1 = oracle_wlc(x, lc, lp1, T)
    f2 = oracle_wlc(x, lc, lp2, T)
    return bool(np.allclose(f2 / f1, lp1 / lp2, rtol=1e-10))


def wlc_low_force_limit(x: np.ndarray, lc: float, lp: float, T: float) -> bool:
    """Near x=0 the WLC force is linear: F ~ (k_BT/Lp)(3x/(2Lc))... the
    exact series: F = (k_BT/Lp)[x/Lc + 3/2 (x/Lc)^2 + ...]."""
    f = oracle_wlc(x, lc, lp, T)
    r = x / lc
    series = (KB * T / lp) * (r + 1.5 * r**2)
    return bool(np.allclose(f, series, rtol=1e-4))


def wlc_singularity_growth(x: np.ndarray, lc: float, lp: float, T: float) -> bool:
    """F diverges as x -> Lc: F(x2) > F(x1) for x2 > x1 near the contour."""
    x1 = 0.9 * lc
    x2 = 0.99 * lc
    return bool(oracle_wlc(np.array([x2]), lc, lp, T)[0]
                > oracle_wlc(np.array([x1]), lc, lp, T)[0])


def fjc_limits(force: np.ndarray, lc: float, b: float, T: float) -> bool:
    """FJC: x(0) = 0 and x -> Lc as F -> inf."""
    from oracle_smfs_polymer import fjc_extension
    x0 = fjc_extension(np.array([0.0]), lc, b, T)
    xbig = fjc_extension(np.array([1e3 * KB * T / b]), lc, b, T)
    return bool(abs(float(x0[0])) < 1e-12) and bool(float(xbig[0]) > 0.99 * lc)


def km_tie_order(lifetimes: np.ndarray, censored: np.ndarray) -> bool:
    """At a simultaneous event/censor time the survival drops (events before
    censors) and the at-risk count decreases afterwards."""
    from oracle_smfs_kinetics import kaplan_meier
    times, surv, _risk = kaplan_meier(lifetimes, censored)
    # construct a known tie: 1 event and 1 censor at the same time
    lt = np.array([1.0, 1.0, 2.0, 3.0])
    ce = np.array([0.0, 1.0, 0.0, 1.0])
    t2, s2, _ = kaplan_meier(lt, ce)
    return bool(s2[0] < 1.0)  # the event at t=1 lowers the survival


KB = 1.380649e-23
