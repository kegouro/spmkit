"""Calibración del cantiléver para espectroscopía de fuerza.

Convierte la señal cruda del fotodiodo en cantidades físicas, en cascada:

    señal (V) ──InVOLS──▶ deflexión (m) ──k──▶ fuerza (N)

donde ``InVOLS`` es la sensibilidad de deflexión (m/V) y ``k`` la constante de
resorte (N/m). Es el primer paso de cualquier análisis de curvas de fuerza en
Nanosurf ANA / JPK Data Processing.

Los formatos modernos (JPK) guardan esta cadena en los metadatos del archivo (ver
el lector correspondiente), de modo que la calibración suele venir dada; estas
funciones la **estiman** cuando falta (InVOLS de una curva sobre sustrato rígido,
``k`` por ruido térmico) o construyen el objeto :class:`Calibration`.
"""

from __future__ import annotations

import numpy as np

from spmkit.core.models import Calibration

#: Constante de Boltzmann (J/K).
_BOLTZMANN = 1.380649e-23


def deflection_sensitivity(
    volts: np.ndarray, height: np.ndarray, contact_fraction: float = 0.3
) -> float:
    """Estima el InVOLS (m/V) de la zona de contacto sobre un sustrato rígido.

    En contacto duro la punta no indenta: todo el desplazamiento del piezo va a
    deflexión, así que ``InVOLS = d(altura)/d(voltaje)`` en esa zona. Se ajusta una
    recta a la fracción final de la curva (mayor indentación).

    Args:
        volts: Señal de deflexión cruda (V).
        height: Altura del piezo (m), mismo tamaño que ``volts``.
        contact_fraction: Fracción final de la curva usada como zona de contacto.

    Returns:
        Sensibilidad de deflexión InVOLS en m/V (positiva).
    """
    volts = np.asarray(volts, dtype=np.float64)
    height = np.asarray(height, dtype=np.float64)
    if volts.size != height.size:
        raise ValueError("volts y height deben tener el mismo tamaño")
    if not 0 < contact_fraction <= 1:
        raise ValueError("contact_fraction debe estar en (0, 1]")
    n = max(2, int(volts.size * contact_fraction))
    slope = float(np.polyfit(volts[-n:], height[-n:], 1)[0])
    return abs(slope)


def volts_to_deflection(volts: np.ndarray, invols: float) -> np.ndarray:
    """Convierte señal (V) a deflexión (m): ``deflexión = volts · InVOLS``."""
    return np.asarray(volts, dtype=np.float64) * invols


def deflection_to_force(deflection_m: np.ndarray, spring_constant: float) -> np.ndarray:
    """Convierte deflexión (m) a fuerza (N): ``F = deflexión · k``."""
    return np.asarray(deflection_m, dtype=np.float64) * spring_constant


def spring_constant_thermal(
    deflection_variance: float,
    temperature: float = 293.15,
    correction_factor: float = 0.817,
) -> float:
    """Constante de resorte ``k`` por el método de ruido térmico (equipartición).

    ``k = χ · k_B · T / ⟨x²⟩``, con ``⟨x²⟩`` la varianza de la deflexión térmica
    (área del pico de resonancia) y ``χ`` el factor de forma de modo. Para el primer
    modo con detección por palanca óptica, ``χ ≈ 0.817`` (Butt & Jaschke 1995).

    Args:
        deflection_variance: ⟨x²⟩ en m² (estrictamente positivo).
        temperature: Temperatura en K.
        correction_factor: Factor de forma de modo ``χ`` (1.0 = equipartición cruda).

    Returns:
        Constante de resorte ``k`` en N/m.
    """
    # ponytail: comparte fórmula con mechanics.thermal_spring_constant; esa se aliará
    # a esta al migrar la nanomecánica al nuevo modelo (evitar dos fuentes de verdad).
    if deflection_variance <= 0:
        raise ValueError(
            f"deflection_variance debe ser estrictamente positivo, se recibió {deflection_variance}"
        )
    return correction_factor * _BOLTZMANN * temperature / deflection_variance


def spring_constant_sader(*_args: object, **_kwargs: object) -> float:
    """Método de Sader (geometría + f0 + Q). Aún no implementado.

    Requiere la función hidrodinámica compleja ``Γ(Re)``, cuya implementación
    correcta se difiere a una fase posterior; una versión aproximada daría física
    incorrecta. Usa :func:`spring_constant_thermal` mientras tanto.
    """
    raise NotImplementedError(
        "El método de Sader requiere la función hidrodinámica Γ(Re) (compleja); "
        "se implementará en una fase posterior. Usa spring_constant_thermal por ahora."
    )


def build_calibration(
    invols: float,
    spring_constant: float,
    method: str = "manual",
    temperature: float = 293.15,
    **provenance: object,
) -> Calibration:
    """Construye un :class:`Calibration` con trazabilidad de su origen."""
    return Calibration(
        invols=invols,
        spring_constant=spring_constant,
        method=method,
        temperature=temperature,
        provenance=dict(provenance),
    )
