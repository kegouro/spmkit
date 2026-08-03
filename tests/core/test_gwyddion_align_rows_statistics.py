"""Public-contract tests for Gwyddion 2.71 Align Rows statistics."""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, get_args

import numpy as np
import pytest

import spmkit.core.analysis as analysis
import spmkit.core.analysis.leveling as leveling_module
from spmkit.core.analysis import (
    GwyddionAlignRowsDirection,
    GwyddionAlignRowsMaskMode,
    gwyddion_align_rows_median,
    gwyddion_align_rows_median_of_differences,
    gwyddion_align_rows_trimmed_mean,
    gwyddion_align_rows_trimmed_mean_of_differences,
)
from spmkit.core.models import SPMChannel

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "fixtures"
    / "gwyddion"
    / "align_rows_statistics"
)
_FUNCTIONS: dict[int, Callable[..., SPMChannel]] = {
    1: gwyddion_align_rows_median,
    2: gwyddion_align_rows_median_of_differences,
    5: gwyddion_align_rows_trimmed_mean,
    6: gwyddion_align_rows_trimmed_mean_of_differences,
}
_MASK_MODES: dict[int, str] = {0: "exclude", 1: "include", 2: "ignore"}
_DIRECTIONS: dict[int, str] = {0: "horizontal", 1: "vertical"}
_EXCEPTIONAL_CASES = {
    "median__plateaus_signed_zero__10",
    "median_of_differences__irregular__11",
    "trimmed_mean_of_differences__irregular__11",
}


def _load() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    manifest = json.loads((_FIXTURE / "align_rows_statistics_reference.json").read_text())
    with np.load(_FIXTURE / "align_rows_statistics_reference.npz", allow_pickle=False) as archive:
        arrays = {
            name: np.array(archive[name], dtype=np.float64, order="C", copy=True)
            for name in archive.files
        }
    return manifest, arrays


def _bits(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array, dtype=np.float64).view(np.uint64)


def _ordered_uint64(bits: int) -> int:
    return (~bits + 1) & ((1 << 64) - 1) if bits >> 63 else bits | (1 << 63)


def _ulp_distance(left: np.uint64, right: np.uint64) -> int:
    return abs(_ordered_uint64(int(left)) - _ordered_uint64(int(right)))


def _assert_bitwise(actual: np.ndarray, expected: np.ndarray, *, case_id: str) -> None:
    differing = _bits(actual) != _bits(expected)
    if not differing.any():
        return
    row, column = (int(item) for item in np.argwhere(differing)[0])
    pytest.fail(
        f"case={case_id} coordinate=({row}, {column}) "
        f"expected_bits={_bits(expected)[row, column]:016x} "
        f"actual_bits={_bits(actual)[row, column]:016x}"
    )


def _channel(data: np.ndarray, *, xreal: float, yreal: float) -> SPMChannel:
    return SPMChannel(
        name="Align Rows fixture",
        data=data,
        unit="V",
        x_range=xreal,
        y_range=yreal,
        direction="backward",
        group="Frozen Align Rows evidence",
        metadata={"source": "gwyddion-2.71-align-rows", "context": {"id": 64}},
    )


def _run(case: dict[str, Any], arrays: dict[str, np.ndarray], channel: SPMChannel) -> SPMChannel:
    function = _FUNCTIONS[int(case["method"])]
    kwargs: dict[str, object] = {
        "mask": None if case["mask_key"] is None else arrays[str(case["mask_key"])],
        "mask_mode": _MASK_MODES[int(case["masking_mode"])],
        "direction": _DIRECTIONS[int(case["direction"])],
    }
    if int(case["method"]) in {5, 6}:
        kwargs["trim_fraction"] = float.fromhex(str(case["trim_fraction_hex"]))
    return function(channel, **kwargs)


