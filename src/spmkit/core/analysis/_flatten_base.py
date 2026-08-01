"""Pure numerical building blocks for automated flat-base levelling."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class HeightDistribution:
    """Height-distribution data compatible with Gwyddion's convention."""

    centers: np.ndarray
    density: np.ndarray
    bin_width: float
    minimum: float
    maximum: float
    sample_count: int


def _gwyddion_height_distribution(data: np.ndarray) -> HeightDistribution:
    """Return a Gwyddion-compatible automatic height distribution."""
    array = np.asarray(data)

    if np.iscomplexobj(array):
        raise TypeError("height distribution requires real-valued data")
    if array.ndim != 2:
        raise ValueError("height distribution requires a two-dimensional array")
    if array.size == 0:
        raise ValueError("height distribution requires at least one value")

    try:
        values = np.asarray(array, dtype=float)
    except (TypeError, ValueError) as exc:
        raise TypeError("height distribution requires numeric data") from exc

    if not np.all(np.isfinite(values)):
        raise ValueError("height distribution requires finite data")

    sample_count = int(values.size)
    bin_count = max(
        2,
        int(np.floor(3.49 * np.cbrt(sample_count) + 0.5)),
    )

    minimum = float(np.min(values))
    maximum = float(np.max(values))
    density = np.zeros(bin_count, dtype=float)

    if minimum == maximum:
        histogram_range = abs(maximum) if minimum != 0.0 else 1.0
        bin_width = histogram_range / bin_count
        centers = (np.arange(bin_count, dtype=float) + 0.5) * bin_width
        density[0] = bin_count / histogram_range
    else:
        histogram_range = maximum - minimum
        bin_width = histogram_range / bin_count
        centers = minimum + (np.arange(bin_count, dtype=float) + 0.5) * bin_width

        flat_values = values.ravel()
        indices = np.floor(
            (flat_values - minimum) * bin_count / histogram_range
        ).astype(np.intp)

        indices[flat_values == maximum] = bin_count - 1
        valid = (indices >= 0) & (indices < bin_count)

        counts = np.bincount(
            indices[valid],
            minlength=bin_count,
        ).astype(float)

        counted = int(np.count_nonzero(valid))
        density = counts * bin_count / (histogram_range * max(counted, 1))

    centers.setflags(write=False)
    density.setflags(write=False)

    return HeightDistribution(
        centers=centers,
        density=density,
        bin_width=float(bin_width),
        minimum=minimum,
        maximum=maximum,
        sample_count=sample_count,
    )
