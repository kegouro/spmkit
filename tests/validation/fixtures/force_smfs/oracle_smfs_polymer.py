"""Independent analytical polymer oracle for FS-F4 (no production imports).

The eWLC root is solved by plain bisection (production uses brentq); the
FJC Langevin is evaluated with an explicit series near zero (production
uses a tanh form); the eFJC uses the same convention as production but is
expressed independently.
"""

from __future__ import annotations

import numpy as np

KB = 1.380649e-23


def wlc_force(x: np.ndarray, lc: float, lp: float, temperature: float) -> np.ndarray:
    """F = (k_BT/Lp)[1/(4(1-x/Lc)^2) - 1/4 + x/Lc]."""
    x = np.asarray(x, dtype=float)
    r = x / lc
    return (KB * temperature / lp) * (1.0 / (4.0 * (1.0 - r) ** 2) - 0.25 + r)


def _ewlc_residual(F: float, x: float, lc: float, lp: float, s: float,
                   temperature: float) -> float:
    r_eff = x / lc - F / s
    if r_eff >= 1.0:
        return 1.0
    g = 1.0 / (4.0 * (1.0 - r_eff) ** 2) - 0.25 + r_eff
    return F - (KB * temperature / lp) * g


def extensible_wlc_force(x: np.ndarray, lc: float, lp: float, s: float,
                         temperature: float, iters: int = 200) -> np.ndarray:
    """eWLC by bisection on [0, F_hi] (independent root strategy)."""
    x = np.asarray(x, dtype=float)
    out = np.empty(x.size, dtype=float)
    for i, xi in enumerate(x):
        f_hi = min(s * (1.0 - xi / lc) * 0.999, s * xi / lc * 2.0 + 1e-18)
        lo, hi = 0.0, f_hi
        for _ in range(iters):
            mid = 0.5 * (lo + hi)
            if _ewlc_residual(mid, float(xi), lc, lp, s, temperature) > 0.0:
                hi = mid
            else:
                lo = mid
        out[i] = 0.5 * (lo + hi)
    return out


def _langevin_series(u: np.ndarray) -> np.ndarray:
    """Langevin with the u/3 - u^3/45 series near zero (independent form)."""
    u = np.asarray(u, dtype=float)
    small = np.abs(u) < 1e-2
    out = np.where(small, u / 3.0 - u**3 / 45.0 + 2.0 * u**5 / 945.0,
                   1.0 / np.tanh(np.where(u == 0, 1.0, u)) - 1.0 / np.where(u == 0, 1.0, u))
    return np.where(u == 0.0, 0.0, out)


def fjc_extension(f: np.ndarray, lc: float, b: float, temperature: float) -> np.ndarray:
    """x = Lc L(F b / k_BT)."""
    f = np.asarray(f, dtype=float)
    return lc * _langevin_series(f * b / (KB * temperature))


def extensible_fjc_extension(f: np.ndarray, lc: float, b: float, sk: float,
                             temperature: float) -> np.ndarray:
    """x = Lc [L(y) + F/Sk]."""
    f = np.asarray(f, dtype=float)
    return lc * (_langevin_series(f * b / (KB * temperature)) + f / sk)
