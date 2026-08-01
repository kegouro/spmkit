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


@dataclass(frozen=True)
class FacetPlaneEstimate:
    """Dominant-plane estimate using Gwyddion's facet weighting."""

    intercept: float
    x_coefficient: float
    y_coefficient: float
    physical_slope_x: float
    physical_slope_y: float
    slope_scale_squared: float
    cell_count: int
    weight_sum: float
    degenerate: bool


def _estimate_gwyddion_facet_plane(
    data: np.ndarray,
    *,
    pixel_size_x: float,
    pixel_size_y: float,
) -> FacetPlaneEstimate:
    """Estimate one dominant-plane correction without modifying the field."""
    array = np.asarray(data)

    if np.issubdtype(array.dtype, np.bool_):
        raise TypeError("facet-plane estimation requires real-valued data")
    if np.iscomplexobj(array):
        raise TypeError("facet-plane estimation requires real-valued data")
    if array.ndim != 2:
        raise ValueError("facet-plane estimation requires a two-dimensional array")
    if array.shape[0] < 2 or array.shape[1] < 2:
        raise ValueError("facet-plane estimation requires at least one pixel cell")

    try:
        values = np.asarray(array, dtype=float)
    except (TypeError, ValueError) as exc:
        raise TypeError("facet-plane estimation requires numeric data") from exc

    if not np.all(np.isfinite(values)):
        raise ValueError("facet-plane estimation requires finite data")

    def positive_pixel_size(value: float, *, name: str) -> float:
        if isinstance(value, (bool, np.bool_)) or np.iscomplexobj(value):
            raise TypeError(f"facet-plane estimation requires {name} to be real")

        try:
            scalar = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"facet-plane estimation requires {name} to be real"
            ) from exc

        if not np.isfinite(scalar) or scalar <= 0.0:
            raise ValueError(
                f"facet-plane estimation requires {name} to be positive"
            )

        return scalar

    dx = positive_pixel_size(pixel_size_x, name="pixel_size_x")
    dy = positive_pixel_size(pixel_size_y, name="pixel_size_y")

    x_slopes = (
        values[1:, 1:]
        + values[:-1, 1:]
        - values[1:, :-1]
        - values[:-1, :-1]
    ) / (2.0 * dx)

    y_slopes = (
        values[1:, :-1]
        + values[1:, 1:]
        - values[:-1, :-1]
        - values[:-1, 1:]
    ) / (2.0 * dy)

    if not np.all(np.isfinite(x_slopes)) or not np.all(np.isfinite(y_slopes)):
        raise ValueError("facet-plane estimation produced non-finite slopes")

    squared_slopes = np.square(x_slopes) + np.square(y_slopes)
    cell_count = int(squared_slopes.size)
    slope_scale_squared = float(np.mean(squared_slopes) / 20.0)

    if slope_scale_squared == 0.0:
        return FacetPlaneEstimate(
            intercept=0.0,
            x_coefficient=0.0,
            y_coefficient=0.0,
            physical_slope_x=0.0,
            physical_slope_y=0.0,
            slope_scale_squared=0.0,
            cell_count=cell_count,
            weight_sum=float(cell_count),
            degenerate=True,
        )

    weights = np.exp(-squared_slopes / slope_scale_squared)
    weight_sum = float(np.sum(weights))

    if not np.isfinite(weight_sum) or weight_sum <= 0.0:
        raise ValueError("facet-plane estimation produced invalid weights")

    physical_slope_x = float(np.sum(x_slopes * weights) / weight_sum)
    physical_slope_y = float(np.sum(y_slopes * weights) / weight_sum)

    x_coefficient = physical_slope_x * dx
    y_coefficient = physical_slope_y * dy
    rows, columns = values.shape
    intercept = -0.5 * (
        x_coefficient * columns
        + y_coefficient * rows
    )

    return FacetPlaneEstimate(
        intercept=float(intercept),
        x_coefficient=float(x_coefficient),
        y_coefficient=float(y_coefficient),
        physical_slope_x=physical_slope_x,
        physical_slope_y=physical_slope_y,
        slope_scale_squared=slope_scale_squared,
        cell_count=cell_count,
        weight_sum=weight_sum,
        degenerate=False,
    )


