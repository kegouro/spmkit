"""Tests for physical arc-revolution background estimation."""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis.background import (
    _arc_structure,
    estimate_arc_revolution_background,
    remove_arc_revolution_background,
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
        metadata={"source": "arc-test"},
    )


def _nearest_index(index: int, size: int) -> int:
    return min(max(index, 0), size - 1)


def _brute_force_below_nearest(
    profile: np.ndarray,
    *,
    radius: float,
    spacing: float,
) -> np.ndarray:
    """Independent one-dimensional rolling-circle oracle."""
    values = np.asarray(profile, dtype=float)
    maximum_offset = min(
        int(np.floor(radius / spacing)),
        values.size - 1,
    )

    offsets = np.arange(
        -maximum_offset,
        maximum_offset + 1,
        dtype=int,
    )
    distances = offsets.astype(float) * spacing
    sagitta = radius - np.sqrt(np.maximum(radius**2 - distances**2, 0.0))

    eroded = np.empty_like(values)

    for center in range(values.size):
        candidates = [
            values[_nearest_index(center + offset, values.size)] + sag
            for offset, sag in zip(offsets, sagitta, strict=True)
        ]
        eroded[center] = min(candidates)

    opened = np.empty_like(values)

    for position in range(values.size):
        candidates = [
            eroded[_nearest_index(position - offset, values.size)] - sag
            for offset, sag in zip(offsets, sagitta, strict=True)
        ]
        opened[position] = max(candidates)

    return opened


def test_flat_surface_is_preserved() -> None:
    data = np.full((5, 7), 3.25)
    channel = _channel(data)

    background = estimate_arc_revolution_background(
        channel,
        radius=3.0,
    )
    corrected = remove_arc_revolution_background(
        channel,
        radius=3.0,
    )

    assert np.allclose(background.data, data)
    assert np.allclose(corrected.data, 0.0)


def test_horizontal_matches_independent_one_dimensional_oracle() -> None:
    profile = np.array([0.0, 0.2, 1.8, 0.5, 0.1, 0.0])
    data = np.vstack([profile, profile + 2.0])
    channel = _channel(
        data,
        x_range=float(profile.size),
        y_range=2.0,
    )

    result = estimate_arc_revolution_background(
        channel,
        radius=2.5,
        direction="horizontal",
        border="nearest",
    )

    expected_first = _brute_force_below_nearest(
        profile,
        radius=2.5,
        spacing=1.0,
    )

    assert np.allclose(result.data[0], expected_first)
    assert np.allclose(result.data[1], expected_first + 2.0)


def test_above_is_exact_inversion_dual() -> None:
    data = np.array(
        [
            [0.0, -0.2, -1.5, -0.3, 0.0],
            [0.1, -0.1, -1.0, -0.2, 0.2],
        ]
    )
    channel = _channel(data)
    inverted = channel.with_data(-data)

    above = estimate_arc_revolution_background(
        channel,
        radius=2.0,
        direction="horizontal",
        side="above",
    )
    below_inverted = estimate_arc_revolution_background(
        inverted,
        radius=2.0,
        direction="horizontal",
        side="below",
    )

    assert np.allclose(above.data, -below_inverted.data)


def test_reconstruction_identity() -> None:
    yy, xx = np.mgrid[0:7, 0:9]
    data = 0.02 * xx + 0.03 * yy + 2.0 * np.exp(-((xx - 4) ** 2 + (yy - 3) ** 2) / 2.0)
    channel = _channel(
        data,
        x_range=9e-6,
        y_range=14e-6,
    )

    background = estimate_arc_revolution_background(
        channel,
        radius=4e-6,
        direction="both",
    )
    corrected = remove_arc_revolution_background(
        channel,
        radius=4e-6,
        direction="both",
    )

    assert np.allclose(
        corrected.data + background.data,
        data,
        rtol=1e-12,
        atol=1e-12,
    )


def test_radius_smaller_than_pixel_spacing_is_identity() -> None:
    data = np.arange(12.0).reshape(3, 4)
    channel = _channel(
        data,
        x_range=4.0,
        y_range=3.0,
    )

    background = estimate_arc_revolution_background(
        channel,
        radius=0.5,
        direction="both",
    )

    assert np.array_equal(background.data, data)


@pytest.mark.parametrize("radius", [0.0, -1.0, np.nan, np.inf])
def test_invalid_radius_is_rejected(radius: float) -> None:
    channel = _channel(np.ones((2, 2)))

    with pytest.raises((TypeError, ValueError)):
        estimate_arc_revolution_background(
            channel,
            radius=radius,
        )


