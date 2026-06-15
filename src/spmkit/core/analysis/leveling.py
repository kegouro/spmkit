"""Nivelación / corrección de fondo de imágenes SPM.

La topografía cruda suele venir con inclinación (tilt) del piezo o del
montaje de la muestra. Estas funciones la corrigen antes de calcular
rugosidad o perfiles.
"""

from __future__ import annotations

import numpy as np

from spmkit.core.models import SPMChannel


def plane_fit(channel: SPMChannel) -> SPMChannel:
    """Resta un plano de mínimos cuadrados ``z = a*x + b*y + c``.

    Es la corrección de inclinación más común para topografía AFM.
    """
    z = channel.data
    rows, cols = z.shape
    yy, xx = np.mgrid[0:rows, 0:cols]
    a_mat = np.column_stack([xx.ravel(), yy.ravel(), np.ones(z.size)])
    coeffs, *_ = np.linalg.lstsq(a_mat, z.ravel(), rcond=None)
    plane = (a_mat @ coeffs).reshape(z.shape)
    return channel.with_data(z - plane)


def polynomial(channel: SPMChannel, order: int = 2) -> SPMChannel:
    """Resta una superficie polinómica 2D de grado ``order``.

    Útil cuando hay curvatura (bow) además de inclinación.
    """
    if order < 1:
        raise ValueError("order debe ser >= 1")
    z = channel.data
    rows, cols = z.shape
    yy, xx = np.mgrid[0:rows, 0:cols]
    x = xx.ravel().astype(np.float64)
    y = yy.ravel().astype(np.float64)
    terms = [(x**i) * (y**j) for i in range(order + 1) for j in range(order + 1 - i)]
    a_mat = np.column_stack(terms)
    coeffs, *_ = np.linalg.lstsq(a_mat, z.ravel(), rcond=None)
    surface = (a_mat @ coeffs).reshape(z.shape)
    return channel.with_data(z - surface)


def align_rows(channel: SPMChannel, method: str = "median") -> SPMChannel:
    """Alinea filas restando su estadístico (corrige saltos línea a línea).

    Args:
        method: ``"median"`` (robusto) o ``"mean"``.
    """
    z = channel.data
    if method == "median":
        baseline = np.median(z, axis=1, keepdims=True)
    elif method == "mean":
        baseline = np.mean(z, axis=1, keepdims=True)
    else:
        raise ValueError("method debe ser 'median' o 'mean'")
    return channel.with_data(z - baseline)
