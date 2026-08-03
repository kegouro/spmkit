"""Public-contract tests for Gwyddion-compatible Revolve Arc."""

from __future__ import annotations

import inspect
from typing import get_args

import numpy as np
import pytest

import spmkit.core.analysis as analysis
import spmkit.core.analysis.background as background_module
from spmkit.core.analysis import (
    BackgroundResult,
    GwyddionArcDirection,
    analyze_gwyddion_arc_revolution_background,
    estimate_gwyddion_arc_revolution_background,
    remove_gwyddion_arc_revolution_background,
)
from spmkit.core.analysis._gwyddion_arc_revolution import (
    _gwyddion_arc_result,
)
from spmkit.core.models import SPMChannel

_ROUTES = [
    ("horizontal", False),
    ("horizontal", True),
    ("vertical", False),
    ("vertical", True),
    ("both", False),
    ("both", True),
]


def _field() -> np.ndarray:
    return np.array(
        [
            [2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5],
            [1.5, 1.75, 2.0, 2.25, 6.0, 2.75, 3.0],
            [1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5],
            [0.5, 0.75, 1.0, -2.0, 1.5, 1.75, 2.0],
            [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5],
        ],
        dtype=np.float64,
    )


def _channel(
    data: np.ndarray | None = None,
    *,
    unit: str = "V",
    x_range: float = 8.0e-6,
    y_range: float = 5.0e-6,
) -> SPMChannel:
    return SPMChannel(
        name="Synthetic CPD",
        data=_field() if data is None else data,
        unit=unit,
        x_range=x_range,
        y_range=y_range,
        direction="backward",
        group="Validation group",
        metadata={
            "source": "frozen synthetic contract",
            "operator": "public-adapter-test",
        },
    )


def _assert_context_preserved(
    source: SPMChannel,
    result: SPMChannel,
) -> None:
    assert result.name == source.name
    assert result.unit == source.unit
    assert result.x_range == source.x_range
    assert result.y_range == source.y_range
    assert result.direction == source.direction
    assert result.group == source.group
    assert result.metadata == source.metadata
    assert result.metadata is not source.metadata


def _assert_array_contract(data: np.ndarray) -> None:
    assert data.dtype == np.float64
    assert data.flags.c_contiguous
    assert not data.flags.writeable


def _roundoff_bound(expected: np.ndarray) -> float:
    scale = max(
        1.0,
        float(np.max(np.abs(expected))),
    )
    return 512.0 * np.finfo(np.float64).eps * scale


def test_public_exports_and_defaults_are_stable() -> None:
    expected_names = {
        "GwyddionArcDirection",
        "estimate_gwyddion_arc_revolution_background",
        "remove_gwyddion_arc_revolution_background",
        "analyze_gwyddion_arc_revolution_background",
    }

    assert expected_names <= set(analysis.__all__)

    for name in expected_names:
        assert getattr(analysis, name) is not None

    assert set(get_args(GwyddionArcDirection)) == {
        "horizontal",
        "vertical",
        "both",
    }

    for function in (
        estimate_gwyddion_arc_revolution_background,
        remove_gwyddion_arc_revolution_background,
        analyze_gwyddion_arc_revolution_background,
    ):
        signature = inspect.signature(function)
        assert signature.parameters["radius_px"].default == 20.0
        assert signature.parameters["direction"].default == "horizontal"
        assert signature.parameters["inverted"].default is False


@pytest.mark.parametrize(("direction", "inverted"), _ROUTES)
def test_public_family_matches_authoritative_private_result(
    direction: str,
    inverted: bool,
) -> None:
    channel = _channel()
    original_data = channel.data.copy()
    original_metadata = dict(channel.metadata)

    expected_background, expected_corrected = _gwyddion_arc_result(
        channel.data,
        2.5,
        direction=direction,  # type: ignore[arg-type]
        inverted=inverted,
    )

    estimated = estimate_gwyddion_arc_revolution_background(
        channel,
        2.5,
        direction=direction,  # type: ignore[arg-type]
        inverted=inverted,
    )
    removed = remove_gwyddion_arc_revolution_background(
        channel,
        2.5,
        direction=direction,  # type: ignore[arg-type]
        inverted=inverted,
    )
    analyzed = analyze_gwyddion_arc_revolution_background(
        channel,
        2.5,
        direction=direction,  # type: ignore[arg-type]
        inverted=inverted,
    )

    assert isinstance(analyzed, BackgroundResult)

    np.testing.assert_array_equal(
        estimated.data,
        expected_background,
    )
    np.testing.assert_array_equal(
        removed.data,
        expected_corrected,
    )
    np.testing.assert_array_equal(
        analyzed.background.data,
        expected_background,
    )
    np.testing.assert_array_equal(
        analyzed.corrected.data,
        expected_corrected,
    )
    np.testing.assert_array_equal(
        analyzed.corrected.data + analyzed.background.data,
        channel.data,
    )

    assert analyzed.method == "gwyddion_arc_revolution"
    assert analyzed.parameters == {
        "radius_px": 2.5,
        "direction": direction,
        "inverted": inverted,
    }

    for result_channel in (
        estimated,
        removed,
        analyzed.background,
        analyzed.corrected,
    ):
        _assert_context_preserved(channel, result_channel)
        _assert_array_contract(result_channel.data)

    np.testing.assert_array_equal(channel.data, original_data)
    assert channel.metadata == original_metadata

    payload = analyzed.to_dict()
    assert payload["method"] == "gwyddion_arc_revolution"
    assert payload["parameters"] == analyzed.parameters
    assert payload["background"]["shape"] == [5, 7]  # type: ignore[index]
    assert payload["corrected"]["unit"] == "V"  # type: ignore[index]


