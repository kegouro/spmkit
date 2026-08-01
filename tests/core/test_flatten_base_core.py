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


def test_flatten_base_facet_stage_runs_exactly_five_iterations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = 4
    columns = 5
    data = np.arange(rows * columns, dtype=float).reshape(rows, columns)
    original = data.copy()

    plane = flatten_base_core.FacetPlaneEstimate(
        intercept=0.4,
        x_coefficient=0.2,
        y_coefficient=-0.1,
        physical_slope_x=0.1,
        physical_slope_y=-0.2,
        slope_scale_squared=0.03,
        cell_count=(rows - 1) * (columns - 1),
        weight_sum=6.0,
        degenerate=False,
    )

    class SuccessfulPeak:
        success = True

    peak = SuccessfulPeak()
    facet_inputs: list[np.ndarray] = []
    peak_inputs: list[np.ndarray] = []

    def fake_facet(
        received: np.ndarray,
        *,
        pixel_size_x: float,
        pixel_size_y: float,
    ) -> flatten_base_core.FacetPlaneEstimate:
        assert pixel_size_x == 2.0
        assert pixel_size_y == 0.5
        facet_inputs.append(received.copy())
        return plane

    def fake_peak(received: np.ndarray) -> SuccessfulPeak:
        peak_inputs.append(received.copy())
        return peak

    monkeypatch.setattr(
        flatten_base_core,
        "_estimate_gwyddion_facet_plane",
        fake_facet,
    )
    monkeypatch.setattr(
        flatten_base_core,
        "_estimate_base_peak",
        fake_peak,
    )

    result = flatten_base_core._run_flatten_base_facet_stage(
        data,
        pixel_size_x=2.0,
        pixel_size_y=0.5,
    )

    column_indices = np.arange(columns, dtype=float)
    row_indices = np.arange(rows, dtype=float)
    xx, yy = np.meshgrid(column_indices, row_indices)
    single_plane = (
        plane.intercept
        + plane.x_coefficient * xx
        + plane.y_coefficient * yy
    )

    np.testing.assert_allclose(
        result.background,
        5.0 * single_plane,
    )
    np.testing.assert_allclose(
        result.corrected,
        data - 5.0 * single_plane,
    )

    assert len(facet_inputs) == 5
    assert len(peak_inputs) == 6
    assert result.initial_peak is peak
    assert result.completed_iterations == 5
    assert len(result.iterations) == 5
    assert result.termination == "maximum_iterations"

    for index, iteration in enumerate(result.iterations):
        assert iteration.index == index
        assert iteration.plane is plane
        assert iteration.peak is peak

    np.testing.assert_array_equal(data, original)
    assert not result.corrected.flags.writeable
    assert not result.background.flags.writeable


def test_flatten_base_facet_stage_stops_before_degenerate_plane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = np.arange(20, dtype=float).reshape(4, 5)
    original = data.copy()

    class SuccessfulPeak:
        success = True

    peak = SuccessfulPeak()
    degenerate_plane = flatten_base_core.FacetPlaneEstimate(
        intercept=0.0,
        x_coefficient=0.0,
        y_coefficient=0.0,
        physical_slope_x=0.0,
        physical_slope_y=0.0,
        slope_scale_squared=0.0,
        cell_count=12,
        weight_sum=12.0,
        degenerate=True,
    )

    peak_calls: list[np.ndarray] = []
    facet_calls: list[np.ndarray] = []

    def fake_peak(received: np.ndarray) -> SuccessfulPeak:
        peak_calls.append(received.copy())
        return peak

    def fake_facet(
        received: np.ndarray,
        *,
        pixel_size_x: float,
        pixel_size_y: float,
    ) -> flatten_base_core.FacetPlaneEstimate:
        assert pixel_size_x == 1.0
        assert pixel_size_y == 1.0
        facet_calls.append(received.copy())
        return degenerate_plane

    monkeypatch.setattr(
        flatten_base_core,
        "_estimate_base_peak",
        fake_peak,
    )
    monkeypatch.setattr(
        flatten_base_core,
        "_estimate_gwyddion_facet_plane",
        fake_facet,
    )

    result = flatten_base_core._run_flatten_base_facet_stage(
        data,
        pixel_size_x=1.0,
        pixel_size_y=1.0,
    )

    assert result.initial_peak is peak
    assert result.termination == "degenerate_plane"
    assert result.completed_iterations == 0
    assert result.iterations == ()
    assert len(peak_calls) == 1
    assert len(facet_calls) == 1

    np.testing.assert_array_equal(result.corrected, data)
    np.testing.assert_array_equal(
        result.background,
        np.zeros_like(data),
    )
    np.testing.assert_array_equal(data, original)
    assert not result.corrected.flags.writeable
    assert not result.background.flags.writeable


