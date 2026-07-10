"""Modelos mecánicos **experimentales, sin validar** — JKR y viscoelástico (SLS).

⚠️  **EXPERIMENTAL / NO VALIDADO.** Estos modelos están construidos según la teoría
publicada pero **no** se han validado contra una referencia independiente (a diferencia
del resto de ``core.analysis``, comprobado a precisión de máquina). Se incluyen *flagged*
para poder revalidarlos en el futuro con datos de referencia; **no** deben usarse para
resultados publicables hasta entonces. Toda función expone ``EXPERIMENTAL = True`` y las
capas de UI/CLI muestran una advertencia.

Contenido:

* :func:`fit_jkr` — contacto adhesivo de Johnson-Kendall-Roberts (esfera-plano). Ajusta el
  módulo reducido ``E*`` y el trabajo de adhesión ``w`` a una curva fuerza-indentación.
  Verificado sólo contra el **límite analítico**: cuando ``w → 0`` reduce a Hertz esférico.
* :func:`fit_relaxation` — sólido lineal estándar (SLS): ajusta una relajación de fuerza a
  indentación constante ``F(t) = F∞ + (F0 − F∞)·exp(−t/τ)`` y reporta ``τ`` y el ratio de
  relajación. Verificado sólo contra el límite elástico (τ → ∞ ⇒ sin relajación).

El ajuste es **numpy puro** (búsqueda en grilla con refinamiento), sin dependencias nuevas.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

#: Marca que estas rutinas son experimentales/sin validar (la UI/CLI lo advierte).
EXPERIMENTAL = True


@dataclass(frozen=True)
class JKRResult:
    """Resultado (experimental) de un ajuste JKR."""

    young_modulus: float  # E (Pa), con E* = E/(1-ν²)
    reduced_modulus: float  # E* (Pa)
    work_of_adhesion: float  # w (J/m²)
    rmse: float  # error cuadrático medio (N)
    r_squared: float
    n_fit: int
    experimental: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RelaxationResult:
    """Resultado (experimental) de un ajuste de relajación (SLS)."""

    tau: float  # tiempo de relajación (s)
    f0: float  # fuerza inicial (N)
    f_inf: float  # fuerza asintótica (N)
    relaxation_ratio: float  # (F0 − F∞)/F0 ∈ [0, 1]
    rmse: float
    r_squared: float
    experimental: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- JKR


def jkr_forward(
    delta: np.ndarray, e_star: float, work_of_adhesion: float, tip_radius: float
) -> np.ndarray:
    """Fuerza JKR (esfera-plano) evaluada en las indentaciones ``delta`` (m).

    Usa la forma **paramétrica** en el radio de contacto ``a``::

        δ(a) = a²/R − sqrt(2π w a / E*)
        F(a) = 4 E* a³ / (3 R) − sqrt(8π w E* a³)

    y se interpola ``F`` en los ``delta`` pedidos sobre la rama de carga (``δ`` creciente).
    Con ``w = 0`` reduce exactamente a Hertz: ``F = (4/3) E* √R · δ^{3/2}``.
    """
    delta = np.asarray(delta, dtype=np.float64)
    d_max = float(np.max(delta)) if delta.size else 0.0

    def _curve(a_max: float) -> tuple[np.ndarray, np.ndarray]:
        a = np.linspace(a_max * 1e-4, a_max, 2048)
        d = a**2 / tip_radius - np.sqrt(2.0 * np.pi * work_of_adhesion * a / e_star)
        f = 4.0 * e_star * a**3 / (3.0 * tip_radius) - np.sqrt(
            8.0 * np.pi * work_of_adhesion * e_star * a**3
        )
        return d, f

    # El término adhesivo baja δ(a): con adhesión hay que crecer `a` para alcanzar δ_max, o la
    # rama se queda en el régimen atractivo y F sale toda negativa (bug histórico). Se crece
    # a_max hasta cubrir δ_max manteniendo densidad razonable de la grilla.
    a_max = 1.6 * np.sqrt(tip_radius * max(d_max, 1e-30))
    d_of_a, f_of_a = _curve(a_max)
    for _ in range(12):
        if float(d_of_a.max()) >= d_max:
            break
        a_max *= 1.5
        d_of_a, f_of_a = _curve(a_max)
    # Rama de carga: desde el mínimo de δ (pull-off) hacia arriba, δ es monótona creciente.
    start = int(np.argmin(d_of_a))
    d_branch = d_of_a[start:]
    f_branch = f_of_a[start:]
    return np.interp(delta, d_branch, f_branch, left=f_branch[0], right=f_branch[-1])


def _hertz_e_star(delta: np.ndarray, force: np.ndarray, tip_radius: float) -> float:
    """Estimación inicial de E* por Hertz esférico (F = k·δ^1.5, k = 4/3 E* √R)."""
    basis = delta**1.5
    denom = float(np.sum(basis**2))
    if denom <= 0:
        return 1.0
    stiffness = float(np.sum(basis * force) / denom)
    return max(stiffness / ((4.0 / 3.0) * np.sqrt(tip_radius)), 1e-3)


def fit_jkr(
    delta: np.ndarray,
    force: np.ndarray,
    tip_radius: float,
    poisson: float = 0.3,
) -> JKRResult:
    """Ajusta el modelo JKR (⚠️ experimental) a ``(delta, force)`` en contacto.

    Busca ``(E*, w)`` que minimizan el error cuadrático por búsqueda en grilla con dos
    refinamientos (numpy puro). ``delta`` en m (indentación ≥ 0), ``force`` en N.

    Verificación: sólo contra el límite ``w → 0`` (Hertz). **No** validado contra
    referencia experimental — ver el aviso del módulo.
    """
    delta = np.asarray(delta, dtype=np.float64)
    force = np.asarray(force, dtype=np.float64)
    if delta.size < 3:
        raise ValueError("se requieren ≥3 puntos en contacto para JKR")

    e0 = _hertz_e_star(delta, force, tip_radius)
    # w típico (J/m²): de la fuerza de pull-off JKR F_adh = (3/2)π w R, si hay adhesión.
    f_min = float(np.min(force))
    w0 = max(2.0 * (-f_min) / (3.0 * np.pi * tip_radius), 0.0) if f_min < 0 else 0.0

    def ssr(e_star: float, w: float) -> float:
        pred = jkr_forward(delta, e_star, w, tip_radius)
        return float(np.sum((force - pred) ** 2))

    e_lo, e_hi = e0 * 0.2, e0 * 5.0
    w_hi = max(w0 * 5.0, e0 * 1e-9)  # cota generosa relativa a la escala del problema
    best_e, best_w = e0, w0
    for _ in range(3):  # coarse → fine → finer
        e_grid = np.linspace(e_lo, e_hi, 21)
        w_grid = np.linspace(0.0, w_hi, 21)
        best = np.inf
        for e_star in e_grid:
            for w in w_grid:
                s = ssr(e_star, w)
                if s < best:
                    best, best_e, best_w = s, float(e_star), float(w)
        # estrecha la ventana alrededor del óptimo
        de = (e_hi - e_lo) / 10.0
        dw = w_hi / 10.0
        e_lo, e_hi = max(best_e - de, 1e-3), best_e + de
        w_hi = best_w + dw

    pred = jkr_forward(delta, best_e, best_w, tip_radius)
    residuals = force - pred
    ssr_val = float(np.sum(residuals**2))
    sst = float(np.sum((force - force.mean()) ** 2))
    r_squared = 1.0 - ssr_val / sst if sst > 0 else 1.0
    return JKRResult(
        young_modulus=best_e * (1.0 - poisson**2),
        reduced_modulus=best_e,
        work_of_adhesion=best_w,
        rmse=float(np.sqrt(ssr_val / residuals.size)),
        r_squared=r_squared,
        n_fit=int(delta.size),
    )


# ------------------------------------------------------------------- viscoelástico


def fit_relaxation(time: np.ndarray, force: np.ndarray) -> RelaxationResult:
    """Ajusta una relajación de fuerza SLS (⚠️ experimental): ``F = F∞ + (F0−F∞)e^{−t/τ}``.

    Para un ``τ`` dado el modelo es lineal en ``(F∞, F0−F∞)`` (mínimos cuadrados cerrados);
    se busca ``τ`` por grilla logarítmica con refinamiento. ``time`` en s, ``force`` en N.

    Verificación: sólo el límite elástico (sin relajación ⇒ ``relaxation_ratio ≈ 0``).
    **No** validado contra referencia experimental.
    """
    time = np.asarray(time, dtype=np.float64)
    force = np.asarray(force, dtype=np.float64)
    if time.size < 4:
        raise ValueError("se requieren ≥4 puntos para ajustar la relajación")
    t = time - time[0]
    span = float(t[-1]) or 1.0

    def fit_for_tau(tau: float) -> tuple[float, float, float, np.ndarray]:
        # F = f_inf·1 + (f0 - f_inf)·exp(-t/tau); base [1, exp(-t/tau)], lineal.
        basis = np.column_stack([np.ones_like(t), np.exp(-t / tau)])
        coef, *_ = np.linalg.lstsq(basis, force, rcond=None)
        f_inf, amp = float(coef[0]), float(coef[1])
        pred = basis @ coef
        return f_inf, f_inf + amp, float(np.sum((force - pred) ** 2)), pred

    best_tau, best = span / 3.0, np.inf
    lo, hi = span / 200.0, span * 5.0
    for _ in range(3):
        for tau in np.geomspace(lo, hi, 25):
            _, _, s, _ = fit_for_tau(float(tau))
            if s < best:
                best, best_tau = s, float(tau)
        lo, hi = best_tau / 3.0, best_tau * 3.0

    f_inf, f0, ssr_val, pred = fit_for_tau(best_tau)
    sst = float(np.sum((force - force.mean()) ** 2))
    r_squared = 1.0 - ssr_val / sst if sst > 0 else 1.0
    ratio = (f0 - f_inf) / f0 if f0 != 0 else 0.0
    return RelaxationResult(
        tau=best_tau,
        f0=f0,
        f_inf=f_inf,
        relaxation_ratio=float(ratio),
        rmse=float(np.sqrt(ssr_val / force.size)),
        r_squared=r_squared,
    )
