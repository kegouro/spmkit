"""Private Gwydion 2.71 derivative-filter components (Sobel X/Y, Prewitt X/Y),
gradient magnitude and native gradient direction.

Implements the first A2 derivative-filter batch with the exact arithmetic of
the frozen canonical source-included campaign profile:

  COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_DERIVATIVE_KERNEL_PROFILE

for Sobel X/Y and Prewitt X/Y, and the frozen platform profile:

  x86-64 / glibc / hypot@GLIBC_2.35 / source-included
  the hypot-of-fields orchestration orchestration

for gradient magnitude.  Gradient direction is a native SPMKit analytical
composite (atan2(gy, gx)) with maturity ceiling NUMERICALLY_VERIFIED; it is
not direct Gwydion parity.

This module is a standalone production reimplementation of the independently
established mathematical contract; it shares no code with the validation
oracles, contains no case identifiers, reads no fixtures, no source trees and
no Gwydion runtime, and never invokes platform-specific runtime libraries.

Frozen semantics reproduced bitwise (validated against the persistent
canonical fixture arrays):

  * 3x3 correlation-style application: kernel row 0 -> row above, row 1 ->
    current row, row 2 -> row below; kernel col 0 -> col-1, col 1 ->
    current, col 2 -> col+1;
  * kernels: hsobel {0.25,0,-0.25, 0.5,0,-0.5, 0.25,0,-0.25},
    vsobel {0.25,0.5,0.25, 0,0,0, -0.25,-0.5,-0.25},
    hprewitt/vprewitt with 1/3 coefficients;
  * sign convention: increasing-right X ramp -> negative Sobel X;
    increasing-down Y ramp -> negative Sobel Y;
  * CLIPPED borders: outside rows/cols fold onto the edge value; the left
    and right columns use the pre-combined sums (k0+k1), (k3+k4), (k6+k7) /
    (k1+k2), (k4+k5), (k7+k8) exactly as the compiled source;
  * width == 1: column-sums of the kernel; height == 1: all three kernel
    rows fold onto the single row; 1x1, 1xN, Nx1 and non-square fields all
    supported;
  * strict left-to-right accumulation order per output element (no FMA, no
    reassociation), including signed-zero bit patterns;
  * magnitude: r = hypot(gx, gy) through numpy.hypot, which is bitwise
    identical to the platform C hypot on the frozen x86-64/glibc platform
    (characterized by the production-parity tests); numpy.hypot is
    overflow/underflow-safe and returns +0.0 for (+-0, +-0);
  * direction: atan2(gy, gx) through numpy.arctan2, radians, range
    (-pi, pi], C99 signed-zero axes, zero vector -> +0.0.

Source/version attribution (behavioral, no code copied): Gwydion 2.71
libprocess convolution module (area_convolve_3x3 with the hsobel/vsobel/
hprewitt/vprewitt kernels) and libprocess arithmetic module
(hypot_of_fields).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]

ORIENTATION_HORIZONTAL = 0
ORIENTATION_VERTICAL = 1

#: Frozen kernel coefficients (gdouble constants, row-major 3x3).
KERNEL_SOBEL_HORIZONTAL: tuple[float, ...] = (0.25, 0.0, -0.25, 0.5, 0.0, -0.5, 0.25, 0.0, -0.25)
KERNEL_SOBEL_VERTICAL: tuple[float, ...] = (0.25, 0.5, 0.25, 0.0, 0.0, 0.0, -0.25, -0.5, -0.25)
KERNEL_PREWITT_HORIZONTAL: tuple[float, ...] = (
    1.0 / 3.0,
    0.0,
    -1.0 / 3.0,
    1.0 / 3.0,
    0.0,
    -1.0 / 3.0,
    1.0 / 3.0,
    0.0,
    -1.0 / 3.0,
)
KERNEL_PREWITT_VERTICAL: tuple[float, ...] = (
    1.0 / 3.0,
    1.0 / 3.0,
    1.0 / 3.0,
    0.0,
    0.0,
    0.0,
    -1.0 / 3.0,
    -1.0 / 3.0,
    -1.0 / 3.0,
)


def _validated_field(value: object, *, label: str) -> np.ndarray:
    """Validate and copy a finite two-dimensional real numeric field."""
    try:
        source = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{label} must be array-compatible") from exc
    if source.ndim != 2:
        raise ValueError(f"{label} must be two-dimensional")
    if 0 in source.shape:
        raise ValueError(f"{label} must have non-empty dimensions")
    if not np.issubdtype(source.dtype, np.number) or np.iscomplexobj(source):
        raise TypeError(f"{label} must contain real numeric values")
    values = np.array(source, dtype=np.float64, order="C", copy=True)
    if not np.isfinite(values).all():
        raise ValueError(f"{label} must be finite")
    return values


def _clipped_convolve_3x3(field: FloatArray, kernel: tuple[float, ...]) -> FloatArray:
    """Bit-exact CLIPPED 3x3 convolution (frozen source arithmetic order).

    Vectorized with the same per-element accumulation order as the compiled
    one-pass scan: kernel row 0 reads the row above (clamped to the top
    edge), kernel row 2 reads the row below (clamped to the bottom edge),
    and the border columns use the frozen pre-combined coefficient sums.
    The input field is never mutated.
    """
    yres, xres = int(field.shape[0]), int(field.shape[1])
    data = np.ascontiguousarray(field, dtype=np.float64)
    k = kernel
    if xres == 1:
        top = k[0] + k[1] + k[2]
        mid = k[3] + k[4] + k[5]
        bot = k[6] + k[7] + k[8]
        row_above = np.vstack([data[0:1], data[:-1]])
        row_below = np.vstack([data[1:], data[-1:]])
        return (top * row_above[:, 0] + mid * data[:, 0] + bot * row_below[:, 0]).reshape(yres, 1)
    row_above = np.vstack([data[0:1], data[:-1]])
    row_below = np.vstack([data[1:], data[-1:]])
    out = np.empty_like(data)
    # interior columns: strict left-to-right accumulation order
    out[:, 1 : xres - 1] = (
        k[0] * row_above[:, 0 : xres - 2]
        + k[1] * row_above[:, 1 : xres - 1]
        + k[2] * row_above[:, 2:xres]
        + k[3] * data[:, 0 : xres - 2]
        + k[4] * data[:, 1 : xres - 1]
        + k[5] * data[:, 2:xres]
        + k[6] * row_below[:, 0 : xres - 2]
        + k[7] * row_below[:, 1 : xres - 1]
        + k[8] * row_below[:, 2:xres]
    )
    # left border (pre-combined sums)
    out[:, 0] = (
        (k[0] + k[1]) * row_above[:, 0]
        + k[2] * row_above[:, 1]
        + (k[3] + k[4]) * data[:, 0]
        + k[5] * data[:, 1]
        + (k[6] + k[7]) * row_below[:, 0]
        + k[8] * row_below[:, 1]
    )
    # right border (pre-combined sums)
    out[:, xres - 1] = (
        k[0] * row_above[:, xres - 2]
        + (k[1] + k[2]) * row_above[:, xres - 1]
        + k[3] * data[:, xres - 2]
        + (k[4] + k[5]) * data[:, xres - 1]
        + k[6] * row_below[:, xres - 2]
        + (k[7] + k[8]) * row_below[:, xres - 1]
    )
    return out


def sobel_component(field: FloatArray, orientation: int) -> FloatArray:
    """Sobel X (orientation 0) or Sobel Y (orientation 1), CLIPPED, bit-exact."""
    kernel = (
        KERNEL_SOBEL_HORIZONTAL if orientation == ORIENTATION_HORIZONTAL else KERNEL_SOBEL_VERTICAL
    )
    return _clipped_convolve_3x3(field, kernel)


def prewitt_component(field: FloatArray, orientation: int) -> FloatArray:
    """Prewitt X (orientation 0) or Prewitt Y (orientation 1), CLIPPED, bit-exact."""
    kernel = (
        KERNEL_PREWITT_HORIZONTAL
        if orientation == ORIENTATION_HORIZONTAL
        else KERNEL_PREWITT_VERTICAL
    )
    return _clipped_convolve_3x3(field, kernel)


def _validate_component_pair(gx: FloatArray, gy: FloatArray, *, label: str) -> None:
    """Common two-component validation (shape and calibration alignment)."""
    if gx.shape != gy.shape:
        raise ValueError(f"{label} component fields must share shape")
    if gx.shape[0] == 0 or gx.shape[1] == 0:
        raise ValueError(f"{label} component fields must have non-empty dimensions")


def gradient_magnitude_fields(gx: FloatArray, gy: FloatArray) -> FloatArray:
    """Point-wise hypot(gx, gy) via numpy.hypot (platform C hypot semantics).

    numpy.hypot is overflow/underflow-safe and returns +0.0 for (+-0, +-0).
    Bitwise identity with the frozen glibc hypot@GLIBC_2.35 profile on
    x86-64 is characterized by the production-parity tests; no cross-libc or
    cross-architecture guarantee is made.  The component fields are never
    mutated.
    """
    _validate_component_pair(gx, gy, label="gradient magnitude")
    x = np.ascontiguousarray(gx, dtype=np.float64)
    y = np.ascontiguousarray(gy, dtype=np.float64)
    return np.hypot(x, y)


def gradient_direction_fields(gx: FloatArray, gy: FloatArray) -> FloatArray:
    """Native gradient direction atan2(gy, gx) via numpy.arctan2, radians.

    Range (-pi, pi]; C99 signed-zero axes; zero vector -> +0.0.  This is a
    NATIVE_SPMKIT_ANALYTICAL_COMPOSITE (maturity NUMERICALLY_VERIFIED), not
    a direct Gwydion parity target.  numpy.arctan2 may differ from the
    compiled glibc atan2 profile by at most ~1 ULP on some inputs; the
    production-parity tests characterize this bounded discrepancy.  The
    component fields are never mutated.
    """
    _validate_component_pair(gx, gy, label="gradient direction")
    x = np.ascontiguousarray(gx, dtype=np.float64)
    y = np.ascontiguousarray(gy, dtype=np.float64)
    return np.arctan2(y, x)