def test_flatten_base_facet_stage_keeps_correction_before_peak_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = 4
    columns = 5
    data = np.arange(rows * columns, dtype=float).reshape(rows, columns)

    class Peak:
        def __init__(self, success: bool) -> None:
            self.success = success

    initial_peak = Peak(success=True)
    failed_peak = Peak(success=False)
    peak_results = [initial_peak, failed_peak]

    plane = flatten_base_core.FacetPlaneEstimate(
        intercept=0.3,
        x_coefficient=0.15,
        y_coefficient=-0.05,
        physical_slope_x=0.075,
        physical_slope_y=-0.1,
        slope_scale_squared=0.02,
        cell_count=12,
        weight_sum=7.0,
        degenerate=False,
    )

    facet_calls = 0

    def fake_peak(received: np.ndarray) -> Peak:
        del received
        return peak_results.pop(0)

    def fake_facet(
        received: np.ndarray,
        *,
        pixel_size_x: float,
        pixel_size_y: float,
    ) -> flatten_base_core.FacetPlaneEstimate:
        nonlocal facet_calls
        del received, pixel_size_x, pixel_size_y
        facet_calls += 1
        return plane

    monkeypatch.setattr(
        flatten_base_core,
        "_estimate_base_peak",
        fake_peak,
    )
    monkeypatch.setattr(
        flatten_base_core,
        "_estimate_gwyddion_facet_plane",
        fake_facet,
    )

    result = flatten_base_core._run_flatten_base_facet_stage(
        data,
        pixel_size_x=2.0,
        pixel_size_y=0.5,
    )

    xx, yy = np.meshgrid(
        np.arange(columns, dtype=float),
        np.arange(rows, dtype=float),
    )
    expected_plane = (
        plane.intercept
        + plane.x_coefficient * xx
        + plane.y_coefficient * yy
    )

    assert facet_calls == 1
    assert peak_results == []
    assert result.initial_peak is initial_peak
    assert result.termination == "peak_failure"
    assert result.completed_iterations == 1
    assert result.iterations[0].index == 0
    assert result.iterations[0].plane is plane
    assert result.iterations[0].peak is failed_peak

    np.testing.assert_allclose(result.background, expected_plane)
    np.testing.assert_allclose(result.corrected, data - expected_plane)


def test_grow_mask_conn4_forms_inclusive_city_block_diamond() -> None:
    mask = np.zeros((5, 5), dtype=bool)
    mask[2, 2] = True

    observed = flatten_base_core._grow_mask_conn4(
        mask,
        radius=2,
    )

    expected = np.array(
        [
            [False, False, True,  False, False],
            [False, True,  True,  True,  False],
            [True,  True,  True,  True,  True ],
            [False, True,  True,  True,  False],
            [False, False, True,  False, False],
        ],
        dtype=bool,
    )

    np.testing.assert_array_equal(observed, expected)


def test_grow_mask_conn4_matches_gwyddion_corner_handling() -> None:
    mask = np.zeros((5, 5), dtype=bool)
    mask[0, 0] = True

    observed = flatten_base_core._grow_mask_conn4(
        mask,
        radius=2,
    )

    expected = np.array(
        [
            [True, True,  True,  True,  True],
            [True, False, False, False, True],
            [True, False, False, False, True],
            [True, False, False, False, True],
            [True, True,  True,  True,  True],
        ],
        dtype=bool,
    )

    np.testing.assert_array_equal(observed, expected)
    assert np.count_nonzero(observed) == 16


def test_grow_mask_conn4_matches_gwyddion_interior_merge_reference() -> None:
    mask = np.zeros((5, 5), dtype=bool)
    mask[2, 1] = True
    mask[2, 3] = True

    observed = flatten_base_core._grow_mask_conn4(
        mask,
        radius=1,
    )

    expected = np.array(
        [
            [False, False, False, False, False],
            [False, True,  False, True,  False],
            [False, True,  True,  True,  False],
            [False, True,  False, True,  False],
            [False, False, False, False, False],
        ],
        dtype=bool,
    )

    np.testing.assert_array_equal(observed, expected)
    assert np.count_nonzero(observed) == 7


def test_grow_mask_conn4_zero_radius_returns_independent_copy() -> None:
    mask = np.zeros((4, 5), dtype=bool)
    mask[1, 3] = True
    original = mask.copy()

    observed = flatten_base_core._grow_mask_conn4(
        mask,
        radius=0,
    )

    np.testing.assert_array_equal(observed, original)
    np.testing.assert_array_equal(mask, original)
    assert not np.shares_memory(observed, mask)

    observed[0, 0] = True
    assert not mask[0, 0]


def test_grow_mask_conn4_matches_gwyddion_empty_mask_handling() -> None:
    mask = np.zeros((4, 5), dtype=bool)

    observed = flatten_base_core._grow_mask_conn4(
        mask,
        radius=3,
    )

    expected = np.array(
        [
            [True, True,  True,  True,  True],
            [True, False, False, False, True],
            [True, False, False, False, True],
            [True, True,  True,  True,  True],
        ],
        dtype=bool,
    )

    np.testing.assert_array_equal(observed, expected)
    assert np.count_nonzero(observed) == 14
    assert not np.shares_memory(observed, mask)


def test_grow_mask_conn4_does_not_mutate_seed_mask() -> None:
    mask = np.zeros((5, 5), dtype=bool)
    mask[2, 2] = True
    original = mask.copy()

    observed = flatten_base_core._grow_mask_conn4(
        mask,
        radius=2,
    )

    np.testing.assert_array_equal(mask, original)
    assert np.count_nonzero(observed) == 13
    assert not np.shares_memory(observed, mask)


