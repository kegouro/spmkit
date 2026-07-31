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


def test_polynomial_background_total_degree_excludes_masked_feature() -> None:
    """Total-degree fitting must preserve an excluded surface feature."""
    rows, cols = 9, 10
    y = np.linspace(-1.0, 1.0, rows)[:, np.newaxis]
    x = np.linspace(-1.0, 1.0, cols)[np.newaxis, :]

    background = 4.0 + 2.0 * x - 3.0 * y + 0.5 * x**2 + 0.75 * x * y - 0.25 * y**2
    data = background.copy()
    data[4, 5] += 50.0

    excluded = np.zeros(data.shape, dtype=bool)
    excluded[4, 5] = True

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=10e-6,
        y_range=9e-6,
    )

    result = leveling.polynomial_background(
        channel,
        degree_mode="total",
        degree=2,
        mask=excluded,
        mask_mode="exclude",
    )

    assert np.allclose(result.data[~excluded], 0.0, atol=1e-10)
    assert np.isclose(result.data[4, 5], 50.0, atol=1e-10)


def test_polynomial_background_supports_independent_degrees() -> None:
    """Independent degrees must permit terms beyond the total-degree limit."""
    rows, cols = 8, 9
    y = np.linspace(-1.0, 1.0, rows)[:, np.newaxis]
    x = np.linspace(-1.0, 1.0, cols)[np.newaxis, :]

    # x**3 * y requires independent degrees (3, 1).
    background = 1.0 + 0.5 * x**2 - 0.25 * y + 2.0 * x**3 * y

    channel = SPMChannel(
        name="Z-Axis",
        data=background,
        unit="nm",
        x_range=9e-6,
        y_range=8e-6,
    )

    result = leveling.polynomial_background(
        channel,
        degree_mode="independent",
        x_degree=3,
        y_degree=1,
    )

    assert np.allclose(result.data, 0.0, atol=1e-10)


def test_polynomial_legacy_api_matches_total_degree_background() -> None:
    """The legacy polynomial API must retain its current total-degree meaning."""
    rows, cols = 6, 7
    yy, xx = np.mgrid[0:rows, 0:cols]
    data = 3.0 + 2.0 * xx - yy + 0.25 * xx**2 + 0.5 * xx * yy

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=7e-6,
        y_range=6e-6,
    )

    legacy = leveling.polynomial(channel, order=2)
    explicit = leveling.polynomial_background(
        channel,
        degree_mode="total",
        degree=2,
    )

    assert np.allclose(legacy.data, explicit.data, atol=1e-10)


@pytest.mark.parametrize(
    ("kwargs", "error_type", "message"),
    [
        (
            {"degree_mode": "unknown"},
            ValueError,
            "polynomial_background degree_mode must be",
        ),
        (
            {"degree_mode": "total", "degree": True},
            TypeError,
            "polynomial_background requires degree to be a non-negative integer",
        ),
        (
            {"degree_mode": "total", "degree": -1},
            ValueError,
            "polynomial_background requires degree to be non-negative",
        ),
        (
            {
                "degree_mode": "total",
                "degree": 2,
                "x_degree": 2,
            },
            ValueError,
            "total degree mode does not accept x_degree or y_degree",
        ),
        (
            {"degree_mode": "independent"},
            ValueError,
            "independent degree mode requires x_degree and y_degree",
        ),
    ],
    ids=[
        "invalid-mode",
        "boolean-degree",
        "negative-degree",
        "total-with-axis-degree",
        "independent-missing-degrees",
    ],
)
def test_polynomial_background_rejects_invalid_degree_configuration(
    kwargs: dict[str, object],
    error_type: type[Exception],
    message: str,
) -> None:
    """Invalid polynomial degree configurations must fail explicitly."""
    channel = SPMChannel(
        name="Z-Axis",
        data=np.arange(25.0).reshape(5, 5),
        unit="nm",
        x_range=5e-6,
        y_range=5e-6,
    )

    with pytest.raises(error_type, match=message):
        leveling.polynomial_background(
            channel,
            **kwargs,  # type: ignore[arg-type]
        )


