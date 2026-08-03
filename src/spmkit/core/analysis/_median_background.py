"""Private numerical kernel for Gwyddion 2.71 Median Background.

This module reproduces the frozen pixel-domain semantics independently with
NumPy.  It deliberately has no public adapter: the future public API owns
channels, metadata, and result objects.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int_]
_GwyddionMedianBackgroundBackend = Literal["direct", "radixtree"]


@dataclass(frozen=True)
class _MedianBackgroundKernelSpec:
    """Immutable discrete-kernel specification for Median Background."""

    radius_px: int
    kernel_resolution: int
    kernel_active_count: int
    rank_index: int
    rank_backend_reference: _GwyddionMedianBackgroundBackend


def _validated_median_background_radius(radius_px: object) -> int:
    """Return a Gwyddion Median Background radius in the frozen range."""
    if isinstance(radius_px, (bool, np.bool_)):
        raise TypeError(
            "Gwyddion Median Background radius_px must be a Python or NumPy "
            "integer scalar; booleans are not valid"
        )
    if not isinstance(radius_px, (int, np.integer)):
        raise TypeError(
            "Gwyddion Median Background radius_px must be a Python or NumPy "
            "integer scalar; booleans are not valid"
        )

    radius = int(radius_px)
    if not 1 <= radius <= 1024:
        raise ValueError(
            "Gwyddion Median Background radius_px must be in the inclusive " "range 1..1024"
        )

    return radius


def _validated_median_background_data(data: object) -> FloatArray:
    """Return a finite, non-empty, C-contiguous float64 copy of 2D data."""
    try:
        source = np.asarray(data)
    except (TypeError, ValueError) as exc:
        raise TypeError("Gwyddion Median Background requires array-compatible data") from exc

    if source.ndim != 2:
        raise ValueError("Gwyddion Median Background requires two-dimensional data")
    if 0 in source.shape:
        raise ValueError("Gwyddion Median Background requires non-empty dimensions")
    if (
        not np.issubdtype(source.dtype, np.number)
        or np.iscomplexobj(source)
        or isinstance(data, (bool, np.bool_))
    ):
        raise TypeError("Gwyddion Median Background requires real numeric data")

    values = np.array(source, dtype=np.float64, order="C", copy=True)
    if not np.all(np.isfinite(values)):
        raise ValueError("Gwyddion Median Background requires finite data")

    return values


@lru_cache(maxsize=8)
def _cached_median_background_active_offsets(radius_px: int) -> IntArray:
    """Build read-only active offsets in the frozen row-major order."""
    diameter = 2 * radius_px + 1
    radius_square = diameter * diameter

    active_count = 0
    max_columns_by_row: list[int] = []
    for dr in range(-radius_px, radius_px + 1):
        remaining = radius_square - 4 * dr * dr
        max_abs_dc = math.isqrt(remaining // 4)
        max_columns_by_row.append(max_abs_dc)
        active_count += 2 * max_abs_dc + 1

    offsets = np.empty((active_count, 2), dtype=np.int_, order="C")
    position = 0
    for dr, max_abs_dc in zip(range(-radius_px, radius_px + 1), max_columns_by_row, strict=True):
        row_count = 2 * max_abs_dc + 1
        stop = position + row_count
        offsets[position:stop, 0] = dr
        offsets[position:stop, 1] = np.arange(-max_abs_dc, max_abs_dc + 1, dtype=np.int_)
        position = stop

    if position != active_count:
        raise RuntimeError("Gwyddion Median Background offset count is inconsistent")
    if active_count % 2 != 1:
        raise RuntimeError("Gwyddion Median Background active count must be odd")
    if not np.array_equal(offsets[active_count // 2], np.array([0, 0], dtype=np.int_)):
        raise RuntimeError("Gwyddion Median Background offsets must contain the centre")
    if not offsets.flags.c_contiguous:
        raise RuntimeError("Gwyddion Median Background offsets must be C-contiguous")

    offsets.setflags(write=False)
    return offsets


def _median_background_active_offsets(radius_px: object) -> IntArray:
    """Return cached active digital-ellipse offsets for ``radius_px``."""
    return _cached_median_background_active_offsets(_validated_median_background_radius(radius_px))


def _median_background_kernel_spec(radius_px: object) -> _MedianBackgroundKernelSpec:
    """Construct the immutable Gwyddion Median Background kernel specification."""
    radius = _validated_median_background_radius(radius_px)
    active_count = _cached_median_background_active_offsets(radius).shape[0]
    backend: _GwyddionMedianBackgroundBackend = "direct" if active_count <= 25 else "radixtree"

    return _MedianBackgroundKernelSpec(
        radius_px=radius,
        kernel_resolution=2 * radius + 1,
        kernel_active_count=active_count,
        rank_index=active_count // 2,
        rank_backend_reference=backend,
    )


def _gwyddion_median_background_result(
    data: object,
    radius_px: object,
) -> tuple[FloatArray, FloatArray, _MedianBackgroundKernelSpec]:
    """Calculate frozen Gwyddion 2.71 Median Background fields.

    Exterior samples are clamped to the nearest valid edge pixel.  The
    selected rank is found independently with :func:`numpy.partition`; no
    Gwyddion selection data structure is reproduced.
    """
    values = _validated_median_background_data(data)
    spec = _median_background_kernel_spec(radius_px)
    offsets = _cached_median_background_active_offsets(spec.radius_px)
    yres, xres = values.shape

    row_indices = np.clip(
        np.arange(yres, dtype=np.int_)[:, np.newaxis] + offsets[np.newaxis, :, 0],
        0,
        yres - 1,
    )
    column_indices = np.clip(
        np.arange(xres, dtype=np.int_)[:, np.newaxis] + offsets[np.newaxis, :, 1],
        0,
        xres - 1,
    )

    background = np.empty(values.shape, dtype=np.float64, order="C")
    for row in range(yres):
        for column in range(xres):
            samples = values[row_indices[row], column_indices[column]]
            background[row, column] = np.partition(samples, spec.rank_index)[spec.rank_index]

    corrected = np.array(values - background, dtype=np.float64, order="C", copy=True)
    return background, corrected, spec
