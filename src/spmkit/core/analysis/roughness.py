"""Parámetros de rugosidad superficial (ISO 25178 areal y ISO 4287 de perfil).

Las funciones esperan datos **ya nivelados** (ver :mod:`spmkit.core.analysis.leveling`).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from spmkit.core.models import SPMChannel


@dataclass(frozen=True)
class RoughnessResult:
    """Parámetros de rugosidad areal (ISO 25178).

    Attributes:
        Sa: Altura media aritmética (media de |z|).
        Sq: Altura media cuadrática (RMS).
        Sz: Altura máxima (pico-valle): ``Sp + |Sv|``.
        Sp: Altura máxima de pico.
        Sv: Profundidad máxima de valle.
        Ssk: Asimetría (skewness) de la distribución de alturas.
        Sku: Curtosis (kurtosis) de la distribución de alturas.
        unit: Unidad de las magnitudes de altura.
        n_points: Número de puntos usados.
    """

    Sa: float
    Sq: float
    Sz: float
    Sp: float
    Sv: float
    Ssk: float
    Sku: float
    unit: str
    n_points: int

    def to_dict(self) -> dict:
        return asdict(self)


def statistics(channel: SPMChannel) -> RoughnessResult:
    """Calcula los parámetros de rugosidad areal de un canal nivelado."""
    z = np.asarray(channel.data, dtype=np.float64)
    flat = z.ravel()
    flat = flat[np.isfinite(flat)]
    mean = flat.mean()
    dev = flat - mean

    sq = float(np.sqrt(np.mean(dev**2)))
    sa = float(np.mean(np.abs(dev)))
    sp = float(dev.max())
    sv = float(dev.min())
    sz = float(sp - sv)
    # Momentos normalizados (con guardia para superficie plana)
    if sq > 0:
        ssk = float(np.mean(dev**3) / sq**3)
        sku = float(np.mean(dev**4) / sq**4)
    else:
        ssk = 0.0
        sku = 0.0

    return RoughnessResult(
        Sa=sa,
        Sq=sq,
        Sz=sz,
        Sp=sp,
        Sv=sv,
        Ssk=ssk,
        Sku=sku,
        unit=channel.unit,
        n_points=int(flat.size),
    )
