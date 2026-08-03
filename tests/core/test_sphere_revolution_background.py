"""Tests for physical sphere-revolution background estimation."""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis.background import (
    _sphere_structure,
    estimate_arc_revolution_background,
    estimate_sphere_revolution_background,
    remove_sphere_revolution_background,
)
from spmkit.core.models import SPMChannel


def _channel(
    data: np.ndarray,
    *,
    unit: str = "m",
    x_range: float | None = None,
    y_range: float | None = None,
) -> SPMChannel:
    rows, columns = data.shape

    return SPMChannel(
        name="Z-Axis",
        data=np.asarray(data),
        unit=unit,
        x_range=float(columns) if x_range is None else x_range,
        y_range=float(rows) if y_range is None else y_range,
        direction="backward",
        group="Synthetic",
        metadata={"source": "sphere-test"},
    )


def _nearest_index(index: int, size: int) -> int:
    return min(max(index, 0), size - 1)


def _reflect_index(index: int, size: int) -> int:
    """Map an integer index using SciPy's half-sample reflection."""
    period = 2 * size
    position = index % period

    if position < size:
        return position

    return period - 1 - position


def _brute_force_sphere_below_nearest(
    data: np.ndarray,
    *,
    radius: float,
    x_spacing: float,
    y_spacing: float,
) -> np.ndarray:
    """Independent two-dimensional spherical-opening oracle."""
    values = np.asarray(data, dtype=float)
    rows, columns = values.shape

    maximum_x_offset = min(
        int(np.floor(radius / x_spacing)),
        columns - 1,
    )
    maximum_y_offset = min(
        int(np.floor(radius / y_spacing)),
        rows - 1,
    )

    offsets: list[tuple[int, int, float]] = []

    for y_offset in range(
        -maximum_y_offset,
        maximum_y_offset + 1,
    ):
        for x_offset in range(
            -maximum_x_offset,
            maximum_x_offset + 1,
        ):
            normalized_x = x_offset * x_spacing / radius
            normalized_y = y_offset * y_spacing / radius
            squared_ratio = normalized_x**2 + normalized_y**2

            if squared_ratio > 1.0 + 8.0 * np.finfo(float).eps:
                continue

            clipped_ratio = min(squared_ratio, 1.0)
            root = np.sqrt(max(1.0 - clipped_ratio, 0.0))
            sagitta = radius * clipped_ratio / (1.0 + root)

            offsets.append(
                (
                    y_offset,
                    x_offset,
                    sagitta,
                )
            )

    eroded = np.empty_like(values)

    for row in range(rows):
        for column in range(columns):
            candidates = [
                values[
                    _nearest_index(row + y_offset, rows),
                    _nearest_index(column + x_offset, columns),
                ]
                + sagitta
                for y_offset, x_offset, sagitta in offsets
            ]
            eroded[row, column] = min(candidates)

    opened = np.empty_like(values)

    for row in range(rows):
        for column in range(columns):
            candidates = [
                eroded[
                    _nearest_index(row - y_offset, rows),
                    _nearest_index(column - x_offset, columns),
                ]
                - sagitta
                for y_offset, x_offset, sagitta in offsets
            ]
            opened[row, column] = max(candidates)

    return opened


