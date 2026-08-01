from __future__ import annotations

import numpy as np
import pytest
from scipy.interpolate import BSpline
from scipy.sparse import eye, kron, vstack

from spmkit.core.analysis._pspline import (
    _difference_matrix,
    _open_uniform_knots,
    fit_pspline_surface,
)


def _surface_from_coefficients(
    coefficients: np.ndarray,
    *,
    rows: int,
    columns: int,
    degree_x: int,
    degree_y: int,
) -> np.ndarray:
    knots_x = _open_uniform_knots(
        coefficients.shape[1],
        degree_x,
    )
    knots_y = _open_uniform_knots(
        coefficients.shape[0],
        degree_y,
    )

    basis_x = BSpline.design_matrix(
        np.linspace(0.0, 1.0, columns),
        knots_x,
        degree_x,
    )
    basis_y = BSpline.design_matrix(
        np.linspace(0.0, 1.0, rows),
        knots_y,
        degree_y,
    )

    return np.asarray(
        basis_y @ coefficients @ basis_x.T,
        dtype=float,
        order="C",
    )


def test_recovers_zero_penalty_tensor_surface() -> None:
    rows = 15
    columns = 17
    n_basis_x = 8
    n_basis_y = 7

    x_index = np.arange(
        n_basis_x,
        dtype=float,
    )[None, :]
    y_index = np.arange(
        n_basis_y,
        dtype=float,
    )[:, None]

    expected_coefficients = 2.0 + 0.3 * x_index - 0.2 * y_index + 0.05 * x_index * y_index

    data = _surface_from_coefficients(
        expected_coefficients,
        rows=rows,
        columns=columns,
        degree_x=3,
        degree_y=3,
    )

    result = fit_pspline_surface(
        data,
        n_basis_x=n_basis_x,
        n_basis_y=n_basis_y,
        degree_x=3,
        degree_y=3,
        penalty_order_x=2,
        penalty_order_y=2,
        smoothing_x=4.0,
        smoothing_y=7.0,
        atol=1e-14,
        btol=1e-14,
    )

    np.testing.assert_allclose(
        result.coefficients,
        expected_coefficients,
        rtol=0.0,
        atol=2e-10,
    )
    np.testing.assert_allclose(
        result.model,
        data,
        rtol=0.0,
        atol=2e-10,
    )

    assert result.penalty_x_norm < 2e-10
    assert result.penalty_y_norm < 2e-10