def test_vertical_matches_independent_one_dimensional_oracle() -> None:
    profile = np.array([0.0, 0.3, 1.7, 0.4, 0.1, 0.0])
    data = np.column_stack((profile, profile + 1.5))
    channel = _channel(
        data,
        x_range=2.0,
        y_range=float(profile.size),
    )

    result = estimate_arc_revolution_background(
        channel,
        radius=2.5,
        direction="vertical",
        border="nearest",
    )

    expected_first = _brute_force_below_nearest(
        profile,
        radius=2.5,
        spacing=1.0,
    )

    assert np.allclose(result.data[:, 0], expected_first)
    assert np.allclose(result.data[:, 1], expected_first + 1.5)


def test_both_is_horizontal_followed_by_vertical() -> None:
    data = np.array(
        [
            [0.0, 0.2, 0.0, 0.1, 0.0],
            [0.3, 1.0, 2.5, 0.8, 0.2],
            [0.0, 0.5, 4.0, 0.4, 0.0],
            [0.2, 0.9, 2.0, 0.7, 0.1],
            [0.0, 0.1, 0.0, 0.2, 0.0],
        ]
    )
    channel = _channel(
        data,
        x_range=5.0,
        y_range=7.5,
    )

    horizontal = estimate_arc_revolution_background(
        channel,
        radius=2.5,
        direction="horizontal",
    )
    sequential = estimate_arc_revolution_background(
        horizontal,
        radius=2.5,
        direction="vertical",
    )
    combined = estimate_arc_revolution_background(
        channel,
        radius=2.5,
        direction="both",
    )

    assert np.allclose(combined.data, sequential.data)


def test_positive_protrusion_is_retained_in_residual() -> None:
    yy, xx = np.mgrid[0:9, 0:11]
    data = 0.05 * xx + 0.03 * yy
    data = data + 3.0 * np.exp(-((xx - 5) ** 2 + (yy - 4) ** 2) / 1.5)
    channel = _channel(
        data,
        x_range=11.0,
        y_range=9.0,
    )

    background = estimate_arc_revolution_background(
        channel,
        radius=3.0,
        direction="both",
        side="below",
    )
    corrected = remove_arc_revolution_background(
        channel,
        radius=3.0,
        direction="both",
        side="below",
    )

    assert np.all(background.data <= data + 1e-12)
    assert corrected.data[4, 5] > corrected.data[0, 0]
    assert np.allclose(corrected.data + background.data, data)


def test_above_background_does_not_fall_below_surface() -> None:
    yy, xx = np.mgrid[0:7, 0:9]
    data = -2.0 * np.exp(-((xx - 4) ** 2 + (yy - 3) ** 2) / 1.5)
    channel = _channel(
        data,
        x_range=9.0,
        y_range=7.0,
    )

    background = estimate_arc_revolution_background(
        channel,
        radius=3.0,
        side="above",
    )
    corrected = remove_arc_revolution_background(
        channel,
        radius=3.0,
        side="above",
    )

    assert np.all(background.data >= data - 1e-12)
    assert np.allclose(corrected.data + background.data, data)


def test_anisotropic_pixel_spacing_changes_axis_response() -> None:
    data = np.zeros((5, 5))
    data[2, 2] = 4.0
    channel = _channel(
        data,
        x_range=5.0,
        y_range=10.0,
    )

    horizontal = estimate_arc_revolution_background(
        channel,
        radius=1.5,
        direction="horizontal",
    )
    vertical = estimate_arc_revolution_background(
        channel,
        radius=1.5,
        direction="vertical",
    )

    # dx = 1 while dy = 2. The horizontal structure spans neighbours,
    # whereas the vertical structure contains only its central sample.
    assert horizontal.data[2, 2] < data[2, 2]
    assert np.array_equal(vertical.data, data)


def test_lateral_range_controls_discrete_physical_structure() -> None:
    data = np.array([[0.0, 0.0, 4.0, 0.0, 0.0]])

    fine = _channel(
        data,
        x_range=5.0,
        y_range=1.0,
    )
    coarse = _channel(
        data,
        x_range=10.0,
        y_range=1.0,
    )

    fine_background = estimate_arc_revolution_background(
        fine,
        radius=1.5,
        direction="horizontal",
    )
    coarse_background = estimate_arc_revolution_background(
        coarse,
        radius=1.5,
        direction="horizontal",
    )

    assert fine_background.data[0, 2] < data[0, 2]
    assert np.array_equal(coarse_background.data, data)