def test_analyze_executes_single_authoritative_result_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = 0
    original = background_module._gwyddion_arc_result

    def counted_result(*args: object, **kwargs: object) -> object:
        nonlocal call_count
        call_count += 1
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        background_module,
        "_gwyddion_arc_result",
        counted_result,
    )

    result = analyze_gwyddion_arc_revolution_background(
        _channel(),
        2.5,
        direction="both",
        inverted=True,
    )

    assert isinstance(result, BackgroundResult)
    assert call_count == 1


@pytest.mark.parametrize(("direction", "inverted"), _ROUTES)
def test_metamorphic_translation_and_positive_scale(
    direction: str,
    inverted: bool,
) -> None:
    data = _field()
    shift = 16.0
    scale = 8.0

    base_channel = _channel(data)
    shifted_channel = _channel(data + shift)
    scaled_channel = _channel(data * scale)

    base_background = estimate_gwyddion_arc_revolution_background(
        base_channel,
        2.5,
        direction=direction,  # type: ignore[arg-type]
        inverted=inverted,
    ).data
    shifted_background = estimate_gwyddion_arc_revolution_background(
        shifted_channel,
        2.5,
        direction=direction,  # type: ignore[arg-type]
        inverted=inverted,
    ).data
    scaled_background = estimate_gwyddion_arc_revolution_background(
        scaled_channel,
        2.5,
        direction=direction,  # type: ignore[arg-type]
        inverted=inverted,
    ).data

    base_corrected = remove_gwyddion_arc_revolution_background(
        base_channel,
        2.5,
        direction=direction,  # type: ignore[arg-type]
        inverted=inverted,
    ).data
    shifted_corrected = remove_gwyddion_arc_revolution_background(
        shifted_channel,
        2.5,
        direction=direction,  # type: ignore[arg-type]
        inverted=inverted,
    ).data
    scaled_corrected = remove_gwyddion_arc_revolution_background(
        scaled_channel,
        2.5,
        direction=direction,  # type: ignore[arg-type]
        inverted=inverted,
    ).data

    expected_shifted_background = base_background + shift
    expected_scaled_background = base_background * scale
    expected_scaled_corrected = base_corrected * scale

    np.testing.assert_allclose(
        shifted_background,
        expected_shifted_background,
        atol=_roundoff_bound(expected_shifted_background),
        rtol=0.0,
    )
    np.testing.assert_allclose(
        shifted_corrected,
        base_corrected,
        atol=_roundoff_bound(base_corrected),
        rtol=0.0,
    )
    np.testing.assert_allclose(
        scaled_background,
        expected_scaled_background,
        atol=_roundoff_bound(expected_scaled_background),
        rtol=0.0,
    )
    np.testing.assert_allclose(
        scaled_corrected,
        expected_scaled_corrected,
        atol=_roundoff_bound(expected_scaled_corrected),
        rtol=0.0,
    )


def test_units_and_lateral_ranges_are_numerically_irrelevant() -> None:
    voltage = _channel(
        unit="V",
        x_range=1.0e-9,
        y_range=2.0e-9,
    )
    phase = _channel(
        unit="deg",
        x_range=0.25,
        y_range=12.0,
    )

    voltage_result = analyze_gwyddion_arc_revolution_background(
        voltage,
        2.5,
        direction="both",
    )
    phase_result = analyze_gwyddion_arc_revolution_background(
        phase,
        2.5,
        direction="both",
    )

    np.testing.assert_array_equal(
        voltage_result.background.data,
        phase_result.background.data,
    )
    np.testing.assert_array_equal(
        voltage_result.corrected.data,
        phase_result.corrected.data,
    )

    assert voltage_result.background.unit == "V"
    assert voltage_result.corrected.unit == "V"
    assert phase_result.background.unit == "deg"
    assert phase_result.corrected.unit == "deg"


