"""Tests de nivelación."""

from __future__ import annotations

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


def test_polynomial_flattens_curvature() -> None:
    rows = cols = 32
    yy, xx = np.mgrid[0:rows, 0:cols]
    bowl = (xx - 16) ** 2 + (yy - 16) ** 2
    ch = SPMChannel(name="Z", data=bowl.astype(float), unit="m", x_range=1e-6, y_range=1e-6)
    leveled = leveling.polynomial(ch, order=2)
    assert np.allclose(leveled.data, 0.0, atol=1e-6)


def test_align_rows() -> None:
    data = np.zeros((10, 10))
    data += np.arange(10).reshape(-1, 1)  # offset por fila
    ch = SPMChannel(name="Z", data=data, unit="m", x_range=1e-6, y_range=1e-6)
    leveled = leveling.align_rows(ch, method="median")
    assert np.allclose(leveled.data, 0.0)


def test_plane_fit_returns_new_channel_without_mutating_input(
    tilted_surface: SPMChannel,
) -> None:
    """Plane fitting must preserve the input and channel identity metadata."""
    original_data = tilted_surface.data.copy()
    original_metadata = dict(tilted_surface.metadata)

    leveled = leveling.plane_fit(tilted_surface)

    # Un objeto nuevo, no el mismo canal.
    assert leveled is not tilted_surface

    # El canal original no fue alterado.
    assert np.array_equal(tilted_surface.data, original_data)
    assert tilted_surface.metadata == original_metadata

    # Los datos nivelados viven en otro array.
    assert leveled.data is not tilted_surface.data

    # Se conserva la identidad física del canal.
    assert leveled.name == tilted_surface.name
    assert leveled.unit == tilted_surface.unit
    assert leveled.x_range == tilted_surface.x_range
    assert leveled.y_range == tilted_surface.y_range
    assert leveled.direction == tilted_surface.direction
    assert leveled.group == tilted_surface.group

    # with_data crea un diccionario exterior nuevo.
    assert leveled.metadata == tilted_surface.metadata
    assert leveled.metadata is not tilted_surface.metadata


def test_zero_mean_sets_arithmetic_mean_to_zero() -> None:
    """Zero-mean leveling must shift only the vertical reference."""
    data = np.array(
        [
            [10.0, 12.0],
            [14.0, 20.0],
        ]
    )
    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=2e-6,
        y_range=3e-6,
        direction="backward",
        group="Scan backward",
        metadata={"source": "synthetic"},
    )

    original_data = data.copy()

    result = leveling.zero_mean(channel)

    assert np.isclose(np.mean(result.data), 0.0)
    # The operation returns independent data without mutating the input.
    assert result is not channel
    assert result.data is not channel.data
    assert np.array_equal(channel.data, original_data)

    # Physical channel context is preserved.
    assert result.name == channel.name
    assert result.unit == channel.unit
    assert result.x_range == channel.x_range
    assert result.y_range == channel.y_range
    assert result.direction == channel.direction
    assert result.group == channel.group

    # with_data copies the outer metadata dictionary.
    assert result.metadata == channel.metadata
    assert result.metadata is not channel.metadata

    # Subtracting a constant must preserve all relative heights.
    assert np.allclose(
        result.data - result.data[0, 0],
        data - data[0, 0],
    )


@pytest.mark.parametrize(
    ("data", "error_type", "message"),
    [
        (
            np.array([1.0, 2.0]),
            ValueError,
            "zero_mean requires a 2D channel",
        ),
        (
            np.empty((0, 2), dtype=float),
            ValueError,
            "zero_mean requires non-empty data",
        ),
        (
            np.array([["a", "b"], ["c", "d"]]),
            TypeError,
            "zero_mean requires numeric data",
        ),
        (
            np.array([[1.0, np.nan], [2.0, 3.0]]),
            ValueError,
            "zero_mean requires finite data",
        ),
        (
            np.array([[1.0, np.inf], [2.0, 3.0]]),
            ValueError,
            "zero_mean requires finite data",
        ),
    ],
    ids=[
        "one-dimensional",
        "empty",
        "non-numeric",
        "nan",
        "infinite",
    ],
)
def test_zero_mean_rejects_invalid_data(
    data: np.ndarray,
    error_type: type[Exception],
    message: str,
) -> None:
    """Invalid inputs must fail explicitly instead of producing bad data."""
    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=2e-6,
        y_range=2e-6,
    )

    with pytest.raises(error_type, match=message):
        leveling.zero_mean(channel)


def test_zero_minimum_sets_lowest_height_to_zero() -> None:
    """Minimum leveling must shift only the vertical reference."""
    data = np.array(
        [
            [-3.0, 1.0],
            [4.0, 9.0],
        ]
    )
    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=2e-6,
        y_range=3e-6,
        direction="backward",
        group="Scan backward",
        metadata={"source": "synthetic"},
    )
    original_data = data.copy()

    result = leveling.zero_minimum(channel)

    assert np.isclose(np.min(result.data), 0.0)

    # Subtracting a constant must preserve all relative heights.
    assert np.allclose(
        result.data - result.data[0, 0],
        data - data[0, 0],
    )

    # Input data and physical channel context are preserved.
    assert result is not channel
    assert result.data is not channel.data
    assert np.array_equal(channel.data, original_data)
    assert result.name == channel.name
    assert result.unit == channel.unit
    assert result.x_range == channel.x_range
    assert result.y_range == channel.y_range
    assert result.direction == channel.direction
    assert result.group == channel.group
    assert result.metadata == channel.metadata
    assert result.metadata is not channel.metadata
