"""Tensor-product penalized B-spline surface fitting.

This module implements the P-spline construction introduced by Eilers and
Marx, Statistical Science 11 (1996), DOI: 10.1214/ss/1038425655.

For coefficient matrix C, data Z, marginal B-spline bases Bx and By, and
difference operators Dx and Dy, the fitted surface minimizes

    ||W**0.5 (Z - By C Bx.T)||**2
    + smoothing_x ||C Dx.T||**2
    + smoothing_y ||Dy C||**2.

The augmented least-squares system is exposed to LSMR as a LinearOperator.
The full tensor-product design matrix is never materialized.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb
from typing import Final

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.interpolate import BSpline
from scipy.linalg import null_space
from scipy.sparse import csr_array, diags
from scipy.sparse.linalg import LinearOperator, lsmr

FloatArray = NDArray[np.float64]

_ACCEPTABLE_LSMR_STOPS: Final[frozenset[int]] = frozenset(
    {
        1,
        2,
        4,
        5,
    }
)


@dataclass(frozen=True)
class PSplineSurfaceFit:
    """Result and diagnostics from a tensor-product P-spline fit."""

    model: FloatArray
    coefficients: FloatArray
    knots_x: FloatArray
    knots_y: FloatArray
    degree_x: int
    degree_y: int
    penalty_order_x: int
    penalty_order_y: int
    smoothing_x: float
    smoothing_y: float
    selected_points: int
    total_points: int
    solver_stop_code: int
    solver_iterations: int
    augmented_residual_norm: float
    normal_residual_norm: float
    operator_norm: float
    condition_estimate: float
    coefficient_norm: float
    weighted_data_residual_norm: float
    penalty_x_norm: float
    penalty_y_norm: float
    x_min: float
    x_max: float
    y_min: float
    y_max: float


def _as_real_numeric_array(
    values: ArrayLike,
    *,
    name: str,
) -> FloatArray:
    """Convert real numeric input without discarding complex components."""
    raw = np.asarray(values)

    if not np.issubdtype(raw.dtype, np.number) or np.iscomplexobj(raw):
        raise TypeError(f"{name} must be real numeric")

    return np.asarray(
        raw,
        dtype=float,
    )


def _readonly_float_array(values: ArrayLike) -> FloatArray:
    result = np.array(
        values,
        dtype=float,
        copy=True,
        order="C",
    )
    result.setflags(write=False)
    return result


def _open_uniform_knots(
    n_basis: int,
    degree: int,
) -> FloatArray:
    if degree < 0:
        raise ValueError("spline degree must be non-negative")

    if n_basis < degree + 1:
        raise ValueError("n_basis must be at least degree + 1")

    n_internal = n_basis - degree - 1

    if n_internal:
        interior = np.linspace(
            0.0,
            1.0,
            n_internal + 2,
            dtype=float,
        )[1:-1]
    else:
        interior = np.empty(0, dtype=float)

    return np.concatenate(
        (
            np.zeros(degree + 1, dtype=float),
            interior,
            np.ones(degree + 1, dtype=float),
        )
    )


def _difference_matrix(
    size: int,
    order: int,
) -> csr_array:
    if order < 1:
        raise ValueError("penalty order must be at least 1")

    if order >= size:
        raise ValueError("penalty order must be smaller than n_basis")

    coefficients = np.array(
        [(-1.0) ** (order - index) * comb(order, index) for index in range(order + 1)],
        dtype=float,
    )

    return csr_array(
        diags(
            coefficients,
            offsets=np.arange(order + 1),
            shape=(size - order, size),
            format="csr",
        )
    )


def _normalized_axis(
    length: int,
    values: ArrayLike | None,
    *,
    name: str,
) -> tuple[FloatArray, float, float]:
    if length < 2:
        raise ValueError(f"{name} axis must contain at least two points")

    if values is None:
        original = np.arange(
            length,
            dtype=float,
        )
    else:
        original = _as_real_numeric_array(
            values,
            name=f"{name} coordinates",
        )

        if original.ndim != 1:
            raise ValueError(f"{name} coordinates must be one-dimensional")

        if original.size != length:
            raise ValueError(f"{name} coordinate count does not match data")

    if not np.all(np.isfinite(original)):
        raise ValueError(f"{name} coordinates must be finite")

    if not np.all(np.diff(original) > 0.0):
        raise ValueError(f"{name} coordinates must be strictly increasing")

    lower = float(original[0])
    upper = float(original[-1])

    normalized = (original - lower) / (upper - lower)

    return (
        np.asarray(normalized, dtype=float),
        lower,
        upper,
    )


def _validate_solver_parameter(
    value: float,
    *,
    name: str,
) -> float:
    raw = np.asarray(value)

    if (
        raw.ndim != 0
        or not np.issubdtype(raw.dtype, np.number)
        or np.iscomplexobj(raw)
        or raw.dtype == np.bool_
    ):
        raise TypeError(f"{name} must be a real numeric scalar")

    validated = float(raw.item())

    if not np.isfinite(validated) or validated <= 0.0:
        raise ValueError(f"{name} must be finite and strictly positive")

    return validated


def _check_penalty_null_space_identifiability(
    *,
    basis_x: csr_array,
    basis_y: csr_array,
    difference_x: csr_array,
    difference_y: csr_array,
    selected: NDArray[np.intp],
    sqrt_weights: FloatArray,
    data_shape: tuple[int, int],
) -> None:
    null_x = null_space(difference_x.toarray())
    null_y = null_space(difference_y.toarray())

    null_surfaces: list[FloatArray] = []

    for y_index in range(null_y.shape[1]):
        for x_index in range(null_x.shape[1]):
            coefficients = np.outer(
                null_y[:, y_index],
                null_x[:, x_index],
            )

            surface = np.asarray(
                basis_y @ coefficients @ basis_x.T,
                dtype=float,
                order="C",
            )

            null_surfaces.append(
                sqrt_weights
                * surface.reshape(
                    data_shape,
                    order="C",
                ).ravel(order="C")[selected]
            )

    null_design = np.column_stack(null_surfaces)

    rank = int(np.linalg.matrix_rank(null_design))

    if rank != null_design.shape[1]:
        raise ValueError("selected data do not identify the P-spline penalty null space")


def fit_pspline_surface(
    data: ArrayLike,
    *,
    x: ArrayLike | None = None,
    y: ArrayLike | None = None,
    mask: ArrayLike | None = None,
    weights: ArrayLike | None = None,
    n_basis_x: int = 12,
    n_basis_y: int = 12,
    degree_x: int = 3,
    degree_y: int = 3,
    penalty_order_x: int = 2,
    penalty_order_y: int = 2,
    smoothing_x: float = 1.0,
    smoothing_y: float = 1.0,
    atol: float = 1e-12,
    btol: float = 1e-12,
    conlim: float = 1e12,
    maxiter: int | None = None,
) -> PSplineSurfaceFit:
    """Fit an anisotropic tensor-product P-spline surface.

    Coordinates are normalized independently to ``[0, 1]``. Consequently,
    smoothing parameters are not silently rescaled when physical scan ranges
    change. Physical anisotropy is represented explicitly through separate
    X and Y basis counts and smoothing parameters.

    ``mask`` is a strict Boolean selection. Non-selected data may contain
    non-finite values. ``weights`` must be finite and non-negative; zero
    weight excludes a selected observation.
    """

    values = _as_real_numeric_array(
        data,
        name="P-spline surface data",
    )

    if values.ndim != 2:
        raise ValueError("P-spline surface data must be two-dimensional")

    rows, columns = values.shape

    normalized_x, x_min, x_max = _normalized_axis(
        columns,
        x,
        name="x",
    )
    normalized_y, y_min, y_max = _normalized_axis(
        rows,
        y,
        name="y",
    )

    if not isinstance(n_basis_x, int) or isinstance(
        n_basis_x,
        bool,
    ):
        raise TypeError("n_basis_x must be an integer")

    if not isinstance(n_basis_y, int) or isinstance(
        n_basis_y,
        bool,
    ):
        raise TypeError("n_basis_y must be an integer")

    knots_x = _open_uniform_knots(
        n_basis_x,
        degree_x,
    )
    knots_y = _open_uniform_knots(
        n_basis_y,
        degree_y,
    )

    difference_x = _difference_matrix(
        n_basis_x,
        penalty_order_x,
    )
    difference_y = _difference_matrix(
        n_basis_y,
        penalty_order_y,
    )

    validated_smoothing_x = _validate_solver_parameter(
        smoothing_x,
        name="smoothing_x",
    )
    validated_smoothing_y = _validate_solver_parameter(
        smoothing_y,
        name="smoothing_y",
    )
    validated_atol = _validate_solver_parameter(
        atol,
        name="atol",
    )
    validated_btol = _validate_solver_parameter(
        btol,
        name="btol",
    )
    validated_conlim = _validate_solver_parameter(
        conlim,
        name="conlim",
    )

    if maxiter is not None:
        if not isinstance(maxiter, int) or isinstance(
            maxiter,
            bool,
        ):
            raise TypeError("maxiter must be an integer")

        if maxiter < 1:
            raise ValueError("maxiter must be strictly positive")

    if mask is None:
        selected_mask = np.ones(
            values.shape,
            dtype=bool,
        )
    else:
        raw_mask = np.asarray(mask)

        if raw_mask.dtype != np.bool_:
            raise TypeError("P-spline mask must be Boolean")

        if raw_mask.shape != values.shape:
            raise ValueError("P-spline mask shape must match data")

        selected_mask = np.array(
            raw_mask,
            dtype=bool,
            copy=True,
            order="C",
        )

    if weights is None:
        weight_values = np.ones(
            values.shape,
            dtype=float,
        )
    else:
        weight_values = _as_real_numeric_array(
            weights,
            name="P-spline weights",
        )

        if weight_values.shape != values.shape:
            raise ValueError("P-spline weights shape must match data")

        if not np.all(np.isfinite(weight_values)):
            raise ValueError("P-spline weights must be finite")

        if np.any(weight_values < 0.0):
            raise ValueError("P-spline weights must be non-negative")

    active = selected_mask & (weight_values > 0.0)
    selected = np.flatnonzero(active.ravel(order="C"))

    if selected.size == 0:
        raise ValueError("P-spline fit requires selected observations")

    flat_values = values.ravel(order="C")
    selected_values = flat_values[selected]

    if not np.all(np.isfinite(selected_values)):
        raise ValueError("selected P-spline data must be finite")

    flat_weights = weight_values.ravel(order="C")
    sqrt_weights = np.sqrt(flat_weights[selected])

    basis_x = csr_array(
        BSpline.design_matrix(
            normalized_x,
            knots_x,
            degree_x,
        )
    )
    basis_y = csr_array(
        BSpline.design_matrix(
            normalized_y,
            knots_y,
            degree_y,
        )
    )

    _check_penalty_null_space_identifiability(
        basis_x=basis_x,
        basis_y=basis_y,
        difference_x=difference_x,
        difference_y=difference_y,
        selected=selected,
        sqrt_weights=sqrt_weights,
        data_shape=values.shape,
    )

    x_penalty_rows = n_basis_y * difference_x.shape[0]
    y_penalty_rows = difference_y.shape[0] * n_basis_x
    coefficient_count = n_basis_y * n_basis_x

    operator_rows = selected.size + x_penalty_rows + y_penalty_rows

    sqrt_smoothing_x = np.sqrt(validated_smoothing_x)
    sqrt_smoothing_y = np.sqrt(validated_smoothing_y)

    def forward(
        coefficient_vector: NDArray[np.float64],
    ) -> FloatArray:
        coefficients = np.asarray(
            coefficient_vector,
            dtype=float,
        ).reshape(
            n_basis_y,
            n_basis_x,
            order="C",
        )

        model = np.asarray(
            basis_y @ coefficients @ basis_x.T,
            dtype=float,
            order="C",
        )
        penalty_x = np.asarray(
            coefficients @ difference_x.T,
            dtype=float,
            order="C",
        )
        penalty_y = np.asarray(
            difference_y @ coefficients,
            dtype=float,
            order="C",
        )

        return np.concatenate(
            (
                sqrt_weights * model.ravel(order="C")[selected],
                sqrt_smoothing_x * penalty_x.ravel(order="C"),
                sqrt_smoothing_y * penalty_y.ravel(order="C"),
            )
        )

    def adjoint(
        residual_vector: NDArray[np.float64],
    ) -> FloatArray:
        residuals = np.asarray(
            residual_vector,
            dtype=float,
        )

        position = 0

        data_residual = sqrt_weights * residuals[position : position + selected.size]
        position += selected.size

        penalty_x_residual = residuals[position : position + x_penalty_rows].reshape(
            n_basis_y,
            difference_x.shape[0],
            order="C",
        )
        position += x_penalty_rows

        penalty_y_residual = residuals[position:].reshape(
            difference_y.shape[0],
            n_basis_x,
            order="C",
        )

        residual_grid = np.zeros(
            values.shape,
            dtype=float,
            order="C",
        )
        residual_grid.flat[selected] = data_residual

        gradient = np.asarray(
            basis_y.T @ residual_grid @ basis_x,
            dtype=float,
            order="C",
        )

        gradient += sqrt_smoothing_x * np.asarray(
            penalty_x_residual @ difference_x,
            dtype=float,
        )
        gradient += sqrt_smoothing_y * np.asarray(
            difference_y.T @ penalty_y_residual,
            dtype=float,
        )

        return np.asarray(
            gradient,
            dtype=float,
            order="C",
        ).ravel(order="C")

    operator = LinearOperator(
        shape=(
            operator_rows,
            coefficient_count,
        ),
        matvec=forward,
        rmatvec=adjoint,
        dtype=float,
    )

    right_hand_side = np.concatenate(
        (
            sqrt_weights * selected_values,
            np.zeros(
                operator_rows - selected.size,
                dtype=float,
            ),
        )
    )

    iteration_limit = (
        maxiter
        if maxiter is not None
        else max(
            1000,
            4 * coefficient_count,
        )
    )

    solution = lsmr(
        operator,
        right_hand_side,
        atol=validated_atol,
        btol=validated_btol,
        conlim=validated_conlim,
        maxiter=iteration_limit,
    )

    (
        coefficient_vector,
        stop_code,
        iterations,
        augmented_residual_norm,
        normal_residual_norm,
        operator_norm,
        condition_estimate,
        coefficient_norm,
    ) = solution

    zero_right_hand_side = bool(np.linalg.norm(right_hand_side) == 0.0)

    converged = stop_code in _ACCEPTABLE_LSMR_STOPS or (stop_code == 0 and zero_right_hand_side)

    if not converged:
        raise RuntimeError(
            "P-spline LSMR did not converge: "
            f"stop_code={stop_code}, "
            f"iterations={iterations}, "
            f"condition_estimate={condition_estimate:.6g}"
        )

    coefficients = np.asarray(
        coefficient_vector,
        dtype=float,
    ).reshape(
        n_basis_y,
        n_basis_x,
        order="C",
    )

    model = np.asarray(
        basis_y @ coefficients @ basis_x.T,
        dtype=float,
        order="C",
    )

    penalty_x = np.asarray(
        coefficients @ difference_x.T,
        dtype=float,
    )
    penalty_y = np.asarray(
        difference_y @ coefficients,
        dtype=float,
    )

    weighted_data_residual = sqrt_weights * (model.ravel(order="C")[selected] - selected_values)

    return PSplineSurfaceFit(
        model=_readonly_float_array(model),
        coefficients=_readonly_float_array(coefficients),
        knots_x=_readonly_float_array(knots_x),
        knots_y=_readonly_float_array(knots_y),
        degree_x=degree_x,
        degree_y=degree_y,
        penalty_order_x=penalty_order_x,
        penalty_order_y=penalty_order_y,
        smoothing_x=validated_smoothing_x,
        smoothing_y=validated_smoothing_y,
        selected_points=int(selected.size),
        total_points=int(values.size),
        solver_stop_code=int(stop_code),
        solver_iterations=int(iterations),
        augmented_residual_norm=float(augmented_residual_norm),
        normal_residual_norm=float(normal_residual_norm),
        operator_norm=float(operator_norm),
        condition_estimate=float(condition_estimate),
        coefficient_norm=float(coefficient_norm),
        weighted_data_residual_norm=float(np.linalg.norm(weighted_data_residual)),
        penalty_x_norm=float(np.linalg.norm(penalty_x)),
        penalty_y_norm=float(np.linalg.norm(penalty_y)),
        x_min=x_min,
        x_max=x_max,
        y_min=y_min,
        y_max=y_max,
    )
