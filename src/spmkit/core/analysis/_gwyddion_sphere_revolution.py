"""Numerical kernels compatible with Gwyddion's Revolve Sphere operation.

This module implements the numerical semantics of the Gwyddion 2.71
``sphere-revolve`` process independently in NumPy.  It intentionally remains
separate from SPMKit's physical sphere-revolution estimator because the two
operations use different radius, scaling, and boundary conventions.
"""

from __future__ import annotations

import math
import sys

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


def _validated_data_array(data: object, operation: str) -> FloatArray:
    """Validate that input data is a real, finite, non-empty 2D array."""
    data_arr = np.asarray(data)

    if (
        data_arr.ndim != 2
        or data_arr.size == 0
        or not np.issubdtype(data_arr.dtype, np.number)
        or np.iscomplexobj(data_arr)
        or isinstance(data, (bool, np.bool_))
    ):
        raise TypeError(f"{operation} requires data to be a real 2D array")

    float_arr = np.array(data_arr, dtype=np.float64, order="C", copy=True)

    if not np.all(np.isfinite(float_arr)):
        raise ValueError(f"{operation} requires data to be finite")

    return float_arr


def _validated_radius(radius: object, operation: str) -> float:
    """Validate that radius is a real scalar finite number between 1.0 and 1000.0."""
    radius_arr = np.asarray(radius)

    if (
        radius_arr.ndim != 0
        or not np.issubdtype(radius_arr.dtype, np.number)
        or np.iscomplexobj(radius_arr)
        or isinstance(radius, (bool, np.bool_))
    ):
        raise TypeError(f"{operation} requires radius to be a real scalar")

    val = float(radius_arr.item())

    if not math.isfinite(val):
        raise ValueError(f"{operation} requires radius to be finite")

    if not 1.0 <= val <= 1000.0:
        raise ValueError(f"{operation} requires radius to be between 1.0 and 1000.0 samples")

    return val


def _validated_inverted(inverted: object, operation: str) -> bool:
    """Validate that inverted option is a boolean."""
    if not isinstance(inverted, (bool, np.bool_)):
        raise TypeError(f"{operation} requires inverted to be a boolean")
    return bool(inverted)


def _readonly_float_array(values: NDArray[np.float64]) -> FloatArray:
    """Return a C-contiguous, read-only float64 copy of the input array."""
    array = np.array(values, dtype=np.float64, order="C", copy=True)
    array.setflags(write=False)
    return array


