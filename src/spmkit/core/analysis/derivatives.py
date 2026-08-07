"""gwyddion 2.71 derivative filters and native gradient composite.

Public surface of the first A2 derivative-filter production batch:

  * gwyddion_sobel_x / gwyddion_sobel_y / gwyddion_prewitt_x /
    gwyddion_prewitt_y: exact component filters, CROSS_VALIDATED within the
    frozen canonical source-included profile
    (COMPILED_gwyddion_2_71_SOURCE_INCLUDED_DERIVATIVE_KERNEL_PROFILE);
  * gwyddion_gradient_magnitude(gx, gy): hypot composition, CROSS_VALIDATED
    only within the frozen x86-64/glibc hypot platform profile;
  * gradient_direction(gx, gy): native SPMKit analytical composite
    atan2(gy, gx), NUMERICALLY_VERIFIED, not direct Gwydion parity.

All operations accept finite two-dimensional SPMChannel inputs only, reject
NaN/Inf/empty/complex data, never mutate inputs, return independently owned
output storage, preserve shape/calibration/direction/metadata, and expose no
public border, mask or ROI/selection parameters.
"""

from __future__ import annotations

import numpy as np

from spmkit.core.analysis._gwyddion_derivative_filters import (
    ORIENTATION_HORIZONTAL,
    ORIENTATION_VERTICAL,
    _validate_component_pair,
    _validated_field,
    gradient_direction_fields,
    gradient_magnitude_fields,
    prewitt_component,
    sobel_component,
)
from spmkit.core.models.spmdata import SPMChannel

__all__ = [
    "gwyddion_sobel_x",
    "gwyddion_sobel_y",
    "gwyddion_prewitt_x",
    "gwyddion_prewitt_y",
    "gwyddion_gradient_magnitude",
    "gradient_direction",
]


def _channel_result(channel: SPMChannel, corrected: np.ndarray) -> SPMChannel:
    if not isinstance(channel, SPMChannel):
        raise TypeError("derivative filter requires an SPMChannel")
    return channel.with_data(corrected)


def _validate_channel(channel: SPMChannel, *, label: str) -> np.ndarray:
    if not isinstance(channel, SPMChannel):
        raise TypeError(f"{label} requires an SPMChannel")
    return _validated_field(channel.data, label=label)


def _validate_component_channels(
    gx: SPMChannel, gy: SPMChannel, *, label: str
) -> tuple[np.ndarray, np.ndarray]:
    """Validate the component-channel pair (shape/calibration/units/context)."""
    if not isinstance(gx, SPMChannel) or not isinstance(gy, SPMChannel):
        raise TypeError(f"{label} requires two SPMChannel components")
    x = _validated_field(gx.data, label=f"{label} gx")
    y = _validated_field(gy.data, label=f"{label} gy")
    _validate_component_pair(x, y, label=label)
    if gx.x_range != gy.x_range or gx.y_range != gy.y_range:
        raise ValueError(f"{label} component channels must share x_range/y_range")
    if gx.unit != gy.unit:
        raise ValueError(f"{label} component channels must have compatible units")
    if gx.direction != gy.direction:
        raise ValueError(f"{label} component channels must share scan direction")
    return x, y


def gwyddion_sobel_x(channel: SPMChannel) -> SPMChannel:
    """Sobel X (horizontal) derivative with frozen Gwydion 2.71 CLIPPED semantics.

    Kernel rows {0.25, 0, -0.25; 0.5, 0, -0.5; 0.25, 0, -0.25}; increasing
    rightward data yields negative responses.  The z-unit of the input is
    preserved (dimensionless kernel).  The input channel is never mutated.
    """
    field = _validate_channel(channel, label="gwyddion_sobel_x")
    result = sobel_component(field, ORIENTATION_HORIZONTAL)
    return _channel_result(channel, result)


def gwyddion_sobel_y(channel: SPMChannel) -> SPMChannel:
    """Sobel Y (vertical) derivative with frozen Gwydion 2.71 CLIPPED semantics.

    Kernel rows {0.25, 0.5, 0.25; 0, 0, 0; -0.25, -0.5, -0.25}; increasing
    downward data yields negative responses.  The z-unit of the input is
    preserved (dimensionless kernel).  The input channel is never mutated.
    """
    field = _validate_channel(channel, label="gwyddion_sobel_y")
    result = sobel_component(field, ORIENTATION_VERTICAL)
    return _channel_result(channel, result)


def gwyddion_prewitt_x(channel: SPMChannel) -> SPMChannel:
    """Prewitt X (horizontal) derivative with frozen Gwydion 2.71 1/3 coefficients.

    Same orientation and CLIPPED semantics as Sobel X; ramp response
    identical to Sobel on planar ramps, 1/3 coefficients on impulses.
    The z-unit of the input is preserved.  The input channel is never
    mutated.
    """
    field = _validate_channel(channel, label="gwyddion_prewitt_x")
    result = prewitt_component(field, ORIENTATION_HORIZONTAL)
    return _channel_result(channel, result)


def gwyddion_prewitt_y(channel: SPMChannel) -> SPMChannel:
    """Prewitt Y (vertical) derivative with frozen Gwydion 2.71 1/3 coefficients.

    Same orientation and CLIPPED semantics as Sobel Y.  The z-unit of the
    input is preserved.  The input channel is never mutated.
    """
    field = _validate_channel(channel, label="gwyddion_prewitt_y")
    result = prewitt_component(field, ORIENTATION_VERTICAL)
    return _channel_result(channel, result)


def gwyddion_gradient_magnitude(gx: SPMChannel, gy: SPMChannel) -> SPMChannel:
    """Gradient magnitude hypot(gx, gy) over explicit component fields.

    Reproduces the frozen the hypot-of-fields orchestration orchestration
    (r[i] = hypot(p[i], q[i])).  Bitwise identity with the compiled glibc
    hypot@GLIBC_2.35 profile is claimed only within the frozen x86-64/glibc
    platform profile; no cross-libc or cross-architecture guarantee.  The
    result z-unit equals the component unit.  Components are never mutated.
    """
    x, y = _validate_component_channels(gx, gy, label="gwyddion_gradient_magnitude")
    result = gradient_magnitude_fields(x, y)
    return _channel_result(gx, result)


def gradient_direction(gx: SPMChannel, gy: SPMChannel) -> SPMChannel:
    """Native gradient direction atan2(gy, gx) in radians.

    Range (-pi, pi]; exact argument order; C99 signed-zero axes; zero
    vector -> +0.0; no normalization.  This is a NATIVE_SPMKIT_ANALYTICAL_
    COMPOSITE (NUMERICALLY_VERIFIED), not direct Gwydion parity.  The result
    unit is "rad".  Components are never mutated.
    """
    x, y = _validate_component_channels(gx, gy, label="gradient_direction")
    result = gradient_direction_fields(x, y)
    direction_channel = _channel_result(gx, result)
    return SPMChannel(
        name=direction_channel.name,
        data=direction_channel.data,
        unit="rad",
        x_range=direction_channel.x_range,
        y_range=direction_channel.y_range,
        direction=direction_channel.direction,
        group=direction_channel.group,
        metadata=dict(direction_channel.metadata),
    )
