from __future__ import annotations

import numpy as np
import pytest

import spmkit.core.analysis._flatten_base as flatten_base_core
from spmkit.core.analysis._flatten_base import (
    BasePeakFit,
    BasePeakWindow,
    HeightDistribution,
    _fit_base_peak,
    _gwyddion_height_distribution,
    _select_base_peak_window,
)


def test_height_distribution_matches_nonconstant_gwyddion_contract() -> None:
    data = np.array(
        [
            [0.0, 0.2, 0.8, 1.5],
            [2.1, 3.1, 3.7, 4.0],
        ],
        dtype=float,
    )
    original = data.copy()

    result = _gwyddion_height_distribution(data)

    expected_counts = np.array([2, 1, 1, 1, 0, 1, 2])
    expected_width = 4.0 / 7.0
    expected_centers = (np.arange(7, dtype=float) + 0.5) * expected_width
    expected_density = expected_counts * 7.0 / (4.0 * data.size)

    np.testing.assert_allclose(result.centers, expected_centers)
    np.testing.assert_allclose(result.density, expected_density)
    assert result.bin_width == pytest.approx(expected_width)
    assert result.minimum == 0.0
    assert result.maximum == 4.0
    assert result.sample_count == data.size
    assert np.sum(result.density) * result.bin_width == pytest.approx(1.0)

    np.testing.assert_array_equal(data, original)
    assert not result.centers.flags.writeable
    assert not result.density.flags.writeable


def test_height_distribution_preserves_gwyddion_constant_field_convention() -> None:
    data = np.full((3, 3), 5.0)

    result = _gwyddion_height_distribution(data)

    expected_width = 5.0 / 7.0
    expected_centers = (np.arange(7, dtype=float) + 0.5) * expected_width
    expected_density = np.zeros(7)
    expected_density[0] = 7.0 / 5.0

    np.testing.assert_allclose(result.centers, expected_centers)
    np.testing.assert_allclose(result.density, expected_density)
    assert result.bin_width == pytest.approx(expected_width)
    assert result.minimum == 5.0
    assert result.maximum == 5.0
    assert result.sample_count == 9
    assert np.sum(result.density) * result.bin_width == pytest.approx(1.0)



def test_base_peak_window_matches_gwyddion_selection_rules() -> None:
    centers = np.arange(9, dtype=float) + 0.5
    density = np.array(
        [0.1, 0.2, 1.0, 1.0, 0.29, 0.1, 0.0, 0.0, 0.0],
        dtype=float,
    )
    distribution = HeightDistribution(
        centers=centers,
        density=density,
        bin_width=1.0,
        minimum=0.0,
        maximum=9.0,
        sample_count=100,
    )

    result = _select_base_peak_window(distribution)

    assert result.peak_index == 2
    assert result.start_index == 0
    assert result.stop_index == 7
    np.testing.assert_array_equal(result.centers, centers[:7])
    np.testing.assert_array_equal(result.density, density[:7])
    assert result.initial_mean == pytest.approx(2.5)
    assert result.initial_offset == 0.0
    assert result.initial_amplitude == pytest.approx(1.0)
    assert result.initial_width == pytest.approx(2.1)
    assert not result.centers.flags.writeable
    assert not result.density.flags.writeable


def test_base_peak_window_rejects_fewer_than_seven_bins() -> None:
    distribution = HeightDistribution(
        centers=np.arange(6, dtype=float) + 0.5,
        density=np.ones(6),
        bin_width=1.0,
        minimum=0.0,
        maximum=6.0,
        sample_count=8,
    )

    with pytest.raises(
        ValueError,
        match="base peak estimation requires at least seven histogram bins",
    ):
        _select_base_peak_window(distribution)


def test_base_peak_fit_recovers_exact_gaussian() -> None:
    centers = np.linspace(-3.0, 3.0, 17)
    expected_mean = 0.35
    expected_offset = 0.18
    expected_amplitude = 2.4
    expected_width = 1.1

    density = expected_offset + expected_amplitude * np.exp(
        -np.square((centers - expected_mean) / expected_width)
    )
    peak_index = int(np.argmax(density))

    window = BasePeakWindow(
        centers=centers,
        density=density,
        peak_index=peak_index,
        start_index=0,
        stop_index=centers.size,
        initial_mean=float(centers[peak_index]),
        initial_offset=0.0,
        initial_amplitude=float(density[peak_index]),
        initial_width=1.8,
    )

    result = _fit_base_peak(window)

    assert result.solver_success
    assert result.covariance_available
    assert result.success
    assert result.mean == pytest.approx(expected_mean, abs=1e-8)
    assert result.offset == pytest.approx(expected_offset, abs=1e-8)
    assert result.amplitude == pytest.approx(expected_amplitude, abs=1e-8)
    assert result.width == pytest.approx(expected_width, abs=1e-8)
    assert result.rms == pytest.approx(expected_width / np.sqrt(2.0), abs=1e-8)
    assert result.residual_norm < 1e-9
    assert result.evaluations > 0
    assert result.jacobian_rank == 4
    assert np.isfinite(result.condition_estimate)


