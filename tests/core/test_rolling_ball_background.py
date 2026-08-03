"""Physical rolling-ball background estimation."""

from __future__ import annotations

from math import floor

import numpy as np
import pytest

from spmkit.core.analysis import (
    BackgroundResult,
    analyze_rolling_ball_background,
    estimate_rolling_ball_background,
    remove_rolling_ball_background,
)
from spmkit.core.models import SPMChannel


def _channel(
    data: np.ndarray,
    *,
    unit: str = "V",
    x_range: float | None = None,
    y_range: float | None = None,
) -> SPMChannel:
    rows, columns = data.shape

    return SPMChannel(
        name="Signal",
        data=np.asarray(data),
        unit=unit,
        x_range=(float(columns) if x_range is None else x_range),
        y_range=(float(rows) if y_range is None else y_range),
        direction="forward",
        group="Scan",
        metadata={"source": "synthetic"},
    )


def _oracle_below(
    data: np.ndarray,
    *,
    radius: float,
    vertical_radius: float,
    x_spacing: float,
    y_spacing: float,
) -> np.ndarray:
    """Independent direct evaluation of the apex-height formula."""
    image = np.asarray(data, dtype=float)
    rows, columns = image.shape

    x_offset = min(
        columns - 1,
        floor(radius / x_spacing),
    )
    y_offset = min(
        rows - 1,
        floor(radius / y_spacing),
    )

    output = np.empty_like(image)

    for row in range(rows):
        for column in range(columns):
            minimum = np.inf

            for dy in range(-y_offset, y_offset + 1):
                for dx in range(-x_offset, x_offset + 1):
                    source_row = row + dy
                    source_column = column + dx

                    if not (0 <= source_row < rows and 0 <= source_column < columns):
                        continue

                    squared_ratio = (dx * x_spacing / radius) ** 2 + (dy * y_spacing / radius) ** 2

                    if squared_ratio > 1.0:
                        continue

                    cost = vertical_radius * (1.0 - np.sqrt(1.0 - squared_ratio))

                    candidate = image[source_row, source_column] + cost
                    minimum = min(minimum, candidate)

            output[row, column] = minimum

    return output


@pytest.mark.parametrize("side", ["below", "above"])
def test_matches_independent_anisotropic_oracle(
    side: str,
) -> None:
    data = np.array(
        [
            [0.0, 1.0, 3.0, 8.0, 5.0, 4.0],
            [2.0, 4.0, 9.0, 7.0, 6.0, 3.0],
            [1.0, 5.0, 8.0, 4.0, 2.0, 1.0],
            [3.0, 6.0, 7.0, 5.0, 4.0, 2.0],
            [4.0, 5.0, 6.0, 8.0, 7.0, 3.0],
        ]
    )
    channel = _channel(
        data,
        x_range=6.0,
        y_range=10.0,
    )

    expected_below = _oracle_below(
        data,
        radius=2.5,
        vertical_radius=4.0,
        x_spacing=1.0,
        y_spacing=2.0,
    )
    expected = (
        expected_below
        if side == "below"
        else -_oracle_below(
            -data,
            radius=2.5,
            vertical_radius=4.0,
            x_spacing=1.0,
            y_spacing=2.0,
        )
    )

    observed = estimate_rolling_ball_background(
        channel,
        radius=2.5,
        vertical_radius=4.0,
        side=side,
    )

    np.testing.assert_allclose(
        observed.data,
        expected,
        rtol=1e-14,
        atol=1e-14,
    )


def test_reference_corner_case_ignores_exterior() -> None:
    channel = _channel(
        np.array(
            [
                [0.0, 10.0],
                [20.0, 30.0],
            ]
        )
    )

    background = estimate_rolling_ball_background(
        channel,
        radius=1.0,
        vertical_radius=1.0,
    )

    expected = np.array(
        [
            [0.0, 1.0],
            [1.0, 11.0],
        ]
    )

    assert np.array_equal(
        background.data,
        expected,
    )


def test_radius_smaller_than_pixel_spacing_is_identity() -> None:
    channel = _channel(
        np.arange(12, dtype=float).reshape(3, 4),
        x_range=8.0,
        y_range=6.0,
    )

    background = estimate_rolling_ball_background(
        channel,
        radius=0.5,
        vertical_radius=2.0,
    )

    assert np.array_equal(
        background.data,
        channel.data,
    )


def test_geometric_automatic_sphere_matches_explicit_native_radius() -> None:
    data_nm = np.array(
        [
            [0.0, 1.0, 4.0, 2.0],
            [1.0, 5.0, 8.0, 3.0],
            [2.0, 4.0, 6.0, 1.0],
        ]
    )
    channel = _channel(
        data_nm,
        unit="nm",
        x_range=4e-9,
        y_range=3e-9,
    )

    automatic = estimate_rolling_ball_background(
        channel,
        radius=2e-9,
    )
    explicit = estimate_rolling_ball_background(
        channel,
        radius=2e-9,
        vertical_radius=2.0,
    )

    np.testing.assert_allclose(
        automatic.data,
        explicit.data,
        rtol=1e-14,
        atol=1e-14,
    )


def test_non_geometric_unit_requires_vertical_radius() -> None:
    channel = _channel(
        np.ones((3, 4)),
        unit="V",
    )

    with pytest.raises(
        ValueError,
        match="unsupported geometric length unit",
    ):
        estimate_rolling_ball_background(
            channel,
            radius=1.0,
        )