def test_flatten_base_mask_uses_strict_threshold_and_degree_radius(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = np.array(
        [
            [6.0, 7.0, 8.0, 2.0],
            [9.0, 1.0, 7.0, 10.0],
            [0.0, 5.0, 3.0, 7.0],
        ],
        dtype=float,
    )
    original = data.copy()

    class Peak:
        success = True
        mean = 1.0
        rms = 2.0

    captured: dict[str, object] = {}

    def fake_grow(
        mask: np.ndarray,
        *,
        radius: int,
    ) -> np.ndarray:
        captured["mask"] = mask.copy()
        captured["radius"] = radius

        grown = mask.copy()
        grown[0, 0] = True
        return grown

    monkeypatch.setattr(
        flatten_base_core,
        "_grow_mask_conn4",
        fake_grow,
    )

    result = flatten_base_core._build_flatten_base_mask(
        data,
        peak=Peak(),
        degree=2,
    )

    expected_raw = data > 7.0
    expected_grown = expected_raw.copy()
    expected_grown[0, 0] = True

    assert result.degree == 2
    assert result.threshold == 7.0
    assert result.growth_radius == 2
    assert captured["radius"] == 2

    np.testing.assert_array_equal(captured["mask"], expected_raw)
    np.testing.assert_array_equal(result.raw, expected_raw)
    np.testing.assert_array_equal(result.grown, expected_grown)

    assert result.raw_count == 3
    assert result.grown_count == 4
    assert not result.raw.flags.writeable
    assert not result.grown.flags.writeable

    np.testing.assert_array_equal(data, original)


def test_flatten_base_mask_integrates_threshold_and_conn4_growth() -> None:
    data = np.zeros((7, 7), dtype=float)
    data[3, 3] = 4.0
    data[0, 0] = 3.0

    class Peak:
        success = True
        mean = 0.0
        rms = 1.0

    result = flatten_base_core._build_flatten_base_mask(
        data,
        peak=Peak(),
        degree=5,
    )

    expected_raw = np.zeros((7, 7), dtype=bool)
    expected_raw[3, 3] = True

    yy, xx = np.mgrid[0:7, 0:7]
    expected_grown = (
        np.abs(yy - 3) + np.abs(xx - 3)
    ) <= 3

    assert result.threshold == 3.0
    assert result.growth_radius == 3
    assert result.raw_count == 1
    assert result.grown_count == 25

    np.testing.assert_array_equal(result.raw, expected_raw)
    np.testing.assert_array_equal(result.grown, expected_grown)


def test_flatten_base_polynomial_iteration_composes_mask_fit_and_peak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = 4
    columns = 5
    data = np.arange(rows * columns, dtype=float).reshape(rows, columns)
    original = data.copy()

    raw_mask = np.zeros_like(data, dtype=bool)
    raw_mask[1, 2] = True

    grown_mask = raw_mask.copy()
    grown_mask[1, 1:4] = True
    grown_mask[0, 2] = True
    grown_mask[2, 2] = True

    raw_mask.setflags(write=False)
    grown_mask.setflags(write=False)

    automatic_mask = flatten_base_core.FlattenBaseMask(
        degree=2,
        threshold=7.0,
        growth_radius=2,
        raw=raw_mask,
        grown=grown_mask,
        raw_count=1,
        grown_count=5,
    )

    class InitialPeak:
        success = True
        mean = 1.0
        rms = 2.0

    class UpdatedPeak:
        success = True
        mean = 0.2
        rms = 0.4

    initial_peak = InitialPeak()
    updated_peak = UpdatedPeak()

    expected_background = np.full_like(data, 1.25)
    coefficients = np.arange(6, dtype=float)
    singular_values = np.linspace(6.0, 1.0, 6)

    captured: dict[str, object] = {}

    def fake_mask(
        received: np.ndarray,
        *,
        peak: InitialPeak,
        degree: int,
    ) -> flatten_base_core.FlattenBaseMask:
        np.testing.assert_array_equal(received, data)
        assert peak is initial_peak
        assert degree == 2
        return automatic_mask

    def fake_fit(
        received: np.ndarray,
        *,
        powers: tuple[tuple[int, int], ...],
        selection: np.ndarray,
        operation: str,
    ) -> tuple[np.ndarray, np.ndarray, int, np.ndarray]:
        np.testing.assert_array_equal(received, data)

        captured["powers"] = powers
        captured["selection"] = selection.copy()
        captured["operation"] = operation

        return (
            expected_background.copy(),
            coefficients.copy(),
            6,
            singular_values.copy(),
        )

    def fake_peak(received: np.ndarray) -> UpdatedPeak:
        np.testing.assert_allclose(
            received,
            data - expected_background,
        )
        return updated_peak

    monkeypatch.setattr(
        flatten_base_core,
        "_build_flatten_base_mask",
        fake_mask,
    )
    monkeypatch.setattr(
        flatten_base_core,
        "_estimate_base_peak",
        fake_peak,
    )

    import spmkit.core.analysis.leveling as leveling

    monkeypatch.setattr(
        leveling,
        "_fit_polynomial_surface_data",
        fake_fit,
    )

    result = flatten_base_core._run_flatten_base_polynomial_iteration(
        data,
        peak=initial_peak,
        degree=2,
    )

    expected_powers = (
        (0, 0),
        (0, 1),
        (0, 2),
        (1, 0),
        (1, 1),
        (2, 0),
    )

    assert captured["powers"] == expected_powers
    assert captured["operation"] == "Flatten Base degree 2"
    np.testing.assert_array_equal(
        captured["selection"],
        ~grown_mask,
    )

    assert result.degree == 2
    assert result.powers == expected_powers
    assert result.mask is automatic_mask
    assert result.selected_count == data.size - 5
    assert result.rank == 6
    assert result.peak is updated_peak

    np.testing.assert_array_equal(result.coefficients, coefficients)
    np.testing.assert_array_equal(
        result.singular_values,
        singular_values,
    )
    np.testing.assert_allclose(
        result.background,
        expected_background,
    )
    np.testing.assert_allclose(
        result.corrected,
        data - expected_background,
    )

    assert not result.coefficients.flags.writeable
    assert not result.singular_values.flags.writeable
    assert not result.background.flags.writeable
    assert not result.corrected.flags.writeable

    np.testing.assert_array_equal(data, original)


def test_flatten_base_polynomial_iteration_recovers_exact_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = 11
    columns = 11
    x = np.linspace(-1.0, 1.0, columns)
    y = np.linspace(-1.0, 1.0, rows)
    xx, yy = np.meshgrid(x, y)

    expected_background = (
        0.10
        + 0.05 * xx
        - 0.04 * yy
        + 0.03 * xx * yy
        + 0.02 * xx**2
        - 0.01 * yy**2
    )

    data = expected_background.copy()
    data[5, 5] += 5.0
    original = data.copy()

    class InitialPeak:
        success = True
        mean = 0.0
        rms = 0.2

    class UpdatedPeak:
        success = True

    updated_peak = UpdatedPeak()

    def fake_updated_peak(received: np.ndarray) -> UpdatedPeak:
        expected_corrected = np.zeros_like(data)
        expected_corrected[5, 5] = 5.0
        np.testing.assert_allclose(
            received,
            expected_corrected,
            atol=2e-13,
        )
        return updated_peak

    monkeypatch.setattr(
        flatten_base_core,
        "_estimate_base_peak",
        fake_updated_peak,
    )

    result = flatten_base_core._run_flatten_base_polynomial_iteration(
        data,
        peak=InitialPeak(),
        degree=2,
    )

    expected_coefficients = np.array(
        [
            0.10,
            -0.04,
            -0.01,
            0.05,
            0.03,
            0.02,
        ],
        dtype=float,
    )
    expected_corrected = np.zeros_like(data)
    expected_corrected[5, 5] = 5.0

    assert result.powers == (
        (0, 0),
        (0, 1),
        (0, 2),
        (1, 0),
        (1, 1),
        (2, 0),
    )
    assert result.mask.raw_count == 1
    assert result.mask.grown_count == 13
    assert result.selected_count == data.size - 13
    assert result.rank == 6
    assert result.peak is updated_peak

    np.testing.assert_allclose(
        result.coefficients,
        expected_coefficients,
        atol=2e-13,
    )
    np.testing.assert_allclose(
        result.background,
        expected_background,
        atol=2e-13,
    )
    np.testing.assert_allclose(
        result.corrected,
        expected_corrected,
        atol=2e-13,
    )
    np.testing.assert_array_equal(data, original)



def test_grow_mask_conn4_matches_gwyddion_271_right_edge_reference() -> None:
    mask = np.zeros((8, 9), dtype=bool)
    mask[2, 4] = True
    mask[5, 7] = True

    observed = flatten_base_core._grow_mask_conn4(
        mask,
        radius=2,
    )

    frozen = (
        "000010000"
        "000111000"
        "001111100"
        "000111010"
        "000010111"
        "000001110"
        "000000111"
        "000000010"
    )
    expected = np.array(
        [value == "1" for value in frozen],
        dtype=bool,
    ).reshape(8, 9)

    np.testing.assert_array_equal(observed, expected)
    assert np.count_nonzero(observed) == 24
    assert not observed[5, 8]


def test_flatten_base_polynomial_iteration_matches_gwyddion_271(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = 8
    columns = 9
    data = np.empty((rows, columns), dtype=float)

    for row in range(rows):
        y = 2.0 * row / (rows - 1.0) - 1.0

        for column in range(columns):
            x = 2.0 * column / (columns - 1.0) - 1.0
            value = (
                0.72
                + 0.18 * x
                - 0.11 * y
                + 0.07 * x * y
                + 0.035 * x**2
                - 0.02 * y**2
                + 0.025 * np.sin(0.9 * column + 0.4 * row)
            )

            if row == 2 and column == 4:
                value += 1.5
            if row == 5 and column == 7:
                value += 1.0

            data[row, column] = value

    original = data.copy()

    class InitialPeak:
        success = True
        mean = 0.75
        rms = 0.10

    class UpdatedPeak:
        success = True

    updated_peak = UpdatedPeak()

    monkeypatch.setattr(
        flatten_base_core,
        "_estimate_base_peak",
        lambda received: updated_peak,
    )

    result = flatten_base_core._run_flatten_base_polynomial_iteration(
        data,
        peak=InitialPeak(),
        degree=2,
    )

    raw_frozen = (
        "000000000"
        "000000000"
        "000010000"
        "000000000"
        "000000000"
        "000000010"
        "000000000"
        "000000000"
    )
    grown_frozen = (
        "000010000"
        "000111000"
        "001111100"
        "000111010"
        "000010111"
        "000001110"
        "000000111"
        "000000010"
    )

    expected_raw = np.array(
        [value == "1" for value in raw_frozen],
        dtype=bool,
    ).reshape(rows, columns)
    expected_grown = np.array(
        [value == "1" for value in grown_frozen],
        dtype=bool,
    ).reshape(rows, columns)

    expected_coefficients = np.array(
        [
            0.71670865227920233,
            -0.11459538697342461,
            -0.024654671854024313,
            0.18007084915965604,
            0.0761606492072983,
            0.056803123388348246,
        ],
        dtype=float,
    )

    x = np.linspace(-1.0, 1.0, columns)
    y = np.linspace(-1.0, 1.0, rows)
    xx, yy = np.meshgrid(x, y)

    expected_background = (
        expected_coefficients[0]
        + expected_coefficients[1] * yy
        + expected_coefficients[2] * yy**2
        + expected_coefficients[3] * xx
        + expected_coefficients[4] * xx * yy
        + expected_coefficients[5] * xx**2
    )

    assert result.degree == 2
    assert result.rank == 6
    assert result.selected_count == 48
    assert result.mask.raw_count == 2
    assert result.mask.grown_count == 24
    assert result.peak is updated_peak

    np.testing.assert_array_equal(result.mask.raw, expected_raw)
    np.testing.assert_array_equal(result.mask.grown, expected_grown)
    np.testing.assert_allclose(
        result.coefficients,
        expected_coefficients,
        atol=5e-13,
        rtol=0.0,
    )
    np.testing.assert_allclose(
        result.background,
        expected_background,
        atol=5e-13,
        rtol=0.0,
    )
    np.testing.assert_allclose(
        result.corrected,
        data - expected_background,
        atol=5e-13,
        rtol=0.0,
    )
    np.testing.assert_array_equal(data, original)


def test_flatten_base_polynomial_stage_runs_degrees_two_to_five(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = 4
    columns = 5
    data = np.arange(rows * columns, dtype=float).reshape(rows, columns)
    original = data.copy()

    class Peak:
        success = True

        def __init__(self, label: str) -> None:
            self.label = label

    peaks = [Peak(f"peak-{index}") for index in range(5)]
    calls: list[tuple[np.ndarray, Peak, int]] = []
    produced_iterations: list[
        flatten_base_core.FlattenBasePolynomialIteration
    ] = []

    def fake_iteration(
        received: np.ndarray,
        *,
        peak: Peak,
        degree: int,
    ) -> flatten_base_core.FlattenBasePolynomialIteration:
        expected_index = len(calls)
        expected_degree = (2, 3, 4, 5)[expected_index]

        assert degree == expected_degree
        assert peak is peaks[expected_index]

        calls.append((received.copy(), peak, degree))

        background = np.full_like(
            data,
            float(degree),
        )
        corrected = received - background

        background.setflags(write=False)
        corrected.setflags(write=False)

        coefficients = np.zeros(1, dtype=float)
        singular_values = np.ones(1, dtype=float)
        coefficients.setflags(write=False)
        singular_values.setflags(write=False)

        empty_mask = np.zeros_like(data, dtype=bool)
        empty_mask.setflags(write=False)

        automatic_mask = flatten_base_core.FlattenBaseMask(
            degree=degree,
            threshold=0.0,
            growth_radius=1 + degree // 2,
            raw=empty_mask,
            grown=empty_mask,
            raw_count=0,
            grown_count=0,
        )

        iteration = (
            flatten_base_core.FlattenBasePolynomialIteration(
                degree=degree,
                powers=((0, 0),),
                mask=automatic_mask,
                selected_count=data.size,
                coefficients=coefficients,
                rank=1,
                singular_values=singular_values,
                background=background,
                corrected=corrected,
                peak=peaks[expected_index + 1],
            )
        )
        produced_iterations.append(iteration)
        return iteration

    monkeypatch.setattr(
        flatten_base_core,
        "_run_flatten_base_polynomial_iteration",
        fake_iteration,
    )

    result = flatten_base_core._run_flatten_base_polynomial_stage(
        data,
        peak=peaks[0],
    )

    expected_background = np.full_like(
        data,
        2.0 + 3.0 + 4.0 + 5.0,
    )

    assert [call[2] for call in calls] == [2, 3, 4, 5]
    assert result.initial_peak is peaks[0]
    assert result.iterations == tuple(produced_iterations)
    assert result.completed_degrees == (2, 3, 4, 5)
    assert result.termination == "completed"

    for index, (received, received_peak, degree) in enumerate(calls):
        expected_previous = sum((2, 3, 4, 5)[:index])
        np.testing.assert_allclose(
            received,
            data - expected_previous,
        )
        assert received_peak is peaks[index]
        assert degree == (2, 3, 4, 5)[index]

    np.testing.assert_allclose(
        result.background,
        expected_background,
    )
    np.testing.assert_allclose(
        result.corrected,
        data - expected_background,
    )

    assert not result.background.flags.writeable
    assert not result.corrected.flags.writeable
    np.testing.assert_array_equal(data, original)


def test_flatten_base_polynomial_stage_stops_after_peak_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = np.arange(20, dtype=float).reshape(4, 5)
    original = data.copy()

    class Peak:
        def __init__(self, success: bool) -> None:
            self.success = success

    initial_peak = Peak(success=True)
    degree_two_peak = Peak(success=True)
    failed_peak = Peak(success=False)

    calls: list[int] = []

    def fake_iteration(
        received: np.ndarray,
        *,
        peak: Peak,
        degree: int,
    ) -> flatten_base_core.FlattenBasePolynomialIteration:
        calls.append(degree)

        if degree == 2:
            assert peak is initial_peak
            next_peak = degree_two_peak
        elif degree == 3:
            assert peak is degree_two_peak
            next_peak = failed_peak
        else:
            raise AssertionError(
                f"unexpected polynomial degree after failure: {degree}"
            )

        background = np.full_like(received, float(degree))
        corrected = received - background

        coefficients = np.zeros(1, dtype=float)
        singular_values = np.ones(1, dtype=float)
        empty_mask = np.zeros_like(received, dtype=bool)

        background.setflags(write=False)
        corrected.setflags(write=False)
        coefficients.setflags(write=False)
        singular_values.setflags(write=False)
        empty_mask.setflags(write=False)

        automatic_mask = flatten_base_core.FlattenBaseMask(
            degree=degree,
            threshold=0.0,
            growth_radius=1 + degree // 2,
            raw=empty_mask,
            grown=empty_mask,
            raw_count=0,
            grown_count=0,
        )

        return flatten_base_core.FlattenBasePolynomialIteration(
            degree=degree,
            powers=((0, 0),),
            mask=automatic_mask,
            selected_count=received.size,
            coefficients=coefficients,
            rank=1,
            singular_values=singular_values,
            background=background,
            corrected=corrected,
            peak=next_peak,
        )

    monkeypatch.setattr(
        flatten_base_core,
        "_run_flatten_base_polynomial_iteration",
        fake_iteration,
    )

    result = flatten_base_core._run_flatten_base_polynomial_stage(
        data,
        peak=initial_peak,
    )

    expected_background = np.full_like(data, 5.0)

    assert calls == [2, 3]
    assert result.initial_peak is initial_peak
    assert result.completed_degrees == (2, 3)
    assert result.termination == "peak_failure"
    assert result.iterations[-1].peak is failed_peak

    np.testing.assert_allclose(
        result.background,
        expected_background,
    )
    np.testing.assert_allclose(
        result.corrected,
        data - expected_background,
    )
    np.testing.assert_array_equal(data, original)

    assert not result.background.flags.writeable
    assert not result.corrected.flags.writeable


def test_flatten_base_mask_uses_parameters_from_unsuccessful_peak() -> None:
    data = np.zeros((5, 5), dtype=float)
    data[2, 2] = 4.0

    class Peak:
        success = False
        mean = 1.0
        rms = 0.5

    result = flatten_base_core._build_flatten_base_mask(
        data,
        peak=Peak(),
        degree=2,
    )

    assert result.threshold == 2.5
    assert result.raw_count == 1
    assert result.grown_count == 13
    assert result.raw[2, 2]


def test_polynomial_stage_runs_degree_two_with_failed_incoming_peak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = np.arange(20, dtype=float).reshape(4, 5)

    class Peak:
        def __init__(self, success: bool) -> None:
            self.success = success

    incoming_peak = Peak(success=False)
    failed_updated_peak = Peak(success=False)
    calls: list[int] = []

    class Iteration:
        degree = 2
        background = np.ones_like(data)
        corrected = data - 1.0
        peak = failed_updated_peak

    def fake_iteration(
        received: np.ndarray,
        *,
        peak: Peak,
        degree: int,
    ) -> Iteration:
        np.testing.assert_array_equal(received, data)
        assert peak is incoming_peak
        assert degree == 2
        calls.append(degree)
        return Iteration()

    monkeypatch.setattr(
        flatten_base_core,
        "_run_flatten_base_polynomial_iteration",
        fake_iteration,
    )

    result = flatten_base_core._run_flatten_base_polynomial_stage(
        data,
        peak=incoming_peak,
    )

    assert calls == [2]
    assert result.completed_degrees == (2,)
    assert result.termination == "peak_failure"

    np.testing.assert_array_equal(
        result.background,
        np.ones_like(data),
    )
    np.testing.assert_array_equal(
        result.corrected,
        data - 1.0,
    )


def test_polynomial_iteration_skips_constant_field_and_reestimates_peak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = np.full((5, 5), 2.5, dtype=float)
    original = data.copy()

    class IncomingPeak:
        success = True
        mean = 2.5
        rms = 0.0

    class UpdatedPeak:
        success = False
        mean = 2.5
        rms = 0.0

    incoming_peak = IncomingPeak()
    updated_peak = UpdatedPeak()
    peak_calls: list[np.ndarray] = []

    def forbidden_mask(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError(
            "constant-field iteration must not construct a mask"
        )

    def forbidden_fit(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError(
            "constant-field iteration must not fit a polynomial"
        )

    def fake_peak(received: np.ndarray) -> UpdatedPeak:
        peak_calls.append(received.copy())
        np.testing.assert_array_equal(received, data)
        return updated_peak

    monkeypatch.setattr(
        flatten_base_core,
        "_build_flatten_base_mask",
        forbidden_mask,
    )
    monkeypatch.setattr(
        flatten_base_core,
        "_estimate_base_peak",
        fake_peak,
    )

    import spmkit.core.analysis.leveling as leveling

    monkeypatch.setattr(
        leveling,
        "_fit_polynomial_surface_data",
        forbidden_fit,
    )

    result = flatten_base_core._run_flatten_base_polynomial_iteration(
        data,
        peak=incoming_peak,
        degree=2,
    )

    assert not result.applied
    assert result.degree == 2
    assert result.powers == ()
    assert result.mask is None
    assert result.selected_count == 0
    assert result.rank == 0
    assert result.coefficients.size == 0
    assert result.singular_values.size == 0
    assert result.peak is updated_peak
    assert len(peak_calls) == 1

    np.testing.assert_array_equal(
        result.background,
        np.zeros_like(data),
    )
    np.testing.assert_array_equal(result.corrected, data)
    np.testing.assert_array_equal(data, original)

    assert not result.coefficients.flags.writeable
    assert not result.singular_values.flags.writeable
    assert not result.background.flags.writeable
    assert not result.corrected.flags.writeable


def test_polynomial_stage_records_unapplied_degree_before_peak_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = np.arange(20, dtype=float).reshape(4, 5)
    original = data.copy()

    class Peak:
        def __init__(self, success: bool) -> None:
            self.success = success

    incoming_peak = Peak(success=True)
    failed_peak = Peak(success=False)

    background = np.zeros_like(data)
    corrected = data.copy()
    coefficients = np.empty(0, dtype=float)
    singular_values = np.empty(0, dtype=float)

    background.setflags(write=False)
    corrected.setflags(write=False)
    coefficients.setflags(write=False)
    singular_values.setflags(write=False)

    skipped_iteration = (
        flatten_base_core.FlattenBasePolynomialIteration(
            degree=2,
            powers=(),
            mask=None,
            selected_count=0,
            coefficients=coefficients,
            rank=0,
            singular_values=singular_values,
            background=background,
            corrected=corrected,
            peak=failed_peak,
            applied=False,
        )
    )

    calls: list[int] = []

    def fake_iteration(
        received: np.ndarray,
        *,
        peak: Peak,
        degree: int,
    ) -> flatten_base_core.FlattenBasePolynomialIteration:
        np.testing.assert_array_equal(received, data)
        assert peak is incoming_peak
        assert degree == 2
        calls.append(degree)
        return skipped_iteration

    monkeypatch.setattr(
        flatten_base_core,
        "_run_flatten_base_polynomial_iteration",
        fake_iteration,
    )

    result = flatten_base_core._run_flatten_base_polynomial_stage(
        data,
        peak=incoming_peak,
    )

    assert calls == [2]
    assert result.attempted_degrees == (2,)
    assert result.completed_degrees == ()
    assert result.iterations == (skipped_iteration,)
    assert result.termination == "peak_failure"

    np.testing.assert_array_equal(
        result.background,
        np.zeros_like(data),
    )
    np.testing.assert_array_equal(result.corrected, data)
    np.testing.assert_array_equal(data, original)

    assert not result.background.flags.writeable
    assert not result.corrected.flags.writeable


def test_flatten_base_composes_stages_and_final_offsets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = np.array(
        [
            [10.0, 11.0, 12.0],
            [13.0, 14.0, 15.0],
            [16.0, 17.0, 18.0],
        ],
        dtype=float,
    )
    original = data.copy()

    class FacetPeak:
        success = True
        mean = 2.0
        rms = 0.5

    class FinalPeak:
        success = True
        mean = 1.5
        rms = 0.2

    facet_peak = FacetPeak()
    final_peak = FinalPeak()

    facet_background = np.full_like(data, 2.0)
    facet_corrected = data - facet_background
    facet_background.setflags(write=False)
    facet_corrected.setflags(write=False)

    facet_stage = flatten_base_core.FacetStageResult(
        corrected=facet_corrected,
        background=facet_background,
        initial_peak=facet_peak,
        iterations=(),
        termination="degenerate_plane",
    )

    polynomial_background = np.full_like(data, 3.0)
    polynomial_corrected = facet_corrected - polynomial_background
    polynomial_background.setflags(write=False)
    polynomial_corrected.setflags(write=False)

    class FinalIteration:
        degree = 5
        peak = final_peak
        applied = True

    polynomial_stage = flatten_base_core.FlattenBasePolynomialStage(
        corrected=polynomial_corrected,
        background=polynomial_background,
        initial_peak=facet_peak,
        iterations=(FinalIteration(),),
        termination="completed",
    )

    calls: dict[str, object] = {}

    def fake_facet_stage(
        received: np.ndarray,
        *,
        pixel_size_x: float,
        pixel_size_y: float,
    ) -> flatten_base_core.FacetStageResult:
        np.testing.assert_array_equal(received, data)
        assert pixel_size_x == 2.0
        assert pixel_size_y == 0.5
        calls["facet"] = True
        return facet_stage

    def fake_polynomial_stage(
        received: np.ndarray,
        *,
        peak: FacetPeak,
    ) -> flatten_base_core.FlattenBasePolynomialStage:
        np.testing.assert_array_equal(received, facet_corrected)
        assert peak is facet_peak
        calls["polynomial"] = True
        return polynomial_stage

    monkeypatch.setattr(
        flatten_base_core,
        "_run_flatten_base_facet_stage",
        fake_facet_stage,
    )
    monkeypatch.setattr(
        flatten_base_core,
        "_run_flatten_base_polynomial_stage",
        fake_polynomial_stage,
    )

    result = flatten_base_core._run_flatten_base(
        data,
        pixel_size_x=2.0,
        pixel_size_y=0.5,
    )

    after_mean_centering = polynomial_corrected - final_peak.mean
    expected_minimum_offset = float(np.min(after_mean_centering))
    expected_corrected = (
        after_mean_centering
        - expected_minimum_offset
    )
    expected_background = (
        facet_background
        + polynomial_background
        + final_peak.mean
        + expected_minimum_offset
    )

    assert calls == {
        "facet": True,
        "polynomial": True,
    }
    assert result.facet_stage is facet_stage
    assert result.polynomial_stage is polynomial_stage
    assert result.final_peak is final_peak
    assert result.mean_centered
    assert result.mean_offset == 1.5
    assert result.minimum_offset == 3.5
    assert result.total_offset == 5.0

    np.testing.assert_allclose(
        result.corrected,
        expected_corrected,
    )
    np.testing.assert_allclose(
        result.background,
        expected_background,
    )
    np.testing.assert_allclose(
        result.corrected + result.background,
        data,
    )
    np.testing.assert_array_equal(data, original)

    assert not result.corrected.flags.writeable
    assert not result.background.flags.writeable


def test_flatten_base_skips_mean_after_failed_final_peak() -> None:
    data = np.array(
        [
            [8.0, 9.0],
            [10.0, 11.0],
        ],
        dtype=float,
    )
    original = data.copy()

    class FacetPeak:
        success = True
        mean = 1.0
        rms = 0.25

    class FailedPeak:
        success = False
        mean = 999.0
        rms = 0.5

    facet_peak = FacetPeak()
    failed_peak = FailedPeak()

    facet_background = np.full_like(data, 1.0)
    facet_corrected = data - facet_background

    facet_stage = flatten_base_core.FacetStageResult(
        corrected=facet_corrected,
        background=facet_background,
        initial_peak=facet_peak,
        iterations=(),
        termination="completed",
    )

    polynomial_background = np.full_like(data, 2.0)
    polynomial_corrected = facet_corrected - polynomial_background

    class FinalIteration:
        degree = 2
        peak = failed_peak
        applied = True

    polynomial_stage = flatten_base_core.FlattenBasePolynomialStage(
        corrected=polynomial_corrected,
        background=polynomial_background,
        initial_peak=facet_peak,
        iterations=(FinalIteration(),),
        termination="peak_failure",
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            flatten_base_core,
            "_run_flatten_base_facet_stage",
            lambda *args, **kwargs: facet_stage,
        )
        monkeypatch.setattr(
            flatten_base_core,
            "_run_flatten_base_polynomial_stage",
            lambda *args, **kwargs: polynomial_stage,
        )

        result = flatten_base_core._run_flatten_base(
            data,
            pixel_size_x=1.0,
            pixel_size_y=1.0,
        )

    expected_minimum_offset = 5.0
    expected_corrected = polynomial_corrected - expected_minimum_offset
    expected_background = (
        facet_background
        + polynomial_background
        + expected_minimum_offset
    )

    assert result.final_peak is failed_peak
    assert not result.mean_centered
    assert result.mean_offset == 0.0
    assert result.minimum_offset == expected_minimum_offset
    assert result.total_offset == expected_minimum_offset

    np.testing.assert_array_equal(
        result.corrected,
        expected_corrected,
    )
    np.testing.assert_array_equal(
        result.background,
        expected_background,
    )
    np.testing.assert_array_equal(
        result.corrected + result.background,
        data,
    )
    np.testing.assert_array_equal(data, original)

    assert not result.corrected.flags.writeable
    assert not result.background.flags.writeable


def test_flatten_base_preserves_nonpositive_minimum_after_mean_centering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = np.array(
        [
            [2.0, 3.0],
            [4.0, 5.0],
        ],
        dtype=float,
    )
    original = data.copy()

    class FacetPeak:
        success = True
        mean = 0.0
        rms = 0.25

    class FinalPeak:
        success = True
        mean = 0.5
        rms = 0.2

    facet_peak = FacetPeak()
    final_peak = FinalPeak()

    facet_background = np.full_like(data, 1.0)
    facet_corrected = data - facet_background

    facet_stage = flatten_base_core.FacetStageResult(
        corrected=facet_corrected,
        background=facet_background,
        initial_peak=facet_peak,
        iterations=(),
        termination="completed",
    )

    polynomial_background = np.full_like(data, 2.0)
    polynomial_corrected = (
        facet_corrected
        - polynomial_background
    )

    class FinalIteration:
        degree = 5
        peak = final_peak
        applied = True

    polynomial_stage = flatten_base_core.FlattenBasePolynomialStage(
        corrected=polynomial_corrected,
        background=polynomial_background,
        initial_peak=facet_peak,
        iterations=(FinalIteration(),),
        termination="completed",
    )

    monkeypatch.setattr(
        flatten_base_core,
        "_run_flatten_base_facet_stage",
        lambda *args, **kwargs: facet_stage,
    )
    monkeypatch.setattr(
        flatten_base_core,
        "_run_flatten_base_polynomial_stage",
        lambda *args, **kwargs: polynomial_stage,
    )

    result = flatten_base_core._run_flatten_base(
        data,
        pixel_size_x=1.0,
        pixel_size_y=1.0,
    )

    expected_corrected = polynomial_corrected - final_peak.mean
    expected_background = (
        facet_background
        + polynomial_background
        + final_peak.mean
    )

    assert result.final_peak is final_peak
    assert result.mean_centered
    assert result.mean_offset == 0.5
    assert result.minimum_offset == 0.0
    assert result.total_offset == 0.5
    assert float(np.min(result.corrected)) == -1.5

    np.testing.assert_allclose(
        result.corrected,
        expected_corrected,
    )
    np.testing.assert_allclose(
        result.background,
        expected_background,
    )
    np.testing.assert_allclose(
        result.corrected + result.background,
        data,
    )
    np.testing.assert_array_equal(data, original)

    assert not result.corrected.flags.writeable
    assert not result.background.flags.writeable
