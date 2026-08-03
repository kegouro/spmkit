"""Independent FITPACK checks for exact P-spline reconstruction."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.interpolate import (
    BSpline,
    LSQBivariateSpline,
)

from spmkit.core.analysis._pspline import (
    _open_uniform_knots,
    fit_pspline_surface,
)


def _validation_problem() -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    degree = 3
    n_basis_x = 7
    n_basis_y = 6

    x = np.linspace(0.0, 1.0, 19)
    y = np.linspace(0.0, 1.0, 17)

    knots_x = _open_uniform_knots(
        n_basis_x,
        degree,
    )
    knots_y = _open_uniform_knots(
        n_basis_y,
        degree,
    )

    basis_x = BSpline.design_matrix(
        x,
        knots_x,
        degree,
    ).toarray()
    basis_y = BSpline.design_matrix(
        y,
        knots_y,
        degree,
    ).toarray()

    x_index = np.arange(
        n_basis_x,
        dtype=float,
    )[None, :]
    y_index = np.arange(
        n_basis_y,
        dtype=float,
    )[:, None]

    coefficients = 1.7 + 0.31 * x_index - 0.23 * y_index + 0.047 * x_index * y_index

    surface = basis_y @ coefficients @ basis_x.T

    return (
        x,
        y,
        knots_x,
        knots_y,
        np.asarray(surface, dtype=float),
    )


def _fitpack_model(
    x: np.ndarray,
    y: np.ndarray,
    knots_x: np.ndarray,
    knots_y: np.ndarray,
    data: np.ndarray,
    selection: np.ndarray,
) -> np.ndarray:
    degree = 3
    xx, yy = np.meshgrid(
        x,
        y,
        indexing="xy",
    )

    interior_x = knots_x[degree + 1 : -(degree + 1)]
    interior_y = knots_y[degree + 1 : -(degree + 1)]

    spline = LSQBivariateSpline(
        xx[selection],
        yy[selection],
        data[selection],
        interior_x,
        interior_y,
        kx=degree,
        ky=degree,
    )

    return np.asarray(
        spline.ev(
            xx.ravel(order="C"),
            yy.ravel(order="C"),
        ).reshape(data.shape),
        dtype=float,
        order="C",
    )


@pytest.mark.parametrize(
    "exclude_feature",
    [False, True],
    ids=[
        "complete_surface",
        "excluded_feature",
    ],
)
def test_fitpack_recovers_penalty_null_surface(
    exclude_feature: bool,
) -> None:
    x, y, knots_x, knots_y, expected = _validation_problem()

    observed = expected.copy()
    selection = np.ones(
        expected.shape,
        dtype=bool,
    )

    if exclude_feature:
        observed[8, 9] += 100.0
        selection[8, 9] = False

    fit = fit_pspline_surface(
        observed,
        x=x,
        y=y,
        mask=selection,
        n_basis_x=7,
        n_basis_y=6,
        degree_x=3,
        degree_y=3,
        penalty_order_x=2,
        penalty_order_y=2,
        smoothing_x=3.0,
        smoothing_y=7.0,
        atol=1e-14,
        btol=1e-14,
    )

    fitpack = _fitpack_model(
        x,
        y,
        knots_x,
        knots_y,
        observed,
        selection,
    )

    np.testing.assert_allclose(
        fit.model,
        expected,
        rtol=0.0,
        atol=1e-9,
    )
    np.testing.assert_allclose(
        fitpack,
        expected,
        rtol=0.0,
        atol=1e-9,
    )
    np.testing.assert_allclose(
        fit.model,
        fitpack,
        rtol=0.0,
        atol=1e-9,
    )

    assert fit.penalty_x_norm < 1e-9
    assert fit.penalty_y_norm < 1e-9