def test_polynomial_background_rejects_rank_deficient_selection() -> None:
    """Selected pixels must determine every requested polynomial term."""
    data = np.arange(25.0).reshape(5, 5)
    mask = np.zeros(data.shape, dtype=bool)
    mask[0, :] = True

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=5e-6,
        y_range=5e-6,
    )

    with pytest.raises(
        ValueError,
        match="selected points do not define a unique polynomial background",
    ):
        leveling.polynomial_background(
            channel,
            degree_mode="independent",
            x_degree=1,
            y_degree=1,
            mask=mask,
            mask_mode="include",
        )


def test_align_rows_can_preserve_global_mean() -> None:
    """Mean-preserving alignment must keep the absolute global level."""
    data = np.array(
        [
            [1.0, 1.0, 1.0],
            [2.0, 2.0, 2.0],
            [6.0, 6.0, 6.0],
        ]
    )
    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=3e-6,
        y_range=3e-6,
    )

    result = leveling.align_rows(
        channel,
        method="median",
        preserve_mean=True,
    )

    expected_level = np.mean(data)

    assert np.allclose(
        np.mean(result.data, axis=1),
        expected_level,
    )
    assert np.isclose(np.mean(result.data), np.mean(data))


@pytest.mark.parametrize("mask_mode", ["include", "exclude"])
def test_align_rows_mask_controls_row_statistic(mask_mode: str) -> None:
    """Masked row alignment must ignore excluded surface features."""
    data = np.array(
        [
            [1.0, 1.0, 100.0],
            [2.0, 2.0, 200.0],
        ]
    )
    excluded = np.zeros(data.shape, dtype=bool)
    excluded[:, 2] = True

    mask = ~excluded if mask_mode == "include" else excluded

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=3e-6,
        y_range=2e-6,
    )

    result = leveling.align_rows(
        channel,
        method="mean",
        mask=mask,
        mask_mode=mask_mode,  # type: ignore[arg-type]
    )

    assert np.allclose(result.data[~excluded], 0.0)
    assert np.allclose(result.data[:, 2], [99.0, 198.0])


@pytest.mark.parametrize(
    ("trim_fraction", "reference_method"),
    [
        (0.0, "mean"),
        (0.5, "median"),
    ],
    ids=["no-trimming-is-mean", "maximum-trimming-is-median"],
)
def test_align_rows_trimmed_mean_endpoints(
    trim_fraction: float,
    reference_method: str,
) -> None:
    """Trimmed mean must interpolate between mean and median."""
    data = np.array(
        [
            [0.0, 1.0, 2.0, 100.0],
            [4.0, 5.0, 6.0, 200.0],
        ]
    )
    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=4e-6,
        y_range=2e-6,
    )

    trimmed = leveling.align_rows(
        channel,
        method="trimmed_mean",
        trim_fraction=trim_fraction,
    )
    reference = leveling.align_rows(
        channel,
        method=reference_method,  # type: ignore[arg-type]
    )

    assert np.allclose(trimmed.data, reference.data)


@pytest.mark.parametrize(
    ("kwargs", "error_type", "message"),
    [
        (
            {"method": "unknown"},
            ValueError,
            "align_rows method must be",
        ),
        (
            {"method": "trimmed_mean", "trim_fraction": True},
            TypeError,
            "align_rows requires trim_fraction to be a real scalar",
        ),
        (
            {"method": "trimmed_mean", "trim_fraction": -0.1},
            ValueError,
            "align_rows requires trim_fraction between 0 and 0.5",
        ),
        (
            {"method": "trimmed_mean", "trim_fraction": 0.6},
            ValueError,
            "align_rows requires trim_fraction between 0 and 0.5",
        ),
        (
            {"preserve_mean": "yes"},
            TypeError,
            "align_rows requires preserve_mean to be boolean",
        ),
    ],
    ids=[
        "unknown-method",
        "boolean-trim",
        "negative-trim",
        "excessive-trim",
        "non-boolean-preserve-mean",
    ],
)
def test_align_rows_rejects_invalid_configuration(
    kwargs: dict[str, object],
    error_type: type[Exception],
    message: str,
) -> None:
    """Invalid row-alignment configurations must fail explicitly."""
    channel = SPMChannel(
        name="Z-Axis",
        data=np.arange(12.0).reshape(3, 4),
        unit="nm",
        x_range=4e-6,
        y_range=3e-6,
    )

    with pytest.raises(error_type, match=message):
        leveling.align_rows(
            channel,
            **kwargs,  # type: ignore[arg-type]
        )