def test_public_exports_types_and_signatures() -> None:
    expected = {
        "GwyddionAlignRowsDirection",
        "GwyddionAlignRowsMaskMode",
        "gwyddion_align_rows_median",
        "gwyddion_align_rows_median_of_differences",
        "gwyddion_align_rows_trimmed_mean",
        "gwyddion_align_rows_trimmed_mean_of_differences",
    }
    assert expected <= set(analysis.__all__)
    assert get_args(GwyddionAlignRowsMaskMode) == ("exclude", "include", "ignore")
    assert get_args(GwyddionAlignRowsDirection) == ("horizontal", "vertical")

    for method, function in _FUNCTIONS.items():
        assert getattr(analysis, function.__name__) is function
        signature = inspect.signature(function)
        assert list(signature.parameters) == (
            ["channel", "trim_fraction", "mask", "mask_mode", "direction"]
            if method in {5, 6}
            else ["channel", "mask", "mask_mode", "direction"]
        )
        assert all(
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
            for name, parameter in signature.parameters.items()
            if name != "channel"
        )
        assert "extract_background" not in signature.parameters
        assert "method" not in signature.parameters
    for private_name in (
        "_GwyddionAlignRowsDirection",
        "_GwyddionAlignRowsMethod",
        "_GwyddionAlignRowsStatisticsResult",
        "_GwyddionMaskMode",
        "_gwyddion_align_rows_statistics_result",
    ):
        assert private_name not in analysis.__all__
        assert not hasattr(analysis, private_name)


def test_explicit_gwyddion_wrappers_remain_separate_from_generic_align_rows() -> None:
    """The validated Gwyddion entry point is explicit and returns a new channel."""
    channel = _channel(
        np.array([[1.0, 2.0], [4.0, 8.0]], dtype=np.float64),
        xreal=2.0,
        yreal=2.0,
    )

    gwyddion_result = gwyddion_align_rows_median(channel)
    generic_result = leveling_module.align_rows(channel, method="median")

    assert gwyddion_result is not generic_result
    assert gwyddion_result is not channel
    assert generic_result is not channel
    assert not np.shares_memory(gwyddion_result.data, generic_result.data)
    assert not np.array_equal(_bits(gwyddion_result.data), _bits(generic_result.data))


def test_all_portable_cases_are_bitwise_exact_deterministic_and_non_mutating() -> None:
    manifest, arrays = _load()
    exact_elements = mutation_matches = no_op_matches = 0
    seen_methods: set[int] = set()
    seen_modes: set[int] = set()
    seen_directions: set[int] = set()
    seen_trims: set[float] = set()
    absent_mask_modes: set[int] = set()
    for case in manifest["cases"]:
        source = arrays[case["input_key"]]
        mask = None if case["mask_key"] is None else arrays[case["mask_key"]]
        source_before = source.copy(order="C")
        mask_before = None if mask is None else mask.copy(order="C")
        channel = _channel(
            source,
            xreal=float.fromhex(case["xreal_hex"]),
            yreal=float.fromhex(case["yreal_hex"]),
        )
        first = _run(case, arrays, channel)
        second = _run(case, arrays, channel)
        expected = arrays[case["portable_corrected_key"]]
        _assert_bitwise(first.data, expected, case_id=case["case_identifier"])
        _assert_bitwise(second.data, first.data, case_id=case["case_identifier"] + "/repeat")
        assert first.data.dtype == np.float64 and first.data.flags.c_contiguous
        assert first.data.shape == source.shape
        assert not np.shares_memory(first.data, source)
        assert np.array_equal(_bits(source), _bits(source_before))
        if mask is not None:
            assert mask_before is not None
            assert np.array_equal(_bits(mask), _bits(mask_before))
        else:
            absent_mask_modes.add(int(case["masking_mode"]))
        changed = bool((_bits(first.data) != _bits(source)).any())
        mutation_matches += int(changed == case["portable_mutated"] == case["installed_mutated"])
        no_op_matches += int((not changed) == (not case["portable_mutated"]))
        exact_elements += first.data.size
        seen_methods.add(int(case["method"]))
        seen_modes.add(int(case["masking_mode"]))
        seen_directions.add(int(case["direction"]))
        seen_trims.add(float.fromhex(case["trim_fraction_hex"]))
    assert exact_elements == 3888
    assert mutation_matches == no_op_matches == 64
    assert seen_methods == {1, 2, 5, 6}
    assert seen_modes == {0, 1, 2}
    assert seen_directions == {0, 1}
    assert {0.0, 0.05, 0.5} <= seen_trims
    assert absent_mask_modes == {0}


@pytest.mark.parametrize("function", list(_FUNCTIONS.values()))
def test_absent_mask_ignores_the_stored_mask_mode(function: Callable[..., SPMChannel]) -> None:
    channel = _channel(
        np.array([[1.0, 2.0, 4.0], [4.0, 5.0, 8.0], [7.0, 8.0, 12.0]], dtype=np.float64),
        xreal=3.0,
        yreal=3.0,
    )
    kwargs: dict[str, object] = {"mask": None, "direction": "vertical"}
    if function in {
        gwyddion_align_rows_trimmed_mean,
        gwyddion_align_rows_trimmed_mean_of_differences,
    }:
        kwargs["trim_fraction"] = 0.05
    outputs = [
        function(channel, mask_mode=mask_mode, **kwargs)
        for mask_mode in ("exclude", "include", "ignore")
    ]
    _assert_bitwise(outputs[0].data, outputs[1].data, case_id="absent-mask/include")
    _assert_bitwise(outputs[0].data, outputs[2].data, case_id="absent-mask/ignore")


