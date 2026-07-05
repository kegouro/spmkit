"""Mapa de propiedades de force-volume **vectorizado** (CPU/GPU) — la ruta rápida.

En vez de correr un ajuste Python por curva (:mod:`forcevolume`), ajusta **toda la
grilla a la vez** con álgebra de arreglos, replicando exactamente la forma cerrada de
:func:`spmkit.core.analysis.forcecurve.fit_force_curve` (orientar por línea base →
corregir base lineal en índice → detectar contacto → ajustar ``F = A·δ^n`` → E*). El
mismo código corre en NumPy (CPU) o CuPy (GPU CUDA) según el backend.

Requisitos: las curvas deben estar **calibradas** (fuerza en N) y tener el **mismo
largo** (típico en force-volume). Si no, usar la ruta por pipeline de
:func:`spmkit.core.analysis.forcevolume.analyze_volume`.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from spmkit.core import compute
from spmkit.core.analysis.forcecurve import display_axis
from spmkit.core.analysis.forcevolume import VolumeResult
from spmkit.core.analysis.mechanics import _MODELS
from spmkit.core.models import ForceVolume

#: Propiedades que produce la ruta rápida.
FAST_KEYS = (
    "young_modulus",
    "adhesion",
    "dissipation",
    "r_squared",
    "contact_point",
    "max_force",
    "max_indentation",
)


def _trapz(f: Any, x: Any) -> Any:
    """Integral trapezoidal por fila (∫f dx), compatible NumPy/CuPy."""
    return 0.5 * ((x[:, 1:] - x[:, :-1]) * (f[:, 1:] + f[:, :-1])).sum(axis=1)


def _fit_batch(
    x: Any,
    force: Any,
    model: str,
    tip_radius: float,
    poisson: float,
    half_angle: float,
    baseline_fraction: float,
    k_sigma: float,
    xp: Any,
) -> dict[str, Any]:
    """Ajuste batched de ``(N, M)`` curvas. Devuelve arreglos ``(N,)`` por propiedad."""
    n, m = force.shape
    exponent = _MODELS[model]
    dmt = model == "dmt"

    # --- orientar: extremo de menor desviación primero ---
    n_or = max(3, m // 4)
    flip = force[:, :n_or].std(axis=1) > force[:, -n_or:].std(axis=1)
    fr = xp.where(flip[:, None], force[:, ::-1], force)
    xr = xp.where(flip[:, None], x[:, ::-1], x)

    # --- corrección de línea base (recta en función del índice) ---
    n_base = max(3, int(m * baseline_fraction))
    idx = xp.arange(m, dtype=xp.float64)
    bi = idx[:n_base]
    bcen = bi - bi.mean()
    denom_b = float((bcen**2).sum())
    mf = fr[:, :n_base].mean(axis=1)
    slope = ((fr[:, :n_base] - mf[:, None]) * bcen[None, :]).sum(axis=1) / denom_b
    intercept = mf - slope * bi.mean()
    fc = fr - (intercept[:, None] + slope[:, None] * idx[None, :])

    adhesion = xp.maximum(0.0, -fc.min(axis=1))
    peak = fc.max(axis=1)

    # --- punto de contacto ---
    rows = xp.arange(n)
    if dmt:
        i0 = fc.argmin(axis=1)
    else:
        sigma = fc[:, : max(3, int(m * baseline_fraction))].std(axis=1)
        thr = xp.maximum(k_sigma * sigma, 1e-6 * peak)
        above = fc > thr[:, None]
        sustained = above[:, :-1] & above[:, 1:]
        i0 = xp.where(
            sustained.any(axis=1),
            sustained.argmax(axis=1),
            xp.where(above.any(axis=1), above.argmax(axis=1), m - 1),
        )
    i_peak = fc.argmax(axis=1)
    hi = xp.where(i_peak > i0 + 2, i_peak + 1, m)

    x0 = xr[rows, i0]
    delta = xp.abs(xr - x0[:, None])
    f_fit = fc + (adhesion[:, None] if dmt else 0.0)

    j = xp.arange(m)[None, :]
    window = (j >= i0[:, None]) & (j < hi[:, None]) & (delta > 0)
    w = window.astype(xp.float64)
    count = w.sum(axis=1)

    basis = delta**exponent
    denom = (basis * basis * w).sum(axis=1)
    safe = denom > 0
    stiffness = xp.where(safe, (basis * f_fit * w).sum(axis=1) / xp.where(safe, denom, 1.0), xp.nan)

    if model in ("sphere", "paraboloid", "dmt"):
        e_star = stiffness / ((4.0 / 3.0) * np.sqrt(tip_radius))
    else:  # cono
        e_star = stiffness * np.pi / (2.0 * np.tan(half_angle))
    young = e_star * (1.0 - poisson**2)

    predicted = stiffness[:, None] * basis
    ssr = ((f_fit - predicted) ** 2 * w).sum(axis=1)
    mean_fit = (f_fit * w).sum(axis=1) / xp.where(count > 0, count, 1.0)
    sst = ((f_fit - mean_fit[:, None]) ** 2 * w).sum(axis=1)
    r2 = xp.where(sst > 0, 1.0 - ssr / xp.where(sst > 0, sst, 1.0), 1.0)

    max_force = xp.where(window, f_fit, -xp.inf).max(axis=1)
    max_indent = xp.where(window, delta, 0.0).max(axis=1)

    # curvas inválidas (pocos puntos o no finitas) → NaN
    bad = (count < 3) | ~xp.isfinite(force).all(axis=1)
    young = xp.where(bad, xp.nan, young)

    return {
        "young_modulus": young,
        "adhesion": xp.where(bad, xp.nan, adhesion),
        "r_squared": xp.where(bad, xp.nan, r2),
        "contact_point": xp.where(bad, xp.nan, x0),
        "max_force": xp.where(bad, xp.nan, max_force),
        "max_indentation": xp.where(bad, xp.nan, max_indent),
    }


def _stack(
    volume: ForceVolume,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, np.ndarray | None]:
    """Apila approach (y retract si es uniforme) en arreglos ``(N, M)`` de NumPy."""
    ext_f: list[np.ndarray] = []
    ext_x: list[np.ndarray] = []
    ret_f: list[np.ndarray] = []
    ret_x: list[np.ndarray] = []
    have_ret = True
    for i in range(volume.n_curves):
        curve = volume.curve(i)
        ext = curve.extend or curve.segments[0]
        force = ext.require_force()
        ext_f.append(np.asarray(force, dtype=np.float64))
        ext_x.append(display_axis(ext.separation, ext.raw_height))
        retract = curve.retract
        if have_ret and retract is not None and retract.force is not None:
            ret_f.append(np.asarray(retract.force, dtype=np.float64))
            ret_x.append(display_axis(retract.separation, retract.raw_height))
        else:
            have_ret = False
    m = ext_f[0].size
    if any(a.size != m for a in ext_f):
        raise ValueError("La ruta rápida requiere curvas del mismo largo; usa el pipeline.")
    fx = np.stack(ext_f)
    xx = np.stack(ext_x)
    if have_ret and all(a.size == ret_f[0].size for a in ret_f) and ret_f[0].size == m:
        return fx, xx, np.stack(ret_f), np.stack(ret_x)
    return fx, xx, None, None


def elasticity_map(
    volume: ForceVolume,
    tip_radius: float = 10e-9,
    poisson: float = 0.3,
    model: str = "sphere",
    half_angle: float = np.deg2rad(20.0),
    baseline_fraction: float = 0.3,
    k_sigma: float = 5.0,
    backend: str = "cpu",
) -> VolumeResult:
    """Mapa de propiedades mecánicas de ``volume`` de forma vectorizada (CPU/GPU).

    Devuelve un :class:`VolumeResult` con los mapas de :data:`FAST_KEYS`, equivalente
    al de :func:`analyze_volume` para el modelo de contacto dado (misma forma cerrada).
    """
    if model not in _MODELS:
        raise ValueError(f"model debe ser uno de {sorted(_MODELS)}")
    ext_f, ext_x, ret_f, ret_x = _stack(volume)
    xp = compute.array_module(backend)
    fitted = _fit_batch(
        xp.asarray(ext_x),
        xp.asarray(ext_f),
        model,
        tip_radius,
        poisson,
        half_angle,
        baseline_fraction,
        k_sigma,
        xp,
    )
    flat = {k: compute.to_numpy(v) for k, v in fitted.items()}

    if ret_f is not None and ret_x is not None:
        w_ext = compute.to_numpy(_trapz(xp.asarray(ext_f), xp.asarray(ext_x)))
        w_ret = compute.to_numpy(_trapz(xp.asarray(ret_f), xp.asarray(ret_x)))
        flat["dissipation"] = np.abs(w_ext - w_ret)
    else:
        flat["dissipation"] = np.full(volume.n_curves, np.nan)

    rows, cols = volume.grid_shape
    maps = {k: v.reshape(rows, cols) for k, v in flat.items()}
    n_ok = int(np.isfinite(flat["young_modulus"]).sum())
    return VolumeResult(
        maps=maps,
        grid_shape=volume.grid_shape,
        n_ok=n_ok,
        n_failed=volume.n_curves - n_ok,
        keys=FAST_KEYS,
    )
