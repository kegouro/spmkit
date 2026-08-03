"""Nivelación / corrección de fondo de imágenes SPM.

La topografía cruda suele venir con inclinación (tilt) del piezo o del
montaje de la muestra. Estas funciones la corrigen antes de calcular
rugosidad o perfiles.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

from spmkit.core.analysis._gwyddion_path_level import _gwyddion_path_level_result
from spmkit.core.geometry import (
    bilinear_sample,
    length_values_from_metres,
    length_values_to_metres,
    physical_to_pixel_indices,
    pixel_center_axes,
)
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
        raise ValueError(f"{operation} requires a mask when mask_mode is '{mask_mode}'")

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


def _trim_fraction(value: object, *, operation: str) -> float:
    """Validate a trimming fraction in the closed interval [0, 0.5]."""
    fraction_data = np.asarray(value)

    if (
        fraction_data.ndim != 0
        or not np.issubdtype(fraction_data.dtype, np.number)
        or np.iscomplexobj(fraction_data)
        or isinstance(value, (bool, np.bool_))
    ):
        raise TypeError(f"{operation} requires trim_fraction to be a real scalar")

    fraction = float(fraction_data.item())

    if not np.isfinite(fraction):
        raise ValueError(f"{operation} requires trim_fraction to be finite")

    if fraction < 0.0 or fraction > 0.5:
        raise ValueError(f"{operation} requires trim_fraction between 0 and 0.5")

    return fraction


def _trimmed_mean(values: np.ndarray, fraction: float) -> float:
    """Return the symmetrically trimmed mean of one-dimensional values."""
    if fraction == 0.5:
        return float(np.median(values))

    ordered = np.sort(values)
    trim_count = int(np.floor(fraction * ordered.size))

    if trim_count == 0:
        return float(np.mean(ordered))

    return float(np.mean(ordered[trim_count:-trim_count]))


def _positive_integer(
    value: object,
    *,
    name: str,
    operation: str,
) -> int:
    """Validate and return a strictly positive integer."""
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value,
        (int, np.integer),
    ):
        raise TypeError(f"{operation} requires {name} to be a positive integer")

    integer_value = int(value)

    if integer_value <= 0:
        raise ValueError(f"{operation} requires {name} to be positive")

    return integer_value


def _positive_real_scalar(
    value: object,
    *,
    name: str,
    operation: str,
) -> float:
    """Validate and return a finite strictly positive real scalar."""
    scalar_data = np.asarray(value)

    if (
        scalar_data.ndim != 0
        or not np.issubdtype(scalar_data.dtype, np.number)
        or np.iscomplexobj(scalar_data)
        or isinstance(value, (bool, np.bool_))
    ):
        raise TypeError(f"{operation} requires {name} to be a positive real scalar")

    scalar = float(scalar_data.item())

    if not np.isfinite(scalar):
        raise ValueError(f"{operation} requires {name} to be finite")

    if scalar <= 0.0:
        raise ValueError(f"{operation} requires {name} to be positive")

    return scalar


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


def gwyddion_path_level(
    channel: SPMChannel,
    lines: object,
    *,
    thickness_px: object = 1,
) -> SPMChannel:
    """Apply the frozen Gwyddion 2.71 Path Level operation.

    ``lines`` is an ordered collection of straight physical-coordinate
    selections ``(x0, y0, x1, y1)``.  Duplicates and ordering are meaningful.
    ``thickness_px`` is an integer from 1 through 128, with default ``1``.
    The operation has fixed Gwyddion Path Level semantics: no interpolation,
    horizontal-line exclusion, and a cumulative row correction.  Finite,
    non-empty two-dimensional data and finite positive channel ranges are
    required.  The input channel is not mutated.

    Returns
    -------
    SPMChannel
        A corrected channel with the input context preserved.
    """
    result = _gwyddion_path_level_result(
        channel.data,
        lines,
        xreal=channel.x_range,
        yreal=channel.y_range,
        thickness_px=thickness_px,
    )
    return channel.with_data(result.corrected)


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


def _rotation_matrix_to_horizontal(
    x_slope: float,
    y_slope: float,
) -> np.ndarray:
    """Return the minimal 3D rotation mapping a plane normal to +Z."""
    normal = np.array(
        [-x_slope, -y_slope, 1.0],
        dtype=float,
    )
    normal /= np.linalg.norm(normal)

    target = np.array([0.0, 0.0, 1.0])
    cross = np.cross(normal, target)
    sine = float(np.linalg.norm(cross))
    cosine = float(np.dot(normal, target))

    if sine <= np.finfo(float).eps:
        return np.eye(3)

    cross_matrix = np.array(
        [
            [0.0, -cross[2], cross[1]],
            [cross[2], 0.0, -cross[0]],
            [-cross[1], cross[0], 0.0],
        ]
    )

    return np.eye(3) + cross_matrix + cross_matrix @ cross_matrix * ((1.0 - cosine) / sine**2)


def rotate_level(
    channel: SPMChannel,
    *,
    mask: np.ndarray | None = None,
    mask_mode: Literal["ignore", "include", "exclude"] = "ignore",
    interpolation: Literal["linear"] = "linear",
    fill_mode: Literal["nearest", "constant"] = "nearest",
    fill_value: float = 0.0,
    preserve_mean: bool = False,
) -> SPMChannel:
    """Flatten a fitted plane by approximate physical 3D image rotation.

    The fitted plane defines an inverse lateral mapping from the output grid
    to the source grid. Heights are interpolated in the source field and then
    rotated in physical XYZ coordinates. Shape and lateral ranges are kept.
    """
    data = _validated_data(
        channel,
        operation="rotate_level",
    )

    if interpolation != "linear":
        raise ValueError("rotate_level interpolation must be 'linear'")

    if fill_mode not in {"nearest", "constant"}:
        raise ValueError("rotate_level fill_mode must be 'nearest' or 'constant'")

    if not isinstance(preserve_mean, (bool, np.bool_)):
        raise TypeError("rotate_level requires preserve_mean to be boolean")

    fill_data = np.asarray(fill_value)

    if (
        fill_data.ndim != 0
        or not np.issubdtype(fill_data.dtype, np.number)
        or np.iscomplexobj(fill_data)
        or isinstance(fill_value, (bool, np.bool_))
    ):
        raise TypeError("rotate_level requires fill_value to be a real scalar")

    fill_scalar = float(fill_data.item())

    if not np.isfinite(fill_scalar):
        raise ValueError("rotate_level requires fill_value to be finite")

    data_metres = length_values_to_metres(
        data,
        unit=channel.unit,
    )
    fill_metres = float(
        length_values_to_metres(
            np.asarray(fill_scalar),
            unit=channel.unit,
        )
    )

    selection = _fit_selection(
        data,
        mask=mask,
        mask_mode=mask_mode,
        operation="rotate_level",
        minimum_points=3,
    )

    x_coordinates, y_coordinates = pixel_center_axes(
        data.shape,
        x_range=channel.x_range,
        y_range=channel.y_range,
    )
    xx, yy = np.meshgrid(
        x_coordinates,
        y_coordinates,
    )

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
        data_metres.ravel()[selected],
        rcond=None,
    )

    if rank < 3:
        raise ValueError("rotate_level selected points do not define a unique plane")

    x_slope = float(coefficients[0])
    y_slope = float(coefficients[1])
    intercept = float(coefficients[2])

    rotation = _rotation_matrix_to_horizontal(
        x_slope,
        y_slope,
    )

    output_plane_points = np.stack(
        (
            xx.ravel(),
            yy.ravel(),
            np.zeros(data.size),
        )
    )

    source_plane_points = rotation.T @ output_plane_points

    source_x = source_plane_points[0].reshape(data.shape)
    source_y = source_plane_points[1].reshape(data.shape)

    x_indices, y_indices = physical_to_pixel_indices(
        source_x,
        source_y,
        shape=data.shape,
        x_range=channel.x_range,
        y_range=channel.y_range,
    )

    rows, columns = data.shape

    outside = (
        (x_indices < 0.0) | (x_indices > columns - 1) | (y_indices < 0.0) | (y_indices > rows - 1)
    )

    sampled_x_indices = np.clip(
        x_indices,
        0.0,
        columns - 1,
    )
    sampled_y_indices = np.clip(
        y_indices,
        0.0,
        rows - 1,
    )

    sampled_heights = bilinear_sample(
        data_metres,
        x_index=sampled_x_indices,
        y_index=sampled_y_indices,
        fill_mode="nearest",
    )

    x_step = channel.x_range / columns
    y_step = channel.y_range / rows

    effective_source_x = (sampled_x_indices + 0.5 - 0.5 * columns) * x_step

    effective_source_y = (sampled_y_indices + 0.5 - 0.5 * rows) * y_step

    actual_source_points = np.stack(
        (
            effective_source_x.ravel(),
            effective_source_y.ravel(),
            (sampled_heights - intercept).ravel(),
        )
    )

    rotated_points = rotation @ actual_source_points
    rotated_height_metres = rotated_points[2].reshape(data.shape)

    if fill_mode == "constant":
        rotated_height_metres = np.where(
            outside,
            fill_metres,
            rotated_height_metres,
        )

    rotated_data = length_values_from_metres(
        rotated_height_metres,
        unit=channel.unit,
    )

    if preserve_mean:
        rotated_data = rotated_data + np.mean(data) - np.mean(rotated_data)

    return channel.with_data(rotated_data)


def _selected_local_facet_slopes(
    data: np.ndarray,
    selection: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return local x/y facet slopes for fully selected pixel cells."""
    rows, columns = data.shape

    if rows < 2 or columns < 2:
        raise ValueError("facet_level requires selected neighbouring pixel cells")

    selected_cells = (
        selection[:-1, :-1] & selection[:-1, 1:] & selection[1:, :-1] & selection[1:, 1:]
    )

    if not np.any(selected_cells):
        raise ValueError("facet_level requires selected neighbouring pixel cells")

    x_coordinates = np.linspace(-1.0, 1.0, columns)
    y_coordinates = np.linspace(-1.0, 1.0, rows)

    x_step = float(x_coordinates[1] - x_coordinates[0])
    y_step = float(y_coordinates[1] - y_coordinates[0])

    x_slopes = (data[:-1, 1:] - data[:-1, :-1] + data[1:, 1:] - data[1:, :-1]) / (2.0 * x_step)

    y_slopes = (data[1:, :-1] - data[:-1, :-1] + data[1:, 1:] - data[:-1, 1:]) / (2.0 * y_step)

    return (
        x_slopes[selected_cells],
        y_slopes[selected_cells],
    )


