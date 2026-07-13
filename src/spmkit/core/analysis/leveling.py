"""Nivelación / corrección de fondo de imágenes SPM.

La topografía cruda suele venir con inclinación (tilt) del piezo o del
montaje de la muestra. Estas funciones la corrigen antes de calcular
rugosidad o perfiles.
"""

from __future__ import annotations

import numpy as np

from spmkit.core.models import SPMChannel


def _image_data(channel: SPMChannel) -> np.ndarray:
    z = np.asarray(channel.data, dtype=np.float64)
    if z.ndim != 2 or z.shape[0] < 2 or z.shape[1] < 2:
        raise ValueError("Se requiere una imagen 2D de al menos 2x2")
    return z


def _fit_coefficients(a_mat: np.ndarray, z: np.ndarray) -> np.ndarray:
    finite = np.isfinite(z).ravel()
    fit_matrix = a_mat[finite]
    if fit_matrix.shape[0] < a_mat.shape[1]:
        raise ValueError("Puntos finitos insuficientes para el ajuste")
    if np.linalg.matrix_rank(fit_matrix) < a_mat.shape[1]:
        raise ValueError("Rango insuficiente de puntos finitos para el ajuste")
    coeffs, *_ = np.linalg.lstsq(fit_matrix, z.ravel()[finite], rcond=None)
    return coeffs


def plane_fit(channel: SPMChannel) -> SPMChannel:
    """Resta un plano de mínimos cuadrados ``z = a*x + b*y + c``.

    Es la corrección de inclinación más común para topografía AFM.
    """
    z = _image_data(channel)
    rows, cols = z.shape
    yy, xx = np.mgrid[0:rows, 0:cols]
    a_mat = np.column_stack([xx.ravel(), yy.ravel(), np.ones(z.size)])
    coeffs = _fit_coefficients(a_mat, z)
    plane = (a_mat @ coeffs).reshape(z.shape)
    return channel.with_data(z - plane)


def polynomial(channel: SPMChannel, order: int = 2) -> SPMChannel:
    """Resta una superficie polinómica 2D de grado ``order``.

    Útil cuando hay curvatura (bow) además de inclinación.
    """
    if order < 1:
        raise ValueError("order debe ser >= 1")
    z = _image_data(channel)
    rows, cols = z.shape
    y_axis = np.linspace(-1.0, 1.0, rows)
    x_axis = np.linspace(-1.0, 1.0, cols)
    yy, xx = np.meshgrid(y_axis, x_axis, indexing="ij")
    x = xx.ravel()
    y = yy.ravel()
    terms = [(x**i) * (y**j) for i in range(order + 1) for j in range(order + 1 - i)]
    a_mat = np.column_stack(terms)
    coeffs = _fit_coefficients(a_mat, z)
    surface = (a_mat @ coeffs).reshape(z.shape)
    return channel.with_data(z - surface)


def align_rows(channel: SPMChannel, method: str = "median") -> SPMChannel:
    """Alinea filas restando su estadístico (corrige saltos línea a línea).

    Args:
        method: ``"median"`` (robusto) o ``"mean"``.
    """
    if method not in {"median", "mean"}:
        raise ValueError("method debe ser 'median' o 'mean'")
    leveled = np.asarray(channel.data, dtype=np.float64).copy()
    for row in leveled:
        finite = np.isfinite(row)
        if not finite.any():
            continue
        baseline = np.median(row[finite]) if method == "median" else np.mean(row[finite])
        row[finite] -= baseline
    return channel.with_data(leveled)