def test_align_rows_rejects_rows_without_selected_points() -> None:
    """Every row must contain data selected for its statistic."""
    data = np.arange(12.0).reshape(3, 4)
    mask = np.ones(data.shape, dtype=bool)
    mask[1, :] = False

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=4e-6,
        y_range=3e-6,
    )

    with pytest.raises(
        ValueError,
        match="align_rows requires at least 1 selected point in every row",
    ):
        leveling.align_rows(
            channel,
            method="median",
            mask=mask,
            mask_mode="include",
        )


def test_align_rows_polynomial_removes_row_background_and_preserves_feature() -> None:
    """Polynomial row alignment must preserve excluded surface features."""
    rows, columns = 4, 9
    x = np.linspace(-1.0, 1.0, columns)

    offsets = np.array([1.0, 3.0, -2.0, 5.0])
    slopes = np.array([0.5, -1.0, 2.0, -0.25])
    curvatures = np.array([0.2, -0.4, 0.75, 0.1])

    data = np.vstack(
        [offsets[row] + slopes[row] * x + curvatures[row] * x**2 for row in range(rows)]
    )

    data[2, 4] += 12.0

    excluded = np.zeros(data.shape, dtype=bool)
    excluded[2, 4] = True

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=9e-6,
        y_range=4e-6,
        metadata={"source": "synthetic"},
    )

    result = leveling.align_rows(
        channel,
        method="polynomial",
        polynomial_degree=2,
        mask=excluded,
        mask_mode="exclude",
    )

    assert np.allclose(result.data[~excluded], 0.0, atol=1e-10)
    assert np.isclose(result.data[2, 4], 12.0, atol=1e-10)


def test_align_rows_polynomial_degree_zero_matches_mean() -> None:
    """A degree-zero row polynomial must reproduce mean alignment."""
    data = np.array(
        [
            [1.0, 2.0, 6.0],
            [4.0, 8.0, 12.0],
        ]
    )
    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=3e-6,
        y_range=2e-6,
    )

    polynomial = leveling.align_rows(
        channel,
        method="polynomial",
        polynomial_degree=0,
    )
    mean = leveling.align_rows(
        channel,
        method="mean",
    )

    assert np.allclose(polynomial.data, mean.data)


def test_align_rows_polynomial_can_preserve_global_mean() -> None:
    """Mean-preserving polynomial alignment must retain the global level."""
    columns = 7
    x = np.linspace(-1.0, 1.0, columns)

    data = np.vstack(
        [
            5.0 + x,
            8.0 - 2.0 * x,
            12.0 + 0.5 * x,
        ]
    )

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=7e-6,
        y_range=3e-6,
    )

    result = leveling.align_rows(
        channel,
        method="polynomial",
        polynomial_degree=1,
        preserve_mean=True,
    )

    assert np.isclose(np.mean(result.data), np.mean(data))
    assert np.allclose(
        result.data,
        np.mean(data),
        atol=1e-10,
    )


@pytest.mark.parametrize(
    ("degree", "error_type", "message"),
    [
        (
            True,
            TypeError,
            "align_rows requires polynomial_degree to be a non-negative integer",
        ),
        (
            1.5,
            TypeError,
            "align_rows requires polynomial_degree to be a non-negative integer",
        ),
        (
            -1,
            ValueError,
            "align_rows requires polynomial_degree to be non-negative",
        ),
    ],
    ids=[
        "boolean",
        "non-integer",
        "negative",
    ],
)
def test_align_rows_polynomial_rejects_invalid_degree(
    degree: object,
    error_type: type[Exception],
    message: str,
) -> None:
    """Polynomial row degree must be a valid non-negative integer."""
    channel = SPMChannel(
        name="Z-Axis",
        data=np.arange(12.0).reshape(3, 4),
        unit="nm",
        x_range=4e-6,
        y_range=3e-6,
    )

    with pytest.raises(error_type, match=message):
        leveling.align_rows(
            channel,
            method="polynomial",
            polynomial_degree=degree,  # type: ignore[arg-type]
        )


