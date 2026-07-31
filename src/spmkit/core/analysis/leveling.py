"""Nivelación / corrección de fondo de imágenes SPM.

La topografía cruda suele venir con inclinación (tilt) del piezo o del
montaje de la muestra. Estas funciones la corrigen antes de calcular
rugosidad o perfiles.
"""

from __future__ import annotations

import numpy as np

from spmkit.core.models import SPMChannel


def _validated_data(channel: SPMChannel, *, operation: str) -> np.ndarray:
    """Return valid 2D, numeric, finite channel data."""
    data = np.asarray(channel.data)

    if data.ndim != 2:
        raise ValueError(f"{operation} requires a 2D channel")
    if data.size == 0:
        raise ValueError(f"{operation} requires non-empty data")
    if not np.issubdtype(data.dtype, np.number):
        raise TypeError(f"{operation} requires numeric data")
    if not np.all(np.isfinite(data)):
        raise ValueError(f"{operation} requires finite data")

    return data


def zero_mean(channel: SPMChannel) -> SPMChannel:
    """Shift the vertical reference so the arithmetic mean is zero."""
    data = _validated_data(channel, operation="zero_mean")
    mean_height = np.mean(data)
    return channel.with_data(data - mean_height)


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
