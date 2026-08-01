"""Tests for the private P-spline background adapter."""

from __future__ import annotations

import json
from unittest.mock import patch

import numpy as np
import pytest
from scipy.interpolate import BSpline

import spmkit.core.analysis as analysis
from spmkit.core.analysis._pspline import (
    _open_uniform_knots,
    fit_pspline_surface,
)
from spmkit.core.analysis.background import (
    BackgroundResult,
    _fit_spline_background,
    analyze_spline_background,
    estimate_spline_background,
    remove_spline_background,
)
from spmkit.core.models import SPMChannel


def _channel(data: np.ndarray) -> SPMChannel:
    return SPMChannel(
        name="Z-Axis",
        data=np.asarray(data),
        unit="nm",
        x_range=17e-6,
        y_range=15e-6,
        direction="forward",
        group="Topography",
        metadata={"source": "synthetic"},
    )


def _zero_penalty_surface(
    *,
    rows: int = 15,
    columns: int = 17,
    n_basis_x: int = 6,
    n_basis_y: int = 6,
) -> np.ndarray:
    degree = 3

    knots_x = _open_uniform_knots(
        n_basis_x,
        degree,
    )
    knots_y = _open_uniform_knots(
        n_basis_y,
        degree,
    )

    basis_x = BSpline.design_matrix(
        np.linspace(0.0, 1.0, columns),
        knots_x,
        degree,
    )
    basis_y = BSpline.design_matrix(
        np.linspace(0.0, 1.0, rows),
        knots_y,
        degree,
    )

    x_index = np.arange(
        n_basis_x,
        dtype=float,
    )[None, :]
    y_index = np.arange(
        n_basis_y,
        dtype=float,
    )[:, None]

    coefficients = 2.0 + 0.3 * x_index - 0.2 * y_index + 0.05 * x_index * y_index

    return np.asarray(
        basis_y @ coefficients @ basis_x.T,
        dtype=float,
        order="C",
    )


def test_adapter_uses_physical_pixel_centres() -> None:
    data = _zero_penalty_surface()
    channel = _channel(data)

    fit = _fit_spline_background(
        channel,
        n_basis_x=6,
        n_basis_y=6,
        smoothing_x=2.0,
        smoothing_y=3.0,
    )

    assert fit.x_min == pytest.approx(
        0.5 * channel.pixel_size_x,
    )
    assert fit.x_max == pytest.approx(
        channel.x_range - 0.5 * channel.pixel_size_x,
    )
    assert fit.y_min == pytest.approx(
        0.5 * channel.pixel_size_y,
    )
    assert fit.y_max == pytest.approx(
        channel.y_range - 0.5 * channel.pixel_size_y,
    )


def test_adapter_matches_direct_core_fit() -> None:
    rng = np.random.default_rng(20260801)
    data = rng.normal(
        size=(15, 17),
    )
    channel = _channel(data)

    weights = np.linspace(
        0.5,
        1.5,
        data.size,
    ).reshape(data.shape)

    x = (np.arange(data.shape[1], dtype=float) + 0.5) * channel.pixel_size_x
    y = (np.arange(data.shape[0], dtype=float) + 0.5) * channel.pixel_size_y

    expected = fit_pspline_surface(
        data,
        x=x,
        y=y,
        mask=np.ones(
            data.shape,
            dtype=bool,
        ),
        weights=weights,
        n_basis_x=6,
        n_basis_y=6,
        smoothing_x=0.8,
        smoothing_y=1.7,
    )

    observed = _fit_spline_background(
        channel,
        weights=weights,
        n_basis_x=6,
        n_basis_y=6,
        smoothing_x=0.8,
        smoothing_y=1.7,
    )

    np.testing.assert_array_equal(
        observed.model,
        expected.model,
    )
    np.testing.assert_array_equal(
        observed.coefficients,
        expected.coefficients,
    )


def test_exclude_mask_removes_feature_from_fit() -> None:
    expected = _zero_penalty_surface()
    data = expected.copy()
    data[7, 8] += 100.0

    mask = np.zeros(
        data.shape,
        dtype=bool,
    )
    mask[7, 8] = True

    observed = estimate_spline_background(
        _channel(data),
        n_basis_x=6,
        n_basis_y=6,
        smoothing_x=4.0,
        smoothing_y=7.0,
        mask=mask,
        mask_mode="exclude",
    )

    np.testing.assert_allclose(
        observed.data,
        expected,
        rtol=0.0,
        atol=3e-10,
    )


def test_include_mask_can_exclude_nonfinite_data() -> None:
    data = _zero_penalty_surface()
    mask = np.ones(
        data.shape,
        dtype=bool,
    )

    mask[7, 8] = False
    data[7, 8] = np.nan

    observed = estimate_spline_background(
        _channel(data),
        n_basis_x=6,
        n_basis_y=6,
        mask=mask,
        mask_mode="include",
    )

    assert np.all(np.isfinite(observed.data))


