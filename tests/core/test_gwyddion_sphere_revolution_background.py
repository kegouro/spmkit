"""Tests for private Gwyddion 2.71 Sphere Revolution numerical kernel."""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis import (
    BackgroundResult,
    analyze_gwyddion_sphere_revolution_background,
    estimate_gwyddion_sphere_revolution_background,
    remove_gwyddion_sphere_revolution_background,
)
from spmkit.core.analysis._gwyddion_sphere_revolution import (
    _gwyddion_sphere_background,
    _gwyddion_sphere_corrected,
    _gwyddion_sphere_result,
)
from spmkit.core.models import SPMChannel


def test_gwyddion_sphere_rejects_non_2d_input() -> None:
    with pytest.raises(TypeError, match="real 2D array"):
        _gwyddion_sphere_background(np.array([1.0, 2.0, 3.0]), 5.0)

    with pytest.raises(TypeError, match="real 2D array"):
        _gwyddion_sphere_background(np.ones((2, 2, 2)), 5.0)


def test_gwyddion_sphere_rejects_empty_dimensions() -> None:
    with pytest.raises(TypeError, match="real 2D array"):
        _gwyddion_sphere_background(np.zeros((0, 5)), 5.0)

    with pytest.raises(TypeError, match="real 2D array"):
        _gwyddion_sphere_background(np.zeros((5, 0)), 5.0)


def test_gwyddion_sphere_rejects_boolean_radius() -> None:
    data = np.ones((5, 5), dtype=np.float64)

    with pytest.raises(TypeError, match="radius to be a real scalar"):
        _gwyddion_sphere_background(data, True)

    with pytest.raises(TypeError, match="radius to be a real scalar"):
        _gwyddion_sphere_background(data, False)


def test_gwyddion_sphere_rejects_nonfinite_radius() -> None:
    data = np.ones((5, 5), dtype=np.float64)

    with pytest.raises(ValueError, match="radius to be finite"):
        _gwyddion_sphere_background(data, float("nan"))

    with pytest.raises(ValueError, match="radius to be finite"):
        _gwyddion_sphere_background(data, float("inf"))


def test_gwyddion_sphere_rejects_radius_below_one() -> None:
    data = np.ones((5, 5), dtype=np.float64)

    with pytest.raises(ValueError, match="between 1.0 and 1000.0 samples"):
        _gwyddion_sphere_background(data, 0.9)


def test_gwyddion_sphere_rejects_radius_above_thousand() -> None:
    data = np.ones((5, 5), dtype=np.float64)

    with pytest.raises(ValueError, match="between 1.0 and 1000.0 samples"):
        _gwyddion_sphere_background(data, 1000.1)


def test_gwyddion_sphere_accepts_radius_boundaries() -> None:
    data = np.ones((5, 5), dtype=np.float64)

    bg_min = _gwyddion_sphere_background(data, 1.0)
    assert bg_min.shape == (5, 5)
    assert np.all(np.isfinite(bg_min))

    bg_max = _gwyddion_sphere_background(data, 1000.0)
    assert bg_max.shape == (5, 5)
    assert np.all(np.isfinite(bg_max))


def test_gwyddion_sphere_converts_input_to_float64() -> None:
    data_int = np.array([[1, 2], [3, 4]], dtype=np.int32)
    bg = _gwyddion_sphere_background(data_int, 2.0)  # type: ignore[arg-type]

    assert bg.dtype == np.float64

    data_f32 = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    bg32 = _gwyddion_sphere_background(data_f32, 2.0)  # type: ignore[arg-type]

    assert bg32.dtype == np.float64


def test_gwyddion_sphere_does_not_mutate_input() -> None:
    data = np.array([[-4.0, -2.0, 0.0], [1.0, 3.0, 7.0], [-1.0, 2.0, 5.0]], dtype=np.float64)
    data_copy = data.copy()

    _gwyddion_sphere_background(data, 1.0)
    np.testing.assert_array_equal(data, data_copy)

    _gwyddion_sphere_result(data, 1.0, inverted=True)
    np.testing.assert_array_equal(data, data_copy)


def test_gwyddion_sphere_background_is_c_contiguous_and_read_only() -> None:
    data = np.ones((5, 5), dtype=np.float64)
    bg = _gwyddion_sphere_background(data, 2.5)

    assert bg.flags.c_contiguous
    assert not bg.flags.writeable

    with pytest.raises(ValueError, match="read-only"):
        bg[0, 0] = 99.0


def test_gwyddion_sphere_result_arrays_are_distinct_and_read_only() -> None:
    data = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    bg, corr = _gwyddion_sphere_result(data, 2.0, inverted=False)

    assert bg is not corr
    assert bg.base is not corr
    assert bg.flags.c_contiguous and not bg.flags.writeable
    assert corr.flags.c_contiguous and not corr.flags.writeable


