from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from spmkit.core.analysis._gwyddion_path_level import (
    _gwyddion_c_trunc_div,
    _gwyddion_normalized_path_level_lines,
    _gwyddion_path_level_result,
    _validated_gwyddion_path_level_data,
    _validated_gwyddion_path_level_lines,
    _validated_gwyddion_path_level_thickness,
)

FIXTURE = Path(__file__).resolve().parents[1] / "validation/fixtures/gwyddion/path_level"


def _fixture() -> tuple[dict[str, object], dict[str, np.ndarray]]:
    manifest = json.loads((FIXTURE / "path_level_reference.json").read_text())
    with np.load(FIXTURE / "path_level_reference.npz", allow_pickle=False) as archive:
        arrays = {name: archive[name].copy(order="C") for name in archive.files}
    return manifest, arrays


def _bits(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array, dtype=np.float64).view(np.uint64)


def _ulp_distance(expected: int, actual: int) -> int:
    def ordered(value: int) -> int:
        return (~value + 1) & ((1 << 64) - 1) if value >> 63 else value | (1 << 63)

    return abs(ordered(expected) - ordered(actual))


def _assert_bits(case_id: str, expected: np.ndarray, actual: np.ndarray) -> None:
    expected_bits = _bits(expected)
    actual_bits = _bits(actual)
    locations = np.argwhere(expected_bits != actual_bits)
    if not len(locations):
        return
    row, column = (int(value) for value in locations[0])
    wanted = int(expected_bits[row, column])
    received = int(actual_bits[row, column])
    raise AssertionError(
        f"{case_id}: coordinate=({row}, {column}), expected={expected[row, column]!r}, "
        f"actual={actual[row, column]!r}, expected_uint64={wanted:016x}, "
        f"actual_uint64={received:016x}, abs={abs(expected[row, column] - actual[row, column])!r}, "
        f"ulp={_ulp_distance(wanted, received)}"
    )


def _lines(case: dict[str, object]) -> np.ndarray:
    values = [float.fromhex(value) for value in case["lines_hex"]]  # type: ignore[index]
    return np.array(values, dtype=np.float64).reshape((-1, 4)) if values else np.empty((0, 4))


def _array_from_bits(bits: list[str]) -> np.ndarray:
    return np.array([int(value, 16) for value in bits], dtype=np.uint64).view(np.float64)


def test_all_frozen_cases_are_bitwise_exact_with_source_diagnostics() -> None:
    manifest, arrays = _fixture()
    endpoint_matches = mutation_matches = no_op_matches = exact_elements = 0
    for case in manifest["cases"]:  # type: ignore[index]
        base = next(base for base in manifest["bases"] if base["base_id"] == case["base_id"])  # type: ignore[index]
        input_data = arrays[base["input_key"]].copy(order="C")
        before = input_data.copy(order="C")
        result = _gwyddion_path_level_result(
            input_data,
            _lines(case),
            xreal=base["xreal"],
            yreal=base["yreal"],
            thickness_px=case["thickness"],
        )
        expected = arrays[case["output_key"]]
        _assert_bits(case["case_id"], expected, result.corrected)
        exact_elements += expected.size
        assert result.normalized_lines == tuple(
            tuple(case["normalized_endpoints"][index : index + 4])
            for index in range(0, len(case["normalized_endpoints"]), 4)
        )
        endpoint_matches += 1
        _assert_bits(
            case["case_id"] + "/row_differences",
            _array_from_bits(case["oracle_row_differences_bits"]),
            result.row_differences,
        )
        _assert_bits(
            case["case_id"] + "/cumulative",
            _array_from_bits(case["oracle_cumulative_correction_bits"]),
            result.cumulative_row_correction,
        )
        changed = not np.array_equal(_bits(result.corrected), _bits(before))
        mutation_matches += changed == case["external_mutation_of_data_field"]
        no_op_matches += (not changed) == case["external_no_op"]
        assert np.array_equal(_bits(input_data), _bits(before))
        assert result.corrected.dtype == np.float64 and result.corrected.flags.c_contiguous
        assert result.corrected.shape == input_data.shape
        assert not np.shares_memory(result.corrected, input_data)
    assert endpoint_matches == 72
    assert mutation_matches == 72
    assert no_op_matches == 72
    assert exact_elements == 4652


def test_line_order_discriminator_is_preserved() -> None:
    manifest, arrays = _fixture()
    selected = {case["case_id"]: case for case in manifest["cases"]}
    outputs = []
    for case_id in ("line_order_a__t1", "line_order_b_permuted__t1"):
        case = selected[case_id]
        base = next(base for base in manifest["bases"] if base["base_id"] == case["base_id"])
        result = _gwyddion_path_level_result(
            arrays[base["input_key"]],
            _lines(case),
            xreal=base["xreal"],
            yreal=base["yreal"],
            thickness_px=1,
        )
        outputs.append(result.corrected)
    assert not np.array_equal(_bits(outputs[0]), _bits(outputs[1]))


def test_endpoint_geometry_and_c_integer_division_contract() -> None:
    lines = _validated_gwyddion_path_level_lines([(7.9, 8.2, 1.1, 0.2), (-5.0, -2.0, 15.0, 12.0)])
    assert _gwyddion_normalized_path_level_lines(lines, xres=9, yres=9, xreal=9.0, yreal=9.0) == (
        (1, 0, 7, 8),
        (0, 0, 8, 8),
    )
    assert [_gwyddion_c_trunc_div(value, 3) for value in (-8, -7, -1, 0, 1, 7, 8)] == [
        -2,
        -2,
        0,
        0,
        0,
        2,
        2,
    ]


def test_validation_and_memory_contracts() -> None:
    assert isinstance(_validated_gwyddion_path_level_thickness(np.uint8(128)), int)
    for value in (True, np.bool_(False), np.array(1), 1.0, "1"):
        with pytest.raises(TypeError):
            _validated_gwyddion_path_level_thickness(value)
    for value in (0, 129, 10**100):
        with pytest.raises(ValueError):
            _validated_gwyddion_path_level_thickness(value)
    for value in (np.array([]), np.array([1.0]), np.empty((0, 2)), np.array([[np.nan]])):
        with pytest.raises(ValueError):
            _validated_gwyddion_path_level_data(value)
    for value in ("line", np.array([1.0, 2.0, 3.0]), np.array([[np.inf, 0, 0, 0]])):
        with pytest.raises((TypeError, ValueError)):
            _validated_gwyddion_path_level_lines(value)
    data = [[0, 1], [2, 3]]
    result = _gwyddion_path_level_result(data, [], xreal=2.0, yreal=2.0, thickness_px=128)
    assert result.corrected.dtype == np.float64 and result.corrected.flags.c_contiguous
    assert not np.shares_memory(result.corrected, np.asarray(data))


def test_signed_zero_and_repeated_execution_are_deterministic() -> None:
    data = np.array([[-0.0, +0.0], [-0.0, +0.0]], dtype=np.float64)
    lines = np.array([[0.0, 0.0, 1.0, 1.0]], dtype=np.float64)
    first = _gwyddion_path_level_result(data, lines, xreal=2.0, yreal=2.0, thickness_px=2)
    second = _gwyddion_path_level_result(data, lines, xreal=2.0, yreal=2.0, thickness_px=2)
    _assert_bits("signed_zero_repeat", first.corrected, second.corrected)
    assert hashlib.sha256(_bits(first.corrected).tobytes()).digest() == hashlib.sha256(
        _bits(second.corrected).tobytes()
    ).digest()