def test_align_rows_polynomial_rejects_rank_deficient_row() -> None:
    """Every row must contain enough independent points for its polynomial."""
    data = np.arange(15.0).reshape(3, 5)
    mask = np.ones(data.shape, dtype=bool)
    mask[1, :] = False
    mask[1, :2] = True

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=5e-6,
        y_range=3e-6,
    )

    with pytest.raises(
        ValueError,
        match="align_rows requires at least 3 selected points in every row",
    ):
        leveling.align_rows(
            channel,
            method="polynomial",
            polynomial_degree=2,
            mask=mask,
            mask_mode="include",
        )


def test_align_rows_median_difference_preserves_large_feature() -> None:
    """Median differences must align offsets without flattening shared features."""
    base_profile = np.array([0.0, 0.0, 8.0, 8.0, 8.0, 0.0, 0.0])
    row_offsets = np.array([1.0, -1.0, -1.0, 1.0])

    data = base_profile[np.newaxis, :] + row_offsets[:, np.newaxis]

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=7e-6,
        y_range=4e-6,
    )

    result = leveling.align_rows(
        channel,
        method="median_difference",
    )

    expected = base_profile + row_offsets[0]

    assert np.allclose(
        result.data,
        expected[np.newaxis, :],
        atol=1e-12,
    )


def test_align_rows_median_difference_preserves_global_tilt() -> None:
    """Difference alignment must preserve the linear slow-axis trend."""
    rows, columns = 7, 9
    row_coordinate = np.arange(rows, dtype=float)
    base_profile = np.linspace(-2.0, 3.0, columns)

    global_tilt = 1.75 * row_coordinate
    row_defects = np.array([0.0, 2.0, -1.0, 1.5, -2.0, 1.0, 0.0])

    data = base_profile[np.newaxis, :] + global_tilt[:, np.newaxis] + row_defects[:, np.newaxis]

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=9e-6,
        y_range=7e-6,
    )

    result = leveling.align_rows(
        channel,
        method="median_difference",
        preserve_tilt=True,
        preserve_mean=True,
    )

    original_slope = np.polyfit(
        row_coordinate,
        np.mean(data, axis=1),
        deg=1,
    )[0]
    corrected_slope = np.polyfit(
        row_coordinate,
        np.mean(result.data, axis=1),
        deg=1,
    )[0]

    assert np.isclose(corrected_slope, original_slope, atol=1e-12)


def test_align_rows_median_difference_can_remove_global_tilt() -> None:
    """Tilt preservation must be explicitly disableable."""
    rows, columns = 5, 6
    row_coordinate = np.arange(rows, dtype=float)
    base_profile = np.linspace(0.0, 2.0, columns)

    data = base_profile[np.newaxis, :] + 3.0 * row_coordinate[:, np.newaxis]

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=6e-6,
        y_range=5e-6,
    )

    result = leveling.align_rows(
        channel,
        method="median_difference",
        preserve_tilt=False,
    )

    assert np.allclose(
        result.data,
        result.data[0],
        atol=1e-12,
    )


def test_align_rows_trimmed_mean_difference_half_matches_median_difference() -> None:
    """Maximum trimming must reproduce median-difference alignment."""
    data = np.array(
        [
            [0.0, 1.0, 2.0, 80.0, 4.0],
            [2.0, 3.0, 4.0, 150.0, 6.0],
            [-1.0, 0.0, 1.0, -100.0, 3.0],
        ]
    )

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=5e-6,
        y_range=3e-6,
    )

    trimmed = leveling.align_rows(
        channel,
        method="trimmed_mean_difference",
        trim_fraction=0.5,
    )
    median = leveling.align_rows(
        channel,
        method="median_difference",
    )

    assert np.allclose(trimmed.data, median.data)