def test_gwyddion_sphere_constant_field_returns_identity_background() -> None:
    data = np.full((7, 7), 5.0, dtype=np.float64)
    bg = _gwyddion_sphere_background(data, 3.0)

    np.testing.assert_allclose(bg, data, atol=0.0, rtol=0.0)


def test_gwyddion_sphere_constant_field_corrected_is_zero() -> None:
    data = np.full((7, 7), 5.0, dtype=np.float64)
    bg, corr = _gwyddion_sphere_result(data, 3.0, inverted=False)

    np.testing.assert_allclose(corr, 0.0, atol=0.0, rtol=0.0)


def test_gwyddion_sphere_radius_one_signed_field_matches_frozen_values() -> None:
    data = np.array(
        [
            [-4.0, -2.0, 0.0],
            [1.0, 3.0, 7.0],
            [-1.0, 2.0, 5.0],
        ],
        dtype=np.float64,
    )

    expected_bg = np.array(
        [
            [4.5694174231575584, 3.0, 0.0],
            [1.0, 3.0, 3.5694174231575579],
            [1.5, 2.0, 5.0],
        ],
        dtype=np.float64,
    )

    expected_corr = np.array(
        [
            [-8.5694174231575584, -5.0, 0.0],
            [0.0, 0.0, 3.4305825768424421],
            [-2.5, 0.0, 0.0],
        ],
        dtype=np.float64,
    )

    bg, corr = _gwyddion_sphere_result(data, 1.0, inverted=False)

    np.testing.assert_allclose(bg, expected_bg, atol=5e-14, rtol=0.0)
    np.testing.assert_allclose(corr, expected_corr, atol=5e-14, rtol=0.0)


def test_gwyddion_sphere_very_flat_branch_returns_finite_values() -> None:
    data = np.arange(25, dtype=np.float64).reshape((5, 5))
    bg = _gwyddion_sphere_background(data, 50.0)

    assert bg.shape == (5, 5)
    assert np.all(np.isfinite(bg))


def test_gwyddion_sphere_uses_xres_for_sphere_size() -> None:
    # On non-square grid (5 rows, 10 cols), radius=8 => sphere_size = min(8, 10) = 8.
    # On transposed grid (10 rows, 5 cols), radius=8 => sphere_size = min(8, 5) = 5.
    data_asym = np.arange(50, dtype=np.float64).reshape((5, 10))
    bg_orig = _gwyddion_sphere_background(data_asym, 8.0)

    data_transposed = data_asym.T
    bg_trans = _gwyddion_sphere_background(data_transposed, 8.0)

    # Verify that transposed background is valid and finite
    assert bg_orig.shape == (5, 10)
    assert bg_trans.shape == (10, 5)
    assert np.all(np.isfinite(bg_orig))
    assert np.all(np.isfinite(bg_trans))


def test_gwyddion_sphere_safe_inversion_duality() -> None:
    data = np.array(
        [
            [-4.0, -2.0, 0.0],
            [1.0, 3.0, 7.0],
            [-1.0, 2.0, 5.0],
        ],
        dtype=np.float64,
    )

    bg_inv, _ = _gwyddion_sphere_result(data, 2.5, inverted=True)
    neg_bg = _gwyddion_sphere_background(-data, 2.5)

    np.testing.assert_allclose(bg_inv, -neg_bg, atol=0.0, rtol=0.0)


def test_gwyddion_sphere_result_reconstructs_input() -> None:
    data = np.array(
        [
            [-4.0, -2.0, 0.0],
            [1.0, 3.0, 7.0],
            [-1.0, 2.0, 5.0],
        ],
        dtype=np.float64,
    )

    for inv in (False, True):
        bg, corr = _gwyddion_sphere_result(data, 2.5, inverted=inv)
        reconstruction = corr + bg
        np.testing.assert_allclose(reconstruction, data, atol=5e-14, rtol=0.0)


def test_gwyddion_sphere_corrected_delegates_to_result() -> None:
    data = np.array(
        [
            [-4.0, -2.0, 0.0],
            [1.0, 3.0, 7.0],
            [-1.0, 2.0, 5.0],
        ],
        dtype=np.float64,
    )

    for inv in (False, True):
        corr_direct = _gwyddion_sphere_corrected(data, 2.5, inverted=inv)
        _, corr_result = _gwyddion_sphere_result(data, 2.5, inverted=inv)
        np.testing.assert_allclose(corr_direct, corr_result, atol=0.0, rtol=0.0)


def test_gwyddion_sphere_accepts_singleton_2d_fields() -> None:
    shapes = [(1, 1), (1, 5), (5, 1)]
    for shape in shapes:
        data = np.arange(shape[0] * shape[1], dtype=np.float64).reshape(shape)
        bg, corr = _gwyddion_sphere_result(data, 2.0, inverted=False)

        assert bg.shape == shape
        assert corr.shape == shape
        assert np.all(np.isfinite(bg))
        assert np.all(np.isfinite(corr))
        np.testing.assert_allclose(corr + bg, data, atol=5e-14, rtol=0.0)