def test_matches_explicit_dense_weighted_masked_oracle() -> None:
    rows = 11
    columns = 13
    n_basis_x = 7
    n_basis_y = 6
    degree_x = 3
    degree_y = 3
    penalty_order_x = 2
    penalty_order_y = 2
    smoothing_x = 0.8
    smoothing_y = 2.1

    rng = np.random.default_rng(20260801)

    data = rng.normal(size=(rows, columns))
    mask = np.ones(
        data.shape,
        dtype=bool,
    )
    mask[3:7, 4:9] = False

    weights = np.linspace(
        0.4,
        1.6,
        data.size,
    ).reshape(data.shape)

    result = fit_pspline_surface(
        data,
        mask=mask,
        weights=weights,
        n_basis_x=n_basis_x,
        n_basis_y=n_basis_y,
        degree_x=degree_x,
        degree_y=degree_y,
        penalty_order_x=penalty_order_x,
        penalty_order_y=penalty_order_y,
        smoothing_x=smoothing_x,
        smoothing_y=smoothing_y,
        atol=1e-14,
        btol=1e-14,
        maxiter=4000,
    )

    knots_x = _open_uniform_knots(
        n_basis_x,
        degree_x,
    )
    knots_y = _open_uniform_knots(
        n_basis_y,
        degree_y,
    )

    basis_x = BSpline.design_matrix(
        np.linspace(0.0, 1.0, columns),
        knots_x,
        degree_x,
    )
    basis_y = BSpline.design_matrix(
        np.linspace(0.0, 1.0, rows),
        knots_y,
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

    selected = np.flatnonzero(mask.ravel(order="C"))
    sqrt_weights = np.sqrt(weights.ravel(order="C")[selected])

    data_operator = kron(
        basis_y,
        basis_x,
        format="csr",
    )[selected]

    weighted_data_operator = data_operator.multiply(sqrt_weights[:, None])

    penalty_x = kron(
        eye(n_basis_y, format="csr"),
        difference_x,
        format="csr",
    )
    penalty_y = kron(
        difference_y,
        eye(n_basis_x, format="csr"),
        format="csr",
    )

    explicit_system = vstack(
        (
            weighted_data_operator,
            np.sqrt(smoothing_x) * penalty_x,
            np.sqrt(smoothing_y) * penalty_y,
        ),
        format="csr",
    )

    right_hand_side = np.concatenate(
        (
            sqrt_weights * data.ravel(order="C")[selected],
            np.zeros(
                explicit_system.shape[0] - selected.size,
                dtype=float,
            ),
        )
    )

    expected_vector = np.linalg.lstsq(
        explicit_system.toarray(),
        right_hand_side,
        rcond=None,
    )[0]

    expected_coefficients = expected_vector.reshape(
        n_basis_y,
        n_basis_x,
        order="C",
    )
    expected_model = np.asarray(
        basis_y @ expected_coefficients @ basis_x.T,
        dtype=float,
        order="C",
    )

    np.testing.assert_allclose(
        result.coefficients,
        expected_coefficients,
        rtol=0.0,
        atol=2e-10,
    )
    np.testing.assert_allclose(
        result.model,
        expected_model,
        rtol=0.0,
        atol=2e-10,
    )


def test_mask_can_exclude_nonfinite_data() -> None:
    data = np.arange(
        99,
        dtype=float,
    ).reshape(9, 11)

    mask = np.ones(
        data.shape,
        dtype=bool,
    )
    mask[4, 5] = False
    data[4, 5] = np.nan

    result = fit_pspline_surface(
        data,
        mask=mask,
        n_basis_x=6,
        n_basis_y=6,
    )

    assert np.all(np.isfinite(result.model))
    assert result.selected_points == data.size - 1


def test_selected_nonfinite_data_is_rejected() -> None:
    data = np.ones(
        (9, 11),
        dtype=float,
    )
    data[4, 5] = np.nan

    with pytest.raises(
        ValueError,
        match="selected P-spline data must be finite",
    ):
        fit_pspline_surface(
            data,
            n_basis_x=6,
            n_basis_y=6,
        )


def test_penalty_null_space_must_be_identifiable() -> None:
    data = np.ones(
        (9, 11),
        dtype=float,
    )
    mask = np.zeros(
        data.shape,
        dtype=bool,
    )
    mask[0, 0] = True

    with pytest.raises(
        ValueError,
        match="penalty null space",
    ):
        fit_pspline_surface(
            data,
            mask=mask,
            n_basis_x=6,
            n_basis_y=6,
        )


def test_input_is_not_mutated_and_results_are_read_only() -> None:
    rng = np.random.default_rng(91)
    data = rng.normal(size=(10, 12))
    original = data.copy()

    result = fit_pspline_surface(
        data,
        n_basis_x=6,
        n_basis_y=6,
    )

    np.testing.assert_array_equal(
        data,
        original,
    )

    assert not result.model.flags.writeable
    assert not result.coefficients.flags.writeable
    assert not result.knots_x.flags.writeable
    assert not result.knots_y.flags.writeable

    with pytest.raises(ValueError):
        result.model[0, 0] = 0.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n_basis_x": 3, "degree_x": 3},
        {"degree_x": -1},
        {"penalty_order_x": 0},
        {
            "n_basis_x": 6,
            "penalty_order_x": 6,
        },
        {"smoothing_x": 0.0},
        {"smoothing_y": np.inf},
        {"atol": 0.0},
        {"btol": 0.0},
        {"conlim": 0.0},
        {"maxiter": 0},
    ],
)
def test_invalid_configuration_is_rejected(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(
        (TypeError, ValueError),
    ):
        fit_pspline_surface(
            np.ones(
                (9, 11),
                dtype=float,
            ),
            n_basis_x=6,
            n_basis_y=6,
            **kwargs,
        )


def test_complex_surface_data_is_rejected() -> None:
    data = np.ones(
        (9, 11),
        dtype=complex,
    )

    with pytest.raises(
        TypeError,
        match="P-spline surface data must be real numeric",
    ):
        fit_pspline_surface(
            data,
            n_basis_x=6,
            n_basis_y=6,
        )


def test_complex_weights_are_rejected() -> None:
    data = np.ones(
        (9, 11),
        dtype=float,
    )
    weights = np.ones(
        data.shape,
        dtype=complex,
    )

    with pytest.raises(
        TypeError,
        match="P-spline weights must be real numeric",
    ):
        fit_pspline_surface(
            data,
            weights=weights,
            n_basis_x=6,
            n_basis_y=6,
        )


def test_complex_coordinates_are_rejected() -> None:
    data = np.ones(
        (9, 11),
        dtype=float,
    )
    x = np.linspace(
        0.0,
        1.0,
        data.shape[1],
    ).astype(complex)

    with pytest.raises(
        TypeError,
        match="x coordinates must be real numeric",
    ):
        fit_pspline_surface(
            data,
            x=x,
            n_basis_x=6,
            n_basis_y=6,
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"smoothing_x": True},
        {"atol": np.array(True)},
    ],
)
def test_boolean_solver_parameters_are_rejected(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(
        TypeError,
        match="must be a real numeric scalar",
    ):
        fit_pspline_surface(
            np.ones(
                (9, 11),
                dtype=float,
            ),
            n_basis_x=6,
            n_basis_y=6,
            **kwargs,
        )
