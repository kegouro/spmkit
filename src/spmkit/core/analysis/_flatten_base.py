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


@dataclass(frozen=True)
class BasePeakWindow:
    """Histogram window and initial parameters for base-peak fitting."""

    centers: np.ndarray
    density: np.ndarray
    peak_index: int
    start_index: int
    stop_index: int
    initial_mean: float
    initial_offset: float
    initial_amplitude: float
    initial_width: float


def _select_base_peak_window(
    distribution: HeightDistribution,
) -> BasePeakWindow:
    """Select Gwyddion's local histogram window around the dominant peak."""
    centers = np.asarray(distribution.centers, dtype=float)
    density = np.asarray(distribution.density, dtype=float)

    if centers.ndim != 1 or density.ndim != 1:
        raise ValueError("base peak estimation requires one-dimensional histogram data")
    if centers.size != density.size:
        raise ValueError("base peak estimation requires matching centers and density")
    if centers.size < 7:
        raise ValueError(
            "base peak estimation requires at least seven histogram bins"
        )
    if not np.all(np.isfinite(centers)) or not np.all(np.isfinite(density)):
        raise ValueError("base peak estimation requires finite histogram data")
    if not np.isfinite(distribution.bin_width) or distribution.bin_width <= 0.0:
        raise ValueError("base peak estimation requires a positive bin width")

    peak_index = int(np.argmax(density))
    peak_height = float(density[peak_index])

    if peak_height <= 0.0:
        raise ValueError("base peak estimation requires a positive histogram peak")

    threshold = 0.3 * peak_height

    start_index = peak_index
    while start_index > 0:
        if density[start_index] < threshold:
            break
        start_index -= 1

    end_index = peak_index
    last_index = density.size - 1
    while end_index < last_index:
        if density[end_index] < threshold:
            break
        end_index += 1

    sample_count = end_index + 1 - start_index
    while sample_count < 7:
        if start_index > 0:
            start_index -= 1
        if end_index < last_index:
            end_index += 1
        sample_count = end_index + 1 - start_index

    stop_index = end_index + 1
    selected_centers = np.array(
        centers[start_index:stop_index],
        dtype=float,
        copy=True,
    )
    selected_density = np.array(
        density[start_index:stop_index],
        dtype=float,
        copy=True,
    )

    selected_centers.setflags(write=False)
    selected_density.setflags(write=False)

    return BasePeakWindow(
        centers=selected_centers,
        density=selected_density,
        peak_index=peak_index,
        start_index=start_index,
        stop_index=stop_index,
        initial_mean=float(centers[peak_index]),
        initial_offset=0.0,
        initial_amplitude=peak_height,
        initial_width=0.3 * sample_count * float(distribution.bin_width),
    )
