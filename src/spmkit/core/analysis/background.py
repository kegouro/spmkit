"""Physical background estimation for SPM images.

This module contains local, physically dimensioned background estimators.
All lateral ranges and algorithm radii are expressed in metres. Channel
height values are converted to metres internally and returned in their
original geometric unit.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from scipy.ndimage import grey_opening

from spmkit.core.geometry import (
    length_values_from_metres,
    length_values_to_metres,
)
from spmkit.core.models import SPMChannel

ArcDirection = Literal["horizontal", "vertical", "both"]
ArcSide = Literal["below", "above"]
ArcBorder = Literal["nearest", "reflect"]


def _validated_channel_data(
    channel: SPMChannel,
    *,
    operation: str,
) -> np.ndarray:
    """Return valid, finite, real, two-dimensional channel data."""
    data = np.asarray(channel.data)

    if data.ndim != 2:
        raise ValueError(f"{operation} requires a 2D channel")

    if data.size == 0:
        raise ValueError(f"{operation} requires non-empty data")

    if not np.issubdtype(data.dtype, np.number) or np.iscomplexobj(data):
        raise TypeError(f"{operation} requires real numeric data")

    if not np.all(np.isfinite(data)):
        raise ValueError(f"{operation} requires finite data")

    return data


def _positive_radius(
    radius: object,
    *,
    operation: str,
) -> float:
    """Validate a physical radius expressed in metres."""
    radius_data = np.asarray(radius)

    if (
        radius_data.ndim != 0
        or not np.issubdtype(radius_data.dtype, np.number)
        or np.iscomplexobj(radius_data)
        or isinstance(radius, (bool, np.bool_))
    ):
        raise TypeError(f"{operation} requires radius to be a positive real scalar")

    value = float(radius_data.item())

    if not np.isfinite(value):
        raise ValueError(f"{operation} requires radius to be finite")

    if value <= 0.0:
        raise ValueError(f"{operation} requires radius to be positive")

    return value


def _validated_choice(
    value: str,
    *,
    name: str,
    allowed: tuple[str, ...],
    operation: str,
) -> str:
    """Validate a string-valued public option."""
    if value not in allowed:
        choices = ", ".join(repr(item) for item in allowed)
        raise ValueError(f"{operation} {name} must be one of {choices}")

    return value


def _axis_spacing(
    channel: SPMChannel,
    *,
    axis: int,
    operation: str,
) -> float:
    """Return the canonical physical pixel spacing for one image axis."""
    spacing = channel.pixel_size_x if axis == 1 else channel.pixel_size_y
    spacing_data = np.asarray(spacing)

    if (
        spacing_data.ndim != 0
        or not np.issubdtype(spacing_data.dtype, np.number)
        or np.iscomplexobj(spacing_data)
    ):
        raise TypeError(f"{operation} requires real numeric lateral pixel spacing")

    spacing_value = float(spacing_data.item())

    if not np.isfinite(spacing_value):
        raise ValueError(f"{operation} requires finite lateral pixel spacing")

    if spacing_value <= 0.0:
        raise ValueError(f"{operation} requires positive lateral pixel spacing")

    return spacing_value


def _arc_structure(
    *,
    radius: float,
    spacing: float,
    sample_count: int,
) -> np.ndarray:
    """Return the non-flat structure for an arc rolling below a profile."""
    if sample_count <= 1:
        return np.array([0.0])

    maximum_supported_offset = sample_count - 1
    radius_in_pixels = radius / spacing

    if not np.isfinite(radius_in_pixels) or radius_in_pixels >= maximum_supported_offset:
        maximum_offset = maximum_supported_offset
    else:
        maximum_offset = int(np.floor(radius_in_pixels))

    if maximum_offset == 0:
        return np.array([0.0])

    offsets = np.arange(
        -maximum_offset,
        maximum_offset + 1,
        dtype=float,
    )
    distances = offsets * spacing
    normalized_distance = distances / radius
    squared_ratio = np.square(normalized_distance)

    root = np.sqrt(
        np.maximum(
            1.0 - squared_ratio,
            0.0,
        )
    )

    # Algebraically equivalent to
    # radius - sqrt(radius**2 - distance**2), but numerically stable when
    # radius is much larger than the lateral pixel spacing.
    sagitta = radius * squared_ratio / (1.0 + root)

    # SciPy grey erosion subtracts the structure and grey dilation adds it.
    # A negative sagitta represents the upper arc of a circle rolling beneath
    # the measured surface.
    return -sagitta


def _opening_along_axis(
    data: np.ndarray,
    *,
    radius: float,
    spacing: float,
    axis: int,
    border: ArcBorder,
) -> np.ndarray:
    """Apply one separable physical arc-opening stage."""
    sample_count = data.shape[axis]
    structure_1d = _arc_structure(
        radius=radius,
        spacing=spacing,
        sample_count=sample_count,
    )

    if structure_1d.size == 1:
        return data.copy()

    structure = structure_1d[np.newaxis, :] if axis == 1 else structure_1d[:, np.newaxis]

    return np.asarray(
        grey_opening(
            data,
            structure=structure,
            mode=border,
        ),
        dtype=float,
    )


def _estimate_below_metres(
    data_metres: np.ndarray,
    channel: SPMChannel,
    *,
    radius: float,
    direction: ArcDirection,
    border: ArcBorder,
    operation: str,
) -> np.ndarray:
    """Estimate the sequential arc envelope below the surface."""
    x_spacing = _axis_spacing(
        channel,
        axis=1,
        operation=operation,
    )
    y_spacing = _axis_spacing(
        channel,
        axis=0,
        operation=operation,
    )

    if direction == "horizontal":
        return _opening_along_axis(
            data_metres,
            radius=radius,
            spacing=x_spacing,
            axis=1,
            border=border,
        )

    if direction == "vertical":
        return _opening_along_axis(
            data_metres,
            radius=radius,
            spacing=y_spacing,
            axis=0,
            border=border,
        )

    horizontal = _opening_along_axis(
        data_metres,
        radius=radius,
        spacing=x_spacing,
        axis=1,
        border=border,
    )

    return _opening_along_axis(
        horizontal,
        radius=radius,
        spacing=y_spacing,
        axis=0,
        border=border,
    )


def estimate_arc_revolution_background(
    channel: SPMChannel,
    radius: float,
    *,
    direction: ArcDirection = "both",
    side: ArcSide = "below",
    border: ArcBorder = "nearest",
) -> SPMChannel:
    """Estimate a physical arc-revolution background.

    Parameters
    ----------
    channel:
        Two-dimensional channel whose Z unit must be a geometric length.
    radius:
        Physical arc radius in metres.
    direction:
        ``"horizontal"`` processes rows, ``"vertical"`` processes columns,
        and ``"both"`` applies horizontal followed by vertical.
    side:
        ``"below"`` rolls the arc beneath the surface. ``"above"`` is the
        exact dual obtained by inversion.
    border:
        SciPy boundary mode. Only ``"nearest"`` and ``"reflect"`` are
        supported.

    Notes
    -----
    Non-finite data and masks are not supported. A radius smaller than the
    relevant pixel spacing produces a one-element structure and therefore
    leaves that stage unchanged.
    """
    operation = "estimate_arc_revolution_background"

    data = _validated_channel_data(
        channel,
        operation=operation,
    )
    radius_value = _positive_radius(
        radius,
        operation=operation,
    )

    direction_value = _validated_choice(
        direction,
        name="direction",
        allowed=("horizontal", "vertical", "both"),
        operation=operation,
    )
    side_value = _validated_choice(
        side,
        name="side",
        allowed=("below", "above"),
        operation=operation,
    )
    border_value = _validated_choice(
        border,
        name="border",
        allowed=("nearest", "reflect"),
        operation=operation,
    )

    data_metres = length_values_to_metres(
        data,
        unit=channel.unit,
    )

    if side_value == "below":
        background_metres = _estimate_below_metres(
            data_metres,
            channel,
            radius=radius_value,
            direction=direction_value,
            border=border_value,
            operation=operation,
        )
    else:
        background_metres = -_estimate_below_metres(
            -data_metres,
            channel,
            radius=radius_value,
            direction=direction_value,
            border=border_value,
            operation=operation,
        )

    background = length_values_from_metres(
        background_metres,
        unit=channel.unit,
    )

    return channel.with_data(background)


def remove_arc_revolution_background(
    channel: SPMChannel,
    radius: float,
    *,
    direction: ArcDirection = "both",
    side: ArcSide = "below",
    border: ArcBorder = "nearest",
) -> SPMChannel:
    """Subtract the estimated arc-revolution background from a channel."""
    background = estimate_arc_revolution_background(
        channel,
        radius,
        direction=direction,
        side=side,
        border=border,
    )

    corrected = np.asarray(channel.data, dtype=float) - np.asarray(
        background.data,
        dtype=float,
    )

    return channel.with_data(corrected)
