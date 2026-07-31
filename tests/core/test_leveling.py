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


def test_shift_vertical_adds_requested_offset() -> None:
    """Vertical shifting must add the requested offset to every pixel."""
    data = np.array(
        [
            [-2.0, 0.0],
            [3.0, 7.0],
        ]
    )
    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=2e-6,
        y_range=3e-6,
        direction="forward",
        group="Scan forward",
        metadata={"source": "synthetic"},
    )
    original_data = data.copy()

    result = leveling.shift_vertical(channel, offset=2.5)

    assert np.allclose(result.data, data + 2.5)

    # A constant shift preserves all relative heights.
    assert np.allclose(
        result.data - result.data[0, 0],
        data - data[0, 0],
    )

    # The input remains unchanged and the channel context is preserved.
    assert np.array_equal(channel.data, original_data)
    assert result is not channel
    assert result.data is not channel.data
    assert result.unit == channel.unit
    assert result.x_range == channel.x_range
    assert result.y_range == channel.y_range
    assert result.metadata == channel.metadata
    assert result.metadata is not channel.metadata


@pytest.mark.parametrize(
    ("offset", "error_type", "message"),
    [
        (
            "2.5",
            TypeError,
            "shift_vertical requires a real numeric scalar offset",
        ),
        (
            [2.5],
            TypeError,
            "shift_vertical requires a real numeric scalar offset",
        ),
        (
            True,
            TypeError,
            "shift_vertical requires a real numeric scalar offset",
        ),
        (
            1.0 + 2.0j,
            TypeError,
            "shift_vertical requires a real numeric scalar offset",
        ),
        (
            np.nan,
            ValueError,
            "shift_vertical requires a finite offset",
        ),
        (
            np.inf,
            ValueError,
            "shift_vertical requires a finite offset",
        ),
    ],
    ids=[
        "string",
        "array",
        "boolean",
        "complex",
        "nan",
        "infinite",
    ],
)
def test_shift_vertical_rejects_invalid_offsets(
    offset: object,
    error_type: type[Exception],
    message: str,
) -> None:
    """Invalid offsets must fail explicitly."""
    channel = SPMChannel(
        name="Z-Axis",
        data=np.array([[1.0, 2.0], [3.0, 4.0]]),
        unit="nm",
        x_range=2e-6,
        y_range=2e-6,
    )

    with pytest.raises(error_type, match=message):
        leveling.shift_vertical(channel, offset=offset)  # type: ignore[arg-type]


@pytest.mark.parametrize("mask_mode", ["include", "exclude"])
def test_plane_fit_mask_controls_fit_selection(mask_mode: str) -> None:
    """Masked plane fitting must ignore an excluded surface feature."""
    rows, cols = 7, 7
    yy, xx = np.mgrid[0:rows, 0:cols]

    background = 2.0 * xx - 0.5 * yy + 10.0
    data = background.copy()
    data[3, 3] += 1000.0

    excluded = np.zeros_like(data, dtype=bool)
    excluded[3, 3] = True

    mask = ~excluded if mask_mode == "include" else excluded

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=7e-6,
        y_range=7e-6,
    )

    result = leveling.plane_fit(
        channel,
        mask=mask,
        mask_mode=mask_mode,  # type: ignore[arg-type]
    )

    assert np.allclose(result.data[~excluded], 0.0, atol=1e-10)
    assert np.isclose(result.data[3, 3], 1000.0, atol=1e-10)