@dataclass(frozen=True)
class FacetStageIteration:
    """One facet correction and the base peak estimated afterwards."""

    index: int
    plane: FacetPlaneEstimate
    peak: BasePeakEstimate


@dataclass(frozen=True)
class FacetStageResult:
    """Result and evidence from the five-step Flatten Base facet stage."""

    corrected: np.ndarray
    background: np.ndarray
    initial_peak: BasePeakEstimate
    iterations: tuple[FacetStageIteration, ...]
    termination: str

    @property
    def completed_iterations(self) -> int:
        """Number of facet planes actually subtracted."""
        return len(self.iterations)


def _run_flatten_base_facet_stage(
    data: np.ndarray,
    *,
    pixel_size_x: float,
    pixel_size_y: float,
) -> FacetStageResult:
    """Run the facet-levelling stage used by Gwyddion Flatten Base."""
    array = np.asarray(data)

    if np.issubdtype(array.dtype, np.bool_) or np.iscomplexobj(array):
        raise TypeError("flatten-base facet stage requires real-valued data")
    if array.ndim != 2:
        raise ValueError(
            "flatten-base facet stage requires a two-dimensional array"
        )
    if array.shape[0] < 2 or array.shape[1] < 2:
        raise ValueError(
            "flatten-base facet stage requires at least one pixel cell"
        )

    try:
        working = np.array(array, dtype=float, copy=True)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            "flatten-base facet stage requires numeric data"
        ) from exc

    if not np.all(np.isfinite(working)):
        raise ValueError("flatten-base facet stage requires finite data")

    background = np.zeros_like(working)
    initial_peak = _estimate_base_peak(working)

    rows, columns = working.shape
    column_indices = np.arange(columns, dtype=float)
    row_indices = np.arange(rows, dtype=float)
    xx, yy = np.meshgrid(column_indices, row_indices)

    iterations: list[FacetStageIteration] = []
    termination = "maximum_iterations"

    for index in range(5):
        plane = _estimate_gwyddion_facet_plane(
            working,
            pixel_size_x=pixel_size_x,
            pixel_size_y=pixel_size_y,
        )

        if plane.degenerate:
            termination = "degenerate_plane"
            break

        plane_surface = (
            plane.intercept
            + plane.x_coefficient * xx
            + plane.y_coefficient * yy
        )

        if not np.all(np.isfinite(plane_surface)):
            raise ValueError(
                "flatten-base facet stage produced a non-finite plane"
            )

        working -= plane_surface
        background += plane_surface

        peak = _estimate_base_peak(working)
        iterations.append(
            FacetStageIteration(
                index=index,
                plane=plane,
                peak=peak,
            )
        )

        if not peak.success:
            termination = "peak_failure"
            break

    corrected = np.array(working, dtype=float, copy=True)
    accumulated_background = np.array(
        background,
        dtype=float,
        copy=True,
    )
    corrected.setflags(write=False)
    accumulated_background.setflags(write=False)

    return FacetStageResult(
        corrected=corrected,
        background=accumulated_background,
        initial_peak=initial_peak,
        iterations=tuple(iterations),
        termination=termination,
    )


