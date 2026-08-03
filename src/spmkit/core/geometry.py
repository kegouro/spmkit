"""Physical geometry primitives for SPM image transformations.

Coordinates use physical pixel centres.  Lateral ranges are expressed in
metres, while channel heights can be converted from supported length units.
The module depends only on NumPy so geometric Core operations remain available
in the minimal SPMKit installation.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

FillMode = Literal["nearest", "constant"]


_LENGTH_SCALES_TO_METRES: dict[str, float] = {
    "m": 1.0,
    "metre": 1.0,
    "meter": 1.0,
    "mm": 1e-3,
    "millimetre": 1e-3,
    "millimeter": 1e-3,
    "µm": 1e-6,
    "um": 1e-6,
    "micrometre": 1e-6,
    "micrometer": 1e-6,
    "nm": 1e-9,
    "nanometre": 1e-9,
    "nanometer": 1e-9,
    "pm": 1e-12,
    "picometre": 1e-12,
    "picometer": 1e-12,
    "å": 1e-10,
    "ångström": 1e-10,
    "angstrom": 1e-10,
}


def _positive_finite_scalar(
    value: object,
    *,
    name: str,
    operation: str,
) -> float:
    """Validate a finite strictly positive real scalar."""
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


def _validated_shape(
    shape: object,
    *,
    operation: str,
) -> tuple[int, int]:
    """Validate a non-empty two-dimensional array shape."""
    if (
        not isinstance(shape, tuple)
        or len(shape) != 2
        or any(
            isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer))
            for value in shape
        )
    ):
        raise TypeError(f"{operation} requires shape to be a two-integer tuple")

    rows, columns = (int(shape[0]), int(shape[1]))

    if rows <= 0 or columns <= 0:
        raise ValueError(f"{operation} requires a non-empty two-dimensional shape")

    return rows, columns


def length_scale_to_metres(unit: str) -> float:
    """Return the multiplicative factor converting a length unit to metres."""
    if not isinstance(unit, str):
        raise TypeError("length_scale_to_metres requires unit to be a string")

    normalized = unit.strip().replace("μ", "µ").lower()

    try:
        return _LENGTH_SCALES_TO_METRES[normalized]
    except KeyError as exc:
        raise ValueError(f"unsupported geometric length unit: {unit!r}") from exc


def length_values_to_metres(
    values: np.ndarray,
    *,
    unit: str,
) -> np.ndarray:
    """Convert finite length values to metres."""
    data = np.asarray(values)

    if not np.issubdtype(data.dtype, np.number):
        raise TypeError("length_values_to_metres requires numeric values")

    if np.iscomplexobj(data):
        raise TypeError("length_values_to_metres requires real values")

    if not np.all(np.isfinite(data)):
        raise ValueError("length_values_to_metres requires finite values")

    return data.astype(float, copy=False) * length_scale_to_metres(unit)


def length_values_from_metres(
    values: np.ndarray,
    *,
    unit: str,
) -> np.ndarray:
    """Convert finite metre values to the requested length unit."""
    data = np.asarray(values, dtype=float)

    if not np.all(np.isfinite(data)):
        raise ValueError("length_values_from_metres requires finite values")

    return data / length_scale_to_metres(unit)


def pixel_center_axes(
    shape: tuple[int, int],
    *,
    x_range: float,
    y_range: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return centred physical X and Y pixel-centre coordinates in metres."""
    rows, columns = _validated_shape(
        shape,
        operation="pixel_center_axes",
    )
    physical_x_range = _positive_finite_scalar(
        x_range,
        name="x_range",
        operation="pixel_center_axes",
    )
    physical_y_range = _positive_finite_scalar(
        y_range,
        name="y_range",
        operation="pixel_center_axes",
    )

    x_step = physical_x_range / columns
    y_step = physical_y_range / rows

    x_coordinates = (np.arange(columns, dtype=float) + 0.5) * x_step - 0.5 * physical_x_range

    y_coordinates = (np.arange(rows, dtype=float) + 0.5) * y_step - 0.5 * physical_y_range

    return x_coordinates, y_coordinates