@pytest.mark.parametrize(
    "vertical_radius",
    [
        0.0,
        -1.0,
        np.nan,
        np.inf,
        -np.inf,
    ],
)
def test_invalid_vertical_radius_value_is_rejected(
    vertical_radius: float,
) -> None:
    channel = _channel(np.ones((3, 4)))

    with pytest.raises(ValueError):
        estimate_rolling_ball_background(
            channel,
            radius=1.0,
            vertical_radius=vertical_radius,
        )


@pytest.mark.parametrize(
    "vertical_radius",
    [
        True,
        "1.0",
        [1.0],
        1.0 + 0.0j,
    ],
)
def test_invalid_vertical_radius_type_is_rejected(
    vertical_radius: object,
) -> None:
    channel = _channel(np.ones((3, 4)))

    with pytest.raises(TypeError):
        estimate_rolling_ball_background(
            channel,
            radius=1.0,
            vertical_radius=vertical_radius,
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
def test_invalid_lateral_radius_value_is_rejected(
    radius: float,
) -> None:
    channel = _channel(np.ones((3, 4)))

    with pytest.raises(ValueError):
        estimate_rolling_ball_background(
            channel,
            radius=radius,
            vertical_radius=1.0,
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
def test_invalid_lateral_radius_type_is_rejected(
    radius: object,
) -> None:
    channel = _channel(np.ones((3, 4)))

    with pytest.raises(TypeError):
        estimate_rolling_ball_background(
            channel,
            radius=radius,
            vertical_radius=1.0,
        )


@pytest.mark.parametrize(
    "side",
    [
        "underneath",
        "nearest",
    ],
)
def test_invalid_side_value_is_rejected(
    side: str,
) -> None:
    channel = _channel(np.ones((3, 4)))

    with pytest.raises(ValueError):
        estimate_rolling_ball_background(
            channel,
            radius=1.0,
            vertical_radius=1.0,
            side=side,
        )


def test_non_string_side_is_rejected() -> None:
    channel = _channel(np.ones((3, 4)))

    with pytest.raises(
        TypeError,
        match="requires side to be a string",
    ):
        estimate_rolling_ball_background(
            channel,
            radius=1.0,
            vertical_radius=1.0,
            side=None,
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
        estimate_rolling_ball_background(
            channel,
            radius=1.0,
            vertical_radius=1.0,
        )


def test_remove_reconstructs_original_data() -> None:
    channel = _channel(
        np.array(
            [
                [0.0, 1.0, 5.0, 2.0],
                [2.0, 6.0, 9.0, 3.0],
                [1.0, 4.0, 7.0, 2.0],
            ]
        )
    )

    background = estimate_rolling_ball_background(
        channel,
        radius=2.0,
        vertical_radius=3.0,
    )
    corrected = remove_rolling_ball_background(
        channel,
        radius=2.0,
        vertical_radius=3.0,
    )

    assert np.array_equal(
        corrected.data + background.data,
        channel.data,
    )


def test_outputs_preserve_context_without_mutating_input() -> None:
    channel = _channel(
        np.arange(20, dtype=float).reshape(4, 5),
    )
    original = channel.data.copy()

    background = estimate_rolling_ball_background(
        channel,
        radius=2.0,
        vertical_radius=3.0,
    )
    corrected = remove_rolling_ball_background(
        channel,
        radius=2.0,
        vertical_radius=3.0,
    )

    assert np.array_equal(channel.data, original)

    for output in (background, corrected):
        assert output.name == channel.name
        assert output.unit == channel.unit
        assert output.x_range == channel.x_range
        assert output.y_range == channel.y_range
        assert output.direction == channel.direction
        assert output.group == channel.group
        assert output.metadata == channel.metadata
        assert output.metadata is not channel.metadata


def test_structured_result_matches_simple_functions() -> None:
    channel = _channel(
        np.arange(20, dtype=float).reshape(4, 5),
    )

    result = analyze_rolling_ball_background(
        channel,
        radius=2.0,
        vertical_radius=3.0,
        side="above",
    )

    expected_background = estimate_rolling_ball_background(
        channel,
        radius=2.0,
        vertical_radius=3.0,
        side="above",
    )
    expected_corrected = remove_rolling_ball_background(
        channel,
        radius=2.0,
        vertical_radius=3.0,
        side="above",
    )

    assert isinstance(result, BackgroundResult)
    assert result.method == "rolling_ball"
    assert result.parameters == {
        "radius": 2.0,
        "vertical_radius": 3.0,
        "side": "above",
        "boundary": "ignore",
    }
    assert np.array_equal(
        result.background.data,
        expected_background.data,
    )
    assert np.array_equal(
        result.corrected.data,
        expected_corrected.data,
    )


def test_geometric_structured_result_records_automatic_mode() -> None:
    channel = _channel(
        np.arange(12, dtype=float).reshape(3, 4),
        unit="nm",
        x_range=4e-9,
        y_range=3e-9,
    )

    result = analyze_rolling_ball_background(
        channel,
        radius=2e-9,
    )

    assert result.parameters == {
        "radius": 2e-9,
        "vertical_radius": None,
        "side": "below",
        "boundary": "ignore",
    }


def test_rolling_ball_api_is_public() -> None:
    from spmkit.core import analysis
    from spmkit.core.analysis.background import (
        analyze_rolling_ball_background as module_analyze,
    )
    from spmkit.core.analysis.background import (
        estimate_rolling_ball_background as module_estimate,
    )
    from spmkit.core.analysis.background import (
        remove_rolling_ball_background as module_remove,
    )

    assert analysis.analyze_rolling_ball_background is module_analyze
    assert analysis.estimate_rolling_ball_background is module_estimate
    assert analysis.remove_rolling_ball_background is module_remove
