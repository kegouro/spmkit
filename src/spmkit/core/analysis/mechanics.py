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
    "dmt": 1.5,  # Derjaguin-Muller-Toporov: Hertz + adhesión como offset constante
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
    """Resultado del ajuste de una curva fuerza-indentación.

    Attributes:
        young_modulus: Módulo de Young estimado (Pa).
        young_modulus_std: Incertidumbre 1σ del módulo (Pa), propagada de la
            covarianza del ajuste lineal. Cero para curvas sin ruido.
        r_squared: Bondad de ajuste (coeficiente de determinación) en [−∞, 1].
        contact_point: Posición ``z0`` del contacto (m).
        adhesion: Fuerza de adhesión / pull-off (N), medida sobre la curva
            corregida de línea base.
        model: Modelo de contacto usado.
        rmse: Error cuadrático medio del ajuste (N).
        n_fit: Número de puntos usados en el ajuste.
    """

    young_modulus: float
    contact_point: float
    adhesion: float
    model: str
    rmse: float
    unit_modulus: str = "Pa"
    young_modulus_std: float = 0.0
    r_squared: float = 1.0
    n_fit: int = 0

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


def find_contact_point(
    curve: ForceCurve, fraction: float = 0.3, k: float = 5.0, method: str = "threshold"
) -> float:
    """Devuelve el ``z`` del punto de contacto. Asume ``curve`` corregida de base.

    Args:
        method: ``"threshold"`` (primer cruce sobre ``k``·σ del ruido de la línea
            base; rápido pero sensible al ruido) o ``"rov"`` (*ratio of variances*,
            Gavara 2016; mucho más robusto en curvas reales ruidosas).
        fraction: Fracción inicial usada como línea base para el umbral.
        k: Número de sigmas del umbral (solo ``method="threshold"``).
    """
    if method == "rov":
        cp = _contact_point_rov(curve.z, curve.force)
        if cp is not None:
            return cp
        # RoV no aplicable (curva muy corta): cae al método de umbral.
    n = max(2, int(curve.z.size * fraction))
    threshold = k * float(np.std(curve.force[:n]))
    above = np.flatnonzero(curve.force > threshold)
    if above.size == 0:
        return float(curve.z[-1])
    return float(curve.z[above[0]])


