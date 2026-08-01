"""Tests for circular local-median background estimation."""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis.background import (
    _median_disk_footprint,
    estimate_median_background,
    remove_median_background,
)
from spmkit.core.models import SPMChannel


def _channel(
    data: np.ndarray,
    *,
    unit: str = "nm",
    x_range: float | None = None,
    y_range: float | None = None,
) -> SPMChannel:
    rows, columns = data.shape

    return SPMChannel(
        name="Signal",
        data=np.asarray(data),
        unit=unit,
        x_range=float(columns) if x_range is None else x_range,
        y_range=float(rows) if y_range is None else y_range,
        direction="forward",
        group="Synthetic",
        metadata={"source": "median-background-test"},
    )


def _disk_offsets(
    radius_pixels: int,
) -> list[tuple[int, int]]:
    """Independent pixel-centre ellipse oracle."""
    diameter = 2 * radius_pixels + 1

    return [
        (row_offset, column_offset)
        for row_offset in range(
            -radius_pixels,
            radius_pixels + 1,
        )
        for column_offset in range(
            -radius_pixels,
            radius_pixels + 1,
        )
        if (2 * row_offset) ** 2 + (2 * column_offset) ** 2 <= diameter**2
    ]


def _nearest_index(index: int, size: int) -> int:
    """Map an index using nearest boundary extension."""
    return min(max(index, 0), size - 1)


def _brute_force_border_extend_median(
    data: np.ndarray,
    *,
    radius_pixels: int,
) -> np.ndarray:
    """Independent circular-median oracle with extended borders."""
    values = np.asarray(data, dtype=float)
    rows, columns = values.shape
    offsets = _disk_offsets(radius_pixels)
    result = np.empty_like(values)

    for row in range(rows):
        for column in range(columns):
            neighbourhood = [
                values[
                    _nearest_index(row + y_offset, rows),
                    _nearest_index(column + x_offset, columns),
                ]
                for y_offset, x_offset in offsets
            ]

            result[row, column] = float(np.median(neighbourhood))

    return result


def test_radius_one_uses_full_three_by_three_ellipse() -> None:
    footprint = _median_disk_footprint(1)

    assert np.array_equal(
        footprint,
        np.ones((3, 3), dtype=bool),
    )

    data = np.array(
        [
            [100.0, 0.0, 100.0],
            [0.0, 1.0, 0.0],
            [100.0, 0.0, 100.0],
        ]
    )

    result = estimate_median_background(
        _channel(data),
        radius_pixels=1,
    )

    # A radius-one Euclidean-centre disk would be a five-pixel cross
    # and would return zero here.  Gwyddion's 3×3 ellipse returns one.
    assert result.data[1, 1] == 1.0


def test_border_uses_nearest_extension() -> None:
    data = np.array(
        [
            [0.0, 10.0],
            [20.0, 30.0],
        ]
    )
    channel = _channel(data)

    result = estimate_median_background(
        channel,
        radius_pixels=1,
    )
    expected = _brute_force_border_extend_median(
        data,
        radius_pixels=1,
    )

    assert np.array_equal(result.data, expected)

    # Gwyddion radius one is a full 3×3 elliptic kernel.  Nearest
    # extension produces four zeroes, two tens, two twenties and 30,
    # so the middle value is 10.
    assert result.data[0, 0] == 10.0


def test_matches_independent_border_extend_oracle() -> None:
    data = np.array(
        [
            [8.0, 1.0, 7.0, 2.0],
            [3.0, 9.0, 0.0, 6.0],
            [5.0, 4.0, 2.0, 1.0],
        ]
    )
    channel = _channel(data)

    result = estimate_median_background(
        channel,
        radius_pixels=2,
    )
    expected = _brute_force_border_extend_median(
        data,
        radius_pixels=2,
    )

    assert np.allclose(
        result.data,
        expected,
        rtol=0.0,
        atol=0.0,
    )


def test_flat_surface_is_preserved() -> None:
    data = np.full((5, 7), 3.25)
    channel = _channel(data)

    background = estimate_median_background(
        channel,
        radius_pixels=2,
    )
    corrected = remove_median_background(
        channel,
        radius_pixels=2,
    )

    assert np.array_equal(background.data, data)
    assert np.array_equal(corrected.data, np.zeros_like(data))


def test_reconstruction_identity() -> None:
    data = np.array(
        [
            [0.0, 0.2, 1.0, 0.1],
            [0.3, 1.5, 3.0, 0.4],
            [0.1, 0.6, 1.8, 0.2],
        ]
    )
    channel = _channel(data)

    background = estimate_median_background(
        channel,
        radius_pixels=2,
    )
    corrected = remove_median_background(
        channel,
        radius_pixels=2,
    )

    assert np.allclose(
        corrected.data + background.data,
        data,
        rtol=1e-13,
        atol=1e-13,
    )


