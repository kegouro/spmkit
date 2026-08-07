"""Independent declarative oracle for the Gwydion 2.71 derivative filters.

Structurally independent from oracle_derivative_filters_source.py:
  * 3x3 stencil geometry expressed as explicit center-relative offsets;
  * clipped coordinate intersection computed per output pixel by clamping
    the stencil window to the field rectangle (no row-buffer scan);
  * its own coefficient tables, transcribed independently;
  * direct mathematical accumulation over the clipped window.

This oracle does NOT require bitwise agreement with the frozen source
arithmetic order (summation order differs by design).  It reports:
  * exact discrete-state agreement (values equal as IEEE numbers);
  * bitwise agreement;
  * finite rounding differences (count and max);
  * maximum absolute difference;
  * maximum output-relative ULP where finite;
  * signed-zero differences.

Independence: no imports of the source oracle, the direction oracle,
production code, fixtures, or campaign code; no case identifiers; no
fixture reads.

Relations provided (discrete, for the relation tests):
  * transpose relation (X derivative of A == Y derivative of A^T);
  * negation relation (filter(-A) == -filter(A));
  * constant relation (all four derivatives vanish on constant fields);
  * magnitude non-negativity;
  * magnitude symmetry under component exchange.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]

# Independent coefficient tables (transcribed separately from the source
# oracle; same frozen constants, different expression layout).
COEFF_SOBEL_X: tuple[tuple[float, float, float], ...] = (
    (0.25, 0.0, -0.25),
    (0.5, 0.0, -0.5),
    (0.25, 0.0, -0.25),
)
COEFF_SOBEL_Y: tuple[tuple[float, float, float], ...] = (
    (0.25, 0.5, 0.25),
    (0.0, 0.0, 0.0),
    (-0.25, -0.5, -0.25),
)
COEFF_PREWITT_X: tuple[tuple[float, float, float], ...] = (
    (1.0 / 3.0, 0.0, -1.0 / 3.0),
    (1.0 / 3.0, 0.0, -1.0 / 3.0),
    (1.0 / 3.0, 0.0, -1.0 / 3.0),
)
COEFF_PREWITT_Y: tuple[tuple[float, float, float], ...] = (
    (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
    (0.0, 0.0, 0.0),
    (-1.0 / 3.0, -1.0 / 3.0, -1.0 / 3.0),
)

# Stencil geometry: center-relative (dy, dx) offsets, row-major.
STENCIL_OFFSETS: tuple[tuple[int, int], ...] = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 0),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)


def _bits_of(value: float) -> int:
    return int(np.asarray(value, dtype=np.float64).view(np.uint64))


def clipped_window_indices(
    center_y: int, center_x: int, height: int, width: int
) -> list[tuple[int, int]]:
    """Clipped coordinate intersection of the 3x3 stencil with the field."""
    indices: list[tuple[int, int]] = []
    for dy, dx in STENCIL_OFFSETS:
        yy = center_y + dy
        xx = center_x + dx
        yy = 0 if yy < 0 else height - 1 if yy >= height else yy
        xx = 0 if xx < 0 else width - 1 if xx >= width else xx
        indices.append((yy, xx))
    return indices


def convolve_declarative(
    field: FloatArray, coeffs: tuple[tuple[float, float, float], ...]
) -> FloatArray:
    """Direct mathematical accumulation over clipped windows.

    Summation order: row-major over the stencil (differs from the frozen
    one-pass scan order, so bitwise identity is not guaranteed; discrete
    equality is).
    """
    height, width = int(field.shape[0]), int(field.shape[1])
    data = np.ascontiguousarray(field, dtype=np.float64)
    out = np.zeros((height, width), dtype=np.float64)
    for y in range(height):
        for x in range(width):
            acc = 0.0
            for idx, (dy, dx) in enumerate(STENCIL_OFFSETS):
                yy, xx = clipped_window_indices(y, x, height, width)[idx]
                acc = acc + coeffs[dy + 1][dx + 1] * float(data[yy, xx])
            out[y, x] = acc
    return out


def sobel_x_declarative(field: FloatArray) -> FloatArray:
    return convolve_declarative(field, COEFF_SOBEL_X)


def sobel_y_declarative(field: FloatArray) -> FloatArray:
    return convolve_declarative(field, COEFF_SOBEL_Y)


def prewitt_x_declarative(field: FloatArray) -> FloatArray:
    return convolve_declarative(field, COEFF_PREWITT_X)


def prewitt_y_declarative(field: FloatArray) -> FloatArray:
    return convolve_declarative(field, COEFF_PREWITT_Y)


def compare_discrete(reference: FloatArray, computed: FloatArray) -> dict[str, float | int]:
    """Characterize the difference between two same-shape arrays.

    Returns exact discrete-state equality, bitwise equality, counts of
    finite rounding / signed-zero differences, max absolute difference and
    max output-relative ULP (where finite).
    """
    if reference.shape != computed.shape:
        raise ValueError("shape mismatch")
    ref = np.ascontiguousarray(reference, dtype=np.float64)
    cmp = np.ascontiguousarray(computed, dtype=np.float64)
    discrete_equal = bool(np.array_equal(ref, cmp, equal_nan=True))
    rb = ref.view(np.uint64).reshape(-1)
    cb = cmp.view(np.uint64).reshape(-1)
    bitwise_equal = bool(np.array_equal(rb, cb))
    n_finite_rounding = 0
    n_signed_zero = 0
    max_abs = 0.0
    max_ulp = 0.0
    for i in range(ref.size):
        a = float(ref.reshape(-1)[i])
        b = float(cmp.reshape(-1)[i])
        if rb[i] == cb[i]:
            continue
        if a == 0.0 and b == 0.0:
            n_signed_zero += 1
            continue
        if not (math.isfinite(a) and math.isfinite(b)):
            continue
        diff = abs(a - b)
        max_abs = max(max_abs, diff)
        scale = max(abs(a), abs(b))
        if scale > 0.0:
            ulp = scale * 2.0**-52
            max_ulp = max(max_ulp, diff / ulp)
        n_finite_rounding += 1
    return {
        "discrete_state_equal": discrete_equal,
        "bitwise_equal": bitwise_equal,
        "finite_rounding_differences": n_finite_rounding,
        "signed_zero_differences": n_signed_zero,
        "max_absolute_difference": max_abs,
        "max_output_relative_ulp": max_ulp,
    }


# --- discrete relations ----------------------------------------------------


def transpose_relation_holds(
    field: FloatArray,
    sobel_x_of: FloatArray,
    sobel_y_of_transpose: FloatArray,
) -> bool:
    """sobel_x(A) == transpose(sobel_y(A^T)) element-wise (discrete)."""
    return bool(np.array_equal(sobel_x_of, sobel_y_of_transpose.T))


def negation_relation_holds(computed_negated: FloatArray, negated_computed: FloatArray) -> bool:
    """filter(-A) == -filter(A) element-wise (discrete)."""
    return bool(np.array_equal(computed_negated, -negated_computed))


def constant_relation_holds(
    sobel_x: FloatArray, sobel_y: FloatArray, prewitt_x: FloatArray, prewitt_y: FloatArray
) -> bool:
    """All four derivatives vanish on constant fields (discrete)."""
    arrays = (sobel_x, sobel_y, prewitt_x, prewitt_y)
    return all(bool(np.all(arr == 0.0)) for arr in arrays)


def magnitude_nonnegative(comp_x: FloatArray, comp_y: FloatArray) -> bool:
    """hypot(px, py) >= 0 for every finite component pair (discrete)."""
    mag = np.hypot(comp_x, comp_y)
    return bool(np.all(mag >= 0.0))


def magnitude_swap_symmetric(comp_x: FloatArray, comp_y: FloatArray) -> bool:
    """hypot(a, b) == hypot(b, a) (discrete; numpy.hypot is symmetric)."""
    return bool(np.array_equal(np.hypot(comp_x, comp_y), np.hypot(comp_y, comp_x)))