def _brute_force_sphere_below_reflect(
    data: np.ndarray,
    *,
    radius: float,
    x_spacing: float,
    y_spacing: float,
) -> np.ndarray:
    """Independent spherical-opening oracle with reflected boundaries."""
    values = np.asarray(data, dtype=float)
    rows, columns = values.shape

    maximum_x_offset = min(
        int(np.floor(radius / x_spacing)),
        columns - 1,
    )
    maximum_y_offset = min(
        int(np.floor(radius / y_spacing)),
        rows - 1,
    )

    offsets: list[tuple[int, int, float]] = []

    for y_offset in range(
        -maximum_y_offset,
        maximum_y_offset + 1,
    ):
        for x_offset in range(
            -maximum_x_offset,
            maximum_x_offset + 1,
        ):
            normalized_x = x_offset * x_spacing / radius
            normalized_y = y_offset * y_spacing / radius
            squared_ratio = normalized_x**2 + normalized_y**2

            if squared_ratio > 1.0 + 8.0 * np.finfo(float).eps:
                continue

            clipped_ratio = min(squared_ratio, 1.0)
            root = np.sqrt(max(1.0 - clipped_ratio, 0.0))
            sagitta = radius * clipped_ratio / (1.0 + root)

            offsets.append(
                (
                    y_offset,
                    x_offset,
                    sagitta,
                )
            )

    eroded = np.empty_like(values)

    for row in range(rows):
        for column in range(columns):
            candidates = [
                values[
                    _reflect_index(row + y_offset, rows),
                    _reflect_index(column + x_offset, columns),
                ]
                + sagitta
                for y_offset, x_offset, sagitta in offsets
            ]
            eroded[row, column] = min(candidates)

    opened = np.empty_like(values)

    for row in range(rows):
        for column in range(columns):
            candidates = [
                eroded[
                    _reflect_index(row - y_offset, rows),
                    _reflect_index(column - x_offset, columns),
                ]
                - sagitta
                for y_offset, x_offset, sagitta in offsets
            ]
            opened[row, column] = max(candidates)

    return opened


def test_sphere_structure_uses_circular_physical_footprint() -> None:
    structure, footprint = _sphere_structure(
        radius=1.1,
        x_spacing=1.0,
        y_spacing=1.0,
        shape=(5, 5),
    )

    expected_footprint = np.array(
        [
            [False, True, False],
            [True, True, True],
            [False, True, False],
        ]
    )

    assert structure.shape == (3, 3)
    assert np.array_equal(footprint, expected_footprint)
    assert structure[1, 1] == 0.0
    assert np.all(structure[footprint] <= 0.0)


def test_flat_surface_is_preserved() -> None:
    data = np.full((5, 7), 3.25)
    channel = _channel(data)

    background = estimate_sphere_revolution_background(
        channel,
        radius=2.0,
    )
    corrected = remove_sphere_revolution_background(
        channel,
        radius=2.0,
    )

    assert np.allclose(background.data, data)
    assert np.allclose(corrected.data, 0.0)


def test_nearest_matches_independent_two_dimensional_oracle() -> None:
    data = np.array(
        [
            [0.0, 0.2, 1.0, 0.1],
            [0.3, 1.5, 3.0, 0.4],
            [0.1, 0.6, 1.8, 0.2],
        ]
    )
    channel = _channel(
        data,
        x_range=4.0,
        y_range=3.0,
    )

    result = estimate_sphere_revolution_background(
        channel,
        radius=1.5,
        border="nearest",
    )
    expected = _brute_force_sphere_below_nearest(
        data,
        radius=1.5,
        x_spacing=1.0,
        y_spacing=1.0,
    )

    assert np.allclose(
        result.data,
        expected,
        rtol=1e-13,
        atol=1e-13,
    )


def test_above_is_exact_inversion_dual() -> None:
    data = np.array(
        [
            [0.0, -0.2, -1.0, -0.1],
            [-0.3, -1.5, -3.0, -0.4],
            [-0.1, -0.6, -1.8, -0.2],
        ]
    )
    channel = _channel(data)
    inverted = channel.with_data(-data)

    above = estimate_sphere_revolution_background(
        channel,
        radius=1.5,
        side="above",
    )
    below_inverted = estimate_sphere_revolution_background(
        inverted,
        radius=1.5,
        side="below",
    )

    assert np.allclose(
        above.data,
        -below_inverted.data,
    )


def test_reconstruction_identity() -> None:
    yy, xx = np.mgrid[0:7, 0:9]
    data = 0.02 * xx + 0.03 * yy + 2.0 * np.exp(-((xx - 4) ** 2 + (yy - 3) ** 2) / 2.0)
    channel = _channel(
        data,
        x_range=9e-6,
        y_range=14e-6,
    )

    background = estimate_sphere_revolution_background(
        channel,
        radius=4e-6,
    )
    corrected = remove_sphere_revolution_background(
        channel,
        radius=4e-6,
    )

    assert np.allclose(
        corrected.data + background.data,
        data,
        rtol=1e-12,
        atol=1e-12,
    )


