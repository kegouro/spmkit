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


def _nonnegative_integer(
    value: object,
    *,
    name: str,
    operation: str,
) -> int:
    """Validate and return a non-negative integer parameter."""
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value,
        (int, np.integer),
    ):
        raise TypeError(f"{operation} requires {name} to be a non-negative integer")

    integer_value = int(value)

    if integer_value < 0:
        raise ValueError(f"{operation} requires {name} to be non-negative")

    return integer_value


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


def polynomial_background(
    channel: SPMChannel,
    *,
    degree_mode: Literal["total", "independent"] = "total",
    degree: int = 2,
    x_degree: int | None = None,
    y_degree: int | None = None,
    mask: np.ndarray | None = None,
    mask_mode: Literal["ignore", "include", "exclude"] = "ignore",
) -> SPMChannel:
    """Subtract a fitted two-dimensional polynomial background."""
    data = _validated_data(
        channel,
        operation="polynomial_background",
    )

    if degree_mode not in {"total", "independent"}:
        raise ValueError("polynomial_background degree_mode must be " "'total' or 'independent'")

    if degree_mode == "total":
        if x_degree is not None or y_degree is not None:
            raise ValueError(
                "polynomial_background total degree mode does not accept " "x_degree or y_degree"
            )

        total_degree = _nonnegative_integer(
            degree,
            name="degree",
            operation="polynomial_background",
        )
        powers = [
            (x_power, y_power)
            for x_power in range(total_degree + 1)
            for y_power in range(total_degree + 1 - x_power)
        ]

    else:
        if x_degree is None or y_degree is None:
            raise ValueError(
                "polynomial_background independent degree mode requires " "x_degree and y_degree"
            )

        horizontal_degree = _nonnegative_integer(
            x_degree,
            name="x_degree",
            operation="polynomial_background",
        )
        vertical_degree = _nonnegative_integer(
            y_degree,
            name="y_degree",
            operation="polynomial_background",
        )

        powers = [
            (x_power, y_power)
            for x_power in range(horizontal_degree + 1)
            for y_power in range(vertical_degree + 1)
        ]

    selection = _fit_selection(
        data,
        mask=mask,
        mask_mode=mask_mode,
        operation="polynomial_background",
        minimum_points=len(powers),
    )

    rows, columns = data.shape

    x_coordinates = np.linspace(-1.0, 1.0, columns) if columns > 1 else np.zeros(columns)
    y_coordinates = np.linspace(-1.0, 1.0, rows) if rows > 1 else np.zeros(rows)
    xx, yy = np.meshgrid(x_coordinates, y_coordinates)

    terms = [(xx**x_power) * (yy**y_power) for x_power, y_power in powers]
    design = np.column_stack([term.ravel() for term in terms])
    selected = selection.ravel()

    coefficients, _, rank, _ = np.linalg.lstsq(
        design[selected],
        data.ravel()[selected],
        rcond=None,
    )

    if rank < len(powers):
        raise ValueError(
            "polynomial_background selected points do not define " "a unique polynomial background"
        )

    background = (design @ coefficients).reshape(data.shape)
    return channel.with_data(data - background)


def polynomial(channel: SPMChannel, order: int = 2) -> SPMChannel:
    """Subtract a limited-total-degree polynomial background.

    This function preserves the original SPMKit API. New code should use
    :func:`polynomial_background`.
    """
    if isinstance(order, (bool, np.bool_)) or not isinstance(
        order,
        (int, np.integer),
    ):
        raise TypeError("order debe ser un entero")

    if order < 1:
        raise ValueError("order debe ser >= 1")

    return polynomial_background(
        channel,
        degree_mode="total",
        degree=int(order),
    )


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