def test_non_geometric_scalar_unit_is_supported() -> None:
    data = np.array(
        [
            [0.1, 0.5, 0.2],
            [0.7, 4.0, 0.3],
        ]
    )
    channel = _channel(
        data,
        unit="V",
    )

    result = estimate_median_background(
        channel,
        radius_pixels=1,
    )

    assert result.unit == "V"
    assert np.all(np.isfinite(result.data))


def test_input_is_not_mutated_and_context_is_preserved() -> None:
    data = np.array(
        [
            [0.0, 0.2, 1.0],
            [0.3, 1.5, 0.4],
        ]
    )
    original = data.copy()
    channel = _channel(data)

    background = estimate_median_background(
        channel,
        radius_pixels=1,
    )
    corrected = remove_median_background(
        channel,
        radius_pixels=1,
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
    "radius_pixels",
    [
        0,
        -1,
        -20,
    ],
)
def test_nonpositive_radius_is_rejected(
    radius_pixels: int,
) -> None:
    channel = _channel(np.ones((3, 4)))

    with pytest.raises(
        ValueError,
        match="radius_pixels to be positive",
    ):
        estimate_median_background(
            channel,
            radius_pixels=radius_pixels,
        )


@pytest.mark.parametrize(
    "radius_pixels",
    [
        True,
        None,
        1.0,
        "2",
        [2],
    ],
)
def test_non_integer_radius_is_rejected(
    radius_pixels: object,
) -> None:
    channel = _channel(np.ones((3, 4)))

    with pytest.raises(
        TypeError,
        match="radius_pixels to be a positive integer",
    ):
        estimate_median_background(
            channel,
            radius_pixels=radius_pixels,
        )


@pytest.mark.parametrize(
    "nonfinite",
    [
        np.nan,
        np.inf,
        -np.inf,
    ],
)
def test_nonfinite_data_are_rejected(
    nonfinite: float,
) -> None:
    data = np.ones((3, 4))
    data[1, 2] = nonfinite
    channel = _channel(data)

    with pytest.raises(
        ValueError,
        match="requires finite data",
    ):
        estimate_median_background(
            channel,
            radius_pixels=1,
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
def test_invalid_channel_data_are_rejected(
    data: np.ndarray,
) -> None:
    channel = SPMChannel(
        name="invalid",
        data=data,
        unit="nm",
        x_range=3.0,
        y_range=2.0,
    )

    with pytest.raises((TypeError, ValueError)):
        estimate_median_background(
            channel,
            radius_pixels=1,
        )


def test_radius_above_gwyddion_limit_is_rejected_before_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from spmkit.core.analysis import background as background_module

    def fail_if_allocated(
        radius_pixels: int,
    ) -> np.ndarray:
        raise AssertionError(f"footprint was allocated for radius {radius_pixels}")

    monkeypatch.setattr(
        background_module,
        "_median_disk_footprint",
        fail_if_allocated,
    )

    with pytest.raises(
        ValueError,
        match=r"\[1, 1024\]",
    ):
        background_module.estimate_median_background(
            _channel(np.ones((2, 3), dtype=float)),
            radius_pixels=10_000,
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
def test_degenerate_dimensions_are_defined(
    data: np.ndarray,
) -> None:
    channel = _channel(data)

    background = estimate_median_background(
        channel,
        radius_pixels=1,
    )
    corrected = remove_median_background(
        channel,
        radius_pixels=1,
    )

    assert background.data.shape == data.shape
    assert corrected.data.shape == data.shape
    assert np.all(np.isfinite(background.data))
    assert np.allclose(
        corrected.data + background.data,
        data,
    )


@pytest.mark.parametrize(
    ("radius_pixels", "expected_count"),
    [
        (1, 9),
        (2, 21),
        (3, 37),
        (4, 69),
        (5, 97),
        (6, 137),
        (7, 177),
        (8, 225),
    ],
)
def test_footprint_counts_match_gwyddion_271(
    radius_pixels: int,
    expected_count: int,
) -> None:
    footprint = _median_disk_footprint(radius_pixels)

    assert int(np.count_nonzero(footprint)) == expected_count


def test_radius_two_matches_frozen_gwyddion_mask() -> None:
    expected = np.array(
        [
            [0, 1, 1, 1, 0],
            [1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1],
            [0, 1, 1, 1, 0],
        ],
        dtype=bool,
    )

    assert np.array_equal(
        _median_disk_footprint(2),
        expected,
    )


def test_median_background_functions_are_publicly_exported() -> None:
    from spmkit.core import analysis
    from spmkit.core.analysis.background import (
        estimate_median_background,
        remove_median_background,
    )

    assert analysis.estimate_median_background is estimate_median_background
    assert analysis.remove_median_background is remove_median_background