def _dominant_facet_slopes(
    x_slopes: np.ndarray,
    y_slopes: np.ndarray,
) -> tuple[float, float]:
    """Estimate the dominant local facet slope using Gaussian reweighting."""
    seed_x = _half_sample_mode(x_slopes)
    seed_y = _half_sample_mode(y_slopes)

    squared_distances = np.square(x_slopes - seed_x) + np.square(y_slopes - seed_y)

    epsilon = np.finfo(float).eps
    positive_distances = squared_distances[squared_distances > epsilon]

    if positive_distances.size == 0:
        return seed_x, seed_y

    scale = float(np.median(positive_distances))
    gaussian_constant = 1.0 / 20.0

    weights = np.exp(-0.5 * squared_distances / (gaussian_constant * scale))

    if float(np.sum(weights)) <= np.finfo(float).tiny:
        return seed_x, seed_y

    return (
        float(np.average(x_slopes, weights=weights)),
        float(np.average(y_slopes, weights=weights)),
    )


def facet_level(
    channel: SPMChannel,
    *,
    mask: np.ndarray | None = None,
    mask_mode: Literal["ignore", "include", "exclude"] = "ignore",
    max_iterations: int = 20,
    tolerance: float = 1e-12,
    preserve_mean: bool = False,
) -> SPMChannel:
    """Level a surface using the prevalent orientation of local facets."""
    data = _validated_data(
        channel,
        operation="facet_level",
    )

    iterations = _positive_integer(
        max_iterations,
        name="max_iterations",
        operation="facet_level",
    )
    convergence_tolerance = _positive_real_scalar(
        tolerance,
        name="tolerance",
        operation="facet_level",
    )

    if not isinstance(preserve_mean, (bool, np.bool_)):
        raise TypeError("facet_level requires preserve_mean to be boolean")

    selection = _fit_selection(
        data,
        mask=mask,
        mask_mode=mask_mode,
        operation="facet_level",
        minimum_points=4,
    )

    rows, columns = data.shape
    x_coordinates = np.linspace(-1.0, 1.0, columns)
    y_coordinates = np.linspace(-1.0, 1.0, rows)
    xx, yy = np.meshgrid(x_coordinates, y_coordinates)

    corrections = np.zeros(data.shape, dtype=float)
    working = data.astype(float, copy=True)

    for _ in range(iterations):
        x_slopes, y_slopes = _selected_local_facet_slopes(
            working,
            selection,
        )
        dominant_x, dominant_y = _dominant_facet_slopes(
            x_slopes,
            y_slopes,
        )

        if np.hypot(dominant_x, dominant_y) <= convergence_tolerance:
            break

        plane_tilt = dominant_x * xx + dominant_y * yy

        corrections += plane_tilt
        working -= plane_tilt

    if preserve_mean:
        corrections -= np.mean(corrections)
    else:
        corrections += float(np.mean(working[selection]))

    return channel.with_data(data - corrections)


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