@pytest.mark.parametrize(
    ("preserve_tilt", "error_type", "message"),
    [
        (
            "yes",
            TypeError,
            "align_rows requires preserve_tilt to be boolean",
        ),
        (
            1,
            TypeError,
            "align_rows requires preserve_tilt to be boolean",
        ),
    ],
    ids=["string", "integer"],
)
def test_align_rows_rejects_invalid_preserve_tilt(
    preserve_tilt: object,
    error_type: type[Exception],
    message: str,
) -> None:
    """Tilt-preservation configuration must be explicitly boolean."""
    channel = SPMChannel(
        name="Z-Axis",
        data=np.arange(12.0).reshape(3, 4),
        unit="nm",
        x_range=4e-6,
        y_range=3e-6,
    )

    with pytest.raises(error_type, match=message):
        leveling.align_rows(
            channel,
            method="median_difference",
            preserve_tilt=preserve_tilt,  # type: ignore[arg-type]
        )


def test_align_rows_difference_requires_shared_selected_pixels() -> None:
    """Adjacent rows must share at least one selected column."""
    data = np.arange(12.0).reshape(3, 4)
    mask = np.zeros(data.shape, dtype=bool)
    mask[0, :2] = True
    mask[1, 2:] = True
    mask[2, 2:] = True

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=4e-6,
        y_range=3e-6,
    )

    with pytest.raises(
        ValueError,
        match="align_rows requires adjacent rows to share selected points",
    ):
        leveling.align_rows(
            channel,
            method="median_difference",
            mask=mask,
            mask_mode="include",
        )


def test_align_rows_matching_downweights_local_slope_mismatch() -> None:
    """Matching must downweight a local defect with incompatible slopes."""
    columns = 9
    base_profile = np.linspace(-1.0, 1.0, columns)

    data = np.vstack(
        [
            base_profile,
            base_profile + 2.0,
        ]
    )
    data[1, 4] += 100.0

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=9e-6,
        y_range=2e-6,
    )

    result = leveling.align_rows(
        channel,
        method="matching",
        preserve_tilt=False,
    )

    clean_columns = np.ones(columns, dtype=bool)
    clean_columns[4] = False

    assert np.allclose(
        result.data[1, clean_columns],
        result.data[0, clean_columns],
        atol=1e-2,
    )
    assert result.data[1, 4] - result.data[0, 4] > 99.0


def test_align_rows_matching_aligns_constant_row_offsets() -> None:
    """Matching must exactly align rows differing only by vertical offsets."""
    base_profile = np.array([0.0, 1.0, 3.0, 2.0, -1.0, 4.0, 5.0])
    offsets = np.array([0.0, 3.0, -2.0, 1.0])

    data = base_profile[np.newaxis, :] + offsets[:, np.newaxis]

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=7e-6,
        y_range=4e-6,
    )

    result = leveling.align_rows(
        channel,
        method="matching",
        preserve_tilt=False,
    )

    assert np.allclose(
        result.data,
        base_profile[np.newaxis, :],
        atol=1e-12,
    )


@pytest.mark.parametrize("mask_mode", ["include", "exclude"])
def test_align_rows_matching_respects_mask_selection(
    mask_mode: str,
) -> None:
    """Matching must estimate offsets only from selected neighbouring pixels."""
    data = np.array(
        [
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [3.0, 3.0, 3.0, 50.0, 50.0, 50.0],
        ]
    )

    excluded = np.zeros(data.shape, dtype=bool)
    excluded[:, 3:] = True

    mask = ~excluded if mask_mode == "include" else excluded

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=6e-6,
        y_range=2e-6,
    )

    result = leveling.align_rows(
        channel,
        method="matching",
        mask=mask,
        mask_mode=mask_mode,  # type: ignore[arg-type]
        preserve_tilt=False,
    )

    assert np.allclose(result.data[1, :3], 0.0, atol=1e-12)
    assert np.allclose(result.data[1, 3:], 47.0, atol=1e-12)