def _grow_mask_conn4(
    mask: np.ndarray,
    *,
    radius: int,
) -> np.ndarray:
    """Reproduce Gwyddion 2.71 CONN4 mask growth.

    This intentionally follows ``gwy_data_field_grains_grow()`` with
    ``from_border=FALSE``, including its special image-border behaviour.
    It is therefore not equivalent to ordinary city-block dilation when
    grains are absent from, or touch, the field boundary.
    """
    values = np.asarray(mask)

    if values.ndim != 2:
        raise ValueError("conn4 mask growth requires a two-dimensional mask")
    if not np.issubdtype(values.dtype, np.bool_):
        raise TypeError("conn4 mask growth requires a boolean mask")
    if isinstance(radius, (bool, np.bool_)) or not isinstance(
        radius,
        (int, np.integer),
    ):
        raise TypeError("conn4 mask growth requires an integer radius")

    radius_value = int(radius)

    if radius_value < 0:
        raise ValueError("conn4 mask growth requires a non-negative radius")
    if values.shape[0] == 0 or values.shape[1] == 0:
        raise ValueError("conn4 mask growth requires a non-empty mask")

    seeds = np.array(values, dtype=bool, copy=True)

    # Gwyddion returns immediately for growth amounts below 0.5.
    if radius_value == 0:
        return seeds

    rows, columns = seeds.shape
    unreachable = int(np.iinfo(np.uint32).max)

    # grains_grow() duplicates and inverts the original mask before the
    # distance transform.  Consequently original mask pixels are zeros,
    # while the surrounding region starts as G_MAXUINT.
    distances = np.where(
        seeds,
        0,
        unreachable,
    ).astype(np.int64, copy=False)

    queue: list[tuple[int, int]] = []

    # init_erosion_4(..., from_border=FALSE) scans only interior pixels.
    for row in range(1, rows - 1):
        for column in range(1, columns - 1):
            if distances[row, column] != unreachable:
                continue

            if (
                distances[row - 1, column] == 0
                or distances[row, column - 1] == 0
                or distances[row, column + 1] == 0
                or distances[row + 1, column] == 0
            ):
                distances[row, column] = 1
                queue.append((row, column))

    distance = 1

    while queue:
        next_queue: list[tuple[int, int]] = []
        next_distance = distance + 1

        for row, column in queue:
            neighbours = (
                (row - 1, column),
                (row, column - 1),
                (row, column + 1),
                (row + 1, column),
            )

            for neighbour_row, neighbour_column in neighbours:
                if not (
                    0 <= neighbour_row < rows
                    and 0 <= neighbour_column < columns
                ):
                    continue

                if (
                    distances[neighbour_row, neighbour_column]
                    != unreachable
                ):
                    continue

                distances[neighbour_row, neighbour_column] = next_distance
                next_queue.append(
                    (neighbour_row, neighbour_column)
                )

        if not next_queue:
            break

        queue = next_queue
        distance = next_distance

    # Gwyddion's post-pass gives distance 1 to border pixels that were
    # never reached by the interior erosion queues.
    top_unreached = distances[0, :] == unreachable
    distances[0, top_unreached] = 1

    bottom_unreached = distances[-1, :] == unreachable
    distances[-1, bottom_unreached] = 1

    left_unreached = distances[:, 0] == unreachable
    distances[left_unreached, 0] = 1

    right_unreached = distances[:, -1] == unreachable
    distances[right_unreached, -1] = 1

    grown = seeds.copy()
    grown[distances <= radius_value] = True

    return grown


@dataclass(frozen=True)
class FlattenBaseMask:
    """Automatic positive-feature mask for one polynomial stage."""

    degree: int
    threshold: float
    growth_radius: int
    raw: np.ndarray
    grown: np.ndarray
    raw_count: int
    grown_count: int