def _fit_polynomial_surface_data(
    data: np.ndarray,
    *,
    powers: tuple[tuple[int, int], ...],
    selection: np.ndarray,
    operation: str,
) -> tuple[np.ndarray, np.ndarray, int, np.ndarray]:
    """Fit and evaluate polynomial terms on normalized pixel coordinates."""
    values = np.asarray(data, dtype=float)
    selected_points = np.asarray(selection, dtype=bool)

    if values.ndim != 2:
        raise ValueError(f"{operation} requires a two-dimensional array")
    if selected_points.shape != values.shape:
        raise ValueError(f"{operation} requires selection to match data shape")
    if not powers:
        raise ValueError(f"{operation} requires at least one polynomial term")

    selected_count = int(np.count_nonzero(selected_points))
    if selected_count < len(powers):
        raise ValueError(
            f"{operation} requires at least {len(powers)} selected points"
        )

    rows, columns = values.shape
    x_coordinates = (
        np.linspace(-1.0, 1.0, columns)
        if columns > 1
        else np.zeros(columns)
    )
    y_coordinates = (
        np.linspace(-1.0, 1.0, rows)
        if rows > 1
        else np.zeros(rows)
    )
    xx, yy = np.meshgrid(x_coordinates, y_coordinates)

    terms = [
        (xx**x_power) * (yy**y_power)
        for x_power, y_power in powers
    ]
    design = np.column_stack([term.ravel() for term in terms])
    selected = selected_points.ravel()

    coefficients, _, rank, singular_values = np.linalg.lstsq(
        design[selected],
        values.ravel()[selected],
        rcond=None,
    )

    if rank < len(powers):
        raise ValueError(
            f"{operation} selected points do not define "
            "a unique polynomial background"
        )

    background = (design @ coefficients).reshape(values.shape)

    return (
        background,
        coefficients,
        int(rank),
        singular_values,
    )


