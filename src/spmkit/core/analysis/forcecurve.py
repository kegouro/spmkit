"""Nanomecánica nativa de curvas de fuerza (Fase 3).

A diferencia de :mod:`spmkit.core.analysis.mechanics` (orientado a espectroscopía
``.nid`` clásica, "contacto a z alto"), este módulo ajusta curvas de fuerza de
forma **robusta a la convención de signo** del eje: funciona igual para JPK
(separación positiva, decreciente al contacto) y NanoSurf (separación negativa),
porque mide la indentación como ``δ = |x − x₀|`` y orienta la curva por su línea
base (la zona plana, sin contacto).

Sobre una :class:`ForceSegment` (o arrays separación/fuerza) entrega módulo de Young
con incertidumbre y R², adhesión y —con approach+retract— energía de disipación
(histéresis). Reutiliza los modelos de contacto validados de :mod:`mechanics`
(Hertz/paraboloide/cono/DMT).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from spmkit.core.analysis.mechanics import _MODELS, _e_star_from_stiffness


@dataclass(frozen=True)
class ForceCurveFit:
    """Resultado del ajuste de elasticidad de una curva de fuerza."""

    young_modulus: float
    young_modulus_std: float
    r_squared: float
    contact_point: float  # valor del eje (m) en el contacto
    adhesion: float  # N (pull-off)
    model: str
    n_fit: int
    unit_modulus: str = "Pa"
    #: Línea de ajuste en coordenadas de display (eje ``x`` y fuerza cruda), para
    #: dibujarla superpuesta a los datos. No forma parte de ``to_dict`` (escalares).
    x_fit: np.ndarray = field(default_factory=lambda: np.empty(0), repr=False, compare=False)
    f_fit: np.ndarray = field(default_factory=lambda: np.empty(0), repr=False, compare=False)
    #: Residuos (dato − ajuste, N) alineados con ``x_fit`` — para la tira de residuos.
    residual: np.ndarray = field(default_factory=lambda: np.empty(0), repr=False, compare=False)

    def to_dict(self) -> dict:
        """Sólo los escalares (para CSV/JSON/CLI); omite las curvas de ajuste."""
        d = asdict(self)
        for k in ("x_fit", "f_fit", "residual"):
            d.pop(k, None)
        return d

    def _repr_html_(self) -> str:
        """Render inline en Jupyter (tabla compacta del ajuste)."""
        e = self.young_modulus / 1e3
        es = self.young_modulus_std / 1e3
        return (
            "<table><tbody>"
            f"<tr><th align='left'>Módulo de Young</th><td>{e:.3g} ± {es:.2g} kPa</td></tr>"
            f"<tr><th align='left'>R²</th><td>{self.r_squared:.4f}</td></tr>"
            f"<tr><th align='left'>Adhesión</th><td>{self.adhesion * 1e9:.3g} nN</td></tr>"
            f"<tr><th align='left'>Modelo</th><td>{self.model}</td></tr>"
            f"<tr><th align='left'>Puntos ajustados</th><td>{self.n_fit}</td></tr>"
            "</tbody></table>"
        )


def display_axis(separation: np.ndarray | None, raw_height: np.ndarray) -> np.ndarray:
    """Eje para ajustar/dibujar: separación punta-muestra si es utilizable, si no altura.

    Se prefiere la separación (indentación real, corregida por flexión). Pero algunos
    instrumentos la entregan **saturada/clipada** (muchos valores repetidos en el
    contacto), inservible; en ese caso se usa la altura del piezo (limpia y monótona),
    que da el módulo "aparente". Fuente única para el pipeline y el lienzo.
    """
    if separation is not None:
        sep = np.asarray(separation, dtype=np.float64)
        if np.unique(sep).size >= 0.9 * sep.size:  # separación no degenerada
            return sep
    return np.asarray(raw_height, dtype=np.float64)


def _orient(x: np.ndarray, f: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Ordena la curva con la línea base (fuerza plana) primero.

    La zona sin contacto tiene fuerza casi constante (baja desviación); la de
    contacto varía mucho. Se pone el extremo de menor desviación al inicio.
    """
    n = max(3, x.size // 4)
    if np.std(f[:n]) <= np.std(f[-n:]):
        return x, f
    return x[::-1], f[::-1]


def _fit_baseline(force: np.ndarray, baseline_fraction: float) -> np.ndarray:
    """Recta de línea base ajustada **en función del índice** (no del eje físico).

    Se usa el índice (0…N) en vez del eje físico (separación ~1e-6 m) porque un
    ``polyfit`` sobre valores ~µm queda mal condicionado; sobre el índice la zona
    sin contacto es igual de lineal y el ajuste es numéricamente estable.
    """
    n_base = max(3, int(force.size * baseline_fraction))
    idx = np.arange(force.size, dtype=np.float64)
    coeffs = np.polyfit(idx[:n_base], force[:n_base], 1)
    return np.polyval(coeffs, idx)


def _baseline_corrected(force: np.ndarray, baseline_fraction: float) -> np.ndarray:
    """Fuerza con la línea base restada (ver :func:`_fit_baseline`)."""
    return force - _fit_baseline(force, baseline_fraction)


def _contact_index(f_corr: np.ndarray, baseline_fraction: float, k: float) -> int:
    """Índice del contacto: primer cruce **sostenido** por sobre ``k``·σ del ruido.

    Usa un umbral robusto (máximo entre ``k``·σ de la base y una fracción del pico)
    para no dispararse con el ruido/offset de la línea base ni con el dip de adhesión
    (que es negativo). Exige que el punto y su vecino sigan en contacto.
    """
    n = max(3, int(f_corr.size * baseline_fraction))
    sigma = float(np.std(f_corr[:n]))
    peak = float(np.max(f_corr))
    # Umbral = k·σ del ruido de la base, con un piso mínimo solo para no dispararse
    # con el ruido de punto flotante en curvas ideales (σ≈0). No sesga el contacto.
    threshold = max(k * sigma, 1e-6 * peak)
    above = f_corr > threshold
    # primer índice donde arranca contacto sostenido (el punto y el siguiente arriba)
    for i in range(above.size - 1):
        if above[i] and above[i + 1]:
            return i
    hit = np.flatnonzero(above)
    return int(hit[0]) if hit.size else f_corr.size - 1


def find_contact(
    x: np.ndarray,
    force: np.ndarray,
    baseline_fraction: float = 0.3,
    k_sigma: float = 5.0,
) -> float:
    """Punto de contacto (valor del eje ``x``) de una curva de fuerza.

    Robusto al signo/orden: orienta por la línea base, corrige base y devuelve el
    primer punto por sobre el ruido.
    """
    x = np.asarray(x, dtype=np.float64)
    force = np.asarray(force, dtype=np.float64)
    finite = np.isfinite(x) & np.isfinite(force)
    x, force = x[finite], force[finite]
    if x.size < 10:
        raise ValueError("Muy pocos puntos finitos para detectar el contacto")
    x, force = _orient(x, force)
    f_corr = _baseline_corrected(force, baseline_fraction)
    return float(x[_contact_index(f_corr, baseline_fraction, k_sigma)])


def fit_force_curve(
    x: np.ndarray,
    force: np.ndarray,
    model: str = "sphere",
    tip_radius: float = 10e-9,
    poisson: float = 0.3,
    half_angle: float = np.deg2rad(20.0),
    baseline_fraction: float = 0.3,
    k_sigma: float = 5.0,
    fit_range: tuple[float, float] | None = None,
) -> ForceCurveFit:
    """Ajusta un modelo de contacto a una curva de fuerza (eje ``x`` = separación).

    Robusto al signo/orden del eje: orienta por la línea base, corrige base, detecta
    contacto y ajusta ``F = A·δ^n`` con ``δ = |x − x₀|`` (por eso ``A`` y el módulo
    salen positivos con cualquier convención).

    ``fit_range`` (min, max en unidades del eje) restringe el análisis a esa ventana
    (selección manual estilo JPK); si deja menos de 10 puntos, se ignora y se usa toda
    la curva (para que arrastrar la región en vivo nunca rompa el ajuste).
    """
    if model not in _MODELS:
        raise ValueError(f"model debe ser uno de {sorted(_MODELS)}")
    x = np.asarray(x, dtype=np.float64)
    force = np.asarray(force, dtype=np.float64)
    finite = np.isfinite(x) & np.isfinite(force)
    x, force = x[finite], force[finite]
    if fit_range is not None:
        lo, hi = sorted(fit_range)
        window = (x >= lo) & (x <= hi)
        if int(np.count_nonzero(window)) >= 10:  # si no, se ignora la ventana
            x, force = x[window], force[window]
    if x.size < 10:
        raise ValueError("Muy pocos puntos finitos para ajustar la curva de fuerza")

    x, force = _orient(x, force)

    # Corrección de línea base (recta en función del índice, bien condicionada).
    baseline = _fit_baseline(force, baseline_fraction)
    f_corr = force - baseline

    adhesion = float(max(0.0, -f_corr.min()))  # pull-off respecto a la base

    if model == "dmt":
        # DMT: el contacto es el punto de snap-in (mínimo de fuerza / máxima adhesión),
        # donde δ=0 y F=−F_adh.
        i0 = int(np.argmin(f_corr))
    else:
        i0 = _contact_index(f_corr, baseline_fraction, k_sigma)
    # Ajustar solo la curva de CARGA: de contacto al máximo de fuerza. Tras el pico,
    # la curva es turnaround/relajación (fuerza baja con la punta ya indentada) y
    # rompería el ajuste monótono F = A·δ^n.
    i_peak = int(np.argmax(f_corr))
    hi = i_peak + 1 if i_peak > i0 + 2 else f_corr.size
    x0 = float(x[i0])
    delta = np.abs(x[i0:hi] - x0)
    f_fit = f_corr[i0:hi]
    if model == "dmt":
        f_fit = f_fit + adhesion  # DMT: adhesión como offset constante

    valid = delta > 0
    delta, f_fit = delta[valid], f_fit[valid]
    if delta.size < 3:
        raise ValueError("Indentación insuficiente tras detectar el contacto")

    exponent = _MODELS[model]
    basis = delta**exponent
    denom = float(np.sum(basis**2))
    stiffness = float(np.sum(basis * f_fit) / denom)
    e_star = _e_star_from_stiffness(stiffness, model, tip_radius, half_angle)
    young = e_star * (1.0 - poisson**2)

    predicted = stiffness * basis
    residuals = f_fit - predicted
    ssr = float(np.sum(residuals**2))
    sst = float(np.sum((f_fit - f_fit.mean()) ** 2))
    r_squared = 1.0 - ssr / sst if sst > 0 else 1.0
    dof = max(1, delta.size - 1)
    var_stiffness = (ssr / dof) / denom
    sigma_young = young * float(np.sqrt(var_stiffness)) / stiffness if stiffness > 0 else 0.0

    # Línea de ajuste en coordenadas de display: predicción (en fuerza corregida)
    # devuelta a fuerza cruda sumando la línea base. Para DMT se descuenta el offset
    # de adhesión que se había añadido al objetivo del ajuste.
    x_fit = x[i0:hi][valid]
    f_fit_line = predicted + baseline[i0:hi][valid]
    if model == "dmt":
        f_fit_line = f_fit_line - adhesion

    return ForceCurveFit(
        young_modulus=young,
        young_modulus_std=sigma_young,
        r_squared=r_squared,
        contact_point=x0,
        adhesion=adhesion,
        model=model,
        n_fit=int(delta.size),
        x_fit=np.asarray(x_fit, dtype=np.float64),
        f_fit=np.asarray(f_fit_line, dtype=np.float64),
        residual=np.asarray(residuals, dtype=np.float64),
    )


def fit_force_curve_mc(
    x: np.ndarray,
    force: np.ndarray,
    invols_rel_err: float = 0.05,
    k_rel_err: float = 0.05,
    n_samples: int = 200,
    seed: int = 0,
    **fit_kwargs: object,
) -> tuple[float, float]:
    """Incertidumbre Monte Carlo del módulo propagando errores de InVOLS y k.

    La fuerza calibrada es ``F ∝ InVOLS·k`` y el módulo es lineal en ``F``, así que
    cada muestra escala la fuerza por un factor con la incertidumbre combinada y
    reajusta. Determinista dada ``seed`` (usa ``np.random.default_rng``).

    Returns:
        ``(módulo_medio, módulo_std)`` en Pa.
    """
    rng = np.random.default_rng(seed)
    moduli = np.empty(n_samples)
    for i in range(n_samples):
        scale = float(rng.normal(1.0, invols_rel_err) * rng.normal(1.0, k_rel_err))
        moduli[i] = fit_force_curve(x, force * scale, **fit_kwargs).young_modulus  # type: ignore[arg-type]
    return float(moduli.mean()), float(moduli.std())


def dissipation_energy(
    x_extend: np.ndarray,
    f_extend: np.ndarray,
    x_retract: np.ndarray,
    f_retract: np.ndarray,
) -> float:
    """Energía disipada (J) = área de histéresis entre approach y retract.

    Integra la fuerza respecto al eje de separación en cada rama y devuelve el valor
    absoluto de la diferencia (∮F·dx del lazo). Cero si approach == retract.
    """
    w_ext = float(np.trapezoid(np.asarray(f_extend, float), np.asarray(x_extend, float)))
    w_ret = float(np.trapezoid(np.asarray(f_retract, float), np.asarray(x_retract, float)))
    return abs(w_ext - w_ret)
