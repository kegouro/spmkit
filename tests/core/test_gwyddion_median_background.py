"""Public-contract tests for Gwyddion 2.71 Median Background."""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

import spmkit.core.analysis as analysis
import spmkit.core.analysis.background as background_module
from spmkit.core.analysis import (
    BackgroundResult,
    analyze_gwyddion_median_background,
    estimate_gwyddion_median_background,
    remove_gwyddion_median_background,
)
from spmkit.core.analysis._median_background import _gwyddion_median_background_result
from spmkit.core.models import SPMChannel

_FIXTURE_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "fixtures"
    / "gwyddion"
    / "median_background"
)
_FIXTURE_PATH = _FIXTURE_DIRECTORY / "median_background_reference.npz"
_MANIFEST_PATH = _FIXTURE_DIRECTORY / "median_background_reference.json"
_PUBLIC_OPERATIONS: tuple[Callable[[SPMChannel, object], object], ...] = (
    estimate_gwyddion_median_background,
    remove_gwyddion_median_background,
    analyze_gwyddion_median_background,
)


def _manifest() -> dict[str, object]:
    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _cases() -> tuple[dict[str, object], ...]:
    manifest = _manifest()
    cases = manifest["cases"]
    assert isinstance(cases, list)
    return tuple(cases)


def _case(name: str) -> dict[str, object]:
    return next(case for case in _cases() if case["name"] == name)


