"""Independent hereditary-integral oracle for FS-F3 (Lee-Radok / Ting).

No production imports.  The quadrature differs from production on purpose:
production uses the Riemann-sum-in-increments rule evaluated at the sample
grid; this oracle uses a high-resolution substep Riemann rule (each sampling
interval subdivided), so shared arithmetic-order bugs cannot survive.
"""

from __future__ import annotations

import numpy as np
from oracle_viscoelastic_lumped import sls_relaxation_modulus


def _sls_modulus(t: np.ndarray, e0: float, e_inf: float, tau: float) -> np.ndarray:
    return sls_relaxation_modulus(t, e0, e_inf, tau)


def _substep_quadrature(t: np.ndarray, delta: np.ndarray, e0: float, e_inf: float,
                        tau: float, coefficient: float, substeps: int = 16) -> np.ndarray:
    """Substep Riemann rule with the same heredity structure."""
    n = t.size
    force = np.empty(n, dtype=float)
    for i in range(n):
        total = 0.0
        for k in range(i + 1):
            # subdivide [t_k, t_{k+1}] (last point: [t_{i-1}, t_i])
            if k == 0:
                t_a = 0.0
                d_a = 0.0
            else:
                t_a = t[k - 1]
                d_a = delta[k - 1] ** 1.5
            if k == i:
                t_b = t[i]
                d_b = delta[i] ** 1.5
            else:
                t_b = t[k]
                d_b = delta[k] ** 1.5
            if t_b <= t_a:
                continue
            seg = (d_b - d_a) / substeps
            for s in range(substeps):
                frac = (s + 0.5) / substeps
                t_mid = t_a + frac * (t_b - t_a)
                e_val = float(_sls_modulus(np.array([t[i] - t_mid]), e0, e_inf, tau)[0])
                total += e_val * seg
        force[i] = coefficient * total
    return force


def lee_radok_force(t: np.ndarray, delta: np.ndarray, e0: float, e_inf: float,
                    tau: float, young: float, radius: float, poisson: float,
                    substeps: int = 16) -> np.ndarray:
    """Lee-Radok spherical loading force (monotonic indentation)."""
    t = np.asarray(t, dtype=float)
    delta = np.asarray(delta, dtype=float)
    if np.any(np.diff(delta) < 0.0) or np.any(delta < 0.0):
        raise ValueError("oracle Lee-Radok requires monotone non-decreasing delta")
    c = (4.0 / 3.0) * float(np.sqrt(radius)) * young / (1.0 - poisson**2)
    return _substep_quadrature(t, delta, e0, e_inf, tau, c, substeps)


def ting_force(loading_t: np.ndarray, loading_delta: np.ndarray,
               unloading_t: np.ndarray, unloading_delta: np.ndarray,
               e0: float, e_inf: float, tau: float, young: float, radius: float,
               poisson: float, substeps: int = 16) -> np.ndarray:
    """Ting spherical loading/unloading force with contact-time memory.

    Unloading: F(t) = c * int_0^{t1(t)} E(t - t') d/dt' [delta(t')^1.5] dt'
    with delta(t1(t)) = delta(t) on the monotone loading branch.
    """
    loading_t = np.asarray(loading_t, dtype=float)
    loading_delta = np.asarray(loading_delta, dtype=float)
    unloading_t = np.asarray(unloading_t, dtype=float)
    unloading_delta = np.asarray(unloading_delta, dtype=float)
    c = (4.0 / 3.0) * float(np.sqrt(radius)) * young / (1.0 - poisson**2)
    force_load = _substep_quadrature(loading_t, loading_delta, e0, e_inf, tau, c, substeps)
    # t1(t): invert the monotone loading branch
    d_max = float(np.max(loading_delta))
    t1 = np.empty(unloading_t.size, dtype=float)
    for i, d_u in enumerate(unloading_delta):
        if d_u > d_max or d_u < 0.0:
            raise ValueError("oracle Ting: unloading indentation outside loading history")
        if d_u <= float(loading_delta[0]):
            t1[i] = float(loading_t[0])
        else:
            idx = int(np.searchsorted(loading_delta, d_u, side="left"))
            idx = min(max(idx, 1), loading_delta.size - 1)
            t_a, t_b = float(loading_t[idx - 1]), float(loading_t[idx])
            d_a, d_b = float(loading_delta[idx - 1]), float(loading_delta[idx])
            t1[i] = t_a + (d_u - d_a) / (d_b - d_a) * (t_b - t_a) if d_b > d_a else t_b
    # unloading quadrature: full loading intervals [t_{k-1}, t_k] for
    # k = 0..k_max (covering [0, t_{k_max}]) plus the partial interval
    # [t_{k_max}, t1] with delta^1.5 linearly interpolated between the
    # loading samples bracketing t1 (t1 lies inside [t_{k_max}, t_{k_max+1}]
    # by construction)
    force_unload = np.empty(unloading_t.size, dtype=float)
    d15 = loading_delta ** 1.5
    for i, t_u in enumerate(unloading_t):
        total = 0.0
        k_max = int(np.searchsorted(loading_t, t1[i], side="right")) - 1
        k_max = min(max(k_max, 0), loading_t.size - 1)
        for k in range(k_max + 1):
            t_a = 0.0 if k == 0 else loading_t[k - 1]
            d15_a = 0.0 if k == 0 else d15[k - 1]
            t_b = loading_t[k]
            d15_b = d15[k]
            if t_b <= t_a:
                continue
            seg = (d15_b - d15_a) / substeps
            for s in range(substeps):
                frac = (s + 0.5) / substeps
                t_mid = t_a + frac * (t_b - t_a)
                e_val = float(_sls_modulus(np.array([t_u - t_mid]), e0, e_inf, tau)[0])
                total += e_val * seg
        # partial interval [t_{k_max}, t1]
        if t1[i] > loading_t[k_max] and k_max + 1 < loading_t.size:
            t_a = loading_t[k_max]
            d15_a = d15[k_max]
            frac = (t1[i] - loading_t[k_max]) / (loading_t[k_max + 1] - loading_t[k_max])
            d15_b = d15_a + frac * (d15[k_max + 1] - d15_a)
            t_b = t1[i]
            seg = (d15_b - d15_a) / substeps
            for s in range(substeps):
                frac_s = (s + 0.5) / substeps
                t_mid = t_a + frac_s * (t_b - t_a)
                e_val = float(_sls_modulus(np.array([t_u - t_mid]), e0, e_inf, tau)[0])
                total += e_val * seg
        force_unload[i] = c * total
    return np.concatenate([force_load, force_unload])
