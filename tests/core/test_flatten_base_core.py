from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis._flatten_base import (
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