def test_equivalent_metres_and_nanometres_agree_physically() -> None:
    data_metres = (
        np.array(
            [
                [0.0, 0.2, 1.5, 0.2, 0.0],
                [0.1, 0.4, 2.0, 0.3, 0.1],
                [0.0, 0.2, 1.2, 0.2, 0.0],
            ]
        )
        * 1e-9
    )

    channel_metres = _channel(
        data_metres,
        unit="m",
        x_range=5e-6,
        y_range=3e-6,
    )
    channel_nanometres = _channel(
        data_metres * 1e9,
        unit="nm",
        x_range=5e-6,
        y_range=3e-6,
    )

    background_metres = estimate_arc_revolution_background(
        channel_metres,
        radius=2.5e-6,
    )
    background_nanometres = estimate_arc_revolution_background(
        channel_nanometres,
        radius=2.5e-6,
    )

    assert np.allclose(
        background_metres.data,
        background_nanometres.data * 1e-9,
        rtol=1e-12,
        atol=1e-18,
    )


@pytest.mark.parametrize("border", ["nearest", "reflect"])
def test_supported_borders_preserve_reconstruction(border: str) -> None:
    data = np.array(
        [
            [0.0, 0.5, 2.0, 0.2],
            [0.1, 1.0, 3.0, 0.4],
            [0.0, 0.3, 1.5, 0.1],
        ]
    )
    channel = _channel(data)

    background = estimate_arc_revolution_background(
        channel,
        radius=2.0,
        border=border,
    )
    corrected = remove_arc_revolution_background(
        channel,
        radius=2.0,
        border=border,
    )

    assert np.all(np.isfinite(background.data))
    assert np.allclose(corrected.data + background.data, data)


@pytest.mark.parametrize(
    "data",
    [
        np.array([[7.0]]),
        np.array([[0.0, 1.0, 3.0, 1.0, 0.0]]),
        np.array([[0.0], [1.0], [3.0], [1.0], [0.0]]),
    ],
    ids=["one-by-one", "one-by-n", "n-by-one"],
)
def test_degenerate_dimensions_are_defined(data: np.ndarray) -> None:
    channel = _channel(data)

    background = estimate_arc_revolution_background(
        channel,
        radius=2.0,
    )
    corrected = remove_arc_revolution_background(
        channel,
        radius=2.0,
    )

    assert background.shape == data.shape
    assert corrected.shape == data.shape
    assert np.all(np.isfinite(background.data))
    assert np.allclose(corrected.data + background.data, data)

    if data.shape == (1, 1):
        assert np.array_equal(background.data, data)
        assert np.array_equal(corrected.data, np.zeros_like(data))


def test_radius_larger_than_domain_is_supported() -> None:
    data = np.array(
        [
            [0.0, 1.0, 3.0, 1.0],
            [0.2, 1.5, 4.0, 0.5],
            [0.0, 0.8, 2.0, 0.0],
        ]
    )
    channel = _channel(
        data,
        x_range=4.0,
        y_range=3.0,
    )

    background = estimate_arc_revolution_background(
        channel,
        radius=100.0,
        border="reflect",
    )
    corrected = remove_arc_revolution_background(
        channel,
        radius=100.0,
        border="reflect",
    )

    assert background.shape == data.shape
    assert np.all(np.isfinite(background.data))
    assert np.allclose(corrected.data + background.data, data)


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("direction", "diagonal"),
        ("side", "inside"),
        ("border", "constant"),
    ],
)
def test_invalid_public_options_are_rejected(
    parameter: str,
    value: str,
) -> None:
    channel = _channel(np.ones((2, 3)))
    kwargs = {parameter: value}

    with pytest.raises(ValueError):
        estimate_arc_revolution_background(
            channel,
            radius=1.0,
            **kwargs,
        )


@pytest.mark.parametrize(
    "data",
    [
        np.array([[0.0, np.nan], [1.0, 2.0]]),
        np.array([[0.0, np.inf], [1.0, 2.0]]),
    ],
    ids=["nan", "infinity"],
)
def test_nonfinite_data_are_rejected(data: np.ndarray) -> None:
    channel = _channel(data)

    with pytest.raises(
        ValueError,
        match="requires finite data",
    ):
        estimate_arc_revolution_background(
            channel,
            radius=1.0,
        )


def test_non_geometric_z_unit_is_rejected() -> None:
    channel = _channel(
        np.ones((3, 4)),
        unit="V",
    )

    with pytest.raises(
        ValueError,
        match="unsupported geometric length unit",
    ):
        estimate_arc_revolution_background(
            channel,
            radius=1.0,
        )


@pytest.mark.parametrize(
    "radius",
    [
        True,
        "1.0",
        [1.0],
        1.0 + 2.0j,
    ],
    ids=["boolean", "string", "array", "complex"],
)
def test_non_real_scalar_radius_is_rejected(radius: object) -> None:
    channel = _channel(np.ones((2, 2)))

    with pytest.raises(TypeError):
        estimate_arc_revolution_background(
            channel,
            radius=radius,
        )