def physical_to_pixel_indices(
    x_coordinates: np.ndarray,
    y_coordinates: np.ndarray,
    *,
    shape: tuple[int, int],
    x_range: float,
    y_range: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Map centred physical coordinates to fractional pixel indices."""
    rows, columns = _validated_shape(
        shape,
        operation="physical_to_pixel_indices",
    )
    physical_x_range = _positive_finite_scalar(
        x_range,
        name="x_range",
        operation="physical_to_pixel_indices",
    )
    physical_y_range = _positive_finite_scalar(
        y_range,
        name="y_range",
        operation="physical_to_pixel_indices",
    )

    x_data, y_data = np.broadcast_arrays(
        np.asarray(x_coordinates, dtype=float),
        np.asarray(y_coordinates, dtype=float),
    )

    if not (np.all(np.isfinite(x_data)) and np.all(np.isfinite(y_data))):
        raise ValueError("physical_to_pixel_indices requires finite coordinates")

    x_step = physical_x_range / columns
    y_step = physical_y_range / rows

    x_indices = x_data / x_step + 0.5 * columns - 0.5
    y_indices = y_data / y_step + 0.5 * rows - 0.5

    return x_indices, y_indices


def bilinear_sample(
    data: np.ndarray,
    *,
    x_index: np.ndarray,
    y_index: np.ndarray,
    fill_mode: FillMode = "nearest",
    fill_value: float = 0.0,
) -> np.ndarray:
    """Sample a regular 2D grid at fractional pixel indices."""
    values = np.asarray(data)

    if values.ndim != 2 or values.size == 0:
        raise ValueError("bilinear_sample requires non-empty two-dimensional data")

    if not np.issubdtype(values.dtype, np.number) or np.iscomplexobj(values):
        raise TypeError("bilinear_sample requires real numeric data")

    if not np.all(np.isfinite(values)):
        raise ValueError("bilinear_sample requires finite data")

    if fill_mode not in {"nearest", "constant"}:
        raise ValueError("bilinear_sample fill_mode must be 'nearest' or 'constant'")

    x_data, y_data = np.broadcast_arrays(
        np.asarray(x_index, dtype=float),
        np.asarray(y_index, dtype=float),
    )

    if not (np.all(np.isfinite(x_data)) and np.all(np.isfinite(y_data))):
        raise ValueError("bilinear_sample requires finite sample coordinates")

    rows, columns = values.shape

    outside = (x_data < 0.0) | (x_data > columns - 1) | (y_data < 0.0) | (y_data > rows - 1)

    sampled_x = np.clip(x_data, 0.0, columns - 1)
    sampled_y = np.clip(y_data, 0.0, rows - 1)

    x0 = np.floor(sampled_x).astype(int)
    y0 = np.floor(sampled_y).astype(int)
    x1 = np.minimum(x0 + 1, columns - 1)
    y1 = np.minimum(y0 + 1, rows - 1)

    x_weight = sampled_x - x0
    y_weight = sampled_y - y0

    top = values[y0, x0] * (1.0 - x_weight) + values[y0, x1] * x_weight
    bottom = values[y1, x0] * (1.0 - x_weight) + values[y1, x1] * x_weight
    sampled = top * (1.0 - y_weight) + bottom * y_weight

    if fill_mode == "constant":
        fill = _positive_or_zero_finite_scalar(fill_value)
        sampled = np.where(outside, fill, sampled)

    return np.asarray(sampled, dtype=float)


def _positive_or_zero_finite_scalar(value: object) -> float:
    """Validate a finite real scalar used as a fill value."""
    scalar_data = np.asarray(value)

    if (
        scalar_data.ndim != 0
        or not np.issubdtype(scalar_data.dtype, np.number)
        or np.iscomplexobj(scalar_data)
        or isinstance(value, (bool, np.bool_))
    ):
        raise TypeError("bilinear_sample requires fill_value to be a real scalar")

    scalar = float(scalar_data.item())

    if not np.isfinite(scalar):
        raise ValueError("bilinear_sample requires fill_value to be finite")

    return scalar