def test_align_rows_matching_preserves_global_tilt() -> None:
    """Matching must preserve slow-axis tilt when requested."""
    rows, columns = 6, 8
    row_coordinate = np.arange(rows, dtype=float)
    base_profile = np.linspace(-2.0, 3.0, columns)

    global_tilt = 1.25 * row_coordinate
    row_defects = np.array([0.0, 2.0, -1.0, 1.5, -2.0, 0.5])

    data = base_profile[np.newaxis, :] + global_tilt[:, np.newaxis] + row_defects[:, np.newaxis]

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=8e-6,
        y_range=6e-6,
    )

    result = leveling.align_rows(
        channel,
        method="matching",
        preserve_tilt=True,
        preserve_mean=True,
    )

    original_slope = np.polyfit(
        row_coordinate,
        np.mean(data, axis=1),
        deg=1,
    )[0]
    corrected_slope = np.polyfit(
        row_coordinate,
        np.mean(result.data, axis=1),
        deg=1,
    )[0]

    assert np.isclose(
        corrected_slope,
        original_slope,
        atol=1e-12,
    )


def test_align_rows_matching_requires_shared_selected_edges() -> None:
    """Adjacent rows must share a selected neighbouring-pixel pair."""
    data = np.arange(15.0).reshape(3, 5)

    mask = np.zeros(data.shape, dtype=bool)
    mask[0, [0, 2, 4]] = True
    mask[1, [0, 2, 4]] = True
    mask[2, [0, 2, 4]] = True

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=5e-6,
        y_range=3e-6,
    )

    with pytest.raises(
        ValueError,
        match=(
            "align_rows matching requires adjacent rows to share " "selected neighbouring pixels"
        ),
    ):
        leveling.align_rows(
            channel,
            method="matching",
            mask=mask,
            mask_mode="include",
        )


def test_align_rows_mode_tracks_dominant_row_level() -> None:
    """Mode alignment must follow the densest cluster in each row."""
    data = np.array(
        [
            [1.0, 1.0, 1.0, 8.0, 20.0],
            [4.0, 4.0, 4.0, -10.0, 30.0],
        ]
    )

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=5e-6,
        y_range=2e-6,
    )

    result = leveling.align_rows(
        channel,
        method="mode",
    )

    expected = np.array(
        [
            [0.0, 0.0, 0.0, 7.0, 19.0],
            [0.0, 0.0, 0.0, -14.0, 26.0],
        ]
    )

    assert np.allclose(result.data, expected)


@pytest.mark.parametrize("mask_mode", ["include", "exclude"])
def test_align_rows_mode_respects_mask_selection(
    mask_mode: str,
) -> None:
    """Modal row level must be estimated only from selected pixels."""
    data = np.array(
        [
            [1.0, 1.0, 1.0, 100.0, 200.0],
            [2.0, 2.0, 2.0, -50.0, 80.0],
        ]
    )

    excluded = np.zeros(data.shape, dtype=bool)
    excluded[:, 3:] = True

    mask = ~excluded if mask_mode == "include" else excluded

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=5e-6,
        y_range=2e-6,
    )

    result = leveling.align_rows(
        channel,
        method="mode",
        mask=mask,
        mask_mode=mask_mode,  # type: ignore[arg-type]
    )

    assert np.allclose(result.data[:, :3], 0.0)
    assert np.allclose(
        result.data[:, 3:],
        np.array(
            [
                [99.0, 199.0],
                [-52.0, 78.0],
            ]
        ),
    )


def test_align_rows_mode_can_preserve_global_mean() -> None:
    """Mean-preserving mode alignment must retain the global level."""
    data = np.array(
        [
            [1.0, 1.0, 1.0, 9.0],
            [4.0, 4.0, 4.0, 20.0],
            [8.0, 8.0, 8.0, -5.0],
        ]
    )

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=4e-6,
        y_range=3e-6,
    )

    result = leveling.align_rows(
        channel,
        method="mode",
        preserve_mean=True,
    )

    assert np.isclose(
        np.mean(result.data),
        np.mean(data),
    )


def test_align_rows_mode_supports_one_selected_point_per_row() -> None:
    """A single selected pixel must define the modal row level."""
    data = np.array(
        [
            [1.0, 5.0, 9.0],
            [2.0, 6.0, 10.0],
        ]
    )

    mask = np.zeros(data.shape, dtype=bool)
    mask[:, 1] = True

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=3e-6,
        y_range=2e-6,
    )

    result = leveling.align_rows(
        channel,
        method="mode",
        mask=mask,
        mask_mode="include",
    )

    assert np.allclose(result.data[:, 1], 0.0)
    assert np.allclose(
        result.data,
        np.array(
            [
                [-4.0, 0.0, 4.0],
                [-4.0, 0.0, 4.0],
            ]
        ),
    )


