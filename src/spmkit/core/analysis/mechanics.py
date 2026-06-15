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

#: Constante de Boltzmann (J/K).
_BOLTZMANN = 1.380649e-23

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


@dataclass(frozen=True)
class MechanicalMap:
    """Mapas de propiedades mecánicas a partir de un conjunto de curvas.

    Cada arreglo tiene la forma de la grilla espacial (``rows × cols``); los
    ajustes fallidos quedan como ``NaN``.
    """

    young_modulus: np.ndarray
    adhesion: np.ndarray
    contact_point: np.ndarray
    grid_shape: tuple[int, int]
    n_curves: int
    n_failed: int
    unit_modulus: str = "Pa"


def _grid_shape(n: int, grid: tuple[int, int] | None) -> tuple[int, int]:
    if grid is not None:
        if grid[0] * grid[1] != n:
            raise ValueError(f"grid {grid} no coincide con {n} curvas")
        return grid
    root = int(round(n**0.5))
    if root * root == n:
        return (root, root)
    return (1, n)  # sin grilla cuadrada: tira 1×N


def fit_all(
    channel: SPMChannel,
    tip_radius: float,
    poisson: float = 0.3,
    model: str = "sphere",
    spring_constant: float | None = None,
    grid: tuple[int, int] | None = None,
) -> MechanicalMap:
    """Ajusta todas las curvas de un canal y arma mapas de módulo y adhesión.

    Args:
        grid: Forma ``(rows, cols)`` de la grilla espacial. Si es ``None`` se
            infiere una grilla cuadrada cuando es posible; si no, queda ``1×N``.
    """
    curves = extract_curves(channel)
    n = len(curves)
    shape = _grid_shape(n, grid)
    young = np.full(n, np.nan)
    adh = np.full(n, np.nan)
    contact = np.full(n, np.nan)
    n_failed = 0
    for i, curve in enumerate(curves):
        try:
            r = fit_hertz(
                curve,
                tip_radius=tip_radius,
                poisson=poisson,
                model=model,
                spring_constant=spring_constant,
            )
            young[i], adh[i], contact[i] = r.young_modulus, r.adhesion, r.contact_point
        except (ValueError, ZeroDivisionError):
            n_failed += 1
    return MechanicalMap(
        young_modulus=young.reshape(shape),
        adhesion=adh.reshape(shape),
        contact_point=contact.reshape(shape),
        grid_shape=shape,
        n_curves=n,
        n_failed=n_failed,
    )


def _e_star_from_stiffness(
    stiffness: float, model: str, tip_radius: float, half_angle: float
) -> float:
    """Despeja el módulo reducido E* de la rigidez ajustada ``F = k·delta^n``."""
    if model in ("sphere", "paraboloid"):
        return stiffness / ((4.0 / 3.0) * np.sqrt(tip_radius))
    # cone (Sneddon)
    return stiffness * np.pi / (2.0 * np.tan(half_angle))


def thermal_spring_constant(deflection_variance: float, temperature: float = 293.15) -> float:
    """Estima la constante de resorte del cantiléver por el método de equipartición.

    Aplica el **teorema de equipartición de la energía**: en equilibrio térmico,
    cada grado de libertad cuadrático almacena una energía promedio de ½·k_B·T.
    Para un cantiléver de constante k::

        ½·k·⟨x²⟩ = ½·k_B·T  →  k = k_B·T / ⟨x²⟩

    Args:
        deflection_variance: Varianza de la deflexión térmica del cantiléver
            ⟨x²⟩ en m². Debe obtenerse del espectro de densidad de potencia
            (área bajo el pico de resonancia) en una zona libre de la muestra.
            Debe ser estrictamente positivo.
        temperature: Temperatura de la muestra en Kelvin (por defecto 293.15 K
            ≈ 20 °C).

    Returns:
        Constante de resorte k en N/m.

    Raises:
        ValueError: Si ``deflection_variance`` no es estrictamente positivo.

    Example::

        >>> thermal_spring_constant(1e-20)
        40.50...
    """
    if deflection_variance <= 0:
        raise ValueError(
            f"deflection_variance debe ser estrictamente positivo, se recibió {deflection_variance}"
        )
    return _BOLTZMANN * temperature / deflection_variance