def _build_flatten_base_mask(
    data: np.ndarray,
    *,
    peak: BasePeakEstimate,
    degree: int,
) -> FlattenBaseMask:
    """Build the automatic exclusion mask used by Flatten Base."""
    values = np.asarray(data)

    if np.issubdtype(values.dtype, np.bool_) or np.iscomplexobj(values):
        raise TypeError("Flatten Base masking requires real-valued data")
    if values.ndim != 2:
        raise ValueError(
            "Flatten Base masking requires a two-dimensional array"
        )
    if isinstance(degree, (bool, np.bool_)) or not isinstance(
        degree,
        (int, np.integer),
    ):
        raise TypeError("Flatten Base masking requires an integer degree")

    degree_value = int(degree)

    if degree_value < 0:
        raise ValueError(
            "Flatten Base masking requires a non-negative degree"
        )
    if not peak.success:
        raise ValueError(
            "Flatten Base masking requires a successful base-peak estimate"
        )

    try:
        numeric = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            "Flatten Base masking requires numeric data"
        ) from exc

    if not np.all(np.isfinite(numeric)):
        raise ValueError("Flatten Base masking requires finite data")

    mean = float(peak.mean)
    rms = float(peak.rms)

    if not np.isfinite(mean) or not np.isfinite(rms):
        raise ValueError(
            "Flatten Base masking requires finite peak parameters"
        )
    if rms < 0.0:
        raise ValueError(
            "Flatten Base masking requires non-negative peak RMS"
        )

    threshold = mean + 3.0 * rms
    growth_radius = 1 + degree_value // 2

    raw = np.array(
        numeric > threshold,
        dtype=bool,
        copy=True,
    )
    grown = np.array(
        _grow_mask_conn4(
            raw,
            radius=growth_radius,
        ),
        dtype=bool,
        copy=True,
    )

    raw_count = int(np.count_nonzero(raw))
    grown_count = int(np.count_nonzero(grown))

    raw.setflags(write=False)
    grown.setflags(write=False)

    return FlattenBaseMask(
        degree=degree_value,
        threshold=float(threshold),
        growth_radius=growth_radius,
        raw=raw,
        grown=grown,
        raw_count=raw_count,
        grown_count=grown_count,
    )



@dataclass(frozen=True)
class FlattenBasePolynomialIteration:
    """Evidence from one masked polynomial correction."""

    degree: int
    powers: tuple[tuple[int, int], ...]
    mask: FlattenBaseMask
    selected_count: int
    coefficients: np.ndarray
    rank: int
    singular_values: np.ndarray
    background: np.ndarray
    corrected: np.ndarray
    peak: BasePeakEstimate


def _run_flatten_base_polynomial_iteration(
    data: np.ndarray,
    *,
    peak: BasePeakEstimate,
    degree: int,
) -> FlattenBasePolynomialIteration:
    """Run one masked polynomial correction used by Flatten Base."""
    automatic_mask = _build_flatten_base_mask(
        data,
        peak=peak,
        degree=degree,
    )
    degree_value = automatic_mask.degree

    powers = tuple(
        (x_power, y_power)
        for x_power in range(degree_value + 1)
        for y_power in range(degree_value + 1 - x_power)
    )

    selection = np.logical_not(automatic_mask.grown)
    selected_count = int(np.count_nonzero(selection))

    from spmkit.core.analysis.leveling import (
        _fit_polynomial_surface_data,
    )

    (
        fitted_background,
        fitted_coefficients,
        rank,
        fitted_singular_values,
    ) = _fit_polynomial_surface_data(
        data,
        powers=powers,
        selection=selection,
        operation=f"Flatten Base degree {degree_value}",
    )

    values = np.asarray(data, dtype=float)
    background = np.array(
        fitted_background,
        dtype=float,
        copy=True,
    )
    coefficients = np.array(
        fitted_coefficients,
        dtype=float,
        copy=True,
    )
    singular_values = np.array(
        fitted_singular_values,
        dtype=float,
        copy=True,
    )

    if background.shape != values.shape:
        raise ValueError(
            "Flatten Base polynomial fit returned an invalid background shape"
        )
    if coefficients.ndim != 1 or coefficients.size != len(powers):
        raise ValueError(
            "Flatten Base polynomial fit returned invalid coefficients"
        )
    if singular_values.ndim != 1:
        raise ValueError(
            "Flatten Base polynomial fit returned invalid singular values"
        )
    if not np.all(np.isfinite(background)):
        raise ValueError(
            "Flatten Base polynomial fit returned a non-finite background"
        )
    if not np.all(np.isfinite(coefficients)):
        raise ValueError(
            "Flatten Base polynomial fit returned non-finite coefficients"
        )
    if not np.all(np.isfinite(singular_values)):
        raise ValueError(
            "Flatten Base polynomial fit returned non-finite singular values"
        )

    corrected = np.array(
        values - background,
        dtype=float,
        copy=True,
    )
    updated_peak = _estimate_base_peak(corrected)

    coefficients.setflags(write=False)
    singular_values.setflags(write=False)
    background.setflags(write=False)
    corrected.setflags(write=False)

    return FlattenBasePolynomialIteration(
        degree=degree_value,
        powers=powers,
        mask=automatic_mask,
        selected_count=selected_count,
        coefficients=coefficients,
        rank=int(rank),
        singular_values=singular_values,
        background=background,
        corrected=corrected,
        peak=updated_peak,
    )