def test_sphere_structure_respects_anisotropic_physical_spacing() -> None:
    structure, footprint = _sphere_structure(
        radius=2.1,
        x_spacing=1.0,
        y_spacing=2.0,
        shape=(5, 5),
    )

    expected_footprint = np.array(
        [
            [False, False, True, False, False],
            [True, True, True, True, True],
            [False, False, True, False, False],
        ]
    )

    assert structure.shape == (3, 5)
    assert np.array_equal(footprint, expected_footprint)

    # ±2 pixels in X and ±1 pixel in Y are both physical distances of 2.
    assert footprint[1, 0]
    assert footprint[0, 2]

    # A diagonal offset of (1 px X, 1 px Y) has physical distance sqrt(5),
    # which lies outside a sphere of radius 2.1.
    assert not footprint[0, 1]


def test_sphere_is_not_separable_arc_revolution() -> None:
    data = np.array(
        [
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, 1.0, 2.0],
        ]
    )
    channel = _channel(
        data,
        x_range=3.0,
        y_range=3.0,
    )

    sphere = estimate_sphere_revolution_background(
        channel,
        radius=1.1,
        border="nearest",
    )
    separable_arc = estimate_arc_revolution_background(
        channel,
        radius=1.1,
        direction="both",
        border="nearest",
    )

    assert not np.allclose(
        sphere.data,
        separable_arc.data,
    )


def test_reflect_matches_independent_two_dimensional_oracle() -> None:
    data = np.array(
        [
            [3.0, 0.2, 0.1, 2.0],
            [0.4, 1.5, 0.3, 0.0],
            [2.0, 0.6, 1.8, 4.0],
        ]
    )
    channel = _channel(
        data,
        x_range=4.0,
        y_range=3.0,
    )

    result = estimate_sphere_revolution_background(
        channel,
        radius=1.5,
        border="reflect",
    )
    expected = _brute_force_sphere_below_reflect(
        data,
        radius=1.5,
        x_spacing=1.0,
        y_spacing=1.0,
    )

    assert np.allclose(
        result.data,
        expected,
        rtol=1e-13,
        atol=1e-13,
    )


def test_radius_smaller_than_both_pixel_spacings_is_identity() -> None:
    data = np.array(
        [
            [0.2, 1.0, 0.4],
            [2.0, 0.1, 1.5],
        ]
    )
    channel = _channel(
        data,
        x_range=3.0,
        y_range=2.0,
    )

    background = estimate_sphere_revolution_background(
        channel,
        radius=0.5,
    )
    corrected = remove_sphere_revolution_background(
        channel,
        radius=0.5,
    )

    assert np.array_equal(background.data, data)
    assert np.array_equal(corrected.data, np.zeros_like(data))


def test_radius_larger_than_domain_is_supported() -> None:
    data = np.array(
        [
            [0.0, 0.2, 1.0, 0.1],
            [0.3, 1.5, 3.0, 0.4],
            [0.1, 0.6, 1.8, 0.2],
        ]
    )
    channel = _channel(data)

    background = estimate_sphere_revolution_background(
        channel,
        radius=1e12,
    )
    corrected = remove_sphere_revolution_background(
        channel,
        radius=1e12,
    )

    assert background.data.shape == data.shape
    assert np.all(np.isfinite(background.data))
    assert np.allclose(
        corrected.data + background.data,
        data,
        rtol=1e-13,
        atol=1e-13,
    )


def test_sphere_structure_preserves_small_sagitta_for_large_radius() -> None:
    structure, footprint = _sphere_structure(
        radius=1e12,
        x_spacing=1.0,
        y_spacing=1.0,
        shape=(3, 3),
    )

    assert structure.shape == (5, 5)
    assert np.all(footprint)
    assert structure[2, 2] == 0.0
    assert structure[2, 3] == pytest.approx(-5e-13, rel=1e-12)
    assert structure[3, 3] == pytest.approx(-1e-12, rel=1e-12)


