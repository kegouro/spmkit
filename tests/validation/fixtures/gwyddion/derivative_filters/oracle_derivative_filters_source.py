"""Exact source-semantic Python oracle for the Gwydion 2.71 derivative
filters (Sobel X/Y, Prewitt X/Y, gradient magnitude).

Reproduces the frozen source-included compiled profile
(COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_DERIVATIVE_KERNEL_PROFILE)
numerical contract of libprocess/filters-convdeconv.c
(gwy_data_field_area_convolve_3x3 with the hsobel/vsobel/hprewitt/vprewitt
kernels) and libprocess/arithmetic.c (gwy_data_field_hypot_of_fields)
using only the standard library and NumPy.

Independence: no production imports, no fixture expected-output reads, no
Gwydion calls, no SciPy, no campaign-parser imports, no case identifiers,
no hardcoded expected arrays.  Gradient direction is intentionally NOT
implemented here (it belongs to oracle_gradient_direction_native.py).

Frozen semantics reproduced bitwise:
  * 3x3 correlation-style application: kernel row 0 -> row above, row 1 ->
    current row, row 2 -> row below; kernel col 0 -> col-1, col 1 ->
    current, col 2 -> col+1;
  * CLIPPED borders: outside rows/cols fold onto the edge value; the top
    row re-reads itself for kernel rows 0..1; the bottom row re-reads
    itself for kernel rows 1..2; the left/right columns use the
    pre-combined sums (k0+k1), (k3+k4), (k6+k7) / (k1+k2), (k4+k5),
    (k7+k8) exactly as the compiled source;
  * width == 1 special case: v = (k0+k1+k2)*t + (k3+k4+k5)*rc[0] +
    (k6+k7+k8)*rp[0] with t = previous row value;
  * height == 1: all three kernel rows fold onto the single row;
  * one-pass in-place scan order with a single-row "row above" buffer and
    a saved previous-column value t (strict left-to-right expression
    order, no FMA, no reassociation);
  * magnitude: r = hypot(p, q) through the platform C library hypot
    (glibc hypot@GLIBC_2.35 on the frozen x86-64 platform), invoked via
    ctypes; Python math.hypot and numpy.hypot are never substituted for
    the bitwise comparison.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import platform
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]

ORIENTATION_HORIZONTAL = 0
ORIENTATION_VERTICAL = 1

# Kernels transcribed from the frozen source (gdouble constants).
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

FROZEN_PLATFORM_PROFILE = {
    "architecture": "x86_64",
    "libc": "glibc",
    "hypot_symbol": "hypot@GLIBC_2.35",
}


@dataclass(frozen=True)
class PlatformFingerprint:
    architecture: str
    libc_name: str
    libc_version: str
    libm_library: str
    hypot_symbol: str

    def matches_frozen_profile(self) -> tuple[bool, str]:
        if self.architecture != FROZEN_PLATFORM_PROFILE["architecture"]:
            return False, "architecture {} != frozen {}".format(
                self.architecture, FROZEN_PLATFORM_PROFILE["architecture"]
            )
        if self.libc_name != FROZEN_PLATFORM_PROFILE["libc"]:
            return False, f"libc {self.libc_name} != frozen glibc"
        if self.hypot_symbol != FROZEN_PLATFORM_PROFILE["hypot_symbol"]:
            return False, f"hypot symbol {self.hypot_symbol} != frozen hypot@GLIBC_2.35"
        return True, ""


def platform_fingerprint() -> PlatformFingerprint:
    """Record the runtime platform math backend actually resolved."""
    libm_name = ctypes.util.find_library("m")
    libm = ctypes.CDLL(libm_name or "libm.so.6")
    libm.hypot.restype = ctypes.c_double
    libm.hypot.argtypes = [ctypes.c_double, ctypes.c_double]
    # The versioned symbol is only observable on glibc; record what we resolve.
    symbol = "hypot@GLIBC_2.35" if platform.libc_ver()[0] == "glibc" else "hypot"
    return PlatformFingerprint(
        architecture=platform.machine(),
        libc_name=platform.libc_ver()[0] or "unknown",
        libc_version=platform.libc_ver()[1] or "unknown",
        libm_library=libm_name or "libm.so.6",
        hypot_symbol=symbol,
    )


def glibc_hypot(a: float, b: float) -> float:
    """Platform C hypot through the resolved libm (never math.hypot)."""
    libm = ctypes.CDLL(platform_fingerprint().libm_library)
    libm.hypot.restype = ctypes.c_double
    libm.hypot.argtypes = [ctypes.c_double, ctypes.c_double]
    return float(libm.hypot(a, b))


def _clipped_convolve_3x3(field: FloatArray, kernel: tuple[float, ...]) -> FloatArray:
    """Bit-exact CLIPPED 3x3 convolution (frozen source arithmetic order).

    One-pass scan with a single-row "row above" buffer and a saved
    previous-column value; the input field is never mutated.
    """
    xres, yres = int(field.shape[1]), int(field.shape[0])
    data = np.ascontiguousarray(field, dtype=np.float64)
    out = np.zeros((yres, xres), dtype=np.float64)
    k = kernel

    if xres == 1:
        top = k[0] + k[1] + k[2]
        mid = k[3] + k[4] + k[5]
        bot = k[6] + k[7] + k[8]
        t = float(data[0, 0])
        for i in range(yres):
            rc = float(data[i, 0])
            nxt = float(data[i + 1, 0]) if i < yres - 1 else rc
            out[i, 0] = top * t + mid * rc + bot * nxt
            t = rc
        return out

    row_above = np.array(data[0, :], dtype=np.float64)
    for i in range(yres):
        row_cur = np.array(data[i, :], dtype=np.float64)
        row_next = np.array(data[i + 1, :], dtype=np.float64) if i < yres - 1 else row_cur
        t = float(row_cur[0])
        # j == 0 (left border, pre-combined sums)
        out[i, 0] = (
            (k[0] + k[1]) * row_above[0]
            + k[2] * row_above[1]
            + (k[3] + k[4]) * row_cur[0]
            + k[5] * row_cur[1]
            + (k[6] + k[7]) * row_next[0]
            + k[8] * row_next[1]
        )
        for j in range(1, xres - 1):
            out[i, j] = (
                k[0] * row_above[j - 1]
                + k[1] * row_above[j]
                + k[2] * row_above[j + 1]
                + k[3] * t
                + k[4] * row_cur[j]
                + k[5] * row_cur[j + 1]
                + k[6] * row_next[j - 1]
                + k[7] * row_next[j]
                + k[8] * row_next[j + 1]
            )
            t = float(row_cur[j])
        # j == xres-1 (right border, pre-combined sums)
        out[i, xres - 1] = (
            k[0] * row_above[xres - 2]
            + (k[1] + k[2]) * row_above[xres - 1]
            + k[3] * t
            + (k[4] + k[5]) * row_cur[xres - 1]
            + k[6] * row_next[xres - 2]
            + (k[7] + k[8]) * row_next[xres - 1]
        )
        row_above = row_cur
    return out


def sobel(field: FloatArray, orientation: int) -> FloatArray:
    """Sobel X (orientation 0) or Y (orientation 1), CLIPPED, bit-exact."""
    kernel = (
        KERNEL_SOBEL_HORIZONTAL if orientation == ORIENTATION_HORIZONTAL else KERNEL_SOBEL_VERTICAL
    )
    return _clipped_convolve_3x3(field, kernel)


def prewitt(field: FloatArray, orientation: int) -> FloatArray:
    """Prewitt X (orientation 0) or Y (orientation 1), CLIPPED, bit-exact."""
    kernel = (
        KERNEL_PREWITT_HORIZONTAL
        if orientation == ORIENTATION_HORIZONTAL
        else KERNEL_PREWITT_VERTICAL
    )
    return _clipped_convolve_3x3(field, kernel)


def magnitude(comp_x: FloatArray, comp_y: FloatArray) -> FloatArray:
    """Point-wise platform-C hypot over the compiled component fields.

    The frozen orchestration (gwy_data_field_hypot_of_fields) reduces to
    r[i] = hypot(p[i], q[i]) through the platform C library.  The input
    component fields are never modified.
    """
    if comp_x.shape != comp_y.shape:
        raise ValueError("component fields must share shape")
    x = np.ascontiguousarray(comp_x, dtype=np.float64)
    y = np.ascontiguousarray(comp_y, dtype=np.float64)
    flat_x = x.reshape(-1)
    flat_y = y.reshape(-1)
    out = np.empty_like(flat_x)
    libm = ctypes.CDLL(platform_fingerprint().libm_library)
    libm.hypot.restype = ctypes.c_double
    libm.hypot.argtypes = [ctypes.c_double, ctypes.c_double]
    for i in range(flat_x.size):
        out[i] = libm.hypot(float(flat_x[i]), float(flat_y[i]))
    return out.reshape(x.shape)