def test_base_peak_fit_marks_constant_density_as_unidentifiable() -> None:
    centers = np.linspace(-3.0, 3.0, 7)
    density = np.ones_like(centers)

    window = BasePeakWindow(
        centers=centers,
        density=density,
        peak_index=0,
        start_index=0,
        stop_index=centers.size,
        initial_mean=float(centers[0]),
        initial_offset=0.0,
        initial_amplitude=1.0,
        initial_width=2.1,
    )

    result = _fit_base_peak(window)

    assert not result.covariance_available
    assert not result.success
    assert result.jacobian_rank < 4


def test_base_peak_fit_matches_gwyddion_271_reference() -> None:
    """Cross-check a perturbed Gaussian against a direct Gwyddion 2.71 probe."""
    centers = -3.0 + 0.375 * np.arange(17, dtype=float)
    density = (
        0.18
        + 2.4 * np.exp(-np.square((centers - 0.35) / 1.1))
        + 0.015 * np.sin(1.7 * centers)
    )
    peak_index = int(np.argmax(density))

    window = BasePeakWindow(
        centers=centers,
        density=density,
        peak_index=peak_index,
        start_index=0,
        stop_index=centers.size,
        initial_mean=float(centers[peak_index]),
        initial_offset=0.0,
        initial_amplitude=float(density[peak_index]),
        initial_width=1.8,
    )

    result = _fit_base_peak(window)

    # Frozen from a direct libgwyddion 2.71 C reference probe.
    assert result.success
    assert result.mean == pytest.approx(
        0.35624774459072917,
        abs=5e-10,
    )
    assert result.rms == pytest.approx(
        0.77337116119210381,
        abs=5e-10,
    )
    assert result.offset == pytest.approx(
        0.18099383510469755,
        abs=5e-10,
    )
    assert result.amplitude == pytest.approx(
        2.4105144489572057,
        abs=5e-10,
    )
    assert result.width == pytest.approx(
        1.0937119849061023,
        abs=5e-10,
    )


def test_estimate_base_peak_composes_verified_stages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = np.arange(64, dtype=float).reshape(8, 8)
    original = data.copy()

    distribution = HeightDistribution(
        centers=np.arange(7, dtype=float) + 0.5,
        density=np.array([0.1, 0.3, 1.0, 0.4, 0.2, 0.1, 0.0]),
        bin_width=1.0,
        minimum=0.0,
        maximum=7.0,
        sample_count=data.size,
    )
    window = BasePeakWindow(
        centers=distribution.centers,
        density=distribution.density,
        peak_index=2,
        start_index=0,
        stop_index=7,
        initial_mean=2.5,
        initial_offset=0.0,
        initial_amplitude=1.0,
        initial_width=2.1,
    )
    fit = BasePeakFit(
        mean=2.45,
        rms=0.4,
        offset=0.01,
        amplitude=0.99,
        width=0.4 * np.sqrt(2.0),
        residual_norm=1e-8,
        solver_success=True,
        covariance_available=True,
        evaluations=12,
        jacobian_rank=4,
        condition_estimate=8.0,
    )

    calls: list[str] = []

    def fake_distribution(received: np.ndarray) -> HeightDistribution:
        assert received is data
        calls.append("distribution")
        return distribution

    def fake_window(received: HeightDistribution) -> BasePeakWindow:
        assert received is distribution
        calls.append("window")
        return window

    def fake_fit(received: BasePeakWindow) -> BasePeakFit:
        assert received is window
        calls.append("fit")
        return fit

    monkeypatch.setattr(
        flatten_base_core,
        "_gwyddion_height_distribution",
        fake_distribution,
    )
    monkeypatch.setattr(
        flatten_base_core,
        "_select_base_peak_window",
        fake_window,
    )
    monkeypatch.setattr(
        flatten_base_core,
        "_fit_base_peak",
        fake_fit,
    )

    result = flatten_base_core._estimate_base_peak(data)

    assert calls == ["distribution", "window", "fit"]
    assert result.distribution is distribution
    assert result.window is window
    assert result.fit is fit
    assert result.success
    assert result.mean == fit.mean
    assert result.rms == fit.rms
    np.testing.assert_array_equal(data, original)


