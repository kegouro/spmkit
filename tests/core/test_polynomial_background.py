"""Tests for global polynomial background estimation."""

from __future__ import annotations

import numpy as np
import pytest

import spmkit.core.analysis as analysis
from spmkit.core.analysis import (
    analyze_polynomial_background,
    estimate_polynomial_background,
    leveling,
    remove_polynomial_background,
)
from spmkit.core.models import SPMChannel


def _channel(data: np.ndarray) -> SPMChannel:
    return SPMChannel(
        name="Z-Axis",
        data=np.asarray(data, dtype=float),
        unit="nm",
        x_range=9e-6,
        y_range=8e-6,
        direction="forward",
        group="Topography",
        metadata={"source": "synthetic"},
    )


def test_total_degree_estimates_exact_polynomial_surface() -> None:
    rows, columns = 8, 9
    y = np.linspace(-1.0, 1.0, rows)[:, np.newaxis]
    x = np.linspace(-1.0, 1.0, columns)[np.newaxis, :]

    expected = 4.0 + 1.5 * x - 0.75 * y + 0.4 * x * y + 0.2 * x**2 - 0.1 * y**2

    channel = _channel(expected)

    observed = estimate_polynomial_background(
        channel,
        degree_mode="total",
        degree=2,
    )

    assert np.allclose(observed.data, expected, atol=1e-12)


def test_independent_degree_supports_tensor_product_terms() -> None:
    rows, columns = 8, 9
    y = np.linspace(-1.0, 1.0, rows)[:, np.newaxis]
    x = np.linspace(-1.0, 1.0, columns)[np.newaxis, :]

    expected = 1.0 + 0.5 * x**2 - 0.25 * y + 2.0 * x**3 * y

    channel = _channel(expected)

    observed = estimate_polynomial_background(
        channel,
        degree_mode="independent",
        x_degree=3,
        y_degree=1,
    )

    assert np.allclose(observed.data, expected, atol=1e-12)


def test_remove_matches_legacy_leveling_api() -> None:
    rows, columns = 7, 8
    yy, xx = np.mgrid[0:rows, 0:columns]

    data = 2.0 + 0.4 * xx - 0.3 * yy + 0.05 * xx * yy + np.sin(xx)

    channel = _channel(data)

    expected = leveling.polynomial_background(
        channel,
        degree_mode="total",
        degree=2,
    )
    observed = remove_polynomial_background(
        channel,
        degree_mode="total",
        degree=2,
    )

    assert np.array_equal(observed.data, expected.data)


def test_mask_excludes_feature_from_fit() -> None:
    rows = columns = 9
    y = np.linspace(-1.0, 1.0, rows)[:, np.newaxis]
    x = np.linspace(-1.0, 1.0, columns)[np.newaxis, :]

    expected = 3.0 + 0.75 * x - 0.5 * y
    data = expected.copy()
    data[4, 4] += 100.0

    mask = np.zeros(data.shape, dtype=bool)
    mask[4, 4] = True

    observed = estimate_polynomial_background(
        _channel(data),
        degree_mode="total",
        degree=1,
        mask=mask,
        mask_mode="exclude",
    )

    assert np.allclose(observed.data, expected, atol=1e-12)


def test_analyze_returns_model_corrected_and_provenance() -> None:
    rows, columns = 8, 9
    y = np.linspace(-1.0, 1.0, rows)[:, np.newaxis]
    x = np.linspace(-1.0, 1.0, columns)[np.newaxis, :]

    data = 2.0 + x - 0.5 * y + 0.25 * x * y
    channel = _channel(data)

    result = analyze_polynomial_background(
        channel,
        degree_mode="total",
        degree=2,
    )

    assert result.method == "polynomial"
    assert result.parameters == {
        "degree_mode": "total",
        "degree": 2,
        "x_degree": None,
        "y_degree": None,
        "mask_mode": "ignore",
        "mask_provided": False,
        "coordinates": "normalized_-1_1",
    }
    assert np.allclose(result.background.data, data, atol=1e-12)
    assert np.allclose(result.corrected.data, 0.0, atol=1e-12)
    assert np.allclose(
        result.background.data + result.corrected.data,
        channel.data,
        atol=1e-12,
    )


def test_outputs_preserve_context_without_mutating_input() -> None:
    data = np.arange(72.0).reshape(8, 9)
    channel = _channel(data)

    original_data = channel.data.copy()
    original_metadata = dict(channel.metadata)

    estimated = estimate_polynomial_background(
        channel,
        degree=2,
    )
    corrected = remove_polynomial_background(
        channel,
        degree=2,
    )

    for output in (estimated, corrected):
        assert output is not channel
        assert output.name == channel.name
        assert output.unit == channel.unit
        assert output.x_range == channel.x_range
        assert output.y_range == channel.y_range
        assert output.direction == channel.direction
        assert output.group == channel.group
        assert output.metadata == channel.metadata

    assert np.array_equal(channel.data, original_data)
    assert channel.metadata == original_metadata


def test_invalid_configuration_is_rejected_by_shared_solver() -> None:
    channel = _channel(np.arange(72.0).reshape(8, 9))

    with pytest.raises(
        ValueError,
        match="polynomial_background degree_mode must be",
    ):
        estimate_polynomial_background(
            channel,
            degree_mode="unknown",  # type: ignore[arg-type]
        )


def test_polynomial_background_api_is_public() -> None:
    assert analysis.estimate_polynomial_background is estimate_polynomial_background
    assert analysis.remove_polynomial_background is remove_polynomial_background
    assert analysis.analyze_polynomial_background is analyze_polynomial_background