@pytest.mark.parametrize("radius_px", [1.0, 1000.0, np.float64(20.0)])
def test_public_radius_boundaries_are_accepted(
    radius_px: object,
) -> None:
    result = analyze_gwyddion_arc_revolution_background(
        _channel(),
        radius_px,  # type: ignore[arg-type]
    )

    assert result.parameters["radius_px"] == float(radius_px)


@pytest.mark.parametrize(
    "radius_px",
    [
        0.0,
        -1.0,
        0.999999,
        1000.000001,
        np.nan,
        np.inf,
        -np.inf,
    ],
)
def test_invalid_radius_values_are_rejected(
    radius_px: float,
) -> None:
    with pytest.raises(ValueError):
        estimate_gwyddion_arc_revolution_background(
            _channel(),
            radius_px,
        )


@pytest.mark.parametrize(
    "radius_px",
    [
        True,
        "20",
        20.0 + 0.0j,
        [20.0],
        np.array([20.0]),
    ],
)
def test_invalid_radius_types_are_rejected(
    radius_px: object,
) -> None:
    with pytest.raises(TypeError):
        estimate_gwyddion_arc_revolution_background(
            _channel(),
            radius_px,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "direction",
    ["diagonal", "", 1, None],
)
def test_invalid_direction_is_rejected(
    direction: object,
) -> None:
    expected_exception = TypeError if not isinstance(direction, str) else ValueError

    with pytest.raises(expected_exception):
        estimate_gwyddion_arc_revolution_background(
            _channel(),
            2.5,
            direction=direction,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "inverted",
    [0, 1, "yes", None],
)
def test_non_boolean_inversion_is_rejected(
    inverted: object,
) -> None:
    with pytest.raises(TypeError):
        estimate_gwyddion_arc_revolution_background(
            _channel(),
            2.5,
            inverted=inverted,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "data",
    [
        np.array([[1.0, np.nan]]),
        np.array([[1.0, np.inf]]),
        np.array([[1.0 + 0.0j, 2.0 + 0.0j]]),
        np.array([1.0, 2.0]),
        np.empty((0, 3)),
    ],
)
def test_invalid_channel_data_is_rejected(
    data: np.ndarray,
) -> None:
    expected_exception = TypeError if np.iscomplexobj(data) else ValueError

    with pytest.raises(expected_exception):
        estimate_gwyddion_arc_revolution_background(
            _channel(data),
            2.5,
        )


@pytest.mark.parametrize(
    ("shape", "direction"),
    [
        ((1, 1), "horizontal"),
        ((5, 1), "horizontal"),
        ((1, 5), "vertical"),
        ((1, 1), "both"),
    ],
)
def test_single_sample_processing_axis_has_safe_identity_semantics(
    shape: tuple[int, int],
    direction: str,
) -> None:
    data = np.arange(
        shape[0] * shape[1],
        dtype=np.float64,
    ).reshape(shape)
    channel = _channel(data)

    result = analyze_gwyddion_arc_revolution_background(
        channel,
        2.5,
        direction=direction,  # type: ignore[arg-type]
    )

    np.testing.assert_array_equal(
        result.background.data,
        data,
    )
    np.testing.assert_array_equal(
        result.corrected.data,
        np.zeros_like(data),
    )


@pytest.mark.parametrize(
    ("shape", "direction"),
    [
        ((1, 5), "horizontal"),
        ((5, 1), "vertical"),
    ],
)
def test_singleton_orthogonal_axis_does_not_force_identity(
    shape: tuple[int, int],
    direction: str,
) -> None:
    """A singleton orthogonal dimension is not a singleton processed axis."""
    data = np.arange(
        shape[0] * shape[1],
        dtype=np.float64,
    ).reshape(shape)
    channel = _channel(data)

    result = analyze_gwyddion_arc_revolution_background(
        channel,
        2.5,
        direction=direction,  # type: ignore[arg-type]
    )

    assert not np.array_equal(
        result.background.data,
        data,
    )
    np.testing.assert_array_equal(
        result.corrected.data + result.background.data,
        data,
    )


def test_public_result_is_deterministic() -> None:
    channel = _channel()

    first = analyze_gwyddion_arc_revolution_background(
        channel,
        2.5,
        direction="both",
        inverted=True,
    )
    second = analyze_gwyddion_arc_revolution_background(
        channel,
        2.5,
        direction="both",
        inverted=True,
    )

    np.testing.assert_array_equal(
        first.background.data,
        second.background.data,
    )
    np.testing.assert_array_equal(
        first.corrected.data,
        second.corrected.data,
    )