@pytest.mark.parametrize(
    ("mask", "mask_mode", "error_type", "message"),
    [
        (
            None,
            "include",
            ValueError,
            "plane_fit requires a mask",
        ),
        (
            np.ones((2, 3), dtype=bool),
            "exclude",
            ValueError,
            "plane_fit requires mask shape to match channel data",
        ),
        (
            np.ones((4, 4), dtype=int),
            "exclude",
            TypeError,
            "plane_fit requires a boolean mask",
        ),
        (
            np.zeros((4, 4), dtype=bool),
            "include",
            ValueError,
            "plane_fit requires at least 3 selected points",
        ),
        (
            None,
            "invalid",
            ValueError,
            "plane_fit mask_mode must be",
        ),
    ],
    ids=[
        "missing-mask",
        "wrong-shape",
        "non-boolean",
        "too-few-points",
        "invalid-mode",
    ],
)
def test_plane_fit_rejects_invalid_mask_configuration(
    mask: object,
    mask_mode: str,
    error_type: type[Exception],
    message: str,
) -> None:
    """Invalid mask configurations must fail explicitly."""
    channel = SPMChannel(
        name="Z-Axis",
        data=np.arange(16.0).reshape(4, 4),
        unit="nm",
        x_range=4e-6,
        y_range=4e-6,
    )

    with pytest.raises(error_type, match=message):
        leveling.plane_fit(
            channel,
            mask=mask,  # type: ignore[arg-type]
            mask_mode=mask_mode,  # type: ignore[arg-type]
        )


def test_plane_fit_rejects_collinear_selected_points() -> None:
    """Three collinear pixels cannot determine a unique plane."""
    mask = np.zeros((3, 3), dtype=bool)
    mask[0, :] = True

    channel = SPMChannel(
        name="Z-Axis",
        data=np.arange(9.0).reshape(3, 3),
        unit="nm",
        x_range=3e-6,
        y_range=3e-6,
    )

    with pytest.raises(
        ValueError,
        match="selected points do not define a unique plane",
    ):
        leveling.plane_fit(
            channel,
            mask=mask,
            mask_mode="include",
        )


def test_three_point_level_subtracts_plane_defined_by_reference_points() -> None:
    """Three reference pixels must define the plane subtracted from the channel."""
    rows, cols = 5, 6
    yy, xx = np.mgrid[0:rows, 0:cols]

    background = 1.5 * xx - 0.25 * yy + 7.0
    data = background.copy()
    data[2, 3] += 4.0

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=6e-6,
        y_range=5e-6,
        direction="forward",
        group="Scan forward",
        metadata={"source": "synthetic"},
    )
    original_data = data.copy()

    points = ((0, 0), (0, 5), (4, 0))
    result = leveling.three_point_level(channel, points=points)

    # The three reference pixels define zero height after leveling.
    for row, column in points:
        assert np.isclose(result.data[row, column], 0.0, atol=1e-12)

    feature_mask = np.ones(data.shape, dtype=bool)
    feature_mask[2, 3] = False

    assert np.allclose(result.data[feature_mask], 0.0, atol=1e-12)
    assert np.isclose(result.data[2, 3], 4.0, atol=1e-12)

    # Input and physical channel context are preserved.
    assert np.array_equal(channel.data, original_data)
    assert result is not channel
    assert result.data is not channel.data
    assert result.name == channel.name
    assert result.unit == channel.unit
    assert result.x_range == channel.x_range
    assert result.y_range == channel.y_range
    assert result.direction == channel.direction
    assert result.group == channel.group
    assert result.metadata == channel.metadata
    assert result.metadata is not channel.metadata


@pytest.mark.parametrize(
    ("points", "error_type", "message"),
    [
        (
            ((0, 0), (0, 1)),
            ValueError,
            "three_point_level requires exactly three",
        ),
        (
            ((0.0, 0.0), (0.0, 2.0), (2.0, 0.0)),
            TypeError,
            "three_point_level requires integer pixel coordinates",
        ),
        (
            ((0, 0), (0, 2), (8, 0)),
            ValueError,
            "three_point_level requires points within channel bounds",
        ),
        (
            ((0, 0), (0, 1), (0, 2)),
            ValueError,
            "three_point_level requires three non-collinear points",
        ),
    ],
    ids=[
        "wrong-count",
        "non-integer",
        "out-of-bounds",
        "collinear",
    ],
)
def test_three_point_level_rejects_invalid_points(
    points: object,
    error_type: type[Exception],
    message: str,
) -> None:
    """Invalid reference-point configurations must fail explicitly."""
    channel = SPMChannel(
        name="Z-Axis",
        data=np.arange(16.0).reshape(4, 4),
        unit="nm",
        x_range=4e-6,
        y_range=4e-6,
    )

    with pytest.raises(error_type, match=message):
        leveling.three_point_level(
            channel,
            points=points,  # type: ignore[arg-type]
        )