def test_ignore_mode_selects_nonfinite_data() -> None:
    data = _zero_penalty_surface()
    data[7, 8] = np.nan

    with pytest.raises(
        ValueError,
        match="selected P-spline data must be finite",
    ):
        estimate_spline_background(
            _channel(data),
            n_basis_x=6,
            n_basis_y=6,
            mask_mode="ignore",
        )


@pytest.mark.parametrize(
    ("mask", "mask_mode", "message"),
    [
        (
            None,
            "include",
            "requires a mask",
        ),
        (
            np.ones(
                (15, 17),
                dtype=int,
            ),
            "include",
            "boolean mask",
        ),
        (
            np.ones(
                (15, 17),
                dtype=bool,
            ),
            "unknown",
            "mask_mode must be",
        ),
    ],
)
def test_shared_mask_contract_is_enforced(
    mask: np.ndarray | None,
    mask_mode: str,
    message: str,
) -> None:
    with pytest.raises(
        (TypeError, ValueError),
        match=message,
    ):
        estimate_spline_background(
            _channel(_zero_penalty_surface()),
            n_basis_x=6,
            n_basis_y=6,
            mask=mask,
            mask_mode=mask_mode,  # type: ignore[arg-type]
        )


def test_output_preserves_context_without_mutation() -> None:
    data = _zero_penalty_surface()
    channel = _channel(data)

    original_data = channel.data.copy()
    original_metadata = dict(channel.metadata)

    observed = estimate_spline_background(
        channel,
        n_basis_x=6,
        n_basis_y=6,
    )

    assert observed is not channel
    assert observed.name == channel.name
    assert observed.unit == channel.unit
    assert observed.x_range == channel.x_range
    assert observed.y_range == channel.y_range
    assert observed.direction == channel.direction
    assert observed.group == channel.group
    assert observed.metadata == channel.metadata
    assert observed.data.flags.c_contiguous
    assert observed.data.flags.writeable

    np.testing.assert_array_equal(
        channel.data,
        original_data,
    )
    assert channel.metadata == original_metadata


def test_estimator_is_not_public_yet() -> None:
    assert not hasattr(
        analysis,
        "estimate_spline_background",
    )
    assert "estimate_spline_background" not in getattr(analysis, "__all__", ())


def test_remove_matches_input_minus_estimate() -> None:
    data = _zero_penalty_surface()
    channel = _channel(data)

    background = estimate_spline_background(
        channel,
        n_basis_x=6,
        n_basis_y=6,
    )
    corrected = remove_spline_background(
        channel,
        n_basis_x=6,
        n_basis_y=6,
    )

    np.testing.assert_allclose(
        corrected.data,
        channel.data - background.data,
        rtol=0.0,
        atol=1e-12,
    )


def test_remove_preserves_context_without_mutation() -> None:
    data = _zero_penalty_surface()
    channel = _channel(data)
    original = channel.data.copy()

    corrected = remove_spline_background(
        channel,
        n_basis_x=6,
        n_basis_y=6,
    )

    assert corrected is not channel
    assert corrected.name == channel.name
    assert corrected.unit == channel.unit
    assert corrected.x_range == channel.x_range
    assert corrected.y_range == channel.y_range
    assert corrected.direction == channel.direction
    assert corrected.group == channel.group
    assert corrected.metadata == channel.metadata

    np.testing.assert_array_equal(
        channel.data,
        original,
    )


def test_analyze_returns_serializable_structured_result() -> None:
    data = _zero_penalty_surface()
    channel = _channel(data)

    result = analyze_spline_background(
        channel,
        n_basis_x=6,
        n_basis_y=6,
        smoothing_x=2.0,
        smoothing_y=3.0,
    )

    assert isinstance(result, BackgroundResult)
    assert result.method == "spline"

    np.testing.assert_allclose(
        result.corrected.data,
        channel.data - result.background.data,
        rtol=0.0,
        atol=1e-12,
    )

    assert result.parameters["n_basis_x"] == 6
    assert result.parameters["n_basis_y"] == 6
    assert result.parameters["smoothing_x"] == 2.0
    assert result.parameters["smoothing_y"] == 3.0
    assert result.parameters["mask_provided"] is False
    assert result.parameters["weights_provided"] is False

    diagnostics = result.parameters["diagnostics"]

    assert isinstance(diagnostics, dict)
    assert diagnostics["selected_points"] == data.size
    assert diagnostics["total_points"] == data.size
    assert diagnostics["solver_iterations"] >= 0
    assert diagnostics["condition_estimate"] >= 0.0

    json.dumps(result.to_dict())


def test_analyze_performs_exactly_one_fit() -> None:
    data = _zero_penalty_surface()
    channel = _channel(data)

    with patch(
        "spmkit.core.analysis.background._fit_spline_background",
        wraps=_fit_spline_background,
    ) as fit_mock:
        result = analyze_spline_background(
            channel,
            n_basis_x=6,
            n_basis_y=6,
        )

    assert fit_mock.call_count == 1
    assert result.method == "spline"