def test_gwyddion_facet_plane_recovers_exact_physical_tilt() -> None:
    rows = 4
    columns = 5
    pixel_size_x = 2.0
    pixel_size_y = 0.5
    expected_physical_x = 0.3
    expected_physical_y = -0.2

    x = np.arange(columns, dtype=float) * pixel_size_x
    y = np.arange(rows, dtype=float) * pixel_size_y
    xx, yy = np.meshgrid(x, y)

    data = 7.0 + expected_physical_x * xx + expected_physical_y * yy
    original = data.copy()

    result = flatten_base_core._estimate_gwyddion_facet_plane(
        data,
        pixel_size_x=pixel_size_x,
        pixel_size_y=pixel_size_y,
    )

    expected_x_coefficient = expected_physical_x * pixel_size_x
    expected_y_coefficient = expected_physical_y * pixel_size_y
    expected_scale_squared = (
        expected_physical_x**2 + expected_physical_y**2
    ) / 20.0
    expected_intercept = -0.5 * (
        expected_x_coefficient * columns
        + expected_y_coefficient * rows
    )
    expected_cells = (rows - 1) * (columns - 1)

    assert not result.degenerate
    assert result.cell_count == expected_cells
    assert result.physical_slope_x == pytest.approx(expected_physical_x)
    assert result.physical_slope_y == pytest.approx(expected_physical_y)
    assert result.x_coefficient == pytest.approx(expected_x_coefficient)
    assert result.y_coefficient == pytest.approx(expected_y_coefficient)
    assert result.intercept == pytest.approx(expected_intercept)
    assert result.slope_scale_squared == pytest.approx(
        expected_scale_squared
    )
    assert result.weight_sum == pytest.approx(
        expected_cells * np.exp(-20.0)
    )

    np.testing.assert_array_equal(data, original)


def test_gwyddion_facet_plane_handles_flat_field_without_nan() -> None:
    data = np.full((4, 5), 3.2)

    result = flatten_base_core._estimate_gwyddion_facet_plane(
        data,
        pixel_size_x=0.4,
        pixel_size_y=0.7,
    )

    assert result.degenerate
    assert result.cell_count == 12
    assert result.intercept == 0.0
    assert result.x_coefficient == 0.0
    assert result.y_coefficient == 0.0
    assert result.physical_slope_x == 0.0
    assert result.physical_slope_y == 0.0
    assert result.slope_scale_squared == 0.0
    assert result.weight_sum == pytest.approx(12.0)


def test_gwyddion_facet_plane_matches_gwyddion_271_reference() -> None:
    """Cross-check the facet estimator against direct libgwyddion 2.71."""
    rows = 6
    columns = 7
    pixel_size_x = 2.0
    pixel_size_y = 0.5

    data = np.empty((rows, columns), dtype=float)

    for row in range(rows):
        for column in range(columns):
            x = column * pixel_size_x
            y = row * pixel_size_y
            value = (
                7.0
                + 0.3 * x
                - 0.2 * y
                + 0.04 * np.sin(0.7 * column + 0.3 * row)
            )

            if row == 1 and column == 2:
                value += 4.0
            if row == 3 and column == 5:
                value += 2.5

            data[row, column] = value

    result = flatten_base_core._estimate_gwyddion_facet_plane(
        data,
        pixel_size_x=pixel_size_x,
        pixel_size_y=pixel_size_y,
    )

    # Frozen from a direct gwy_data_field_fit_facet_plane() probe.
    assert not result.degenerate
    assert result.intercept == pytest.approx(
        -1.7454698947303242,
        abs=5e-13,
    )
    assert result.x_coefficient == pytest.approx(
        0.58850087792355377,
        abs=5e-13,
    )
    assert result.y_coefficient == pytest.approx(
        -0.10476105933403794,
        abs=5e-13,
    )
    assert result.physical_slope_x == pytest.approx(
        0.29425043896177688,
        abs=5e-13,
    )
    assert result.physical_slope_y == pytest.approx(
        -0.20952211866807588,
        abs=5e-13,
    )

    assert result.cell_count == 30
    assert result.slope_scale_squared == pytest.approx(
        0.16422579481110028,
        abs=5e-14,
    )
    assert result.weight_sum == pytest.approx(
        9.9247467971063745,
        abs=5e-13,
    )
