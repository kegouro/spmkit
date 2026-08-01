"""Pure numerical building blocks for automated flat-base levelling."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares


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


@dataclass(frozen=True)
class BasePeakFit:
    """Result and identifiability diagnostics for a Gaussian base peak."""

    mean: float
    rms: float
    offset: float
    amplitude: float
    width: float
    residual_norm: float
    solver_success: bool
    covariance_available: bool
    evaluations: int
    jacobian_rank: int
    condition_estimate: float

    @property
    def success(self) -> bool:
        """Whether the fitted peak is both converged and identifiable."""
        return self.solver_success and self.covariance_available


def _fit_base_peak(window: BasePeakWindow) -> BasePeakFit:
    """Fit Gwyddion's Gaussian parameterization to a selected peak window."""
    centers = np.asarray(window.centers, dtype=float)
    density = np.asarray(window.density, dtype=float)

    if centers.ndim != 1 or density.ndim != 1:
        raise ValueError("base peak fitting requires one-dimensional data")
    if centers.size != density.size:
        raise ValueError("base peak fitting requires matching centers and density")
    if centers.size < 4:
        raise ValueError("base peak fitting requires at least four samples")
    if not np.all(np.isfinite(centers)) or not np.all(np.isfinite(density)):
        raise ValueError("base peak fitting requires finite data")

    initial_width = abs(float(window.initial_width))
    initial = np.array(
        [
            window.initial_mean,
            window.initial_offset,
            window.initial_amplitude,
            initial_width,
        ],
        dtype=float,
    )

    if not np.all(np.isfinite(initial)):
        raise ValueError("base peak fitting requires finite initial parameters")
    if initial_width == 0.0:
        raise ValueError("base peak fitting requires a non-zero initial width")

    coordinate_span = max(float(np.ptp(centers)), 1.0)
    width_floor = np.finfo(float).eps * coordinate_span

    def gaussian_components(
        parameters: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, float]:
        mean, _, _, width = parameters
        safe_width = float(width)

        if abs(safe_width) < width_floor:
            safe_width = np.copysign(
                width_floor,
                safe_width if safe_width != 0.0 else 1.0,
            )

        delta = centers - mean
        scaled = delta / safe_width
        exponential = np.exp(-np.square(scaled))
        return exponential, scaled, safe_width

    def residuals(parameters: np.ndarray) -> np.ndarray:
        _, offset, amplitude, _ = parameters
        exponential, _, _ = gaussian_components(parameters)
        return offset + amplitude * exponential - density

    def jacobian(parameters: np.ndarray) -> np.ndarray:
        _, _, amplitude, _ = parameters
        exponential, scaled, safe_width = gaussian_components(parameters)

        return np.column_stack(
            (
                2.0 * amplitude * exponential * scaled / safe_width,
                np.ones_like(centers),
                exponential,
                2.0 * amplitude * exponential * np.square(scaled) / safe_width,
            )
        )

    def rank_and_condition(matrix: np.ndarray) -> tuple[int, float]:
        singular_values = np.linalg.svd(matrix, compute_uv=False)

        if singular_values.size == 0 or singular_values[0] == 0.0:
            return 0, float("inf")

        tolerance = (
            np.finfo(float).eps
            * max(matrix.shape)
            * singular_values[0]
        )
        rank = int(np.count_nonzero(singular_values > tolerance))

        if rank < 4 or singular_values[-1] <= tolerance:
            return rank, float("inf")

        return rank, float(singular_values[0] / singular_values[-1])

    density_scale = max(float(np.max(np.abs(density))), 1.0)
    constant_tolerance = 32.0 * np.finfo(float).eps * density_scale

    if float(np.ptp(density)) <= constant_tolerance:
        parameters = np.array(
            [
                window.initial_mean,
                float(np.mean(density)),
                0.0,
                initial_width,
            ],
            dtype=float,
        )
        jacobian_rank, condition_estimate = rank_and_condition(
            jacobian(parameters)
        )

        return BasePeakFit(
            mean=float(parameters[0]),
            rms=initial_width / np.sqrt(2.0),
            offset=float(parameters[1]),
            amplitude=0.0,
            width=initial_width,
            residual_norm=float(np.linalg.norm(residuals(parameters))),
            solver_success=False,
            covariance_available=False,
            evaluations=0,
            jacobian_rank=jacobian_rank,
            condition_estimate=condition_estimate,
        )

    solution = least_squares(
        residuals,
        initial,
        jac=jacobian,
        method="lm",
        ftol=1e-12,
        xtol=1e-12,
        gtol=1e-12,
        max_nfev=2000,
    )

    parameters = np.asarray(solution.x, dtype=float)
    width = abs(float(parameters[3]))
    jacobian_rank, condition_estimate = rank_and_condition(
        np.asarray(solution.jac, dtype=float)
    )

    solver_success = bool(
        solution.success
        and np.all(np.isfinite(parameters))
        and np.all(np.isfinite(solution.fun))
    )
    covariance_available = bool(
        solver_success
        and jacobian_rank == 4
        and width > width_floor
    )

    return BasePeakFit(
        mean=float(parameters[0]),
        rms=width / np.sqrt(2.0),
        offset=float(parameters[1]),
        amplitude=float(parameters[2]),
        width=width,
        residual_norm=float(np.linalg.norm(solution.fun)),
        solver_success=solver_success,
        covariance_available=covariance_available,
        evaluations=int(solution.nfev),
        jacobian_rank=jacobian_rank,
        condition_estimate=condition_estimate,
    )


@dataclass(frozen=True)
class BasePeakEstimate:
    """Complete base-peak estimate with intermediate numerical evidence."""

    distribution: HeightDistribution
    window: BasePeakWindow
    fit: BasePeakFit

    @property
    def success(self) -> bool:
        """Whether the Gaussian base peak is identifiable."""
        return self.fit.success

    @property
    def mean(self) -> float:
        """Fitted base-peak position."""
        return self.fit.mean

    @property
    def rms(self) -> float:
        """Fitted base-peak RMS width."""
        return self.fit.rms


def _estimate_base_peak(data: np.ndarray) -> BasePeakEstimate:
    """Estimate the dominant base peak from a two-dimensional field."""
    distribution = _gwyddion_height_distribution(data)
    window = _select_base_peak_window(distribution)
    fit = _fit_base_peak(window)

    return BasePeakEstimate(
        distribution=distribution,
        window=window,
        fit=fit,
    )