def _channel() -> SPMChannel:
    data = np.array(
        [
            [-4.0, -2.0, 0.0],
            [1.0, 3.0, 7.0],
            [-1.0, 2.0, 5.0],
        ],
        dtype=np.float64,
    )
    return SPMChannel(
        name="Test Sphere",
        data=data,
        unit="m",
        x_range=8.0e-6,
        y_range=5.0e-6,
        metadata={"source": "test_gwyddion_sphere"},
    )


def test_estimate_gwyddion_sphere_background_matches_private_result() -> None:
    ch = _channel()
    for inv in (False, True):
        pub_bg = estimate_gwyddion_sphere_revolution_background(ch, 2.5, inverted=inv)
        priv_bg, _ = _gwyddion_sphere_result(ch.data, 2.5, inverted=inv)

        np.testing.assert_allclose(pub_bg.data, priv_bg, atol=0.0, rtol=0.0)


def test_remove_gwyddion_sphere_background_matches_private_result() -> None:
    ch = _channel()
    for inv in (False, True):
        pub_corr = remove_gwyddion_sphere_revolution_background(ch, 2.5, inverted=inv)
        _, priv_corr = _gwyddion_sphere_result(ch.data, 2.5, inverted=inv)

        np.testing.assert_allclose(pub_corr.data, priv_corr, atol=0.0, rtol=0.0)


def test_analyze_gwyddion_sphere_background_returns_consistent_result() -> None:
    ch = _channel()
    for inv in (False, True):
        res = analyze_gwyddion_sphere_revolution_background(ch, 2.5, inverted=inv)

        assert isinstance(res, BackgroundResult)
        assert res.method == "gwyddion_sphere_revolution"
        assert res.parameters == {"radius_px": 2.5, "inverted": inv}

        priv_bg, priv_corr = _gwyddion_sphere_result(ch.data, 2.5, inverted=inv)
        np.testing.assert_allclose(res.background.data, priv_bg, atol=0.0, rtol=0.0)
        np.testing.assert_allclose(res.corrected.data, priv_corr, atol=0.0, rtol=0.0)
        np.testing.assert_allclose(
            res.corrected.data + res.background.data,
            ch.data,
            atol=5e-14,
            rtol=0.0,
        )


def test_gwyddion_sphere_public_method_and_parameters() -> None:
    ch = _channel()
    res = analyze_gwyddion_sphere_revolution_background(ch, 15.0, inverted=True)

    assert res.method == "gwyddion_sphere_revolution"
    assert res.parameters == {"radius_px": 15.0, "inverted": True}


def test_gwyddion_sphere_public_preserves_channel_context() -> None:
    ch = _channel()
    res = analyze_gwyddion_sphere_revolution_background(ch, 2.5)

    assert res.background.unit == ch.unit
    assert res.background.x_range == ch.x_range
    assert res.background.y_range == ch.y_range
    assert res.background.metadata == ch.metadata

    assert res.corrected.unit == ch.unit
    assert res.corrected.x_range == ch.x_range
    assert res.corrected.y_range == ch.y_range
    assert res.corrected.metadata == ch.metadata


def test_gwyddion_sphere_public_does_not_mutate_channel() -> None:
    ch = _channel()
    ch_data_copy = ch.data.copy()

    estimate_gwyddion_sphere_revolution_background(ch, 2.5)
    remove_gwyddion_sphere_revolution_background(ch, 2.5)
    analyze_gwyddion_sphere_revolution_background(ch, 2.5)

    np.testing.assert_array_equal(ch.data, ch_data_copy)


def test_gwyddion_sphere_public_exports_are_available() -> None:
    import spmkit.core.analysis as analysis_mod

    assert hasattr(analysis_mod, "estimate_gwyddion_sphere_revolution_background")
    assert hasattr(analysis_mod, "remove_gwyddion_sphere_revolution_background")
    assert hasattr(analysis_mod, "analyze_gwyddion_sphere_revolution_background")

    assert "estimate_gwyddion_sphere_revolution_background" in analysis_mod.__all__
    assert "remove_gwyddion_sphere_revolution_background" in analysis_mod.__all__
    assert "analyze_gwyddion_sphere_revolution_background" in analysis_mod.__all__


def test_gwyddion_sphere_physical_api_remains_distinct() -> None:
    import spmkit.core.analysis as analysis_mod

    phys_estimate = analysis_mod.estimate_sphere_revolution_background
    gwy_estimate = analysis_mod.estimate_gwyddion_sphere_revolution_background

    assert phys_estimate is not gwy_estimate

