"""Public-contract tests for frozen Gwyddion 2.71 Path Level."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

import spmkit.core.analysis as analysis
import spmkit.core.analysis.leveling as leveling_module
from spmkit.core.analysis import gwyddion_path_level
from spmkit.core.models import SPMChannel

_FIXTURE_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "fixtures"
    / "gwyddion"
    / "path_level"
)
_FIXTURE_PATH = _FIXTURE_DIRECTORY / "path_level_reference.npz"
_MANIFEST_PATH = _FIXTURE_DIRECTORY / "path_level_reference.json"


def _manifest() -> dict[str, object]:
    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _channel(data: np.ndarray, *, xreal: float, yreal: float) -> SPMChannel:
    return SPMChannel(
        name="Path Level fixture",
        data=data,
        unit="V",
        x_range=xreal,
        y_range=yreal,
        direction="backward",
        group="Frozen Path Level evidence",
        metadata={"source": "gwyddion-2.71-pathlevel", "context": {"id": 11}},
    )


def _lines(case: dict[str, object]) -> np.ndarray:
    values = [float.fromhex(value) for value in case["lines_hex"]]  # type: ignore[index]
    if not values:
        return np.empty((0, 4), dtype=np.float64)
    return np.array(values, dtype=np.float64).reshape((-1, 4))


def _ordered_uint64(bits: int) -> int:
    sign_bit = 1 << 63
    return ((~bits + 1) & ((1 << 64) - 1)) if bits & sign_bit else bits | sign_bit


def _maximum_ulp_distance(expected: np.ndarray, actual: np.ndarray) -> int:
    expected_bits = expected.view(np.uint64).ravel()
    actual_bits = actual.view(np.uint64).ravel()
    return max(
        abs(_ordered_uint64(int(wanted)) - _ordered_uint64(int(received)))
        for wanted, received in zip(expected_bits, actual_bits, strict=True)
    )


def _assert_bitwise_equal(actual: np.ndarray, expected: np.ndarray, *, case_id: str) -> None:
    actual_bits = actual.view(np.uint64)
    expected_bits = expected.view(np.uint64)
    if np.array_equal(actual_bits, expected_bits):
        return
    row, column = np.argwhere(actual_bits != expected_bits)[0]
    actual_value = int(actual_bits[row, column])
    expected_value = int(expected_bits[row, column])
    ulp_distance = abs(_ordered_uint64(actual_value) - _ordered_uint64(expected_value))
    pytest.fail(
        f"case={case_id} coordinate=({row}, {column}) "
        f"expected={expected[row, column]!r} actual={actual[row, column]!r} "
        f"expected_uint64={expected_value} actual_uint64={actual_value} "
        f"absolute_difference={abs(actual[row, column] - expected[row, column])!r} "
        f"ulp_distance={ulp_distance}"
    )


def test_public_export_and_signature() -> None:
    assert "gwyddion_path_level" in analysis.__all__
    assert analysis.gwyddion_path_level is gwyddion_path_level
    signature = inspect.signature(gwyddion_path_level)
    assert list(signature.parameters) == ["channel", "lines", "thickness_px"]
    assert signature.parameters["thickness_px"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["thickness_px"].default == 1
    for forbidden in ("mask", "roi", "path", "interpolation", "origin"):
        assert forbidden not in signature.parameters
    for private_name in (
        "_GwyddionPathLevelLine",
        "_GwyddionPathLevelResult",
        "_gwyddion_c_trunc_div",
        "_gwyddion_normalized_path_level_lines",
        "_gwyddion_path_level_result",
    ):
        assert private_name not in analysis.__all__
        assert not hasattr(analysis, private_name)


def test_all_frozen_public_outputs_are_bitwise_exact() -> None:
    manifest = _manifest()
    with np.load(_FIXTURE_PATH, allow_pickle=False) as archive:
        exact_elements = signed_zero_mismatches = mutation_matches = no_op_matches = 0
        maximum_absolute_difference = 0.0
        maximum_ulp_distance = 0
        ordered_outputs: dict[str, np.ndarray] = {}
        for case in manifest["cases"]:  # type: ignore[index]
            base = next(
                base for base in manifest["bases"] if base["base_id"] == case["base_id"]  # type: ignore[index]
            )
            source_data = np.array(
                archive[base["input_key"]],
                dtype=np.float64,
                order="C",
                copy=True,
            )
            original_bits = source_data.view(np.uint64).copy()
            channel = _channel(source_data, xreal=base["xreal"], yreal=base["yreal"])
            output = gwyddion_path_level(
                channel,
                _lines(case),
                thickness_px=case["thickness"],
            )
            expected = archive[case["output_key"]]
            _assert_bitwise_equal(output.data, expected, case_id=case["case_id"])
            exact_elements += expected.size
            maximum_absolute_difference = max(
                maximum_absolute_difference,
                float(np.max(np.abs(output.data - expected))),
            )
            maximum_ulp_distance = max(
                maximum_ulp_distance,
                _maximum_ulp_distance(expected, output.data),
            )
            signed_zero_mismatches += int(
                np.count_nonzero(
                    (output.data == 0.0)
                    & (expected == 0.0)
                    & (output.data.view(np.uint64) != expected.view(np.uint64))
                )
            )
            changed = not np.array_equal(output.data.view(np.uint64), original_bits)
            mutation_matches += changed == case["external_mutation_of_data_field"]
            no_op_matches += (not changed) == case["external_no_op"]
            assert np.array_equal(channel.data.view(np.uint64), original_bits)
            assert output.data.dtype == np.float64 and output.data.flags.c_contiguous
            assert output.data.shape == channel.data.shape
            assert not np.shares_memory(output.data, channel.data)
            ordered_outputs[case["case_id"]] = output.data
        assert exact_elements == 4652
        assert maximum_absolute_difference == 0.0
        assert maximum_ulp_distance == 0
        assert signed_zero_mismatches == 0
        assert mutation_matches == 72
        assert no_op_matches == 72
        assert not np.array_equal(
            ordered_outputs["line_order_a__t1"].view(np.uint64),
            ordered_outputs["line_order_b_permuted__t1"].view(np.uint64),
        )


def test_context_is_preserved_with_independent_metadata_and_data() -> None:
    manifest = _manifest()
    base = next(
        base
        for base in manifest["bases"]
        if base["base_id"] == "signed_gradient_positive_slope"
    )  # type: ignore[index]
    case = next(case for case in manifest["cases"] if case["base_id"] == base["base_id"])  # type: ignore[index]
    with np.load(_FIXTURE_PATH, allow_pickle=False) as archive:
        channel = _channel(
            np.array(archive[base["input_key"]], dtype=np.float64, order="C", copy=True),
            xreal=base["xreal"],
            yreal=base["yreal"],
        )
    output = gwyddion_path_level(channel, _lines(case), thickness_px=case["thickness"])
    assert output.name == channel.name
    assert output.unit == channel.unit
    assert output.x_range == channel.x_range and output.y_range == channel.y_range
    assert output.direction == channel.direction and output.group == channel.group
    assert output.metadata == channel.metadata and output.metadata is not channel.metadata
    output.metadata["new_key"] = True
    assert "new_key" not in channel.metadata


@pytest.mark.parametrize(
    ("lines", "thickness_px", "error_type"),
    [
        ([(0.0, 0.0, 1.0, 1.0)], True, TypeError),
        ([(0.0, 0.0, 1.0, 1.0)], np.array(1), TypeError),
        ([(0.0, 0.0, 1.0, 1.0)], 0, ValueError),
        ([(0.0, 0.0, 1.0, 1.0)], 129, ValueError),
        ([(0.0, 0.0, 1.0, 1.0)], 1.0, TypeError),
        ([(0.0, 0.0, 1.0, 1.0)], "1", TypeError),
        ([(0.0, 1.0)], 1, ValueError),
        ("line", 1, TypeError),
        (np.array([["a", "b", "c", "d"]], dtype=object), 1, TypeError),
        (np.array([[np.inf, 0.0, 1.0, 1.0]]), 1, ValueError),
    ],
)
def test_public_validation_is_delegated(
    lines: object,
    thickness_px: object,
    error_type: type[Exception],
) -> None:
    channel = _channel(np.ones((3, 4), dtype=np.float64), xreal=4.0, yreal=3.0)
    with pytest.raises(error_type):
        gwyddion_path_level(channel, lines, thickness_px=thickness_px)
    invalid_data = _channel(np.array([[np.nan]], dtype=np.float64), xreal=1.0, yreal=1.0)
    with pytest.raises(ValueError, match="finite"):
        gwyddion_path_level(invalid_data, [], thickness_px=1)


@pytest.mark.parametrize(
    ("data", "error_type"),
    [
        (np.ones(3), ValueError),
        (np.empty((0, 2)), ValueError),
        (np.array([["a"]]), TypeError),
        (np.array([[np.inf]]), ValueError),
    ],
)
def test_public_data_and_extent_validation_is_delegated(
    data: np.ndarray,
    error_type: type[Exception],
) -> None:
    channel = _channel(data, xreal=1.0, yreal=1.0)
    with pytest.raises(error_type):
        gwyddion_path_level(channel, [], thickness_px=1)
    for xreal, yreal in ((0.0, 1.0), (1.0, np.inf)):
        valid = _channel(np.ones((2, 2)), xreal=xreal, yreal=yreal)
        with pytest.raises(ValueError):
            gwyddion_path_level(valid, [], thickness_px=1)


def test_each_public_call_invokes_private_entry_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    original = leveling_module._gwyddion_path_level_result

    def counted_entry(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(leveling_module, "_gwyddion_path_level_result", counted_entry)
    channel = _channel(np.arange(12, dtype=np.float64).reshape(3, 4), xreal=4.0, yreal=3.0)
    gwyddion_path_level(channel, [(0.0, 0.0, 3.0, 2.0)], thickness_px=2)
    assert calls == 1
