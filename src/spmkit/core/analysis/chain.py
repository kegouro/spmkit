"""Modelos de cadena polimérica (SMFS) — Worm-Like Chain (WLC).

Espectroscopía de fuerza de molécula única: al estirar una proteína/ácido nucleico, la
fuerza de retracción sigue un modelo entrópico de cadena. Este módulo implementa el WLC
(Marko-Siggia y la corrección de Bouchiat de alta precisión) y ajusta longitud de contorno
``L`` y longitud de persistencia ``lp`` a un evento de estiramiento.

**Ajuste separable** (igual que la detección de contacto): como ``F = (k_B T / lp) · g(x/L)``,
para un ``L`` fijo ``lp`` es un factor lineal con solución cerrada → el problema conjunto se
reduce a una búsqueda 1D robusta sobre ``L``. numpy puro.

Nota de alcance: el ajuste asume la curva **ya corregida de línea base** en la rama de
retracción (la corrección de drift/baseline de retract y la detección de eventos son etapas
aparte). Validado por recuperación de parámetros conocidos (``tests/validation/test_recovery``).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

#: Constante de Boltzmann (J/K).
_KB = 1.380649e-23

#: Coeficientes de la corrección de Bouchiat et al. (1999), a₂…a₇. Reducen el error del WLC
#: de Marko-Siggia (~10% cerca de la extensión total) a ~0.01%.
_BOUCHIAT = (-0.5164228, -2.737418, 16.07497, -38.87607, 39.49944, -14.17718)


@dataclass(frozen=True)
class ChainFit:
    """Resultado del ajuste de un modelo de cadena a un evento de estiramiento."""

    contour_length: float  # L (m)
    persistence_length: float  # lp (m)
    r_squared: float
    rmse: float  # N
    model: str
    temperature: float  # K
    n_fit: int

    def to_dict(self) -> dict:
        return asdict(self)


def _reduced(x: np.ndarray, contour_length: float) -> np.ndarray:
    """Extensión relativa r = x/L, acotada a [0, 0.999) para evitar el polo en r=1."""
    return np.clip(x / contour_length, 0.0, 0.999)


def wlc_force(
    x: np.ndarray,
    contour_length: float,
    persistence_length: float,
    temperature: float = 298.0,
    model: str = "bouchiat",
) -> np.ndarray:
    """Fuerza WLC (N) para extensión ``x`` (m), contorno ``L`` y persistencia ``lp`` (m).

    ``model="marko_siggia"`` usa la interpolación clásica; ``"bouchiat"`` añade la corrección
    polinómica de alta precisión.
    """
    kt = _KB * temperature
    r = _reduced(x, contour_length)
    g = 1.0 / (4.0 * (1.0 - r) ** 2) - 0.25 + r
    if model == "bouchiat":
        g = g + sum(a * r ** (i + 2) for i, a in enumerate(_BOUCHIAT))
    elif model != "marko_siggia":
        raise ValueError(f"model debe ser 'marko_siggia' o 'bouchiat'; se recibió {model!r}")
    return (kt / persistence_length) * g


def _shape(x: np.ndarray, contour_length: float, temperature: float, model: str) -> np.ndarray:
    """Forma ``g(x/L)`` del WLC **sin** el factor k_BT/lp (para el ajuste separable)."""
    kt = _KB * temperature
    return wlc_force(x, contour_length, 1.0, temperature, model) / kt  # lp=1 → g·k_BT; /kt → g


def fit_wlc(
    extension: np.ndarray,
    force: np.ndarray,
    model: str = "bouchiat",
    temperature: float = 298.0,
    length_bounds: tuple[float, float] | None = None,
) -> ChainFit:
    """Ajusta el WLC a ``(extension, force)`` y recupera ``L`` y ``lp``.

    Separable: para cada candidato ``L``, ``lp`` sale por mínimos cuadrados cerrados
    (``F = (k_BT/lp)·g(x/L)``); se busca ``L`` en 1D (grilla + refinamiento). Robusto y
    sin solver no lineal. La curva debe estar corregida de línea base (rama de retracción).
    """
    x = np.asarray(extension, dtype=np.float64)
    f = np.asarray(force, dtype=np.float64)
    finite = np.isfinite(x) & np.isfinite(f)
    x, f = x[finite], f[finite]
    if x.size < 5:
        raise ValueError("se requieren ≥5 puntos para ajustar el WLC")
    x_max = float(np.max(x))
    if x_max <= 0:
        raise ValueError("la extensión debe ser positiva")

    lo, hi = length_bounds or (x_max * 1.001, x_max * 3.0)

    def residual(contour_length: float) -> tuple[float, float]:
        g = _shape(x, contour_length, temperature, model)  # g(x/L)
        denom = float(np.sum(g * g))
        if denom <= 0.0:
            return np.inf, 0.0
        a = float(np.sum(g * f) / denom)  # a = k_BT/lp (factor lineal cerrado)
        pred = a * g
        return float(np.sum((f - pred) ** 2)), a

    best_l = min(np.linspace(lo, hi, 80), key=lambda ll: residual(ll)[0])
    step = (hi - lo) / 80.0
    for _ in range(4):  # refina L
        best_l = min(np.linspace(best_l - step, best_l + step, 21), key=lambda ll: residual(ll)[0])
        step /= 10.0

    ssr, a = residual(best_l)
    lp = _KB * temperature / a if a > 0 else np.nan
    sst = float(np.sum((f - f.mean()) ** 2))
    r2 = 1.0 - ssr / sst if sst > 0 else 1.0
    return ChainFit(
        contour_length=float(best_l),
        persistence_length=float(lp),
        r_squared=float(r2),
        rmse=float(np.sqrt(ssr / f.size)),
        model=model,
        temperature=temperature,
        n_fit=int(f.size),
    )
