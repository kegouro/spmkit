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


def _packed_lower_index(row: int, column: int) -> int:
    """Index a row-packed lower-triangular symmetric matrix."""
    return row * (row + 1) // 2 + column


def _gwyddion_cholesky_decompose(
    dimension: int,
    packed: np.ndarray,
) -> bool:
    """Decompose a packed SPD matrix using Gwyddion's loop order."""
    for diagonal in range(dimension):
        value = float(
            packed[_packed_lower_index(diagonal, diagonal)]
        )

        for index in range(diagonal):
            factor = float(
                packed[_packed_lower_index(diagonal, index)]
            )
            value -= factor * factor

        if value <= 0.0:
            return False

        root = float(np.sqrt(value))
        packed[_packed_lower_index(diagonal, diagonal)] = root

        for row in range(diagonal + 1, dimension):
            value = float(
                packed[_packed_lower_index(row, diagonal)]
            )

            for index in range(diagonal):
                value -= (
                    float(
                        packed[
                            _packed_lower_index(diagonal, index)
                        ]
                    )
                    * float(
                        packed[
                            _packed_lower_index(row, index)
                        ]
                    )
                )

            packed[_packed_lower_index(row, diagonal)] = (
                value / root
            )

    return True


def _gwyddion_cholesky_solve(
    dimension: int,
    decomposition: np.ndarray,
    right_hand_side: np.ndarray,
) -> None:
    """Solve an SPD system using Gwyddion's substitution order."""
    for row in range(dimension):
        for column in range(row):
            right_hand_side[row] -= (
                decomposition[
                    _packed_lower_index(row, column)
                ]
                * right_hand_side[column]
            )

        right_hand_side[row] /= decomposition[
            _packed_lower_index(row, row)
        ]

    for row in range(dimension - 1, -1, -1):
        for column in range(row + 1, dimension):
            right_hand_side[row] -= (
                decomposition[
                    _packed_lower_index(column, row)
                ]
                * right_hand_side[column]
            )

        right_hand_side[row] /= decomposition[
            _packed_lower_index(row, row)
        ]


def _gwyddion_cholesky_invert(
    dimension: int,
    packed: np.ndarray,
) -> bool:
    """Invert a packed SPD matrix using Gwyddion's algorithm."""
    temporary = np.empty(dimension, dtype=float)
    packed_offset = 0

    for pivot in range(dimension - 1, -1, -1):
        scale = float(packed[0])

        if scale <= 0.0:
            return False

        row_end = 0

        for row in range(dimension - 1):
            packed_offset = row_end + 1
            row_end += row + 2
            element = float(packed[packed_offset])

            temporary[row] = -element / scale

            if row >= pivot:
                temporary[row] = -temporary[row]

            for index in range(packed_offset, row_end):
                packed[index - (row + 1)] = (
                    packed[index + 1]
                    + element
                    * temporary[index - packed_offset]
                )

        packed[row_end] = 1.0 / scale

        for row in range(dimension - 1):
            packed[packed_offset + row] = temporary[row]

    return True