def _estimate_polynomial_background_data(
    channel: SPMChannel,
    *,
    degree_mode: Literal["total", "independent"] = "total",
    degree: int = 2,
    x_degree: int | None = None,
    y_degree: int | None = None,
    mask: np.ndarray | None = None,
    mask_mode: Literal["ignore", "include", "exclude"] = "ignore",
) -> np.ndarray:
    """Estimate a fitted two-dimensional polynomial background array."""
    data = _validated_data(
        channel,
        operation="polynomial_background",
    )

    if degree_mode not in {"total", "independent"}:
        raise ValueError("polynomial_background degree_mode must be 'total' or 'independent'")

    if degree_mode == "total":
        if x_degree is not None or y_degree is not None:
            raise ValueError(
                "polynomial_background total degree mode does not accept x_degree or y_degree"
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
                "polynomial_background independent degree mode requires x_degree and y_degree"
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

    background, _, _, _ = _fit_polynomial_surface_data(
        data,
        powers=tuple(powers),
        selection=selection,
        operation="polynomial_background",
    )

    return background


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
    background = _estimate_polynomial_background_data(
        channel,
        degree_mode=degree_mode,
        degree=degree,
        x_degree=x_degree,
        y_degree=y_degree,
        mask=mask,
        mask_mode=mask_mode,
    )
    data = np.asarray(channel.data, dtype=float)
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


def _half_sample_mode(values: np.ndarray) -> float:
    """Estimate the mode using the deterministic half-sample method."""
    ordered = np.sort(np.asarray(values, dtype=float))

    while True:
        count = ordered.size

        if count == 1:
            return float(ordered[0])

        if count == 2:
            return float(np.mean(ordered))

        if count == 3:
            left_width = ordered[1] - ordered[0]
            right_width = ordered[2] - ordered[1]

            if left_width < right_width:
                return float(np.mean(ordered[:2]))

            if right_width < left_width:
                return float(np.mean(ordered[1:]))

            return float(ordered[1])

        interval_size = (count + 1) // 2
        widths = ordered[interval_size - 1 :] - ordered[: count - interval_size + 1]
        start = int(np.argmin(widths))

        ordered = ordered[start : start + interval_size]


def _facet_tilt_row_corrections(
    data: np.ndarray,
    selection: np.ndarray,
) -> np.ndarray:
    """Estimate per-row tilt from the prevalent local slope."""
    row_count, column_count = data.shape

    if column_count < 2:
        raise ValueError("align_rows facet_tilt requires selected neighbouring pixels in every row")

    x_coordinates = np.linspace(
        -1.0,
        1.0,
        column_count,
    )
    x_coordinates = x_coordinates - np.mean(x_coordinates)
    x_steps = np.diff(x_coordinates)

    corrections = np.empty(data.shape, dtype=float)

    for row_index in range(row_count):
        selected_edges = selection[row_index, :-1] & selection[row_index, 1:]

        if not np.any(selected_edges):
            raise ValueError(
                "align_rows facet_tilt requires selected neighbouring pixels in every row"
            )

        local_slopes = np.diff(data[row_index]) / x_steps

        prevalent_slope = _half_sample_mode(local_slopes[selected_edges])

        corrections[row_index] = prevalent_slope * x_coordinates

    return corrections


def _without_linear_row_component(
    corrections: np.ndarray,
) -> np.ndarray:
    """Remove the least-squares linear component from row corrections."""
    row_count = corrections.size

    if row_count <= 1:
        return corrections.copy()

    row_coordinates = np.arange(row_count, dtype=float)
    centered_rows = row_coordinates - np.mean(row_coordinates)
    centered_corrections = corrections - np.mean(corrections)

    denominator = float(np.dot(centered_rows, centered_rows))

    if denominator == 0.0:
        return corrections.copy()

    correction_slope = float(np.dot(centered_rows, centered_corrections) / denominator)

    return corrections - correction_slope * centered_rows


def _matching_row_corrections(
    data: np.ndarray,
    selection: np.ndarray,
    *,
    preserve_tilt: bool,
) -> np.ndarray:
    """Estimate row offsets by matching locally flat neighbouring segments."""
    row_count = data.shape[0]
    corrections = np.zeros(row_count, dtype=float)

    for row_index in range(1, row_count):
        shared_selection = selection[row_index - 1] & selection[row_index]
        shared_edges = shared_selection[:-1] & shared_selection[1:]

        if not np.any(shared_edges):
            raise ValueError(
                "align_rows matching requires adjacent rows to share selected neighbouring pixels"
            )

        previous_row = data[row_index - 1]
        current_row = data[row_index]

        vertical_differences = 0.5 * (
            current_row[:-1] - previous_row[:-1] + current_row[1:] - previous_row[1:]
        )

        previous_slopes = np.diff(previous_row)
        current_slopes = np.diff(current_row)

        local_flatness = np.abs(previous_slopes) + np.abs(current_slopes)
        selected_flatness = local_flatness[shared_edges]

        scale = float(np.median(selected_flatness))
        epsilon = np.finfo(float).eps

        if scale <= epsilon:
            positive_flatness = selected_flatness[selected_flatness > epsilon]
            scale = float(np.median(positive_flatness)) if positive_flatness.size else 1.0

        normalized_flatness = selected_flatness / scale
        weights = 1.0 / np.square(np.hypot(1.0, normalized_flatness))

        increment = float(
            np.average(
                vertical_differences[shared_edges],
                weights=weights,
            )
        )

        corrections[row_index] = corrections[row_index - 1] + increment

    if preserve_tilt:
        corrections = _without_linear_row_component(corrections)

    return corrections


def _difference_row_corrections(
    data: np.ndarray,
    selection: np.ndarray,
    *,
    statistic: Literal["median", "trimmed_mean"],
    trim_fraction: float,
    preserve_tilt: bool,
) -> np.ndarray:
    """Estimate cumulative row offsets from vertical neighbour differences."""

    row_count = data.shape[0]

    corrections = np.zeros(row_count, dtype=float)

    for row_index in range(1, row_count):
        shared_selection = selection[row_index - 1] & selection[row_index]

        if not np.any(shared_selection):
            raise ValueError("align_rows requires adjacent rows to share selected points")

        differences = data[row_index, shared_selection] - data[row_index - 1, shared_selection]

        if statistic == "median":
            increment = float(np.median(differences))

        else:
            increment = _trimmed_mean(
                differences,
                trim_fraction,
            )

        corrections[row_index] = corrections[row_index - 1] + increment

    if preserve_tilt:
        corrections = _without_linear_row_component(corrections)

    return corrections


def align_rows(
    channel: SPMChannel,
    method: Literal[
        "median",
        "mean",
        "mode",
        "trimmed_mean",
        "polynomial",
        "median_difference",
        "trimmed_mean_difference",
        "matching",
        "facet_tilt",
    ] = "median",
    *,
    trim_fraction: float = 0.0,
    polynomial_degree: int = 1,
    mask: np.ndarray | None = None,
    mask_mode: Literal["ignore", "include", "exclude"] = "ignore",
    preserve_mean: bool = False,
    preserve_tilt: bool = True,
) -> SPMChannel:
    """Align rows by subtracting a fitted or representative row background.

    ``preserve_mean=False`` retains the historical SPMKit behaviour.
    ``preserve_mean=True`` keeps the mean correction at zero, matching
    the absolute-level convention used by Gwyddion.
    """
    data = _validated_data(channel, operation="align_rows")

    allowed_methods = {
        "median",
        "mean",
        "mode",
        "trimmed_mean",
        "polynomial",
        "median_difference",
        "trimmed_mean_difference",
        "matching",
        "facet_tilt",
    }

    if method not in allowed_methods:
        raise ValueError(
            "align_rows method must be 'median', 'mean', 'mode', "
            "'trimmed_mean', 'polynomial', 'median_difference', "
            "'trimmed_mean_difference', 'matching', or 'facet_tilt'"
        )

    if not isinstance(preserve_mean, (bool, np.bool_)):
        raise TypeError("align_rows requires preserve_mean to be boolean")

    if not isinstance(preserve_tilt, (bool, np.bool_)):
        raise TypeError("align_rows requires preserve_tilt to be boolean")

    fraction = _trim_fraction(
        trim_fraction,
        operation="align_rows",
    )

    selection = _fit_selection(
        data,
        mask=mask,
        mask_mode=mask_mode,
        operation="align_rows",
        minimum_points=1,
    )

    if method == "polynomial":
        degree = _nonnegative_integer(
            polynomial_degree,
            name="polynomial_degree",
            operation="align_rows",
        )
        required_points = degree + 1
    else:
        degree = 0
        required_points = 1

    selected_per_row = np.count_nonzero(selection, axis=1)

    if np.any(selected_per_row < required_points):
        point_word = "point" if required_points == 1 else "points"
        raise ValueError(
            f"align_rows requires at least {required_points} selected {point_word} in every row"
        )

    difference_methods = {
        "median_difference",
        "trimmed_mean_difference",
    }

    if method == "facet_tilt":
        corrections = _facet_tilt_row_corrections(
            data,
            selection,
        )

    elif method == "matching":
        row_corrections = _matching_row_corrections(
            data,
            selection,
            preserve_tilt=bool(preserve_tilt),
        )
        corrections = row_corrections[:, np.newaxis]

    elif method in difference_methods:
        statistic: Literal["median", "trimmed_mean"] = (
            "median" if method == "median_difference" else "trimmed_mean"
        )

        row_corrections = _difference_row_corrections(
            data,
            selection,
            statistic=statistic,
            trim_fraction=fraction,
            preserve_tilt=bool(preserve_tilt),
        )
        corrections = row_corrections[:, np.newaxis]

    elif method == "polynomial":
        columns = data.shape[1]
        x_coordinates = np.linspace(-1.0, 1.0, columns) if columns > 1 else np.zeros(columns)

        design = np.vander(
            x_coordinates,
            N=degree + 1,
            increasing=True,
        )

        corrections = np.empty(data.shape, dtype=float)

        for row_index in range(data.shape[0]):
            selected = selection[row_index]

            coefficients, _, rank, _ = np.linalg.lstsq(
                design[selected],
                data[row_index, selected],
                rcond=None,
            )

            if rank < degree + 1:
                raise ValueError(
                    "align_rows selected points do not define a unique polynomial in every row"
                )

            corrections[row_index] = design @ coefficients

    else:
        baselines = np.empty(data.shape[0], dtype=float)

        for row_index in range(data.shape[0]):
            row_values = data[row_index, selection[row_index]]

            if method == "median":
                baselines[row_index] = np.median(row_values)
            elif method == "mean":
                baselines[row_index] = np.mean(row_values)
            elif method == "mode":
                baselines[row_index] = _half_sample_mode(row_values)
            else:
                baselines[row_index] = _trimmed_mean(
                    row_values,
                    fraction,
                )

        corrections = baselines[:, np.newaxis]

    if preserve_mean:
        corrections = corrections - np.mean(corrections)

    return channel.with_data(data - corrections)