def test_equivalent_metres_and_nanometres_agree_physically() -> None:
    data_metres = (
        np.array(
            [
                [0.0, 0.2, 1.0, 0.1],
                [0.3, 1.5, 3.0, 0.4],
                [0.1, 0.6, 1.8, 0.2],
            ]
        )
        * 1e-9
    )

    channel_metres = _channel(
        data_metres,
        unit="m",
        x_range=4e-6,
        y_range=3e-6,
    )
    channel_nanometres = _channel(
        data_metres * 1e9,
        unit="nm",
        x_range=4e-6,
        y_range=3e-6,
    )

    background_metres = estimate_sphere_revolution_background(
        channel_metres,
        radius=1.5e-6,
    )
    background_nanometres = estimate_sphere_revolution_background(
        channel_nanometres,
        radius=1.5e-6,
    )

    assert np.allclose(
        background_metres.data,
        background_nanometres.data * 1e-9,
        rtol=1e-12,
        atol=1e-18,
    )


def test_input_is_not_mutated_and_context_is_preserved() -> None:
    data = np.array(
        [
            [0.0, 0.2, 1.0],
            [0.3, 1.5, 0.4],
        ]
    )
    original = data.copy()
    channel = _channel(data)

    background = estimate_sphere_revolution_background(
        channel,
        radius=1.5,
    )
    corrected = remove_sphere_revolution_background(
        channel,
        radius=1.5,
    )

    assert np.array_equal(channel.data, original)

    for result in (background, corrected):
        assert result is not channel
        assert result.name == channel.name
        assert result.unit == channel.unit
        assert result.x_range == channel.x_range
        assert result.y_range == channel.y_range
        assert result.direction == channel.direction
        assert result.group == channel.group
        assert result.metadata == channel.metadata
        assert result.metadata is not channel.metadata


@pytest.mark.parametrize(
    "nonfinite",
    [
        np.nan,
        np.inf,
        -np.inf,
    ],
)
def test_nonfinite_data_are_rejected(nonfinite: float) -> None:
    data = np.ones((3, 4))
    data[1, 2] = nonfinite
    channel = _channel(data)

    with pytest.raises(
        ValueError,
        match="requires finite data",
    ):
        estimate_sphere_revolution_background(
            channel,
            radius=1.0,
        )


def test_non_geometric_z_unit_is_rejected() -> None:
    channel = _channel(
        np.ones((3, 4)),
        unit="V",
    )

    with pytest.raises((TypeError, ValueError)):
        estimate_sphere_revolution_background(
            channel,
            radius=1.0,
        )


@pytest.mark.parametrize(
    "radius",
    [
        0.0,
        -1.0,
        np.nan,
        np.inf,
        -np.inf,
    ],
)
def test_invalid_radius_is_rejected(radius: float) -> None:
    channel = _channel(np.ones((3, 4)))

    with pytest.raises(ValueError):
        estimate_sphere_revolution_background(
            channel,
            radius=radius,
        )


@pytest.mark.parametrize(
    "radius",
    [
        True,
        None,
        "1.0",
        [1.0],
        1.0 + 0.0j,
    ],
)
def test_non_real_scalar_radius_is_rejected(radius: object) -> None:
    channel = _channel(np.ones((3, 4)))

    with pytest.raises(TypeError):
        estimate_sphere_revolution_background(
            channel,
            radius=radius,
        )


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("side", "underneath"),
        ("border", "wrap"),
    ],
)
def test_invalid_public_options_are_rejected(
    parameter: str,
    value: str,
) -> None:
    channel = _channel(np.ones((3, 4)))
    kwargs = {parameter: value}

    with pytest.raises(ValueError):
        estimate_sphere_revolution_background(
            channel,
            radius=1.0,
            **kwargs,
        )


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("side", None),
        ("border", 1),
    ],
)
def test_non_string_public_options_are_rejected(
    parameter: str,
    value: object,
) -> None:
    channel = _channel(np.ones((3, 4)))
    kwargs = {parameter: value}

    with pytest.raises(
        TypeError,
        match=rf"requires {parameter} to be a string",
    ):
        estimate_sphere_revolution_background(
            channel,
            radius=1.0,
            **kwargs,
        )