@dataclass(frozen=True)
class FlattenBasePolynomialStage:
    """Evidence from the complete degree 2–5 polynomial stage."""

    corrected: np.ndarray
    background: np.ndarray
    initial_peak: BasePeakEstimate
    iterations: tuple[FlattenBasePolynomialIteration, ...]
    termination: str

    @property
    def completed_degrees(self) -> tuple[int, ...]:
        """Polynomial degrees successfully applied."""
        return tuple(
            iteration.degree
            for iteration in self.iterations
        )


def _run_flatten_base_polynomial_stage(
    data: np.ndarray,
    *,
    peak: BasePeakEstimate,
) -> FlattenBasePolynomialStage:
    """Run the degree 2, 3, 4 and 5 Flatten Base corrections."""
    values = np.asarray(data)

    if np.issubdtype(values.dtype, np.bool_) or np.iscomplexobj(values):
        raise TypeError(
            "Flatten Base polynomial stage requires real-valued data"
        )
    if values.ndim != 2:
        raise ValueError(
            "Flatten Base polynomial stage requires a two-dimensional array"
        )

    try:
        working = np.array(values, dtype=float, copy=True)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            "Flatten Base polynomial stage requires numeric data"
        ) from exc

    if not np.all(np.isfinite(working)):
        raise ValueError(
            "Flatten Base polynomial stage requires finite data"
        )

    accumulated_background = np.zeros_like(working)
    iterations: list[FlattenBasePolynomialIteration] = []
    current_peak = peak
    termination = "completed"

    for degree in (2, 3, 4, 5):
        if not current_peak.success:
            termination = "peak_failure"
            break

        iteration = _run_flatten_base_polynomial_iteration(
            working,
            peak=current_peak,
            degree=degree,
        )

        iteration_background = np.asarray(
            iteration.background,
            dtype=float,
        )
        iteration_corrected = np.asarray(
            iteration.corrected,
            dtype=float,
        )

        if iteration_background.shape != working.shape:
            raise ValueError(
                "Flatten Base polynomial iteration returned "
                "an invalid background shape"
            )
        if iteration_corrected.shape != working.shape:
            raise ValueError(
                "Flatten Base polynomial iteration returned "
                "an invalid corrected shape"
            )
        if not np.all(np.isfinite(iteration_background)):
            raise ValueError(
                "Flatten Base polynomial iteration returned "
                "a non-finite background"
            )
        if not np.all(np.isfinite(iteration_corrected)):
            raise ValueError(
                "Flatten Base polynomial iteration returned "
                "non-finite corrected data"
            )

        accumulated_background += iteration_background
        working = np.array(
            iteration_corrected,
            dtype=float,
            copy=True,
        )
        iterations.append(iteration)
        current_peak = iteration.peak

        if not current_peak.success:
            termination = "peak_failure"
            break

    corrected = np.array(working, dtype=float, copy=True)
    background = np.array(
        accumulated_background,
        dtype=float,
        copy=True,
    )

    corrected.setflags(write=False)
    background.setflags(write=False)

    return FlattenBasePolynomialStage(
        corrected=corrected,
        background=background,
        initial_peak=peak,
        iterations=tuple(iterations),
        termination=termination,
    )
