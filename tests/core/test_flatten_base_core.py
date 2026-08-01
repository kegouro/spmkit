from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis._flatten_base import (
    HeightDistribution,
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
