"""Análisis KPFM: potencial de contacto (CPD) y función de trabajo.

En KPFM se mide la diferencia de potencial de contacto (CPD, *Contact
Potential Difference*) entre la punta y la muestra::

    V_CPD = (phi_tip - phi_sample) / e

de donde la función de trabajo de la muestra es::

    phi_sample = phi_tip - e * V_CPD

Si se trabaja en eV y V_CPD en voltios, ``e * V_CPD`` (en eV) es
numéricamente igual a ``V_CPD`` (en V).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from spmkit.core.models import SPMChannel


@dataclass(frozen=True)
class CPDResult:
    """Estadísticas del canal de potencial de contacto (CPD)."""

    mean: float
    std: float
    minimum: float
    maximum: float
    contrast: float
    unit: str
    work_function: float | None = None
    work_function_unit: str = "eV"

    def to_dict(self) -> dict:
        return asdict(self)


def statistics(channel: SPMChannel, tip_work_function: float | None = None) -> CPDResult:
    """Estadísticas del canal CPD y, si se da ``tip_work_function``, la phi de la muestra.

    Args:
        channel: Canal de CPD/potencial (unidad típica ``V``).
        tip_work_function: Función de trabajo de la punta en eV. Si se entrega,
            se calcula ``phi_sample = phi_tip - V_CPD_medio``.
    """
    if channel.unit.casefold() != "v":
        raise ValueError("El canal KPFM debe estar expresado en voltios SI (V)")
    if tip_work_function is not None and (
        not np.isfinite(tip_work_function) or tip_work_function <= 0
    ):
        raise ValueError("tip_work_function debe ser finita y estrictamente positiva")
    v = np.asarray(channel.data, dtype=np.float64).ravel()
    v = v[np.isfinite(v)]
    if v.size == 0:
        raise ValueError("Canal KPFM sin datos finitos")
    mean = float(v.mean())
    work_function = None
    if tip_work_function is not None:
        work_function = float(tip_work_function - mean)

    return CPDResult(
        mean=mean,
        std=float(v.std()),
        minimum=float(v.min()),
        maximum=float(v.max()),
        contrast=float(v.max() - v.min()),
        unit=channel.unit,
        work_function=work_function,
    )
