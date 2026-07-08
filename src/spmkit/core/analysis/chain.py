"""Modelos de cadena polimérica (SMFS) — Worm-Like Chain (WLC) y Freely-Jointed Chain (FJC).

Espectroscopía de fuerza de molécula única: al estirar una proteína/ácido nucleico, la
fuerza de retracción sigue un modelo entrópico de cadena. Este módulo implementa dos
modelos y sus ajustes por recuperación de parámetros conocidos:

- **WLC** (Marko-Siggia + corrección de Bouchiat): ``F(x)`` explícita; recupera contorno
  ``L`` y persistencia ``lp``.
- **FJC** (Freely-Jointed Chain, Langevin): ``x(F) = L · L(F·b/k_BT)``; recupera contorno
  ``L`` y longitud de Kuhn ``b`` (con ``lp = b/2``). Como ``F(x)`` no tiene forma cerrada,
  el FJC se ajusta en el espacio de extensión ``x(F)`` (convención estándar).

**Ajuste separable** (igual que la detección de contacto): en ambos modelos la longitud
que multiplica es un factor **lineal** dada la longitud no lineal (``lp`` dado ``L`` en el
WLC; ``L`` dado ``b`` en el FJC) → solución cerrada por mínimos cuadrados y búsqueda 1D
robusta sobre el parámetro no lineal. numpy puro, sin solver.

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
    """Resultado del ajuste de un modelo de cadena a un evento de estiramiento.

    ``rmse`` está en las unidades del eje ajustado: N para el WLC (ajusta ``F(x)``) y m
    para el FJC (ajusta ``x(F)``). ``kuhn_length`` solo lo llena el FJC (``lp = b/2``).
    """

    contour_length: float  # L (m)
    persistence_length: float  # lp (m)
    r_squared: float
    rmse: float  # N (WLC) o m (FJC) — ver docstring
    model: str
    temperature: float  # K
    n_fit: int
    kuhn_length: float | None = None  # b (m), solo FJC; lp = b/2

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


# --------------------------------------------------------------------- FJC (Langevin)


def _langevin(u: np.ndarray) -> np.ndarray:
    """Función de Langevin ``L(u) = coth(u) − 1/u``, con serie ``u/3`` cerca de 0.

    Evita el ``0/0`` en ``u→0`` (donde ``coth(u)−1/u → u/3``) sin generar avisos de
    división: la rama no tomada usa un ``u`` ficticio de 1.0.
    """
    u = np.asarray(u, dtype=np.float64)
    safe = np.where(u == 0.0, 1.0, u)
    return np.where(np.abs(u) < 1e-4, u / 3.0, 1.0 / np.tanh(safe) - 1.0 / safe)


def fjc_extension(
    force: np.ndarray,
    contour_length: float,
    kuhn_length: float,
    temperature: float = 298.0,
) -> np.ndarray:
    """Extensión FJC (m) para fuerza ``force`` (N), contorno ``L`` y Kuhn ``b`` (m).

    ``x(F) = L · L(F·b / k_BT)`` con ``L`` la función de Langevin. Modelo directo (la
    extensión es explícita en la fuerza; la inversa ``F(x)`` no tiene forma cerrada).
    """
    kt = _KB * temperature
    return contour_length * _langevin(np.asarray(force, dtype=np.float64) * kuhn_length / kt)


def fit_fjc(
    extension: np.ndarray,
    force: np.ndarray,
    temperature: float = 298.0,
    kuhn_bounds: tuple[float, float] | None = None,
) -> ChainFit:
    """Ajusta el FJC a ``(extension, force)`` y recupera ``L`` y la longitud de Kuhn ``b``.

    Separable en el espacio de extensión: para cada candidato ``b``, el contorno ``L`` sale
    por mínimos cuadrados cerrados (``x = L · L(F·b/k_BT)``); se busca ``b`` en 1D (grilla
    logarítmica + refinamiento), parametrizada por la fuerza reducida máxima ``u_max =
    F_max·b/k_BT`` (que controla la curvatura de Langevin). La curva debe estar corregida de
    línea base (rama de retracción). Devuelve ``lp = b/2`` en ``persistence_length``.
    """
    x = np.asarray(extension, dtype=np.float64)
    f = np.asarray(force, dtype=np.float64)
    finite = np.isfinite(x) & np.isfinite(f)
    x, f = x[finite], f[finite]
    if x.size < 5:
        raise ValueError("se requieren ≥5 puntos para ajustar el FJC")
    f_max = float(np.max(np.abs(f)))
    if f_max <= 0:
        raise ValueError("la fuerza debe tener magnitud positiva")

    kt = _KB * temperature
    b_scale = kt / f_max  # b tal que u_max = F_max·b/k_BT = 1
    # u_max ∈ [0.1, 200] cubre desde régimen casi lineal hasta saturación de Langevin.
    lo, hi = kuhn_bounds or (0.1 * b_scale, 200.0 * b_scale)

    def residual(kuhn: float) -> tuple[float, float]:
        g = _langevin(f * kuhn / kt)  # L(F·b/k_BT)
        denom = float(np.sum(g * g))
        if denom <= 0.0:
            return np.inf, 0.0
        length = float(np.sum(g * x) / denom)  # L = factor lineal cerrado
        return float(np.sum((x - length * g) ** 2)), length

    grid = np.geomspace(lo, hi, 80)  # escala → grilla logarítmica
    best_b = float(min(grid, key=lambda bb: residual(bb)[0]))
    step = best_b * 0.5
    for _ in range(5):  # refina b localmente
        cand = np.linspace(max(best_b - step, lo * 1e-3), best_b + step, 21)
        best_b = float(min(cand, key=lambda bb: residual(bb)[0]))
        step /= 5.0

    ssr, length = residual(best_b)
    sst = float(np.sum((x - x.mean()) ** 2))
    r2 = 1.0 - ssr / sst if sst > 0 else 1.0
    return ChainFit(
        contour_length=float(length),
        persistence_length=float(best_b / 2.0),  # lp = b/2
        r_squared=float(r2),
        rmse=float(np.sqrt(ssr / x.size)),  # RMSE en metros (ajuste en extensión)
        model="fjc",
        temperature=temperature,
        n_fit=int(x.size),
        kuhn_length=float(best_b),
    )