def test_absolute_mask_thresholds_ignore_routing_and_global_fallback() -> None:
    data = np.array([[100.0, -1000.0, 7.0, 0.0], [200.0, -800.0, 9.0, 10.0]])
    mask = np.array([[-0.0, 0.0, 0.5, 1.0], [-0.0, 0.0, 0.5, 1.0]])
    channel = _channel(data, xreal=4.0, yreal=2.0)
    included = gwyddion_align_rows_median(channel, mask=mask, mask_mode="include")
    excluded = gwyddion_align_rows_median(channel, mask=mask, mask_mode="exclude")
    ignored = gwyddion_align_rows_median(channel, mask=mask, mask_mode="ignore")
    _assert_bitwise(
        included.data,
        np.array([[101.5, -998.5, 8.5, 1.5], [198.5, -801.5, 7.5, 8.5]]),
        case_id="absolute/include",
    )
    _assert_bitwise(
        excluded.data,
        np.array([[101.0, -999.0, 8.0, 1.0], [199.0, -801.0, 8.0, 9.0]]),
        case_id="absolute/exclude",
    )
    _assert_bitwise(included.data, ignored.data, case_id="absolute/ignore")

    fallback_data = np.array(
        [[0.0, 70.0, 80.0, 90.0], [10.0, 100.0, 80.0, 90.0], [30.0, 70.0, 80.0, 90.0]]
    )
    fallback_mask = np.array([[1.0, 0.0, 0.0, 0.0], [1.0, 1.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0]])
    fallback = gwyddion_align_rows_median(
        _channel(fallback_data, xreal=4.0, yreal=3.0),
        mask=fallback_mask,
        mask_mode="include",
    )
    _assert_bitwise(
        fallback.data,
        fallback_data - np.array([[-30.0], [60.0], [-30.0]]),
        case_id="absolute/zero-one-fallback",
    )


def test_difference_joint_thresholds_and_zero_one_pair_fallback() -> None:
    data = np.array(
        [[0.0, 0.0, 100.0, 500.0], [10.0, 10.0, 1000.0, 700.0], [40.0, 40.0, 2000.0, 900.0]]
    )
    channel = _channel(data, xreal=4.0, yreal=3.0)
    include_mask = np.array([[2.0, 2.0, 1.0, 0.5]] * 3)
    exclude_mask = np.array([[0.0, 0.5, 1.0, 2.0]] * 3)
    included = gwyddion_align_rows_median_of_differences(
        channel, mask=include_mask, mask_mode="include"
    )
    excluded = gwyddion_align_rows_median_of_differences(
        channel, mask=exclude_mask, mask_mode="exclude"
    )
    assert not np.array_equal(_bits(included.data), _bits(data))
    assert not np.array_equal(_bits(excluded.data), _bits(data))

    one_pair_mask = np.array([[2.0, 0.0, 0.0, 0.0]] * 3)
    fallback = gwyddion_align_rows_median_of_differences(
        channel, mask=one_pair_mask, mask_mode="include"
    )
    _assert_bitwise(fallback.data, data, case_id="difference/zero-one-pair-fallback")