def _fit_base_peak_gwyddion_lm(
    window: BasePeakWindow,
) -> BasePeakFit:
    """Fit a Gaussian using Gwyddion's nonlinear-fit semantics."""
    centers = np.asarray(window.centers, dtype=float)
    density = np.asarray(window.density, dtype=float)

    if centers.ndim != 1 or density.ndim != 1:
        raise ValueError(
            "base peak fitting requires one-dimensional data"
        )
    if centers.size != density.size:
        raise ValueError(
            "base peak fitting requires matching centers and density"
        )
    if centers.size < 4:
        raise ValueError(
            "base peak fitting requires at least four samples"
        )
    if (
        not np.all(np.isfinite(centers))
        or not np.all(np.isfinite(density))
    ):
        raise ValueError(
            "base peak fitting requires finite data"
        )

    parameters = np.array(
        [
            window.initial_mean,
            window.initial_offset,
            window.initial_amplitude,
            window.initial_width,
        ],
        dtype=float,
    )

    if not np.all(np.isfinite(parameters)):
        raise ValueError(
            "base peak fitting requires finite initial parameters"
        )
    if parameters[3] == 0.0:
        raise ValueError(
            "base peak fitting requires a non-zero initial width"
        )

    parameter_count = 4
    packed_size = parameter_count * (parameter_count + 1) // 2
    finite_limit = np.finfo(float).max

    damping = 1.0e-4
    damping_decrease = 0.4
    damping_increase = 10.0
    damping_zero_replacement = 1.0e-6
    convergence_tolerance = 1.0e-16
    derivative_scale = 1.0e-5
    maximum_iterations = 100
    maximum_unimproved = 12

    evaluations = 0

    def gaussian_value(
        coordinate: float,
        current: np.ndarray,
    ) -> tuple[float, bool]:
        nonlocal evaluations
        evaluations += 1

        width = float(current[3])

        if width == 0.0:
            return 0.0, False

        scaled = (
            float(coordinate) - float(current[0])
        ) / width

        with np.errstate(
            over="ignore",
            invalid="ignore",
        ):
            value = (
                float(current[2])
                * float(np.exp(-(scaled * scaled)))
                + float(current[1])
            )

        return value, True

    def calculate_residuals(
        current: np.ndarray,
    ) -> tuple[np.ndarray, float, bool]:
        residuals = np.empty(centers.size, dtype=float)
        residual_sum = 0.0

        for index in range(centers.size):
            value, valid = gaussian_value(
                float(centers[index]),
                current,
            )

            if not valid:
                return residuals, -1.0, False

            residual = value - float(density[index])
            residuals[index] = residual
            residual_sum += residual * residual

        if not np.isfinite(residual_sum):
            return residuals, -1.0, False

        return residuals, residual_sum, True

    def calculate_derivatives(
        coordinate: float,
        current: np.ndarray,
    ) -> tuple[np.ndarray, bool]:
        derivatives = np.empty(parameter_count, dtype=float)
        perturbed = current.copy()

        for parameter_index in range(parameter_count):
            step = (
                abs(float(perturbed[parameter_index]))
                * derivative_scale
            )

            if step == 0.0:
                step = derivative_scale

            perturbed[parameter_index] -= step
            left, valid = gaussian_value(
                coordinate,
                perturbed,
            )

            if not valid:
                return derivatives, False

            perturbed[parameter_index] += 2.0 * step
            right, valid = gaussian_value(
                coordinate,
                perturbed,
            )

            if not valid:
                return derivatives, False

            derivatives[parameter_index] = (
                (right - left) / (2.0 * step)
            )
            perturbed[parameter_index] = current[
                parameter_index
            ]

        return derivatives, True

    def rank_and_condition(
        current: np.ndarray,
    ) -> tuple[int, float]:
        jacobian = np.empty(
            (centers.size, parameter_count),
            dtype=float,
        )

        for index in range(centers.size):
            derivatives, valid = calculate_derivatives(
                float(centers[index]),
                current,
            )

            if not valid:
                return 0, float("inf")

            jacobian[index, :] = derivatives

        singular_values = np.linalg.svd(
            jacobian,
            compute_uv=False,
        )

        if (
            singular_values.size == 0
            or singular_values[0] == 0.0
        ):
            return 0, float("inf")

        tolerance = (
            np.finfo(float).eps
            * max(jacobian.shape)
            * singular_values[0]
        )
        rank = int(
            np.count_nonzero(
                singular_values > tolerance
            )
        )

        if (
            rank < parameter_count
            or singular_values[-1] <= tolerance
        ):
            return rank, float("inf")

        condition = float(
            singular_values[0] / singular_values[-1]
        )
        return rank, condition

    residuals, residual_sum_new, evaluation_valid = (
        calculate_residuals(parameters)
    )

    if not evaluation_valid:
        width = abs(float(parameters[3]))

        return BasePeakFit(
            mean=float(parameters[0]),
            rms=width / np.sqrt(2.0),
            offset=float(parameters[1]),
            amplitude=float(parameters[2]),
            width=width,
            residual_norm=float("inf"),
            solver_success=False,
            covariance_available=False,
            evaluations=evaluations,
            jacobian_rank=0,
            condition_estimate=float("inf"),
        )

    best_parameters = parameters.copy()
    residual_sum_best = finite_limit

    gradient = np.empty(parameter_count, dtype=float)
    normal = np.empty(packed_size, dtype=float)
    saved_normal: np.ndarray | None = None
    saved_parameters: np.ndarray | None = None

    iteration = 0
    unimproved = 0
    finished = False

    while True:
        if unimproved == 0:
            damping *= damping_decrease
            residual_sum_best = residual_sum_new
            best_parameters = parameters.copy()

            gradient.fill(0.0)
            normal.fill(0.0)

            for sample_index in range(centers.size):
                derivatives, valid = calculate_derivatives(
                    float(centers[sample_index]),
                    parameters,
                )

                if not valid:
                    evaluation_valid = False
                    residual_sum_best = -1.0
                    break

                for row in range(parameter_count):
                    gradient[row] += (
                        derivatives[row]
                        * residuals[sample_index]
                    )

                    packed_row = row * (row + 1) // 2

                    for column in range(row + 1):
                        normal[packed_row + column] += (
                            derivatives[row]
                            * derivatives[column]
                        )

            if not evaluation_valid:
                break

            saved_normal = normal.copy()
            saved_parameters = parameters.copy()

        if saved_normal is None or saved_parameters is None:
            evaluation_valid = False
            residual_sum_best = -1.0
            break

        positive_definite = False
        first_pass = True

        while (
            not positive_definite
            and np.isfinite(damping)
        ):
            if not first_pass:
                normal[:] = saved_normal
            else:
                first_pass = False

            step = -gradient.copy()

            for parameter_index in range(parameter_count):
                diagonal = (
                    parameter_index
                    * (parameter_index + 3)
                    // 2
                )

                if saved_normal[diagonal] == 0.0:
                    normal[diagonal] = damping
                else:
                    normal[diagonal] = (
                        saved_normal[diagonal]
                        * (1.0 + damping)
                    )

            positive_definite = (
                _gwyddion_cholesky_decompose(
                    parameter_count,
                    normal,
                )
            )

            if not positive_definite:
                damping *= damping_increase

                if damping == 0.0:
                    damping = damping_zero_replacement

        if not np.isfinite(damping):
            evaluation_valid = False
            residual_sum_best = -1.0
            break

        _gwyddion_cholesky_solve(
            parameter_count,
            normal,
            step,
        )

        parameters = saved_parameters + step

        unchanged = 0

        for parameter_index in range(parameter_count):
            if (
                abs(
                    float(parameters[parameter_index])
                    - float(
                        saved_parameters[parameter_index]
                    )
                )
                == 0.0
            ):
                unchanged += 1

        if unchanged == parameter_count:
            break

        (
            residuals,
            residual_sum_new,
            evaluation_valid,
        ) = calculate_residuals(parameters)

        if not evaluation_valid:
            residual_sum_best = -1.0
            break

        if (
            residual_sum_new == 0.0
            or (
                iteration > 2
                and abs(
                    (
                        residual_sum_best
                        - residual_sum_new
                    )
                    / residual_sum_best
                )
                < convergence_tolerance
            )
        ):
            finished = True

        if residual_sum_new >= residual_sum_best:
            damping *= damping_increase

            if damping == 0.0:
                damping = damping_zero_replacement

            unimproved += 1
        else:
            unimproved = 0

        if unimproved >= maximum_unimproved:
            break

        iteration += 1

        if iteration >= maximum_iterations:
            break

        if finished:
            break

    parameters = best_parameters.copy()
    solver_evaluations = evaluations

    covariance_available = False

    if evaluation_valid and saved_normal is not None:
        original_normal = saved_normal.copy()
        covariance = saved_normal.copy()

        for parameter_index in range(parameter_count):
            diagonal = (
                parameter_index
                * (parameter_index + 3)
                // 2
            )

            if original_normal[diagonal] == 0.0:
                covariance[diagonal] = 1.0

        covariance_available = (
            _gwyddion_cholesky_invert(
                parameter_count,
                covariance,
            )
        )

        if not covariance_available:
            covariance = original_normal.copy()

            for parameter_index in range(parameter_count):
                diagonal = (
                    parameter_index
                    * (parameter_index + 3)
                    // 2
                )

                if original_normal[diagonal] == 0.0:
                    covariance[diagonal] = 1.0

                covariance[diagonal] *= 1.0001

            covariance_available = (
                _gwyddion_cholesky_invert(
                    parameter_count,
                    covariance,
                )
            )

        covariance_available = bool(
            covariance_available
            and np.all(np.isfinite(covariance))
        )

    finite_parameters = bool(
        np.all(np.isfinite(parameters))
    )

    if not finite_parameters:
        covariance_available = False

    jacobian_rank, condition_estimate = (
        rank_and_condition(parameters)
    )

    width = abs(float(parameters[3]))
    solver_success = bool(
        covariance_available
        and finite_parameters
        and residual_sum_best >= 0.0
    )

    residual_norm = (
        float(np.sqrt(residual_sum_best))
        if residual_sum_best >= 0.0
        else float("inf")
    )

    return BasePeakFit(
        mean=float(parameters[0]),
        rms=width / np.sqrt(2.0),
        offset=float(parameters[1]),
        amplitude=float(parameters[2]),
        width=width,
        residual_norm=residual_norm,
        solver_success=solver_success,
        covariance_available=covariance_available,
        evaluations=solver_evaluations,
        jacobian_rank=jacobian_rank,
        condition_estimate=condition_estimate,
    )


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

    normalized_window = BasePeakWindow(
        centers=window.centers,
        density=window.density,
        peak_index=window.peak_index,
        start_index=window.start_index,
        stop_index=window.stop_index,
        initial_mean=window.initial_mean,
        initial_offset=window.initial_offset,
        initial_amplitude=window.initial_amplitude,
        initial_width=initial_width,
    )

    return _fit_base_peak_gwyddion_lm(
        normalized_window
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
    mask: FlattenBaseMask | None
    selected_count: int
    coefficients: np.ndarray
    rank: int
    singular_values: np.ndarray
    background: np.ndarray
    corrected: np.ndarray
    peak: BasePeakEstimate
    applied: bool = True


def _run_flatten_base_polynomial_iteration(
    data: np.ndarray,
    *,
    peak: BasePeakEstimate,
    degree: int,
) -> FlattenBasePolynomialIteration:
    """Run one masked polynomial correction used by Flatten Base."""
    values = np.asarray(data)

    if np.issubdtype(values.dtype, np.bool_) or np.iscomplexobj(values):
        raise TypeError(
            "Flatten Base polynomial iteration requires real-valued data"
        )
    if values.ndim != 2:
        raise ValueError(
            "Flatten Base polynomial iteration requires "
            "a two-dimensional array"
        )
    if values.size == 0:
        raise ValueError(
            "Flatten Base polynomial iteration requires non-empty data"
        )
    if isinstance(degree, (bool, np.bool_)) or not isinstance(
        degree,
        (int, np.integer),
    ):
        raise TypeError(
            "Flatten Base polynomial iteration requires an integer degree"
        )

    degree_value = int(degree)

    if degree_value < 0:
        raise ValueError(
            "Flatten Base polynomial iteration requires "
            "a non-negative degree"
        )

    try:
        numeric = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            "Flatten Base polynomial iteration requires numeric data"
        ) from exc

    if not np.all(np.isfinite(numeric)):
        raise ValueError(
            "Flatten Base polynomial iteration requires finite data"
        )

    if float(np.max(numeric)) <= float(np.min(numeric)):
        background = np.zeros_like(numeric)
        corrected = np.array(numeric, dtype=float, copy=True)
        coefficients = np.empty(0, dtype=float)
        singular_values = np.empty(0, dtype=float)

        updated_peak = _estimate_base_peak(corrected)

        background.setflags(write=False)
        corrected.setflags(write=False)
        coefficients.setflags(write=False)
        singular_values.setflags(write=False)

        return FlattenBasePolynomialIteration(
            degree=degree_value,
            powers=(),
            mask=None,
            selected_count=0,
            coefficients=coefficients,
            rank=0,
            singular_values=singular_values,
            background=background,
            corrected=corrected,
            peak=updated_peak,
            applied=False,
        )

    automatic_mask = _build_flatten_base_mask(
        numeric,
        peak=peak,
        degree=degree_value,
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
    def attempted_degrees(self) -> tuple[int, ...]:
        """Polynomial degrees attempted by the stage."""
        return tuple(
            iteration.degree
            for iteration in self.iterations
        )

    @property
    def completed_degrees(self) -> tuple[int, ...]:
        """Polynomial degrees that actually subtracted a background."""
        return tuple(
            iteration.degree
            for iteration in self.iterations
            if getattr(iteration, "applied", True)
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


@dataclass(frozen=True)
class FlattenBaseResult:
    """Complete Flatten Base result and stage-level evidence."""

    corrected: np.ndarray
    background: np.ndarray
    facet_stage: FacetStageResult
    polynomial_stage: FlattenBasePolynomialStage
    final_peak: BasePeakEstimate
    mean_offset: float
    minimum_offset: float
    mean_centered: bool

    @property
    def total_offset(self) -> float:
        """Total constant offset subtracted after background leveling."""
        return self.mean_offset + self.minimum_offset


def _run_flatten_base(
    data: np.ndarray,
    *,
    pixel_size_x: float,
    pixel_size_y: float,
) -> FlattenBaseResult:
    """Run the complete Gwyddion-compatible Flatten Base pipeline."""
    facet_stage = _run_flatten_base_facet_stage(
        data,
        pixel_size_x=pixel_size_x,
        pixel_size_y=pixel_size_y,
    )

    if facet_stage.iterations:
        polynomial_input_peak = facet_stage.iterations[-1].peak
    else:
        polynomial_input_peak = facet_stage.initial_peak

    polynomial_stage = _run_flatten_base_polynomial_stage(
        facet_stage.corrected,
        peak=polynomial_input_peak,
    )

    if polynomial_stage.iterations:
        final_peak = polynomial_stage.iterations[-1].peak
    else:
        final_peak = polynomial_stage.initial_peak

    corrected = np.array(
        polynomial_stage.corrected,
        dtype=float,
        copy=True,
    )
    background = np.array(
        facet_stage.background,
        dtype=float,
        copy=True,
    )
    polynomial_background = np.asarray(
        polynomial_stage.background,
        dtype=float,
    )

    if background.shape != corrected.shape:
        raise ValueError(
            "Flatten Base facet stage returned incompatible shapes"
        )
    if polynomial_background.shape != corrected.shape:
        raise ValueError(
            "Flatten Base polynomial stage returned "
            "incompatible shapes"
        )
    if corrected.size == 0:
        raise ValueError(
            "Flatten Base requires non-empty corrected data"
        )
    if not np.all(np.isfinite(corrected)):
        raise ValueError(
            "Flatten Base polynomial stage returned "
            "non-finite corrected data"
        )
    if not np.all(np.isfinite(background)):
        raise ValueError(
            "Flatten Base facet stage returned "
            "a non-finite background"
        )
    if not np.all(np.isfinite(polynomial_background)):
        raise ValueError(
            "Flatten Base polynomial stage returned "
            "a non-finite background"
        )

    background += polynomial_background

    mean_centered = bool(final_peak.success)
    mean_offset = (
        float(final_peak.mean)
        if mean_centered
        else 0.0
    )

    if mean_centered:
        corrected -= mean_offset
        background += mean_offset

    remaining_minimum = float(np.min(corrected))
    minimum_offset = (
        remaining_minimum
        if remaining_minimum > 0.0
        else 0.0
    )

    if minimum_offset > 0.0:
        corrected -= minimum_offset
        background += minimum_offset

    corrected.setflags(write=False)
    background.setflags(write=False)

    return FlattenBaseResult(
        corrected=corrected,
        background=background,
        facet_stage=facet_stage,
        polynomial_stage=polynomial_stage,
        final_peak=final_peak,
        mean_offset=mean_offset,
        minimum_offset=minimum_offset,
        mean_centered=mean_centered,
    )
