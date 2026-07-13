"""Tests de nivelación."""

from __future__ import annotations

import warnings
from collections.abc import Callable

import numpy as np
import pytest

from spmkit.core.analysis import leveling
from spmkit.core.models import SPMChannel


def test_plane_fit_removes_tilt(tilted_surface: SPMChannel) -> None:
    leveled = leveling.plane_fit(tilted_surface)
    # Tras quitar el plano, la media debe ser ~0 y el rango mucho menor.
    assert abs(leveled.data.mean()) < 1e-6
    assert np.ptp(leveled.data) < np.ptp(tilted_surface.data)


def test_plane_fit_preserves_metadata(tilted_surface: SPMChannel) -> None:
    leveled = leveling.plane_fit(tilted_surface)
    assert leveled.unit == tilted_surface.unit
    assert leveled.x_range == tilted_surface.x_range
    assert leveled.shape == tilted_surface.shape


def test_plane_fit_does_not_mutate_or_share_input_data(tilted_surface: SPMChannel) -> None:
    original_data = tilted_surface.data.copy()

    leveled = leveling.plane_fit(tilted_surface)

    assert np.array_equal(tilted_surface.data, original_data)
    assert isinstance(leveled, SPMChannel)
    assert leveled is not tilted_surface
    assert not np.shares_memory(leveled.data, tilted_surface.data)


def test_plane_fit_ignores_nan_and_preserves_mask() -> None:
    yy, xx = np.mgrid[0:4, 0:4]
    data = (2.0 * xx + 3.0 * yy + 1.0).astype(float)
    data[1, 2] = np.nan
    original = data.copy()
    ch = SPMChannel(name="Z", data=data, unit="m", x_range=1e-6, y_range=1e-6)

    leveled = leveling.plane_fit(ch)

    assert np.isnan(leveled.data[1, 2])
    assert np.allclose(leveled.data[np.isfinite(original)], 0.0, atol=1e-12)
    assert np.array_equal(ch.data, original, equal_nan=True)


def test_polynomial_flattens_curvature() -> None:
    rows = cols = 32
    yy, xx = np.mgrid[0:rows, 0:cols]
    bowl = (xx - 16) ** 2 + (yy - 16) ** 2
    ch = SPMChannel(name="Z", data=bowl.astype(float), unit="m", x_range=1e-6, y_range=1e-6)
    leveled = leveling.polynomial(ch, order=2)
    assert np.allclose(leveled.data, 0.0, atol=1e-6)


def test_polynomial_ignores_nan_and_preserves_mask() -> None:
    yy, xx = np.mgrid[0:4, 0:4]
    data = (xx**2 + yy**2 + xx * yy).astype(float)
    data[2, 1] = np.nan
    original = data.copy()
    ch = SPMChannel(name="Z", data=data, unit="m", x_range=1e-6, y_range=1e-6)

    leveled = leveling.polynomial(ch, order=2)

    assert np.isnan(leveled.data[2, 1])
    assert np.allclose(leveled.data[np.isfinite(original)], 0.0, atol=1e-10)
    assert np.array_equal(ch.data, original, equal_nan=True)


def test_polynomial_avoids_false_rank_loss_on_large_coordinates() -> None:
    ch = SPMChannel(name="Z", data=np.zeros((32, 32)), unit="m", x_range=1e-6, y_range=1e-6)

    leveled = leveling.polynomial(ch, order=8)

    assert np.array_equal(leveled.data, np.zeros((32, 32)))


@pytest.mark.parametrize("operation", [leveling.plane_fit, leveling.polynomial])
def test_surface_fit_requires_image_of_at_least_two_by_two(
    operation: Callable[[SPMChannel], SPMChannel],
) -> None:
    ch = SPMChannel(name="Z", data=np.ones((1, 4)), unit="m", x_range=1e-6, y_range=1e-6)

    with pytest.raises(ValueError, match="2x2"):
        operation(ch)


def test_plane_fit_requires_enough_independent_finite_points() -> None:
    ch = SPMChannel(
        name="Z",
        data=np.array([[1.0, np.nan], [np.nan, 2.0]]),
        unit="m",
        x_range=1e-6,
        y_range=1e-6,
    )

    with pytest.raises(ValueError, match="(?i)puntos finitos"):
        leveling.plane_fit(ch)


def test_plane_fit_rejects_collinear_finite_points_by_rank() -> None:
    data = np.full((3, 3), np.nan)
    np.fill_diagonal(data, [1.0, 2.0, 3.0])
    ch = SPMChannel(name="Z", data=data, unit="m", x_range=1e-6, y_range=1e-6)

    with pytest.raises(ValueError, match="(?i)rango insuficiente"):
        leveling.plane_fit(ch)


def test_polynomial_requires_enough_independent_finite_points() -> None:
    ch = SPMChannel(name="Z", data=np.ones((2, 2)), unit="m", x_range=1e-6, y_range=1e-6)

    with pytest.raises(ValueError, match="(?i)puntos finitos"):
        leveling.polynomial(ch, order=2)


def test_polynomial_rejects_dependent_basis_by_rank() -> None:
    ch = SPMChannel(name="Z", data=np.ones((2, 3)), unit="m", x_range=1e-6, y_range=1e-6)

    with pytest.raises(ValueError, match="(?i)rango insuficiente"):
        leveling.polynomial(ch, order=2)


def test_align_rows() -> None:
    data = np.zeros((10, 10))
    data += np.arange(10).reshape(-1, 1)  # offset por fila
    ch = SPMChannel(name="Z", data=data, unit="m", x_range=1e-6, y_range=1e-6)
    leveled = leveling.align_rows(ch, method="median")
    assert np.allclose(leveled.data, 0.0)


@pytest.mark.parametrize("method", ["median", "mean"])
def test_align_rows_ignores_nan_without_warning(method: str) -> None:
    data = np.array([[1.0, np.nan, 3.0], [np.nan, np.nan, np.nan]])
    ch = SPMChannel(name="Z", data=data, unit="m", x_range=1e-6, y_range=1e-6)

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        leveled = leveling.align_rows(ch, method=method)

    assert not recorded
    assert np.array_equal(leveled.data[0], np.array([-1.0, np.nan, 1.0]), equal_nan=True)
    assert np.isnan(leveled.data[1]).all()
