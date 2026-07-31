"""Nivelación / corrección de fondo de imágenes SPM.

La topografía cruda suele venir con inclinación (tilt) del piezo o del
montaje de la muestra. Estas funciones la corrigen antes de calcular
rugosidad o perfiles.
"""

from __future__ import annotations

from typing import Literal

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


def _fit_selection(
    data: np.ndarray,
    *,
    mask: np.ndarray | None,
    mask_mode: Literal["ignore", "include", "exclude"],
    operation: str,
    minimum_points: int,
) -> np.ndarray:
    """Return pixels selected for a background fit."""
    allowed_modes = {"ignore", "include", "exclude"}

    if mask_mode not in allowed_modes:
        raise ValueError(f"{operation} mask_mode must be 'ignore', 'include', or 'exclude'")

    if mask_mode == "ignore":
        return np.ones(data.shape, dtype=bool)

    if mask is None:
        raise ValueError(f"{operation} requires a mask when mask_mode is " f"'{mask_mode}'")

    mask_data = np.asarray(mask)

    if mask_data.shape != data.shape:
        raise ValueError(f"{operation} requires mask shape to match channel data")

    if mask_data.dtype != np.bool_:
        raise TypeError(f"{operation} requires a boolean mask")

    selection = mask_data if mask_mode == "include" else ~mask_data

    if np.count_nonzero(selection) < minimum_points:
        raise ValueError(f"{operation} requires at least {minimum_points} selected points")

    return selection


def zero_mean(channel: SPMChannel) -> SPMChannel:
    """Shift the vertical reference so the arithmetic mean is zero."""
    data = _validated_data(channel, operation="zero_mean")
    mean_height = np.mean(data)
    return channel.with_data(data - mean_height)


def zero_minimum(channel: SPMChannel) -> SPMChannel:
    """Shift the vertical reference so the minimum height is zero."""
    data = _validated_data(channel, operation="zero_minimum")
    minimum_height = np.min(data)
    return channel.with_data(data - minimum_height)


def shift_vertical(channel: SPMChannel, *, offset: float) -> SPMChannel:
    """Add a finite scalar offset to every height value."""
    data = _validated_data(channel, operation="shift_vertical")
    offset_array = np.asarray(offset)

    if (
        offset_array.ndim != 0
        or not np.issubdtype(offset_array.dtype, np.number)
        or np.iscomplexobj(offset_array)
    ):
        raise TypeError("shift_vertical requires a real numeric scalar offset")

    offset_value = float(offset_array.item())

    if not np.isfinite(offset_value):
        raise ValueError("shift_vertical requires a finite offset")

    return channel.with_data(data + offset_value)


def plane_fit(
    channel: SPMChannel,
    *,
    mask: np.ndarray | None = None,
    mask_mode: Literal["ignore", "include", "exclude"] = "ignore",
) -> SPMChannel:
    """Subtract a least-squares plane from a two-dimensional channel."""
    data = _validated_data(channel, operation="plane_fit")
    selection = _fit_selection(
        data,
        mask=mask,
        mask_mode=mask_mode,
        operation="plane_fit",
        minimum_points=3,
    )

    rows, cols = data.shape
    yy, xx = np.mgrid[0:rows, 0:cols]

    design = np.column_stack(
        (
            xx.ravel(),
            yy.ravel(),
            np.ones(data.size),
        )
    )
    selected = selection.ravel()

    coefficients, _, rank, _ = np.linalg.lstsq(
        design[selected],
        data.ravel()[selected],
        rcond=None,
    )

    if rank < 3:
        raise ValueError("plane_fit selected points do not define a unique plane")

    plane = coefficients[0] * xx + coefficients[1] * yy + coefficients[2]

    return channel.with_data(data - plane)


def three_point_level(
    channel: SPMChannel,
    *,
    points: tuple[
        tuple[int, int],
        tuple[int, int],
        tuple[int, int],
    ],
) -> SPMChannel:
    """Subtract the plane defined by three non-collinear reference pixels."""
    data = _validated_data(channel, operation="three_point_level")
    point_data = np.asarray(points)

    if point_data.shape != (3, 2):
        raise ValueError("three_point_level requires exactly three (row, column) points")

    if not np.issubdtype(point_data.dtype, np.integer):
        raise TypeError("three_point_level requires integer pixel coordinates")

    point_rows = point_data[:, 0]
    point_columns = point_data[:, 1]

    rows, columns = data.shape
    out_of_bounds = (
        np.any(point_rows < 0)
        or np.any(point_rows >= rows)
        or np.any(point_columns < 0)
        or np.any(point_columns >= columns)
    )

    if out_of_bounds:
        raise ValueError("three_point_level requires points within channel bounds")

    design = np.column_stack(
        (
            point_columns.astype(float),
            point_rows.astype(float),
            np.ones(3),
        )
    )

    if np.linalg.matrix_rank(design) < 3:
        raise ValueError("three_point_level requires three non-collinear points")

    heights = data[point_rows, point_columns]
    coefficients = np.linalg.solve(design, heights)

    yy, xx = np.mgrid[0:rows, 0:columns]
    plane = coefficients[0] * xx + coefficients[1] * yy + coefficients[2]

    return channel.with_data(data - plane)


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