def _case_arrays(case: dict[str, object]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    arrays = case["arrays"]
    assert isinstance(arrays, dict)
    with np.load(_FIXTURE_PATH, allow_pickle=False) as archive:
        return (
            np.array(archive[arrays["input"]], dtype=np.float64, order="C", copy=True),
            np.array(archive[arrays["background"]], dtype=np.float64, order="C", copy=True),
            np.array(archive[arrays["corrected"]], dtype=np.float64, order="C", copy=True),
        )


def _channel(data: np.ndarray) -> SPMChannel:
    return SPMChannel(
        name="Median Background fixture",
        data=data,
        unit="V",
        x_range=9.5e-6,
        y_range=6.5e-6,
        direction="backward",
        group="Frozen external evidence",
        metadata={
            "source": "gwyddion-2.71-median-background",
            "context": {"campaign": "frozen"},
        },
    )


def _ordered_bits(bits: int) -> int:
    sign_bit = 1 << 63
    return ((~bits + 1) & ((1 << 64) - 1)) if bits & sign_bit else bits | sign_bit


def _assert_bitwise_equal(
    actual: np.ndarray,
    expected: np.ndarray,
    *,
    case: str,
    operation: str,
    array: str,
) -> None:
    actual_bits = actual.view(np.uint64)
    expected_bits = expected.view(np.uint64)
    if np.array_equal(actual_bits, expected_bits):
        return

    row, column = np.argwhere(actual_bits != expected_bits)[0]
    actual_bit_value = int(actual_bits[row, column])
    expected_bit_value = int(expected_bits[row, column])
    ulp_distance = abs(_ordered_bits(actual_bit_value) - _ordered_bits(expected_bit_value))
    pytest.fail(
        f"case={case} operation={operation} array={array} "
        f"coordinate=({row}, {column}) expected={expected[row, column]!r} "
        f"actual={actual[row, column]!r} expected_uint64={expected_bit_value} "
        f"actual_uint64={actual_bit_value} "
        f"absolute_difference={abs(actual[row, column] - expected[row, column])!r} "
        f"ulp_distance={ulp_distance}"
    )


def _expected_parameters(case: dict[str, object]) -> dict[str, object]:
    return {
        "radius_px": case["radius"],
        "kernel_resolution": case["kernel_resolution"],
        "kernel_active_count": case["kernel_active_count"],
        "rank_index": case["rank_index"],
        "rank_backend_reference": case["rank_backend_reference"],
        "border_policy": "gwyddion_border_extend",
        "kernel_geometry": "gwyddion_digital_ellipse",
    }


def test_public_exports_and_signature_contract() -> None:
    expected_names = {
        "estimate_gwyddion_median_background",
        "remove_gwyddion_median_background",
        "analyze_gwyddion_median_background",
    }

    assert expected_names <= set(analysis.__all__)
    for name in expected_names:
        assert getattr(analysis, name) is not None

    for operation in _PUBLIC_OPERATIONS:
        signature = inspect.signature(operation)
        assert list(signature.parameters) == ["channel", "radius_px"]
        assert signature.parameters["radius_px"].default == 20
        assert signature.parameters["radius_px"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD

    for private_name in (
        "_MedianBackgroundKernelSpec",
        "_validated_median_background_radius",
        "_median_background_active_offsets",
        "_median_background_kernel_spec",
        "_gwyddion_median_background_result",
    ):
        assert private_name not in analysis.__all__
        assert not hasattr(analysis, private_name)


@pytest.mark.parametrize(
    "case_name",
    ["wide_r1", "wide_r3", "wide_r20", "singleton_1x1_r1024"],
)
def test_analyze_reports_exact_frozen_metadata(case_name: str) -> None:
    case = _case(case_name)
    data, _, _ = _case_arrays(case)

    result = analyze_gwyddion_median_background(
        _channel(data),
        case["radius"],
    )

    assert isinstance(result, BackgroundResult)
    assert result.method == "gwyddion_median_background"
    assert result.parameters == _expected_parameters(case)


@pytest.mark.parametrize("case", _cases(), ids=lambda case: str(case["name"]))
def test_analyze_matches_all_frozen_cases_bitwise(case: dict[str, object]) -> None:
    data, expected_background, expected_corrected = _case_arrays(case)
    source = _channel(data)
    original = source.data.copy()

    result = analyze_gwyddion_median_background(source, case["radius"])

    _assert_bitwise_equal(
        result.background.data,
        expected_background,
        case=str(case["name"]),
        operation="analyze",
        array="background",
    )
    _assert_bitwise_equal(
        result.corrected.data,
        expected_corrected,
        case=str(case["name"]),
        operation="analyze",
        array="corrected",
    )
    assert result.parameters == _expected_parameters(case)
    assert np.array_equal(source.data, original)
    assert np.max(np.abs(source.data - (result.background.data + result.corrected.data))) <= 1e-15


@pytest.mark.parametrize("case_name", ["wide_r1", "wide_r3"])
def test_estimate_and_remove_match_private_and_fixture(case_name: str) -> None:
    case = _case(case_name)
    data, expected_background, expected_corrected = _case_arrays(case)
    source = _channel(data)
    private_background, private_corrected, _ = _gwyddion_median_background_result(
        source.data,
        case["radius"],
    )

    estimated = estimate_gwyddion_median_background(source, case["radius"])
    removed = remove_gwyddion_median_background(source, case["radius"])

    for actual, expected, operation, array in (
        (estimated.data, private_background, "estimate", "background-private"),
        (removed.data, private_corrected, "remove", "corrected-private"),
        (estimated.data, expected_background, "estimate", "background-fixture"),
        (removed.data, expected_corrected, "remove", "corrected-fixture"),
    ):
        _assert_bitwise_equal(
            actual,
            expected,
            case=case_name,
            operation=operation,
            array=array,
        )


def test_context_array_contract_and_memory_independence_are_preserved() -> None:
    case = _case("signed_r3")
    data, _, _ = _case_arrays(case)
    source = _channel(data)
    result = analyze_gwyddion_median_background(source, case["radius"])

    for output in (result.background, result.corrected):
        assert output.name == source.name
        assert output.unit == source.unit
        assert output.x_range == source.x_range
        assert output.y_range == source.y_range
        assert output.direction == source.direction
        assert output.group == source.group
        assert output.metadata == source.metadata
        assert output.metadata is not source.metadata
        assert output.data.shape == source.data.shape
        assert output.data.dtype == np.float64
        assert output.data.flags.c_contiguous
        assert np.all(np.isfinite(output.data))
        assert not np.shares_memory(output.data, source.data)

    assert not np.shares_memory(result.background.data, result.corrected.data)
    result.background.metadata["adapter"] = "background"
    assert "adapter" not in source.metadata
    assert "adapter" not in result.corrected.metadata


@pytest.mark.parametrize(
    ("radius_px", "exception"),
    [
        (True, TypeError),
        (np.array(2, dtype=np.int64), TypeError),
        (0, ValueError),
        (1025, ValueError),
        (10**100, ValueError),
    ],
)
@pytest.mark.parametrize("operation", _PUBLIC_OPERATIONS)
def test_invalid_radius_is_delegated_without_relaxation(
    radius_px: object,
    exception: type[Exception],
    operation: Callable[[SPMChannel, object], object],
) -> None:
    case = _case("wide_r1")
    data, _, _ = _case_arrays(case)

    with pytest.raises(exception):
        operation(_channel(data), radius_px)


@pytest.mark.parametrize("operation", _PUBLIC_OPERATIONS)
@pytest.mark.parametrize("nonfinite", [np.nan, np.inf, -np.inf])
def test_nonfinite_data_rejection_is_delegated(
    operation: Callable[[SPMChannel, object], object],
    nonfinite: float,
) -> None:
    data = np.ones((2, 3), dtype=np.float64)
    data[0, 1] = nonfinite

    with pytest.raises(ValueError, match="finite data"):
        operation(_channel(data), 1)


@pytest.mark.parametrize("operation", _PUBLIC_OPERATIONS)
def test_each_public_operation_invokes_private_kernel_once(
    monkeypatch: pytest.MonkeyPatch,
    operation: Callable[[SPMChannel, object], object],
) -> None:
    case = _case("wide_r3")
    data, _, _ = _case_arrays(case)
    call_count = 0
    original = background_module._gwyddion_median_background_result

    def counted_result(
        received_data: object,
        received_radius_px: object,
    ) -> tuple[np.ndarray, np.ndarray, object]:
        nonlocal call_count
        call_count += 1
        return original(received_data, received_radius_px)

    monkeypatch.setattr(
        background_module,
        "_gwyddion_median_background_result",
        counted_result,
    )

    operation(_channel(data), case["radius"])

    assert call_count == 1


def test_default_radius_and_to_dict_are_publicly_stable() -> None:
    case = _case("wide_r20")
    data, expected_background, expected_corrected = _case_arrays(case)

    result = analyze_gwyddion_median_background(_channel(data))

    _assert_bitwise_equal(
        result.background.data,
        expected_background,
        case="wide_r20",
        operation="analyze-default",
        array="background",
    )
    _assert_bitwise_equal(
        result.corrected.data,
        expected_corrected,
        case="wide_r20",
        operation="analyze-default",
        array="corrected",
    )
    assert result.parameters == _expected_parameters(case)
    assert result.to_dict()["method"] == "gwyddion_median_background"
