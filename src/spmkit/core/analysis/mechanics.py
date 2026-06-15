"""Análisis de nanomecánica a partir de curvas fuerza-distancia.

.. warning::
   Esqueleto inicial. La extracción de curvas fuerza-distancia desde los
   modos *nanomech* de NanoSurf aún no está implementada; estas funciones
   definen la API y el modelo de resultado para construir sobre ellos.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class IndentationResult:
    """Resultado del ajuste de una curva fuerza-indentación."""

    young_modulus: float
    adhesion: float
    contact_point: float
    model: str
    unit_modulus: str = "Pa"

    def to_dict(self) -> dict:
        return asdict(self)


def young_modulus_hertz(
    indentation: np.ndarray,
    force: np.ndarray,
    tip_radius: float,
    poisson: float = 0.3,
) -> IndentationResult:
    """Ajusta el modelo de Hertz (punta esférica) a una curva fuerza-indentación.

    Modelo de Hertz para indentador esférico::

        F = (4/3) * (E / (1 - nu^2)) * sqrt(R) * delta^(3/2)

    Args:
        indentation: Indentación ``delta`` (m), solo región de contacto (>= 0).
        force: Fuerza (N) correspondiente.
        tip_radius: Radio de la punta ``R`` (m).
        poisson: Coeficiente de Poisson de la muestra.

    Returns:
        :class:`IndentationResult` con el módulo de Young estimado.
    """
    delta = np.asarray(indentation, dtype=np.float64)
    f = np.asarray(force, dtype=np.float64)
    mask = delta > 0
    delta, f = delta[mask], f[mask]
    if delta.size < 3:
        raise ValueError("Se requieren al menos 3 puntos en contacto (delta > 0)")

    # F = k * delta^1.5  =>  k = (4/3) * E* * sqrt(R), con E* = E/(1-nu^2)
    basis = delta**1.5
    k = float(np.sum(basis * f) / np.sum(basis**2))
    e_star = k / ((4.0 / 3.0) * np.sqrt(tip_radius))
    young = e_star * (1.0 - poisson**2)

    return IndentationResult(
        young_modulus=young,
        adhesion=float(-f.min()) if f.min() < 0 else 0.0,
        contact_point=0.0,
        model="hertz_sphere",
    )