def test_input_is_not_mutated_and_context_is_preserved() -> None:
    data = np.array(
        [
            [0.0, 0.5, 2.0],
            [0.2, 1.0, 3.0],
        ]
    )
    channel = _channel(
        data,
        unit="nm",
        x_range=3e-6,
        y_range=2e-6,
    )
    original_data = channel.data.copy()
    original_metadata = dict(channel.metadata)

    background = estimate_arc_revolution_background(
        channel,
        radius=2e-6,
    )
    corrected = remove_arc_revolution_background(
        channel,
        radius=2e-6,
    )

    assert np.array_equal(channel.data, original_data)
    assert channel.metadata == original_metadata

    for result in (background, corrected):
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
    ("data", "error_type", "message"),
    [
        (
            np.array([0.0, 1.0, 2.0]),
            ValueError,
            "requires a 2D channel",
        ),
        (
            np.empty((0, 3)),
            ValueError,
            "requires non-empty data",
        ),
        (
            np.array([["a", "b"], ["c", "d"]]),
            TypeError,
            "requires real numeric data",
        ),
        (
            np.array(
                [
                    [1.0 + 0.0j, 2.0 + 1.0j],
                    [3.0 + 0.0j, 4.0 + 0.0j],
                ]
            ),
            TypeError,
            "requires real numeric data",
        ),
    ],
    ids=[
        "one-dimensional",
        "empty",
        "non-numeric",
        "complex",
    ],
)
def test_invalid_channel_data_are_rejected(
    data: np.ndarray,
    error_type: type[Exception],
    message: str,
) -> None:
    channel = SPMChannel(
        name="Z-Axis",
        data=data,
        unit="m",
        x_range=2.0,
        y_range=2.0,
    )

    with pytest.raises(error_type, match=message):
        estimate_arc_revolution_background(
            channel,
            radius=1.0,
        )


@pytest.mark.parametrize(
    ("x_range", "y_range", "message"),
    [
        (0.0, 2.0, "positive lateral pixel spacing"),
        (-1.0, 2.0, "positive lateral pixel spacing"),
        (np.inf, 2.0, "finite lateral pixel spacing"),
        (2.0, 0.0, "positive lateral pixel spacing"),
        (2.0, -1.0, "positive lateral pixel spacing"),
        (2.0, np.inf, "finite lateral pixel spacing"),
    ],
)
def test_invalid_lateral_geometry_is_rejected(
    x_range: float,
    y_range: float,
    message: str,
) -> None:
    channel = _channel(
        np.ones((2, 3)),
        x_range=x_range,
        y_range=y_range,
    )

    with pytest.raises(ValueError, match=message):
        estimate_arc_revolution_background(
            channel,
            radius=1.0,
        )


@pytest.mark.parametrize(
    "direction",
    ["horizontal", "vertical", "both"],
)
@pytest.mark.parametrize(
    "side",
    ["below", "above"],
)
def test_reconstruction_identity_for_every_mode(
    direction: str,
    side: str,
) -> None:
    data = np.array(
        [
            [0.0, 0.2, 1.0, 0.1],
            [0.3, 1.4, 3.0, 0.4],
            [0.1, 0.5, 1.8, 0.2],
        ]
    )
    channel = _channel(
        data,
        x_range=4.0,
        y_range=3.0,
    )

    background = estimate_arc_revolution_background(
        channel,
        radius=2.0,
        direction=direction,
        side=side,
    )
    corrected = remove_arc_revolution_background(
        channel,
        radius=2.0,
        direction=direction,
        side=side,
    )

    assert np.allclose(
        corrected.data + background.data,
        data,
        rtol=1e-13,
        atol=1e-13,
    )


def test_functions_are_available_from_public_analysis_api() -> None:
    from spmkit.core.analysis import (
        estimate_arc_revolution_background as public_estimate,
    )
    from spmkit.core.analysis import (
        remove_arc_revolution_background as public_remove,
    )

    assert public_estimate is estimate_arc_revolution_background
    assert public_remove is remove_arc_revolution_background


def test_arc_structure_preserves_small_sagitta_for_large_radius() -> None:
    structure = _arc_structure(
        radius=1e12,
        spacing=1.0,
        sample_count=3,
    )

    expected = np.array(
        [
            -2e-12,
            -5e-13,
            0.0,
            -5e-13,
            -2e-12,
        ]
    )

    assert structure.shape == (5,)
    assert np.allclose(
        structure,
        expected,
        rtol=1e-12,
        atol=0.0,
    )
