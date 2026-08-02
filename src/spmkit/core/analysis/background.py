"""Background estimation and removal for SPM images.

Local geometric estimators use explicit physical or pixel-based scales.
Global polynomial and spline estimators fit models over the complete image
using explicitly documented coordinate and mask conventions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

import numpy as np
from scipy.ndimage import generic_filter, grey_erosion, grey_opening

from spmkit.core.analysis._gwyddion_arc_revolution import (
    GwyddionArcDirection,
    _gwyddion_arc_result,
)
from spmkit.core.analysis._gwyddion_sphere_revolution import (
    _gwyddion_sphere_result,
)
from spmkit.core.analysis._pspline import (
    PSplineSurfaceFit,
    fit_pspline_surface,
)
from spmkit.core.geometry import (
    length_values_from_metres,
    length_values_to_metres,
)
from spmkit.core.models import SPMChannel

ArcDirection = Literal["horizontal", "vertical", "both"]
ArcSide = Literal["below", "above"]
ArcBorder = Literal["nearest", "reflect"]
BackgroundMethod = Literal[
    "arc_revolution",
    "gwyddion_arc_revolution",
    "gwyddion_sphere_revolution",
    "sphere_revolution",
    "rolling_ball",
    "median",
    "polynomial",
    "spline",
]


@dataclass(frozen=True)
class BackgroundResult:
    """Structured result of a background-removal operation.

    The complete background and corrected channels are retained for inspection.
    ``parameters`` records the effective public algorithm configuration.
    """

    background: SPMChannel
    corrected: SPMChannel
    method: BackgroundMethod
    parameters: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        """Return a serializable representation of the numerical result."""

        def channel_payload(channel: SPMChannel) -> dict[str, object]:
            data = np.asarray(channel.data)

            return {
                "name": channel.name,
                "unit": channel.unit,
                "shape": list(channel.shape),
                "x_range": float(channel.x_range),
                "y_range": float(channel.y_range),
                "direction": channel.direction,
                "group": channel.group,
                "data": data.tolist(),
            }

        return {
            "method": self.method,
            "parameters": dict(self.parameters),
            "background": channel_payload(self.background),
            "corrected": channel_payload(self.corrected),
        }


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


def _validated_gwyddion_radius_px(
    radius_px: object,
    *,
    operation: str,
) -> float:
    """Validate the public Gwyddion radius measured in samples."""
    radius_data = np.asarray(radius_px)

    if (
        radius_data.ndim != 0
        or not np.issubdtype(radius_data.dtype, np.number)
        or np.iscomplexobj(radius_data)
        or isinstance(radius_px, (bool, np.bool_))
    ):
        raise TypeError(
            f"{operation} requires radius_px to be a real scalar"
        )

    value = float(radius_data.item())

    if not np.isfinite(value):
        raise ValueError(
            f"{operation} requires radius_px to be finite"
        )

    if not 1.0 <= value <= 1000.0:
        raise ValueError(
            f"{operation} requires radius_px to be between "
            "1.0 and 1000.0 inclusive"
        )

    return value


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


def _positive_vertical_radius(
    vertical_radius: object,
    *,
    operation: str,
) -> float:
    """Validate a vertical rolling-ball semiaxis in channel units."""
    radius_data = np.asarray(vertical_radius)

    if (
        radius_data.ndim != 0
        or not np.issubdtype(radius_data.dtype, np.number)
        or np.iscomplexobj(radius_data)
        or isinstance(vertical_radius, (bool, np.bool_))
    ):
        raise TypeError(f"{operation} requires vertical_radius to be a positive real scalar")

    value = float(radius_data.item())

    if not np.isfinite(value):
        raise ValueError(f"{operation} requires vertical_radius to be finite")

    if value <= 0.0:
        raise ValueError(f"{operation} requires vertical_radius to be positive")

    return value


def _validated_choice(
    value: object,
    *,
    name: str,
    allowed: tuple[str, ...],
    operation: str,
) -> str:
    """Validate a string-valued public option."""
    if not isinstance(value, str):
        raise TypeError(f"{operation} requires {name} to be a string")

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


def _gwyddion_arc_channels(
    channel: SPMChannel,
    radius_px: object,
    *,
    direction: object,
    inverted: object,
    operation: str,
) -> tuple[
    SPMChannel,
    SPMChannel,
    float,
    GwyddionArcDirection,
    bool,
]:
    """Validate one request and return background and corrected channels."""
    data = _validated_channel_data(
        channel,
        operation=operation,
    )
    radius_value = _validated_gwyddion_radius_px(
        radius_px,
        operation=operation,
    )
    direction_value = cast(
        GwyddionArcDirection,
        _validated_choice(
            direction,
            name="direction",
            allowed=("horizontal", "vertical", "both"),
            operation=operation,
        ),
    )

    if not isinstance(inverted, (bool, np.bool_)):
        raise TypeError(
            f"{operation} requires inverted to be a boolean"
        )

    inverted_value = bool(inverted)

    background_data, corrected_data = _gwyddion_arc_result(
        data,
        radius_value,
        direction=direction_value,
        inverted=inverted_value,
    )

    return (
        channel.with_data(background_data),
        channel.with_data(corrected_data),
        radius_value,
        direction_value,
        inverted_value,
    )


def estimate_gwyddion_arc_revolution_background(
    channel: SPMChannel,
    radius_px: float = 20.0,
    *,
    direction: GwyddionArcDirection = "horizontal",
    inverted: bool = False,
) -> SPMChannel:
    """Estimate a Gwyddion 2.71-compatible Revolve Arc background.

    Parameters
    ----------
    channel:
        Real, finite, non-empty two-dimensional channel.  The Z unit is
        preserved and need not represent geometric length.
    radius_px:
        Arc radius in samples.  The public Gwyddion-compatible range is
        inclusive from 1.0 through 1000.0.
    direction:
        ``"horizontal"`` processes rows, ``"vertical"`` processes columns,
        and ``"both"`` applies horizontal followed by vertical.
    inverted:
        Apply the exact dual ``-B(-data)``.

    Notes
    -----
    This is a data-adaptive compatibility estimator, not SPMKit's physical
    arc-revolution model, tip deconvolution, or surface reconstruction.
    Edges use the truncated support of Gwyddion 2.71; there is no border mode.
    """
    background, _, _, _, _ = _gwyddion_arc_channels(
        channel,
        radius_px,
        direction=direction,
        inverted=inverted,
        operation="estimate_gwyddion_arc_revolution_background",
    )
    return background


def remove_gwyddion_arc_revolution_background(
    channel: SPMChannel,
    radius_px: float = 20.0,
    *,
    direction: GwyddionArcDirection = "horizontal",
    inverted: bool = False,
) -> SPMChannel:
    """Subtract a Gwyddion 2.71-compatible Revolve Arc background."""
    _, corrected, _, _, _ = _gwyddion_arc_channels(
        channel,
        radius_px,
        direction=direction,
        inverted=inverted,
        operation="remove_gwyddion_arc_revolution_background",
    )
    return corrected


def _gwyddion_sphere_channels(
    channel: SPMChannel,
    radius_px: object,
    *,
    inverted: object,
    operation: str,
) -> tuple[
    SPMChannel,
    SPMChannel,
    float,
    bool,
]:
    """Validate one request and return background and corrected channels."""
    data = _validated_channel_data(
        channel,
        operation=operation,
    )
    radius_value = _validated_gwyddion_radius_px(
        radius_px,
        operation=operation,
    )

    if not isinstance(inverted, (bool, np.bool_)):
        raise TypeError(
            f"{operation} requires inverted to be a boolean"
        )

    inverted_value = bool(inverted)

    background_data, corrected_data = _gwyddion_sphere_result(
        data,
        radius_value,
        inverted=inverted_value,
    )

    return (
        channel.with_data(background_data),
        channel.with_data(corrected_data),
        radius_value,
        inverted_value,
    )


def estimate_gwyddion_sphere_revolution_background(
    channel: SPMChannel,
    radius_px: float = 20.0,
    *,
    inverted: bool = False,
) -> SPMChannel:
    """Estimate a Gwyddion 2.71-compatible Sphere Revolution background.

    Parameters
    ----------
    channel:
        Real, finite, non-empty two-dimensional channel.  The Z unit is
        preserved and need not represent geometric length.
    radius_px:
        Sphere radius in samples.  The public Gwyddion-compatible range is
        inclusive from 1.0 through 1000.0.
    inverted:
        Apply the exact dual ``-B(-data)``.

    Notes
    -----
    This is a data-adaptive compatibility estimator, not SPMKit's physical
    sphere-revolution model, tip deconvolution, or surface reconstruction.
    """
    background, _, _, _ = _gwyddion_sphere_channels(
        channel,
        radius_px,
        inverted=inverted,
        operation="estimate_gwyddion_sphere_revolution_background",
    )
    return background


def remove_gwyddion_sphere_revolution_background(
    channel: SPMChannel,
    radius_px: float = 20.0,
    *,
    inverted: bool = False,
) -> SPMChannel:
    """Subtract a Gwyddion 2.71-compatible Sphere Revolution background."""
    _, corrected, _, _ = _gwyddion_sphere_channels(
        channel,
        radius_px,
        inverted=inverted,
        operation="remove_gwyddion_sphere_revolution_background",
    )
    return corrected


def _sphere_structure(
    *,
    radius: float,
    x_spacing: float,
    y_spacing: float,
    shape: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray]:
    """Return a physical spherical-cap structure and its circular footprint."""
    rows, columns = shape

    maximum_x_offset = columns - 1
    radius_in_x_pixels = radius / x_spacing

    if not np.isfinite(radius_in_x_pixels) or radius_in_x_pixels >= maximum_x_offset:
        x_offset = maximum_x_offset
    else:
        x_offset = int(np.floor(radius_in_x_pixels))

    maximum_y_offset = rows - 1
    radius_in_y_pixels = radius / y_spacing

    if not np.isfinite(radius_in_y_pixels) or radius_in_y_pixels >= maximum_y_offset:
        y_offset = maximum_y_offset
    else:
        y_offset = int(np.floor(radius_in_y_pixels))

    x_offsets = np.arange(
        -x_offset,
        x_offset + 1,
        dtype=float,
    )
    y_offsets = np.arange(
        -y_offset,
        y_offset + 1,
        dtype=float,
    )

    normalized_x = x_offsets * x_spacing / radius
    normalized_y = y_offsets * y_spacing / radius

    squared_ratio = np.square(normalized_y)[:, np.newaxis] + np.square(normalized_x)[np.newaxis, :]

    tolerance = 8.0 * np.finfo(float).eps
    footprint = squared_ratio <= 1.0 + tolerance

    clipped_ratio = np.minimum(
        squared_ratio,
        1.0,
    )
    root = np.sqrt(
        np.maximum(
            1.0 - clipped_ratio,
            0.0,
        )
    )

    # Stable form of radius - sqrt(radius**2 - distance**2).
    sagitta = radius * clipped_ratio / (1.0 + root)

    # Values outside the footprint are ignored by SciPy. Keeping them at zero
    # prevents irrelevant invalid or extreme structure values.
    structure = np.where(
        footprint,
        -sagitta,
        0.0,
    )

    return structure, footprint


def _opening_with_sphere(
    data: np.ndarray,
    *,
    radius: float,
    x_spacing: float,
    y_spacing: float,
    border: ArcBorder,
) -> np.ndarray:
    """Apply one physical two-dimensional spherical opening."""
    structure, footprint = _sphere_structure(
        radius=radius,
        x_spacing=x_spacing,
        y_spacing=y_spacing,
        shape=data.shape,
    )

    if footprint.size == 1:
        return data.copy()

    return np.asarray(
        grey_opening(
            data,
            footprint=footprint,
            structure=structure,
            mode=border,
        ),
        dtype=float,
    )


def _estimate_sphere_below_metres(
    data_metres: np.ndarray,
    channel: SPMChannel,
    *,
    radius: float,
    border: ArcBorder,
    operation: str,
) -> np.ndarray:
    """Estimate the spherical envelope rolling below a surface."""
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

    return _opening_with_sphere(
        data_metres,
        radius=radius,
        x_spacing=x_spacing,
        y_spacing=y_spacing,
        border=border,
    )


def estimate_sphere_revolution_background(
    channel: SPMChannel,
    radius: float,
    *,
    side: ArcSide = "below",
    border: ArcBorder = "nearest",
) -> SPMChannel:
    """Estimate a physical spherical-revolution background.

    The structuring surface is a true spherical cap in physical XY
    coordinates. With anisotropic pixels its footprint can therefore appear
    elliptical in index space while remaining circular in physical space.
    """
    operation = "estimate_sphere_revolution_background"

    data = _validated_channel_data(
        channel,
        operation=operation,
    )
    radius_value = _positive_radius(
        radius,
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
        background_metres = _estimate_sphere_below_metres(
            data_metres,
            channel,
            radius=radius_value,
            border=border_value,
            operation=operation,
        )
    else:
        background_metres = -_estimate_sphere_below_metres(
            -data_metres,
            channel,
            radius=radius_value,
            border=border_value,
            operation=operation,
        )

    background = length_values_from_metres(
        background_metres,
        unit=channel.unit,
    )

    return channel.with_data(background)


def remove_sphere_revolution_background(
    channel: SPMChannel,
    radius: float,
    *,
    side: ArcSide = "below",
    border: ArcBorder = "nearest",
) -> SPMChannel:
    """Subtract the estimated spherical-revolution background."""
    background = estimate_sphere_revolution_background(
        channel,
        radius,
        side=side,
        border=border,
    )

    corrected = np.asarray(channel.data, dtype=float) - np.asarray(
        background.data,
        dtype=float,
    )

    return channel.with_data(corrected)


def _rolling_ball_structure(
    *,
    radius: float,
    vertical_radius: float,
    x_spacing: float,
    y_spacing: float,
    shape: tuple[int, int],
    spherical: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """Return a physical rolling-ball structure and footprint."""
    rows, columns = shape

    maximum_x_offset = columns - 1
    radius_in_x_pixels = radius / x_spacing

    if not np.isfinite(radius_in_x_pixels) or radius_in_x_pixels >= maximum_x_offset:
        x_offset = maximum_x_offset
    else:
        x_offset = int(np.floor(radius_in_x_pixels))

    maximum_y_offset = rows - 1
    radius_in_y_pixels = radius / y_spacing

    if not np.isfinite(radius_in_y_pixels) or radius_in_y_pixels >= maximum_y_offset:
        y_offset = maximum_y_offset
    else:
        y_offset = int(np.floor(radius_in_y_pixels))

    x_offsets = np.arange(
        -x_offset,
        x_offset + 1,
        dtype=float,
    )
    y_offsets = np.arange(
        -y_offset,
        y_offset + 1,
        dtype=float,
    )

    x_distances = x_offsets * x_spacing
    y_distances = y_offsets * y_spacing

    squared_distance = np.square(y_distances)[:, np.newaxis] + np.square(x_distances)[np.newaxis, :]
    squared_radius = radius * radius
    squared_ratio = squared_distance / squared_radius

    tolerance = 8.0 * np.finfo(float).eps
    footprint = squared_ratio <= 1.0 + tolerance

    if spherical:
        # Physical sphere and scikit-image ball_kernel arithmetic:
        # height = sqrt(radius**2 - distance**2).
        clipped_distance = np.minimum(
            squared_distance,
            squared_radius,
        )
        height = np.sqrt(
            np.maximum(
                squared_radius - clipped_distance,
                0.0,
            )
        )
        sagitta = radius - height
    else:
        # General ellipsoid and scikit-image ellipsoid_kernel arithmetic:
        # height = vertical_radius * sqrt(1 - normalized distance**2).
        clipped_ratio = np.minimum(
            squared_ratio,
            1.0,
        )
        root = np.sqrt(
            np.maximum(
                1.0 - clipped_ratio,
                0.0,
            )
        )
        height = vertical_radius * root
        sagitta = vertical_radius - height

    # scipy.ndimage.grey_erosion calculates min(image - structure).
    # A negative sagitta therefore evaluates min(image + sagitta).
    structure = np.where(
        footprint,
        -sagitta,
        0.0,
    )

    return structure, footprint


def _estimate_rolling_ball_below(
    data: np.ndarray,
    channel: SPMChannel,
    *,
    radius: float,
    vertical_radius: float,
    spherical: bool,
    operation: str,
) -> np.ndarray:
    """Evaluate the rolling-ball apex field below a surface."""
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

    structure, footprint = _rolling_ball_structure(
        radius=radius,
        vertical_radius=vertical_radius,
        x_spacing=x_spacing,
        y_spacing=y_spacing,
        shape=data.shape,
        spherical=spherical,
    )

    if footprint.size == 1:
        return data.copy()

    return np.asarray(
        grey_erosion(
            data,
            footprint=footprint,
            structure=structure,
            mode="constant",
            cval=np.inf,
        ),
        dtype=float,
    )


def estimate_rolling_ball_background(
    channel: SPMChannel,
    radius: float,
    *,
    vertical_radius: float | None = None,
    side: ArcSide = "below",
) -> SPMChannel:
    """Estimate a background using a physical rolling ball.

    The lateral semiaxis ``radius`` is expressed in metres.  When
    ``vertical_radius`` is omitted, channel Z values must represent length;
    they are converted to metres and a physical sphere with equal lateral
    and vertical radii is used.

    An explicit ``vertical_radius`` is interpreted in the native channel
    unit, permitting ellipsoidal kernels for voltage, phase, current and
    other non-geometric channels.

    The estimator is the apex-height rolling-ball operation described by
    Sternberg (1983), equivalent to non-flat grey erosion.  Samples outside
    the image are ignored by assigning them positive infinity.

    References
    ----------
    S. R. Sternberg, "Biomedical Image Processing", Computer 16(1),
    22-34 (1983), doi:10.1109/MC.1983.1654163.
    """
    operation = "estimate_rolling_ball_background"

    data = _validated_channel_data(
        channel,
        operation=operation,
    )
    radius_value = _positive_radius(
        radius,
        operation=operation,
    )
    side_value = _validated_choice(
        side,
        name="side",
        allowed=("below", "above"),
        operation=operation,
    )

    use_geometric_z = vertical_radius is None

    if use_geometric_z:
        working_data = length_values_to_metres(
            data,
            unit=channel.unit,
        )
        vertical_radius_value = radius_value
    else:
        working_data = np.asarray(
            data,
            dtype=float,
        )
        vertical_radius_value = _positive_vertical_radius(
            vertical_radius,
            operation=operation,
        )

    if side_value == "below":
        working_background = _estimate_rolling_ball_below(
            working_data,
            channel,
            radius=radius_value,
            vertical_radius=vertical_radius_value,
            spherical=use_geometric_z,
            operation=operation,
        )
    else:
        working_background = -_estimate_rolling_ball_below(
            -working_data,
            channel,
            radius=radius_value,
            vertical_radius=vertical_radius_value,
            spherical=use_geometric_z,
            operation=operation,
        )

    if use_geometric_z:
        background = length_values_from_metres(
            working_background,
            unit=channel.unit,
        )
    else:
        background = working_background

    return channel.with_data(background)


def remove_rolling_ball_background(
    channel: SPMChannel,
    radius: float,
    *,
    vertical_radius: float | None = None,
    side: ArcSide = "below",
) -> SPMChannel:
    """Subtract a rolling-ball background from a channel."""
    background = estimate_rolling_ball_background(
        channel,
        radius,
        vertical_radius=vertical_radius,
        side=side,
    )

    corrected = np.asarray(
        channel.data,
        dtype=float,
    ) - np.asarray(
        background.data,
        dtype=float,
    )

    return channel.with_data(corrected)


def _positive_pixel_radius(
    radius_pixels: object,
    *,
    operation: str,
) -> int:
    """Validate a strictly positive integer radius expressed in pixels."""
    radius_data = np.asarray(radius_pixels)

    if (
        radius_data.ndim != 0
        or not np.issubdtype(radius_data.dtype, np.integer)
        or isinstance(radius_pixels, (bool, np.bool_))
    ):
        raise TypeError(f"{operation} requires radius_pixels to be a positive integer")

    value = int(radius_data.item())

    if value <= 0:
        raise ValueError(f"{operation} requires radius_pixels to be positive")

    return value


def _validated_median_radius(
    radius_pixels: int,
    *,
    operation: str,
) -> int:
    """Validate the Gwyddion Median Level integer-radius contract."""
    maximum_radius = 1024

    if radius_pixels > maximum_radius:
        raise ValueError(f"{operation}: radius_pixels must be in the range [1, {maximum_radius}]")

    return radius_pixels


def _median_disk_footprint(
    radius_pixels: int,
) -> np.ndarray:
    """Return Gwyddion's pixel-centre elliptic kernel rasterization.

    Gwyddion creates a square bounding box of side ``2*r + 1`` and
    includes pixel centres inside the corresponding ellipse.  For a
    circular odd-sized kernel this is equivalent to

    ``(2*x)**2 + (2*y)**2 <= (2*r + 1)**2``.

    The integer form avoids floating-point boundary ambiguity.
    """
    coordinates = 2 * np.arange(
        -radius_pixels,
        radius_pixels + 1,
        dtype=np.int64,
    )
    diameter = 2 * radius_pixels + 1

    squared_distance = coordinates[:, np.newaxis] ** 2 + coordinates[np.newaxis, :] ** 2

    return squared_distance <= diameter**2


def _median_background_border_extend(
    data: np.ndarray,
    *,
    radius_pixels: int,
) -> np.ndarray:
    """Calculate a circular local median using nearest border extension."""
    footprint = _median_disk_footprint(radius_pixels)

    return np.asarray(
        generic_filter(
            np.asarray(data, dtype=float),
            function=np.median,
            footprint=footprint,
            mode="nearest",
        ),
        dtype=float,
    )


def estimate_median_background(
    channel: SPMChannel,
    radius_pixels: int,
) -> SPMChannel:
    """Estimate a local median background with a circular pixel kernel.

    The neighbourhood radius is an integer number of pixels. At image edges
    values are extended using the nearest boundary sample.
    The operation is rank-based and therefore does not require a geometric Z
    unit.
    """
    operation = "estimate_median_background"

    data = _validated_channel_data(
        channel,
        operation=operation,
    )
    radius_value = _positive_pixel_radius(
        radius_pixels,
        operation=operation,
    )
    radius_value = _validated_median_radius(
        radius_value,
        operation=operation,
    )

    background = _median_background_border_extend(
        data,
        radius_pixels=radius_value,
    )

    return channel.with_data(background)


def remove_median_background(
    channel: SPMChannel,
    radius_pixels: int,
) -> SPMChannel:
    """Subtract a circular local-median background from a channel."""
    background = estimate_median_background(
        channel,
        radius_pixels,
    )

    corrected = np.asarray(channel.data, dtype=float) - np.asarray(
        background.data,
        dtype=float,
    )

    return channel.with_data(corrected)


def estimate_polynomial_background(
    channel: SPMChannel,
    *,
    degree_mode: Literal["total", "independent"] = "total",
    degree: int = 2,
    x_degree: int | None = None,
    y_degree: int | None = None,
    mask: np.ndarray | None = None,
    mask_mode: Literal["ignore", "include", "exclude"] = "ignore",
) -> SPMChannel:
    """Estimate a global two-dimensional polynomial background.

    Pixel-centre coordinates are normalized independently to ``[-1, 1]``.
    ``degree_mode="total"`` includes terms with ``x_power + y_power <= degree``.
    ``degree_mode="independent"`` includes the full tensor-product basis up to
    ``x_degree`` and ``y_degree``.

    A mask controls only the points used for fitting.  The fitted model is
    evaluated over the complete image.
    """
    from spmkit.core.analysis.leveling import (
        _estimate_polynomial_background_data,
    )

    background = _estimate_polynomial_background_data(
        channel,
        degree_mode=degree_mode,
        degree=degree,
        x_degree=x_degree,
        y_degree=y_degree,
        mask=mask,
        mask_mode=mask_mode,
    )

    return channel.with_data(background)


def remove_polynomial_background(
    channel: SPMChannel,
    *,
    degree_mode: Literal["total", "independent"] = "total",
    degree: int = 2,
    x_degree: int | None = None,
    y_degree: int | None = None,
    mask: np.ndarray | None = None,
    mask_mode: Literal["ignore", "include", "exclude"] = "ignore",
) -> SPMChannel:
    """Subtract a global two-dimensional polynomial background."""
    background = estimate_polynomial_background(
        channel,
        degree_mode=degree_mode,
        degree=degree,
        x_degree=x_degree,
        y_degree=y_degree,
        mask=mask,
        mask_mode=mask_mode,
    )

    data = np.asarray(channel.data, dtype=float)
    background_data = np.asarray(background.data, dtype=float)

    return channel.with_data(data - background_data)


def _fit_spline_background(
    channel: SPMChannel,
    *,
    n_basis_x: int = 12,
    n_basis_y: int = 12,
    degree_x: int = 3,
    degree_y: int = 3,
    penalty_order_x: int = 2,
    penalty_order_y: int = 2,
    smoothing_x: float = 1.0,
    smoothing_y: float = 1.0,
    mask: np.ndarray | None = None,
    mask_mode: Literal["ignore", "include", "exclude"] = "ignore",
    weights: np.ndarray | None = None,
    atol: float = 1e-12,
    btol: float = 1e-12,
    conlim: float = 1e12,
    maxiter: int | None = None,
) -> PSplineSurfaceFit:
    """Fit a P-spline background while preserving complete diagnostics."""
    from spmkit.core.analysis.leveling import _fit_selection

    data = np.asarray(channel.data)

    if data.ndim != 2:
        raise ValueError("spline_background requires a 2D channel")

    rows, columns = data.shape

    if rows < 2 or columns < 2:
        raise ValueError("spline_background requires at least two rows and two columns")

    selection = _fit_selection(
        data,
        mask=mask,
        mask_mode=mask_mode,
        operation="spline_background",
        minimum_points=1,
    )

    x_coordinates = (np.arange(columns, dtype=float) + 0.5) * float(channel.pixel_size_x)
    y_coordinates = (np.arange(rows, dtype=float) + 0.5) * float(channel.pixel_size_y)

    return fit_pspline_surface(
        data,
        x=x_coordinates,
        y=y_coordinates,
        mask=selection,
        weights=weights,
        n_basis_x=n_basis_x,
        n_basis_y=n_basis_y,
        degree_x=degree_x,
        degree_y=degree_y,
        penalty_order_x=penalty_order_x,
        penalty_order_y=penalty_order_y,
        smoothing_x=smoothing_x,
        smoothing_y=smoothing_y,
        atol=atol,
        btol=btol,
        conlim=conlim,
        maxiter=maxiter,
    )


def estimate_spline_background(
    channel: SPMChannel,
    *,
    n_basis_x: int = 12,
    n_basis_y: int = 12,
    degree_x: int = 3,
    degree_y: int = 3,
    penalty_order_x: int = 2,
    penalty_order_y: int = 2,
    smoothing_x: float = 1.0,
    smoothing_y: float = 1.0,
    mask: np.ndarray | None = None,
    mask_mode: Literal["ignore", "include", "exclude"] = "ignore",
    weights: np.ndarray | None = None,
) -> SPMChannel:
    """Estimate a global anisotropic tensor-product P-spline background.

    The basis is evaluated at physical pixel-centre coordinates. Each axis is
    normalized independently inside the P-spline solver. A mask controls only
    observations used for fitting; the model is evaluated over the full image.
    """
    fit = _fit_spline_background(
        channel,
        n_basis_x=n_basis_x,
        n_basis_y=n_basis_y,
        degree_x=degree_x,
        degree_y=degree_y,
        penalty_order_x=penalty_order_x,
        penalty_order_y=penalty_order_y,
        smoothing_x=smoothing_x,
        smoothing_y=smoothing_y,
        mask=mask,
        mask_mode=mask_mode,
        weights=weights,
    )

    background = np.array(
        fit.model,
        dtype=float,
        copy=True,
        order="C",
    )

    return channel.with_data(background)


def remove_spline_background(
    channel: SPMChannel,
    *,
    n_basis_x: int = 12,
    n_basis_y: int = 12,
    degree_x: int = 3,
    degree_y: int = 3,
    penalty_order_x: int = 2,
    penalty_order_y: int = 2,
    smoothing_x: float = 1.0,
    smoothing_y: float = 1.0,
    mask: np.ndarray | None = None,
    mask_mode: Literal["ignore", "include", "exclude"] = "ignore",
    weights: np.ndarray | None = None,
) -> SPMChannel:
    """Subtract a global anisotropic tensor-product P-spline background."""
    background = estimate_spline_background(
        channel,
        n_basis_x=n_basis_x,
        n_basis_y=n_basis_y,
        degree_x=degree_x,
        degree_y=degree_y,
        penalty_order_x=penalty_order_x,
        penalty_order_y=penalty_order_y,
        smoothing_x=smoothing_x,
        smoothing_y=smoothing_y,
        mask=mask,
        mask_mode=mask_mode,
        weights=weights,
    )

    data = np.asarray(channel.data, dtype=float)
    background_data = np.asarray(background.data, dtype=float)

    return channel.with_data(data - background_data)


def _build_background_result(
    channel: SPMChannel,
    background: SPMChannel,
    *,
    method: BackgroundMethod,
    parameters: dict[str, object],
) -> BackgroundResult:
    """Build a structured result without recalculating the background."""
    corrected = channel.with_data(
        np.asarray(channel.data, dtype=float) - np.asarray(background.data, dtype=float)
    )

    return BackgroundResult(
        background=background,
        corrected=corrected,
        method=method,
        parameters=dict(parameters),
    )


def analyze_arc_revolution_background(
    channel: SPMChannel,
    radius: float,
    *,
    direction: ArcDirection = "both",
    side: ArcSide = "below",
    border: ArcBorder = "nearest",
) -> BackgroundResult:
    """Estimate and subtract an arc-revolution background in one pass."""
    background = estimate_arc_revolution_background(
        channel,
        radius,
        direction=direction,
        side=side,
        border=border,
    )

    return _build_background_result(
        channel,
        background,
        method="arc_revolution",
        parameters={
            "radius": float(radius),
            "direction": direction,
            "side": side,
            "border": border,
        },
    )


def analyze_gwyddion_arc_revolution_background(
    channel: SPMChannel,
    radius_px: float = 20.0,
    *,
    direction: GwyddionArcDirection = "horizontal",
    inverted: bool = False,
) -> BackgroundResult:
    """Estimate and subtract a compatible Revolve Arc background once."""
    (
        background,
        corrected,
        radius_value,
        direction_value,
        inverted_value,
    ) = _gwyddion_arc_channels(
        channel,
        radius_px,
        direction=direction,
        inverted=inverted,
        operation="analyze_gwyddion_arc_revolution_background",
    )

    return BackgroundResult(
        background=background,
        corrected=corrected,
        method="gwyddion_arc_revolution",
        parameters={
            "radius_px": radius_value,
            "direction": direction_value,
            "inverted": inverted_value,
        },
    )


def analyze_gwyddion_sphere_revolution_background(
    channel: SPMChannel,
    radius_px: float = 20.0,
    *,
    inverted: bool = False,
) -> BackgroundResult:
    """Estimate and subtract a compatible Sphere Revolution background once."""
    (
        background,
        corrected,
        radius_value,
        inverted_value,
    ) = _gwyddion_sphere_channels(
        channel,
        radius_px,
        inverted=inverted,
        operation="analyze_gwyddion_sphere_revolution_background",
    )

    return BackgroundResult(
        background=background,
        corrected=corrected,
        method="gwyddion_sphere_revolution",
        parameters={
            "radius_px": radius_value,
            "inverted": inverted_value,
        },
    )


def analyze_sphere_revolution_background(
    channel: SPMChannel,
    radius: float,
    *,
    side: ArcSide = "below",
    border: ArcBorder = "nearest",
) -> BackgroundResult:
    """Estimate and subtract a spherical background in one pass."""
    background = estimate_sphere_revolution_background(
        channel,
        radius,
        side=side,
        border=border,
    )

    return _build_background_result(
        channel,
        background,
        method="sphere_revolution",
        parameters={
            "radius": float(radius),
            "side": side,
            "border": border,
        },
    )


def analyze_rolling_ball_background(
    channel: SPMChannel,
    radius: float,
    *,
    vertical_radius: float | None = None,
    side: ArcSide = "below",
) -> BackgroundResult:
    """Estimate and subtract a rolling-ball background in one pass."""
    background = estimate_rolling_ball_background(
        channel,
        radius,
        vertical_radius=vertical_radius,
        side=side,
    )

    return _build_background_result(
        channel,
        background,
        method="rolling_ball",
        parameters={
            "radius": float(radius),
            "vertical_radius": (None if vertical_radius is None else float(vertical_radius)),
            "side": side,
            "boundary": "ignore",
        },
    )


def analyze_polynomial_background(
    channel: SPMChannel,
    *,
    degree_mode: Literal["total", "independent"] = "total",
    degree: int = 2,
    x_degree: int | None = None,
    y_degree: int | None = None,
    mask: np.ndarray | None = None,
    mask_mode: Literal["ignore", "include", "exclude"] = "ignore",
) -> BackgroundResult:
    """Estimate and subtract a polynomial background in one fit."""
    background = estimate_polynomial_background(
        channel,
        degree_mode=degree_mode,
        degree=degree,
        x_degree=x_degree,
        y_degree=y_degree,
        mask=mask,
        mask_mode=mask_mode,
    )

    return _build_background_result(
        channel,
        background,
        method="polynomial",
        parameters={
            "degree_mode": degree_mode,
            "degree": (int(degree) if degree_mode == "total" else None),
            "x_degree": (int(x_degree) if x_degree is not None else None),
            "y_degree": (int(y_degree) if y_degree is not None else None),
            "mask_mode": mask_mode,
            "mask_provided": mask is not None,
            "coordinates": "normalized_-1_1",
        },
    )


def analyze_spline_background(
    channel: SPMChannel,
    *,
    n_basis_x: int = 12,
    n_basis_y: int = 12,
    degree_x: int = 3,
    degree_y: int = 3,
    penalty_order_x: int = 2,
    penalty_order_y: int = 2,
    smoothing_x: float = 1.0,
    smoothing_y: float = 1.0,
    mask: np.ndarray | None = None,
    mask_mode: Literal["ignore", "include", "exclude"] = "ignore",
    weights: np.ndarray | None = None,
) -> BackgroundResult:
    """Estimate and subtract a P-spline background using one fit."""
    fit = _fit_spline_background(
        channel,
        n_basis_x=n_basis_x,
        n_basis_y=n_basis_y,
        degree_x=degree_x,
        degree_y=degree_y,
        penalty_order_x=penalty_order_x,
        penalty_order_y=penalty_order_y,
        smoothing_x=smoothing_x,
        smoothing_y=smoothing_y,
        mask=mask,
        mask_mode=mask_mode,
        weights=weights,
    )

    background = channel.with_data(
        np.array(
            fit.model,
            dtype=float,
            copy=True,
            order="C",
        )
    )

    return _build_background_result(
        channel,
        background,
        method="spline",
        parameters={
            "n_basis_x": int(fit.coefficients.shape[1]),
            "n_basis_y": int(fit.coefficients.shape[0]),
            "degree_x": int(fit.degree_x),
            "degree_y": int(fit.degree_y),
            "penalty_order_x": int(fit.penalty_order_x),
            "penalty_order_y": int(fit.penalty_order_y),
            "smoothing_x": float(fit.smoothing_x),
            "smoothing_y": float(fit.smoothing_y),
            "mask_mode": mask_mode,
            "mask_provided": mask is not None,
            "weights_provided": weights is not None,
            "coordinates": "physical_pixel_centres_normalized_0_1",
            "diagnostics": {
                "selected_points": int(fit.selected_points),
                "total_points": int(fit.total_points),
                "solver_stop_code": int(fit.solver_stop_code),
                "solver_iterations": int(fit.solver_iterations),
                "augmented_residual_norm": float(fit.augmented_residual_norm),
                "normal_residual_norm": float(fit.normal_residual_norm),
                "operator_norm": float(fit.operator_norm),
                "condition_estimate": float(fit.condition_estimate),
                "coefficient_norm": float(fit.coefficient_norm),
                "weighted_data_residual_norm": float(fit.weighted_data_residual_norm),
                "penalty_x_norm": float(fit.penalty_x_norm),
                "penalty_y_norm": float(fit.penalty_y_norm),
                "x_min": float(fit.x_min),
                "x_max": float(fit.x_max),
                "y_min": float(fit.y_min),
                "y_max": float(fit.y_max),
            },
        },
    )


def analyze_median_background(
    channel: SPMChannel,
    radius_pixels: int,
) -> BackgroundResult:
    """Estimate and subtract a local-median background in one pass."""
    background = estimate_median_background(
        channel,
        radius_pixels,
    )

    return _build_background_result(
        channel,
        background,
        method="median",
        parameters={
            "radius_pixels": int(radius_pixels),
            "border": "nearest",
        },
    )