def test_installed_fast_math_profile_matches_the_frozen_exception_policy() -> None:
    manifest, arrays = _load()
    exact_arrays = exact_elements = finite_nonzero = signed_zero = nan = infinity = 0
    maximum_absolute = 0.0
    maximum_ulp = 0
    exceptional_cases: set[str] = set()
    mutation_matches = 0
    for case in manifest["cases"]:
        source = arrays[case["input_key"]]
        channel = _channel(
            source,
            xreal=float.fromhex(case["xreal_hex"]),
            yreal=float.fromhex(case["yreal_hex"]),
        )
        portable = _run(case, arrays, channel).data
        installed = arrays[case["installed_corrected_key"]]
        differing = _bits(portable) != _bits(installed)
        exact_arrays += int(not differing.any())
        exact_elements += int((~differing).sum())
        if differing.any():
            exceptional_cases.add(case["case_identifier"])
        for row, column in np.argwhere(differing):
            left = portable[row, column]
            right = installed[row, column]
            if np.isnan(left) or np.isnan(right):
                nan += 1
            elif np.isinf(left) or np.isinf(right):
                infinity += 1
            elif left == right == 0.0:
                signed_zero += 1
            else:
                finite_nonzero += 1
                maximum_absolute = max(maximum_absolute, abs(left - right))
                maximum_ulp = max(
                    maximum_ulp,
                    _ulp_distance(_bits(portable)[row, column], _bits(installed)[row, column]),
                )
        changed = bool((_bits(portable) != _bits(source)).any())
        mutation_matches += int(changed == case["installed_mutated"])
    assert exact_arrays == 61
    assert exact_elements == 3757
    assert finite_nonzero == 128
    assert signed_zero == 3
    assert nan == infinity == 0
    assert maximum_absolute <= 5.329070518200751e-15
    assert maximum_ulp <= 144
    assert exceptional_cases == _EXCEPTIONAL_CASES
    assert mutation_matches == 64


def test_channel_context_is_preserved_with_independent_metadata_and_output() -> None:
    manifest, arrays = _load()
    case = next(
        item for item in manifest["cases"] if item["case_identifier"] == "median__constant__00"
    )
    source = arrays[case["input_key"]].copy(order="C")
    channel = _channel(
        source,
        xreal=float.fromhex(case["xreal_hex"]),
        yreal=float.fromhex(case["yreal_hex"]),
    )
    output = _run(case, arrays, channel)
    assert output.name == channel.name and output.unit == channel.unit
    assert output.x_range == channel.x_range and output.y_range == channel.y_range
    assert output.direction == channel.direction and output.group == channel.group
    assert output.metadata == channel.metadata and output.metadata is not channel.metadata
    output.metadata["new_key"] = True
    assert "new_key" not in channel.metadata
    assert output.data.flags.c_contiguous and not np.shares_memory(output.data, channel.data)


@pytest.mark.parametrize(
    ("function", "kwargs", "error_type"),
    [
        (gwyddion_align_rows_median, {"mask_mode": "selected"}, ValueError),
        (gwyddion_align_rows_median, {"direction": "diagonal"}, ValueError),
        (gwyddion_align_rows_median, {"mask": np.ones((2, 3))}, ValueError),
        (gwyddion_align_rows_median, {"mask": np.array([[np.nan, 0.0], [0.0, 0.0]])}, ValueError),
        (gwyddion_align_rows_median, {"mask": np.array([["mask"]])}, TypeError),
        (gwyddion_align_rows_trimmed_mean, {"trim_fraction": -0.01}, ValueError),
        (gwyddion_align_rows_trimmed_mean, {"trim_fraction": 0.51}, ValueError),
        (gwyddion_align_rows_trimmed_mean_of_differences, {"trim_fraction": True}, TypeError),
    ],
)
def test_public_validation_errors(
    function: Callable[..., SPMChannel], kwargs: dict[str, object], error_type: type[Exception]
) -> None:
    channel = _channel(np.ones((2, 2), dtype=np.float64), xreal=2.0, yreal=2.0)
    with pytest.raises(error_type):
        function(channel, **kwargs)


def test_each_public_call_delegates_to_the_private_entry_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def counted_entry(*args: object, **kwargs: object) -> SimpleNamespace:
        calls.append(dict(kwargs))
        return SimpleNamespace(corrected=np.ones((2, 2), dtype=np.float64))

    monkeypatch.setattr(leveling_module, "_gwyddion_align_rows_statistics_result", counted_entry)
    channel = _channel(np.zeros((2, 2), dtype=np.float64), xreal=2.0, yreal=2.0)
    for method, function in _FUNCTIONS.items():
        kwargs: dict[str, object] = {}
        if method in {5, 6}:
            kwargs["trim_fraction"] = 0.5
        output = function(channel, **kwargs)
        assert output.data.flags.c_contiguous and output.data.dtype == np.float64
    assert len(calls) == 4
    assert [call["method"] for call in calls] == [
        leveling_module._GwyddionAlignRowsMethod.MEDIAN,
        leveling_module._GwyddionAlignRowsMethod.MEDIAN_OF_DIFFERENCES,
        leveling_module._GwyddionAlignRowsMethod.TRIMMED_MEAN,
        leveling_module._GwyddionAlignRowsMethod.TRIMMED_MEAN_OF_DIFFERENCES,
    ]
    assert all("extract_background" not in call for call in calls)