def test_align_rows_facet_tilt_removes_row_slopes_preserving_offsets() -> None:
    """Facet tilt must remove row slopes without changing row offsets."""
    columns = 9
    x = np.linspace(-1.0, 1.0, columns)

    offsets = np.array([2.0, -3.0, 7.0])
    slopes = np.array([1.5, -2.0, 0.75])

    data = np.vstack([offsets[row] + slopes[row] * x for row in range(offsets.size)])

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=9e-6,
        y_range=3e-6,
    )

    result = leveling.align_rows(
        channel,
        method="facet_tilt",
    )

    expected = np.repeat(
        offsets[:, np.newaxis],
        columns,
        axis=1,
    )

    assert np.allclose(result.data, expected, atol=1e-12)
    assert np.allclose(
        np.mean(result.data, axis=1),
        np.mean(data, axis=1),
        atol=1e-12,
    )


def test_align_rows_facet_tilt_is_robust_to_local_spike() -> None:
    """A local spike must not dominate the prevalent row slope."""
    columns = 9
    x = np.linspace(-1.0, 1.0, columns)

    data = np.vstack(
        [
            3.0 + 2.0 * x,
            -4.0 - 1.5 * x,
        ]
    )
    data[0, 4] += 100.0
    data[1, 5] -= 80.0

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=9e-6,
        y_range=2e-6,
    )

    result = leveling.align_rows(
        channel,
        method="facet_tilt",
    )

    clean_first = np.ones(columns, dtype=bool)
    clean_first[4] = False

    clean_second = np.ones(columns, dtype=bool)
    clean_second[5] = False

    assert np.allclose(
        result.data[0, clean_first],
        3.0,
        atol=1e-12,
    )
    assert np.allclose(
        result.data[1, clean_second],
        -4.0,
        atol=1e-12,
    )
    assert np.isclose(result.data[0, 4], 103.0, atol=1e-12)
    assert np.isclose(result.data[1, 5], -84.0, atol=1e-12)


@pytest.mark.parametrize("mask_mode", ["include", "exclude"])
def test_align_rows_facet_tilt_respects_mask_selection(
    mask_mode: str,
) -> None:
    """Facet tilt must estimate slopes only from selected adjacent pixels."""
    columns = 8
    x = np.linspace(-1.0, 1.0, columns)

    data = np.vstack(
        [
            2.0 + 3.0 * x,
            -1.0 - 2.0 * x,
        ]
    )

    data[:, 5:] += np.array([[20.0], [-30.0]])

    excluded = np.zeros(data.shape, dtype=bool)
    excluded[:, 5:] = True

    mask = ~excluded if mask_mode == "include" else excluded

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=8e-6,
        y_range=2e-6,
    )

    result = leveling.align_rows(
        channel,
        method="facet_tilt",
        mask=mask,
        mask_mode=mask_mode,  # type: ignore[arg-type]
    )

    assert np.allclose(result.data[0, :5], 2.0, atol=1e-12)
    assert np.allclose(result.data[1, :5], -1.0, atol=1e-12)

    assert np.allclose(result.data[0, 5:], 22.0, atol=1e-12)
    assert np.allclose(result.data[1, 5:], -31.0, atol=1e-12)


def test_align_rows_facet_tilt_requires_selected_adjacent_pixels() -> None:
    """Each row must contain a selected neighbouring-pixel pair."""
    data = np.arange(15.0).reshape(3, 5)

    mask = np.zeros(data.shape, dtype=bool)
    mask[:, [0, 2, 4]] = True

    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="nm",
        x_range=5e-6,
        y_range=3e-6,
    )

    with pytest.raises(
        ValueError,
        match=("align_rows facet_tilt requires selected " "neighbouring pixels in every row"),
    ):
        leveling.align_rows(
            channel,
            method="facet_tilt",
            mask=mask,
            mask_mode="include",
        )