def _gwyddion_sphere_background(
    data: FloatArray,
    radius: float,
) -> FloatArray:
    """Calculate Gwyddion 2.71 Sphere Revolution background on 2D float64 data.

    Parameters
    ----------
    data:
        Two-dimensional real finite float64 array.
    radius:
        Sphere radius in samples (1.0 through 1000.0).

    Returns
    -------
    numpy.ndarray
        Read-only C-contiguous float64 background matrix.
    """
    array = _validated_data_array(data, "_gwyddion_sphere_background")
    radius_val = _validated_radius(radius, "_gwyddion_sphere_background")

    yres, xres = array.shape

    # 1. Serial global mean (C-order)
    total = 0.0
    for value in array.ravel(order="C"):
        total += float(value)
    mean = total / float(array.size)

    # 2. Serial global population RMS (C-order)
    sum2 = 0.0
    for value in array.ravel(order="C"):
        delta = float(value) - mean
        sum2 += delta * delta
    rms = math.sqrt(sum2 / float(array.size))

    # 3. Global scaling parameter q
    q = rms / math.sqrt(5.0 / 6.0)

    # 4. Discrete sphere dimensions
    sphere_size = math.floor(min(radius_val, float(xres)) + 0.5)
    sphere_resolution = 2 * sphere_size + 1
    local_filter_size = sphere_size // 2
    very_flat = (radius_val / 8.0) > float(xres)

    center = sphere_size
    sphere_z = np.zeros((sphere_resolution, sphere_resolution), dtype=np.float64, order="C")

    # 5. Discrete sphere construction (quadrant loop)
    for i in range(sphere_size + 1):
        u = i / radius_val
        for j in range(sphere_size + 1):
            v = j / radius_val
            r2 = u * u + v * v
            if very_flat:
                z = (r2 / 2.0) * (1.0 + (r2 / 4.0) * (1.0 + r2 / 2.0))
            else:
                z = 2.0 if r2 > 1.0 else 1.0 - math.sqrt(1.0 - r2)
            sphere_z[center - i, center - j] = z
            sphere_z[center - i, center + j] = z
            sphere_z[center + i, center - j] = z
            sphere_z[center + i, center + j] = z

    # Correction 1: explicit scalar loop scaling
    sphere_scaled = np.zeros(
        (sphere_resolution, sphere_resolution),
        dtype=np.float64,
        order="C",
    )
    for row in range(sphere_resolution):
        for column in range(sphere_resolution):
            sphere_scaled[row, column] = -q * float(sphere_z[row, column])

    # 6. Direct local mean field
    if local_filter_size == 0:
        local_mean = np.array(array, dtype=np.float64, order="C", copy=True)
    else:
        neg_ext = (local_filter_size - 1) // 2
        pos_ext = local_filter_size // 2
        local_mean = np.zeros((yres, xres), dtype=np.float64, order="C")
        for r in range(yres):
            r_start = max(0, r - neg_ext)
            r_stop = min(yres - 1, r + pos_ext)
            for c in range(xres):
                c_start = max(0, c - neg_ext)
                c_stop = min(xres - 1, c + pos_ext)
                sum_val = 0.0
                count = 0
                for rr in range(r_start, r_stop + 1):
                    for cc in range(c_start, c_stop + 1):
                        sum_val += float(array[rr, cc])
                        count += 1
                local_mean[r, c] = sum_val / float(count)

    # 7. Direct local RMS field
    if local_filter_size == 0:
        local_rms = np.array(array, dtype=np.float64, order="C", copy=True)
    elif local_filter_size == 1:
        local_rms = np.zeros((yres, xres), dtype=np.float64, order="C")
    else:
        neg_ext = (local_filter_size - 1) // 2
        pos_ext = local_filter_size // 2
        local_rms = np.zeros((yres, xres), dtype=np.float64, order="C")
        for r in range(yres):
            r_start = max(0, r - neg_ext)
            r_stop = min(yres - 1, r + pos_ext)
            for c in range(xres):
                c_start = max(0, c - neg_ext)
                c_stop = min(xres - 1, c + pos_ext)
                sum_val = 0.0
                sum_sq = 0.0
                count = 0
                for rr in range(r_start, r_stop + 1):
                    for cc in range(c_start, c_stop + 1):
                        val = float(array[rr, cc])
                        sum_val += val
                        sum_sq += val * val
                        count += 1
                m = sum_val / float(count)
                m_sq = sum_sq / float(count)
                var = m_sq - m * m
                if var < 0.0:
                    var = 0.0
                local_rms[r, c] = math.sqrt(var)

    # 8. Outlier-trimmed field T
    trimmed = np.zeros((yres, xres), dtype=np.float64, order="C")
    for r in range(yres):
        for c in range(xres):
            thresh = local_mean[r, c] - 2.5 * local_rms[r, c]
            val = float(array[r, c])
            trimmed[r, c] = thresh if thresh > val else val

    # 9. Two-dimensional lower envelope minimization
    bg = np.zeros((yres, xres), dtype=np.float64, order="C")
    for r in range(yres):
        for c in range(xres):
            ifrom = max(0, r - sphere_size) - r
            ito = min(r + sphere_size, yres - 1) - r
            jfrom = max(0, c - sphere_size) - c
            jto = min(c + sphere_size, xres - 1) - c
            minimum = sys.float_info.max
            for ii in range(ifrom, ito + 1):
                for jj in range(jfrom, jto + 1):
                    sph_val = float(sphere_scaled[center + ii, center + jj])
                    if sph_val >= -q:
                        data_val = float(trimmed[r + ii, c + jj])
                        cand = data_val - sph_val
                        if cand < minimum:
                            minimum = cand
            bg[r, c] = minimum

    return _readonly_float_array(bg)


def _gwyddion_sphere_result(
    data: FloatArray,
    radius: float,
    *,
    inverted: bool = False,
) -> tuple[FloatArray, FloatArray]:
    """Calculate Gwyddion 2.71 Sphere Revolution (background, corrected) tuple.

    Parameters
    ----------
    data:
        Two-dimensional real finite float64 array.
    radius:
        Sphere radius in samples (1.0 through 1000.0).
    inverted:
        Apply safe dual inversion ``-B(-data)``.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray]
        Read-only float64 (background, corrected) array pair.
    """
    array = _validated_data_array(data, "_gwyddion_sphere_result")
    _validated_radius(radius, "_gwyddion_sphere_result")
    inv_bool = _validated_inverted(inverted, "_gwyddion_sphere_result")

    if not inv_bool:
        bg_arr = _gwyddion_sphere_background(array, radius)
        bg_raw = np.asarray(bg_arr)
    else:
        negated = -array
        neg_bg = _gwyddion_sphere_background(negated, radius)
        bg_raw = -np.asarray(neg_bg)

    corr_raw = np.zeros(array.shape, dtype=np.float64, order="C")
    yres, xres = array.shape
    for r in range(yres):
        for c in range(xres):
            corr_raw[r, c] = float(array[r, c]) - float(bg_raw[r, c])

    return _readonly_float_array(bg_raw), _readonly_float_array(corr_raw)


def _gwyddion_sphere_corrected(
    data: FloatArray,
    radius: float,
    *,
    inverted: bool = False,
) -> FloatArray:
    """Calculate Gwyddion 2.71 Sphere Revolution corrected field.

    Parameters
    ----------
    data:
        Two-dimensional real finite float64 array.
    radius:
        Sphere radius in samples (1.0 through 1000.0).
    inverted:
        Apply safe dual inversion ``-B(-data)``.

    Returns
    -------
    numpy.ndarray
        Read-only C-contiguous float64 corrected matrix.
    """
    return _gwyddion_sphere_result(data, radius, inverted=inverted)[1]