def _contact_point_rov(z: np.ndarray, force: np.ndarray, window: int | None = None) -> float | None:
    """Punto de contacto por *ratio of variances* (Gavara, Sci. Rep. 2016).

    Compara, punto a punto, la varianza de la ventana posterior con la anterior;
    al entrar en contacto la varianza salta, así que el contacto es el máximo del
    cociente. Robusto al ruido a diferencia del umbral de ``k``·σ. Devuelve
    ``None`` si la curva es demasiado corta para el método.
    """
    n = int(force.size)
    w = window if window is not None else max(3, n // 20)
    if n < 2 * w + 1:
        return None
    eps = 1e-12 * float(np.max(force**2)) + 1e-300  # evita 0/0 en líneas base sin ruido
    # ponytail: bucle O(n) claro; vectorizar con momentos acumulados si las curvas crecen mucho.
    rov = np.full(n, -np.inf)
    for i in range(w, n - w):
        var_before = float(np.var(force[i - w : i]))
        var_after = float(np.var(force[i : i + w]))
        rov[i] = var_after / (var_before + eps)
    return float(z[int(np.argmax(rov))])


def fit_hertz(
    curve: ForceCurve,
    tip_radius: float,
    poisson: float = 0.3,
    model: str = "sphere",
    contact_point: float | None = None,
    spring_constant: float | None = None,
    contact_method: str = "threshold",
    half_angle: float = np.deg2rad(20.0),
) -> IndentationResult:
    """Ajusta un modelo de contacto a la curva y estima el módulo de Young.

    * ``sphere``/``paraboloid``: ``F = (4/3) E* sqrt(R) delta^1.5``
    * ``cone`` (Sneddon): ``F = (2/pi) E* tan(alpha) delta^2``
    * ``dmt`` (Derjaguin-Muller-Toporov): ``F = (4/3) E* sqrt(R) delta^1.5 - F_adh``,
      idéntico a Hertz esférico salvo un offset de adhesión constante; recomendado
      para muestras rígidas con adhesión no despreciable.

    con ``E* = E / (1 - nu^2)`` (punta rígida). El resultado incluye la
    incertidumbre 1σ del módulo y el R² del ajuste.

    Args:
        tip_radius: Radio de la punta ``R`` (m) para modelos esféricos/DMT.
        poisson: Coeficiente de Poisson de la muestra.
        model: ``"sphere"``, ``"paraboloid"``, ``"cone"`` o ``"dmt"``.
        contact_point: ``z0`` (m). Si es ``None`` se detecta automáticamente.
        spring_constant: Constante del cantiléver (N/m) para corregir la
            indentación por la deflexión. Si es ``None``, ``delta ≈ z - z0``.
        contact_method: Método de detección del contacto (``"threshold"`` o
            ``"rov"``), solo si ``contact_point is None``.
        half_angle: Semiángulo de la punta cónica (rad), solo para ``cone``.
    """
    if model not in _MODELS:
        raise ValueError(f"model debe ser uno de {sorted(_MODELS)}")

    corrected = baseline_correct(curve)
    adh = adhesion(corrected)  # pull-off medido sobre la curva corregida de base
    z0 = (
        find_contact_point(corrected, method=contact_method)
        if contact_point is None
        else contact_point
    )

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

    # DMT: la parte elástica es F_medida + F_adh (adhesión como offset constante).
    f_fit = f_c + adh if model == "dmt" else f_c

    exponent = _MODELS[model]
    basis = delta**exponent
    denom = float(np.sum(basis**2))
    stiffness = float(np.sum(basis * f_fit) / denom)  # k tal que F = k·delta^n

    e_star = _e_star_from_stiffness(stiffness, model, tip_radius, half_angle)
    young = e_star * (1.0 - poisson**2)

    predicted = stiffness * basis
    residuals = f_fit - predicted
    ssr = float(np.sum(residuals**2))
    rmse = float(np.sqrt(ssr / residuals.size))

    # Bondad de ajuste e incertidumbre (modelo lineal F = k·basis por el origen).
    sst = float(np.sum((f_fit - f_fit.mean()) ** 2))
    r_squared = 1.0 - ssr / sst if sst > 0 else 1.0
    dof = max(1, delta.size - 1)
    var_stiffness = (ssr / dof) / denom
    sigma_young = young * float(np.sqrt(var_stiffness)) / stiffness if stiffness > 0 else 0.0

    return IndentationResult(
        young_modulus=young,
        contact_point=float(z0),
        adhesion=adh,
        model=model,
        rmse=rmse,
        young_modulus_std=sigma_young,
        r_squared=r_squared,
        n_fit=int(delta.size),
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
    contact_method: str = "threshold",
    half_angle: float = np.deg2rad(20.0),
) -> MechanicalMap:
    """Ajusta todas las curvas de un canal y arma mapas de módulo y adhesión.

    Args:
        grid: Forma ``(rows, cols)`` de la grilla espacial. Si es ``None`` se
            infiere una grilla cuadrada cuando es posible; si no, queda ``1×N``.
        contact_method: Método de detección del contacto para cada curva.
        half_angle: Semiángulo de la punta cónica (rad), propagado a cada ajuste
            ``cone`` (antes quedaba fijo en el valor por defecto).
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
                contact_method=contact_method,
                half_angle=half_angle,
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
    if model in ("sphere", "paraboloid", "dmt"):
        return stiffness / ((4.0 / 3.0) * np.sqrt(tip_radius))
    # cone (Sneddon)
    return stiffness * np.pi / (2.0 * np.tan(half_angle))


def thermal_spring_constant(
    deflection_variance: float,
    temperature: float = 293.15,
    correction_factor: float = 1.0,
) -> float:
    """Estima la constante de resorte del cantiléver por el método de equipartición.

    Aplica el **teorema de equipartición de la energía**: en equilibrio térmico,
    cada grado de libertad cuadrático almacena una energía promedio de ½·k_B·T.
    Para un cantiléver de constante k::

        ½·k·⟨x²⟩ = ½·k_B·T  →  k = χ · k_B·T / ⟨x²⟩

    donde ``χ`` (``correction_factor``) corrige por la forma del modo cuando la
    deflexión se mide con palanca óptica: la equipartición cruda supone el
    desplazamiento del extremo, pero el detector integra la pendiente, de modo
    que para el primer modo ``χ ≈ 0.817`` (Butt & Jaschke 1995). Con
    ``correction_factor=1.0`` se recupera la equipartición sin corregir.

    Args:
        deflection_variance: Varianza de la deflexión térmica del cantiléver
            ⟨x²⟩ en m². Debe obtenerse del espectro de densidad de potencia
            (área bajo el pico de resonancia) en una zona libre de la muestra.
            Debe ser estrictamente positivo.
        temperature: Temperatura de la muestra en Kelvin (por defecto 293.15 K
            ≈ 20 °C).
        correction_factor: Factor de corrección de forma de modo ``χ`` (1.0 por
            defecto; ≈0.817 para el primer modo con detección por palanca óptica).

    Returns:
        Constante de resorte k en N/m.

    Raises:
        ValueError: Si ``deflection_variance`` no es estrictamente positivo.

    Example::

        >>> round(thermal_spring_constant(1e-20), 4)
        0.4047
    """
    if deflection_variance <= 0:
        raise ValueError(
            f"deflection_variance debe ser estrictamente positivo, se recibió {deflection_variance}"
        )
    return correction_factor * _BOLTZMANN * temperature / deflection_variance
