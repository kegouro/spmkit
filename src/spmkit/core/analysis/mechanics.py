"""Análisis de nanomecánica a partir de curvas fuerza-distancia (force-distance).

Flujo típico:

1. :func:`extract_curves` saca las curvas individuales de un canal de
   espectroscopía (grupos ``Spec`` de NanoSurf: ``Lines`` curvas ×
   ``Points`` muestras, con eje Z en ``Dim0`` y fuerza en ``Dim2``).
2. :func:`baseline_correct` quita la línea base (zona sin contacto).
3. :func:`find_contact_point` detecta el punto de contacto.
4. :func:`fit_hertz` ajusta un modelo de contacto y estima el módulo de Young.

Convención: ``z`` creciente acerca la punta a la muestra; el contacto ocurre
a ``z`` alto. En el régimen de contacto, la indentación es
``delta = (z - z0) - deflexión``; con cantiléver rígido o sin constante de
resorte se aproxima ``delta ≈ z - z0``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from spmkit.core.models import SPMChannel

#: Modelos de contacto soportados y su exponente de indentación.
_MODELS = {
    "sphere": 1.5,  # Hertz esférico / paraboloide (R = radio de punta)
    "paraboloid": 1.5,
    "cone": 2.0,  # Sneddon cónico (alpha = semiángulo)
}


@dataclass(frozen=True)
class ForceCurve:
    """Una curva fuerza-distancia individual."""

    z: np.ndarray
    force: np.ndarray
    index: int = 0
    direction: str = "forward"
    z_unit: str = "m"
    force_unit: str = "N"
    metadata: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return int(self.z.size)


@dataclass(frozen=True)
class IndentationResult:
    """Resultado del ajuste de una curva fuerza-indentación."""

    young_modulus: float
    contact_point: float
    adhesion: float
    model: str
    rmse: float
    unit_modulus: str = "Pa"

    def to_dict(self) -> dict:
        return asdict(self)


def extract_curves(channel: SPMChannel) -> list[ForceCurve]:
    """Extrae las curvas fuerza-distancia de un canal de espectroscopía.

    El eje Z se reconstruye de los metadatos ``Dim0Min``/``Dim0Range`` del
    canal; la fuerza son los datos del canal (una curva por fila).
    """
    data = np.atleast_2d(np.asarray(channel.data, dtype=np.float64))
    n_curves, n_points = data.shape
    meta = channel.metadata
    z_min = float(meta.get("Dim0Min", 0.0))
    z_range = float(meta.get("Dim0Range", float(n_points)))
    z = z_min + np.linspace(0.0, z_range, n_points)
    z_unit = meta.get("Dim0Unit", "m")
    return [
        ForceCurve(
            z=z,
            force=data[i],
            index=i,
            direction=channel.direction,
            z_unit=z_unit,
            force_unit=channel.unit or "N",
            metadata={"source_channel": channel.name},
        )
        for i in range(n_curves)
    ]


def baseline_correct(curve: ForceCurve, fraction: float = 0.3) -> ForceCurve:
    """Resta la línea base ajustada a la zona sin contacto (``z`` bajo)."""
    if not 0 < fraction < 1:
        raise ValueError("fraction debe estar en (0, 1)")
    n = max(2, int(curve.z.size * fraction))
    coeffs = np.polyfit(curve.z[:n], curve.force[:n], 1)
    baseline = np.polyval(coeffs, curve.z)
    return ForceCurve(
        z=curve.z,
        force=curve.force - baseline,
        index=curve.index,
        direction=curve.direction,
        z_unit=curve.z_unit,
        force_unit=curve.force_unit,
        metadata=dict(curve.metadata),
    )


def find_contact_point(curve: ForceCurve, fraction: float = 0.3, k: float = 5.0) -> float:
    """Devuelve el ``z`` del punto de contacto (primer cruce sobre el ruido).

    Usa la desviación estándar de la línea base como umbral (``k`` sigmas).
    Asume que ``curve`` ya está corregida de base.
    """
    n = max(2, int(curve.z.size * fraction))
    threshold = k * float(np.std(curve.force[:n]))
    above = np.flatnonzero(curve.force > threshold)
    if above.size == 0:
        return float(curve.z[-1])
    return float(curve.z[above[0]])


def fit_hertz(
    curve: ForceCurve,
    tip_radius: float,
    poisson: float = 0.3,
    model: str = "sphere",
    contact_point: float | None = None,
    spring_constant: float | None = None,
    half_angle: float = np.deg2rad(20.0),
) -> IndentationResult:
    """Ajusta un modelo de contacto a la curva y estima el módulo de Young.

    * ``sphere``/``paraboloid``: ``F = (4/3) E* sqrt(R) delta^1.5``
    * ``cone`` (Sneddon): ``F = (2/pi) E* tan(alpha) delta^2``

    con ``E* = E / (1 - nu^2)``.

    Args:
        tip_radius: Radio de la punta ``R`` (m) para modelos esféricos.
        poisson: Coeficiente de Poisson de la muestra.
        model: ``"sphere"``, ``"paraboloid"`` o ``"cone"``.
        contact_point: ``z0`` (m). Si es ``None`` se detecta automáticamente.
        spring_constant: Constante del cantiléver (N/m) para corregir la
            indentación por la deflexión. Si es ``None``, ``delta ≈ z - z0``.
        half_angle: Semiángulo de la punta cónica (rad), solo para ``cone``.
    """
    if model not in _MODELS:
        raise ValueError(f"model debe ser uno de {sorted(_MODELS)}")

    corrected = baseline_correct(curve)
    z0 = find_contact_point(corrected) if contact_point is None else contact_point

    mask = corrected.z >= z0
    z_c = corrected.z[mask]
    f_c = corrected.force[mask]
    if z_c.size < 3:
        raise ValueError("Muy pocos puntos en contacto para ajustar")

    delta = z_c - z0
    if spring_constant is not None and spring_constant > 0:
        delta = delta - f_c / spring_constant
    valid = delta > 0
    delta, f_c = delta[valid], f_c[valid]
    if delta.size < 3:
        raise ValueError("Indentación insuficiente tras la corrección")

    exponent = _MODELS[model]
    basis = delta**exponent
    stiffness = float(np.sum(basis * f_c) / np.sum(basis**2))  # k tal que F = k·delta^n

    e_star = _e_star_from_stiffness(stiffness, model, tip_radius, half_angle)
    young = e_star * (1.0 - poisson**2)

    predicted = stiffness * basis
    rmse = float(np.sqrt(np.mean((f_c - predicted) ** 2)))

    return IndentationResult(
        young_modulus=young,
        contact_point=float(z0),
        adhesion=adhesion(curve),
        model=model,
        rmse=rmse,
    )


def adhesion(curve: ForceCurve) -> float:
    """Fuerza de adhesión: magnitud del mínimo de fuerza (pull-off)."""
    fmin = float(np.min(curve.force))
    return -fmin if fmin < 0 else 0.0


def _e_star_from_stiffness(
    stiffness: float, model: str, tip_radius: float, half_angle: float
) -> float:
    """Despeja el módulo reducido E* de la rigidez ajustada ``F = k·delta^n``."""
    if model in ("sphere", "paraboloid"):
        return stiffness / ((4.0 / 3.0) * np.sqrt(tip_radius))
    # cone (Sneddon)
    return stiffness * np.pi / (2.0 * np.tan(half_angle))
