"""Structured background-result contracts."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from spmkit.core.analysis import (
    BackgroundResult,
    analyze_arc_revolution_background,
    analyze_median_background,
    analyze_rolling_ball_background,
    analyze_sphere_revolution_background,
)
from spmkit.core.analysis.background import (
    estimate_arc_revolution_background,
    estimate_median_background,
    estimate_sphere_revolution_background,
    remove_arc_revolution_background,
    remove_median_background,
    remove_sphere_revolution_background,
)
from spmkit.core.models import SPMChannel


def _channel() -> SPMChannel:
    data = (
        np.array(
            [
                [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
                [1.0, 2.0, 5.0, 4.0, 5.0, 6.0],
                [2.0, 4.0, 8.0, 7.0, 6.0, 7.0],
                [3.0, 4.0, 7.0, 6.0, 5.0, 8.0],
                [4.0, 5.0, 6.0, 7.0, 8.0, 9.0],
            ],
            dtype=float,
        )
        * 1e-9
    )

    return SPMChannel(
        name="Topography",
        data=data,
        unit="m",
        x_range=6e-6,
        y_range=5e-6,
        direction="forward",
        group="Scan",
        metadata={"source": "synthetic"},
    )


def test_arc_result_matches_existing_public_functions() -> None:
    channel = _channel()
    radius = 5e-6

    result = analyze_arc_revolution_background(
        channel,
        radius,
        direction="both",
        side="below",
        border="nearest",
    )

    expected_background = estimate_arc_revolution_background(
        channel,
        radius,
        direction="both",
        side="below",
        border="nearest",
    )
    expected_corrected = remove_arc_revolution_background(
        channel,
        radius,
        direction="both",
        side="below",
        border="nearest",
    )

    assert isinstance(result, BackgroundResult)
    assert result.method == "arc_revolution"
    assert result.parameters == {
        "radius": radius,
        "direction": "both",
        "side": "below",
        "border": "nearest",
    }
    assert np.array_equal(
        result.background.data,
        expected_background.data,
    )
    assert np.array_equal(
        result.corrected.data,
        expected_corrected.data,
    )


def test_sphere_result_matches_existing_public_functions() -> None:
    channel = _channel()
    radius = 5e-6

    result = analyze_sphere_revolution_background(
        channel,
        radius,
        side="below",
        border="nearest",
    )

    expected_background = estimate_sphere_revolution_background(
        channel,
        radius,
        side="below",
        border="nearest",
    )
    expected_corrected = remove_sphere_revolution_background(
        channel,
        radius,
        side="below",
        border="nearest",
    )

    assert result.method == "sphere_revolution"
    assert result.parameters == {
        "radius": radius,
        "side": "below",
        "border": "nearest",
    }
    assert np.array_equal(
        result.background.data,
        expected_background.data,
    )
    assert np.array_equal(
        result.corrected.data,
        expected_corrected.data,
    )


def test_median_result_matches_existing_public_functions() -> None:
    channel = _channel()

    result = analyze_median_background(
        channel,
        radius_pixels=2,
    )

    expected_background = estimate_median_background(
        channel,
        radius_pixels=2,
    )
    expected_corrected = remove_median_background(
        channel,
        radius_pixels=2,
    )

    assert result.method == "median"
    assert result.parameters == {
        "radius_pixels": 2,
        "border": "nearest",
    }
    assert np.array_equal(
        result.background.data,
        expected_background.data,
    )
    assert np.array_equal(
        result.corrected.data,
        expected_corrected.data,
    )


@pytest.mark.parametrize(
    "analyzer",
    [
        lambda channel: analyze_arc_revolution_background(
            channel,
            5e-6,
        ),
        lambda channel: analyze_sphere_revolution_background(
            channel,
            5e-6,
        ),
        lambda channel: analyze_rolling_ball_background(
            channel,
            5e-6,
        ),
        lambda channel: analyze_median_background(
            channel,
            2,
        ),
    ],
)
def test_result_channels_preserve_context(analyzer) -> None:
    channel = _channel()
    result = analyzer(channel)

    for output in (result.background, result.corrected):
        assert output.name == channel.name
        assert output.unit == channel.unit
        assert output.x_range == channel.x_range
        assert output.y_range == channel.y_range
        assert output.direction == channel.direction
        assert output.group == channel.group
        assert output.metadata == channel.metadata
        assert output.metadata is not channel.metadata


def test_background_result_is_frozen() -> None:
    result = analyze_median_background(
        _channel(),
        radius_pixels=1,
    )

    with pytest.raises(FrozenInstanceError):
        result.method = "arc_revolution"  # type: ignore[misc]


def test_to_dict_is_json_serializable() -> None:
    result = analyze_median_background(
        _channel(),
        radius_pixels=1,
    )

    payload = result.to_dict()

    assert payload["method"] == "median"
    assert payload["parameters"] == {
        "radius_pixels": 1,
        "border": "nearest",
    }

    background = payload["background"]
    corrected = payload["corrected"]

    assert isinstance(background, dict)
    assert isinstance(corrected, dict)
    assert background["shape"] == [5, 6]
    assert corrected["shape"] == [5, 6]
    assert isinstance(background["data"], list)
    assert isinstance(corrected["data"], list)

    json.dumps(payload)


def test_structured_background_api_is_public() -> None:
    from spmkit.core import analysis

    assert analysis.BackgroundResult is BackgroundResult
    assert analysis.analyze_arc_revolution_background is analyze_arc_revolution_background
    assert analysis.analyze_sphere_revolution_background is analyze_sphere_revolution_background
    assert analysis.analyze_rolling_ball_background is analyze_rolling_ball_background
    assert analysis.analyze_median_background is analyze_median_background
