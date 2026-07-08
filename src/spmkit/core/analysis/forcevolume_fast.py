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


def _joint_contact_batch(
    xr: Any, fc: Any, exponent: float, i_peak: Any, baseline_fraction: float, xp: Any
) -> Any:
    """Punto de contacto por **ajuste conjunto**, vectorizado sobre ``N`` curvas.

    Espejo vectorizado de :func:`forcecurve._joint_contact_point`: para cada curva busca el
    ``z_c`` que minimiza el residuo de ``F = A·δ^n`` (A cerrado por z_c) sobre la rama de
    carga. Inmune al sesgo del umbral bajo ruido (ver `tests/validation/test_recovery.py`).
    """
    n, m = fc.shape
    rows = xp.arange(n)
    base_n = max(3, int(m * baseline_fraction))
    base_x = xp.median(xr[:, :base_n], axis=1)
    sense = xp.where(xr[rows, i_peak] >= base_x, 1.0, -1.0)
    j = xp.arange(m)[None, :]
    dom = (j <= i_peak[:, None]).astype(xp.float64)  # base + carga (dominio fijo)
    big = float(xp.abs(xr).max()) + 1.0
    lo = xp.where(dom > 0, xr, big).min(axis=1)
    hi = xp.where(dom > 0, xr, -big).max(axis=1)

    def ssr_at(zc: Any) -> Any:  # zc: (n,) → ssr (n,)
        delta = xp.clip(sense[:, None] * (xr - zc[:, None]), 0.0, None) * dom
        basis = delta**exponent
        denom = (basis * basis).sum(axis=1)
        a = xp.where(
            denom > 0, (basis * fc * dom).sum(axis=1) / xp.where(denom > 0, denom, 1.0), 0.0
        )
        return ((fc - a[:, None] * basis) ** 2 * dom).sum(axis=1)

    span = hi - lo
    best_zc = lo.copy()
    best_ssr = xp.full(n, xp.inf)
    grid = xp.linspace(0.0, 1.0, 64)
    for t in grid:  # grilla gruesa
        zc = lo + span * float(t)
        s = ssr_at(zc)
        better = s < best_ssr
        best_ssr, best_zc = xp.where(better, s, best_ssr), xp.where(better, zc, best_zc)
    step = span / 64.0
    fine = xp.linspace(-1.0, 1.0, 21)
    for _ in range(3):  # refinamiento
        for t in fine:
            zc = best_zc + step * float(t)
            s = ssr_at(zc)
            better = s < best_ssr
            best_ssr, best_zc = xp.where(better, s, best_ssr), xp.where(better, zc, best_zc)
        step = step / 10.0
    return best_zc


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
    contact_method: str = "joint",
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
    sigma_base = fc[:, :n_base].std(axis=1)  # ruido de la línea base (gate de contacto)

    # --- punto de contacto ---
    rows = xp.arange(n)
    i_peak = fc.argmax(axis=1)
    j = xp.arange(m)[None, :]
    if dmt:
        i0 = fc.argmin(axis=1)
        x0 = xr[rows, i0]
    elif contact_method == "joint":
        # Ajuste conjunto (default): z_c continuo inmune al sesgo del umbral bajo ruido.
        x0 = _joint_contact_batch(xr, fc, exponent, i_peak, baseline_fraction, xp)
        base_x = xp.median(xr[:, : max(3, int(m * baseline_fraction))], axis=1)
        sense = xp.where(xr[rows, i_peak] >= base_x, 1.0, -1.0)
        on_load = (sense[:, None] * (xr - x0[:, None]) > 0) & (j <= i_peak[:, None])
        i0 = xp.where(on_load.any(axis=1), on_load.argmax(axis=1), i_peak)
    else:  # umbral k·σ (rápido; sesga ~+30% con ruido)
        sigma = fc[:, : max(3, int(m * baseline_fraction))].std(axis=1)
        thr = xp.maximum(k_sigma * sigma, 1e-6 * peak)
        above = fc > thr[:, None]
        sustained = above[:, :-1] & above[:, 1:]
        i0 = xp.where(
            sustained.any(axis=1),
            sustained.argmax(axis=1),
            xp.where(above.any(axis=1), above.argmax(axis=1), m - 1),
        )
        x0 = xr[rows, i0]
    hi = xp.where(i_peak > i0 + 2, i_peak + 1, m)
    delta = xp.abs(xr - x0[:, None])
    f_fit = fc + (adhesion[:, None] if dmt else 0.0)

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

    # curvas inválidas → NaN: pocos puntos, no finitas, o **sin contacto sobre el ruido**
    # (peak ≤ k·σ_base). El gate de contacto lo restaura tras pasar al ajuste conjunto:
    # una curva plana no debe recuperar E≈0 como si fuera un ajuste válido.
    no_contact = peak <= k_sigma * sigma_base
    bad = (count < 3) | ~xp.isfinite(force).all(axis=1) | no_contact
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
    contact_method: str = "joint",
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
        contact_method,
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