@pytest.mark.parametrize(
    "data",
    [
        np.ones(4),
        np.empty((0, 3)),
        np.array([["a", "b"], ["c", "d"]]),
        np.ones((2, 3), dtype=complex),
    ],
    ids=[
        "one-dimensional",
        "empty",
        "non-numeric",
        "complex",
    ],
)
def test_invalid_channel_data_are_rejected(data: np.ndarray) -> None:
    channel = SPMChannel(
        name="invalid",
        data=data,
        unit="m",
        x_range=3.0,
        y_range=2.0,
    )

    with pytest.raises((TypeError, ValueError)):
        estimate_sphere_revolution_background(
            channel,
            radius=1.0,
        )


@pytest.mark.parametrize(
    ("x_range", "y_range"),
    [
        (0.0, 3.0),
        (-1.0, 3.0),
        (np.inf, 3.0),
        (4.0, 0.0),
        (4.0, -1.0),
        (4.0, np.inf),
    ],
)
def test_invalid_lateral_geometry_is_rejected(
    x_range: float,
    y_range: float,
) -> None:
    channel = _channel(
        np.ones((3, 4)),
        x_range=x_range,
        y_range=y_range,
    )

    with pytest.raises(ValueError):
        estimate_sphere_revolution_background(
            channel,
            radius=1.0,
        )


@pytest.mark.parametrize("side", ["below", "above"])
@pytest.mark.parametrize("border", ["nearest", "reflect"])
def test_reconstruction_identity_for_every_mode(
    side: str,
    border: str,
) -> None:
    data = np.array(
        [
            [0.0, 0.2, 1.0, 0.1],
            [0.3, 1.5, 3.0, 0.4],
            [0.1, 0.6, 1.8, 0.2],
        ]
    )
    channel = _channel(data)

    background = estimate_sphere_revolution_background(
        channel,
        radius=1.5,
        side=side,
        border=border,
    )
    corrected = remove_sphere_revolution_background(
        channel,
        radius=1.5,
        side=side,
        border=border,
    )

    assert np.allclose(
        corrected.data + background.data,
        data,
        rtol=1e-13,
        atol=1e-13,
    )


@pytest.mark.parametrize(
    "data",
    [
        np.array([[2.0]]),
        np.array([[0.0, 2.0, 0.5, 1.0]]),
        np.array([[0.0], [2.0], [0.5], [1.0]]),
    ],
    ids=[
        "one-by-one",
        "one-row",
        "one-column",
    ],
)
def test_degenerate_dimensions_are_defined(data: np.ndarray) -> None:
    channel = _channel(data)

    background = estimate_sphere_revolution_background(
        channel,
        radius=2.0,
    )
    corrected = remove_sphere_revolution_background(
        channel,
        radius=2.0,
    )

    assert background.data.shape == data.shape
    assert corrected.data.shape == data.shape
    assert np.all(np.isfinite(background.data))
    assert np.allclose(
        corrected.data + background.data,
        data,
    )


def test_below_background_does_not_exceed_surface() -> None:
    data = np.array(
        [
            [0.0, 0.2, 1.0, 0.1],
            [0.3, 1.5, 3.0, 0.4],
            [0.1, 0.6, 1.8, 0.2],
        ]
    )
    channel = _channel(data)

    background = estimate_sphere_revolution_background(
        channel,
        radius=1.5,
        side="below",
    )

    assert np.all(background.data <= data + 1e-13)


def test_above_background_does_not_fall_below_surface() -> None:
    data = np.array(
        [
            [0.0, -0.2, -1.0, -0.1],
            [-0.3, -1.5, -3.0, -0.4],
            [-0.1, -0.6, -1.8, -0.2],
        ]
    )
    channel = _channel(data)

    background = estimate_sphere_revolution_background(
        channel,
        radius=1.5,
        side="above",
    )

    assert np.all(background.data >= data - 1e-13)


def test_functions_are_available_from_public_analysis_api() -> None:
    from spmkit.core.analysis import (
        estimate_sphere_revolution_background as public_estimate,
    )
    from spmkit.core.analysis import (
        remove_sphere_revolution_background as public_remove,
    )

    assert public_estimate is estimate_sphere_revolution_background
    assert public_remove is remove_sphere_revolution_background
