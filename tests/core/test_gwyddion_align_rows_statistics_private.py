from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from spmkit.core.analysis._gwyddion_align_rows_statistics import (
    _gwyddion_align_rows_statistics_result,
    _GwyddionAlignRowsDirection,
    _GwyddionAlignRowsMethod,
    _GwyddionAlignRowsStatisticsResult,
    _GwyddionMaskMode,
    _minimum_sample_count,
    _paired_differences,
    _selected_row_values,
    _trimmed_mean_or_median,
)

FIXTURE = Path(__file__).resolve().parents[1] / "validation/fixtures/gwyddion/align_rows_statistics"


def _load() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    manifest = json.loads((FIXTURE / "align_rows_statistics_reference.json").read_text())
    with np.load(FIXTURE / "align_rows_statistics_reference.npz", allow_pickle=False) as archive:
        arrays = {name: archive[name].copy(order="C") for name in archive.files}
    return manifest, arrays


def _bits(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array, dtype=np.float64).view(np.uint64)


def _assert_bits(case_id: str, expected: np.ndarray, actual: np.ndarray) -> None:
    mismatch = np.argwhere(_bits(expected) != _bits(actual))
    if not len(mismatch):
        return
    row, column = (int(value) for value in mismatch[0])
    raise AssertionError(
        f"{case_id}: row={row}, column={column}, expected={_bits(expected)[row, column]:016x}, "
        f"actual={_bits(actual)[row, column]:016x}"
    )


def _ulp_distance(left: np.uint64, right: np.uint64) -> int:
    def ordered(value: int) -> int:
        return (~value + 1) & ((1 << 64) - 1) if value >> 63 else value | (1 << 63)

    return abs(ordered(int(left)) - ordered(int(right)))


def _run(case: dict[str, Any], arrays: dict[str, np.ndarray]) -> _GwyddionAlignRowsStatisticsResult:
    return _gwyddion_align_rows_statistics_result(
        arrays[case["input_key"]],
        method=case["method"],
        masking_mode=case["masking_mode"],
        direction=case["direction"],
        trim_fraction=float.fromhex(case["trim_fraction_hex"]),
        mask=None if case["mask_key"] is None else arrays[case["mask_key"]],
        extract_background=case["extract_background_request"],
    )


def test_all_portable_v2_cases_are_bitwise_exact_and_non_mutating() -> None:
    manifest, arrays = _load()
    exact = backgrounds = mutation_matches = 0
    for case in manifest["cases"]:
        input_data = arrays[case["input_key"]]
        mask = None if case["mask_key"] is None else arrays[case["mask_key"]]
        input_before = input_data.copy(order="C")
        mask_before = None if mask is None else mask.copy(order="C")
        first = _run(case, arrays)
        second = _run(case, arrays)
        _assert_bits(
            case["case_identifier"], arrays[case["portable_corrected_key"]], first.corrected
        )
        _assert_bits(case["case_identifier"] + "/repeat", first.corrected, second.corrected)
        expected_corrections = np.array(
            [int(value, 16) for value in case["portable_correction_sequence_bits"]], dtype=np.uint64
        ).view(np.float64)
        _assert_bits(
            case["case_identifier"] + "/corrections",
            expected_corrections,
            first.correction_sequence,
        )
        assert first.corrected.dtype == np.float64 and first.corrected.flags.c_contiguous
        assert (
            first.correction_sequence.dtype == np.float64
            and first.correction_sequence.flags.c_contiguous
        )
        assert not np.shares_memory(first.corrected, input_data)
        assert np.array_equal(_bits(input_data), _bits(input_before))
        if mask is not None:
            assert mask_before is not None
            assert np.array_equal(_bits(mask), _bits(mask_before))
        if case["extract_background_request"]:
            assert first.background is not None
            _assert_bits(
                case["case_identifier"] + "/background",
                arrays[case["portable_background_key"]],
                first.background,
            )
            reconstruction = np.empty_like(input_data)
            for row in range(input_data.shape[0]):
                for column in range(input_data.shape[1]):
                    reconstruction[row, column] = (
                        input_data[row, column] - first.background[row, column]
                    )
            _assert_bits(
                case["case_identifier"] + "/reconstruction", first.corrected, reconstruction
            )
            backgrounds += first.background.size
        else:
            assert first.background is None
        exact += first.corrected.size
        changed = bool((_bits(first.corrected) != _bits(input_data)).any())
        mutation_matches += int(changed == case["installed_mutated"])
    assert exact == 3888
    assert backgrounds == 504
    assert mutation_matches == 64


def test_installed_profile_divergence_policy_is_exactly_preserved() -> None:
    manifest, arrays = _load()
    exceptional = {
        "median__plateaus_signed_zero__10",
        "median_of_differences__irregular__11",
        "trimmed_mean_of_differences__irregular__11",
    }
    finite_nonzero = signed_zero = exact = maximum_ulp = 0
    maximum_absolute = 0.0
    for case in manifest["cases"]:
        portable = _run(case, arrays).corrected
        installed = arrays[case["installed_corrected_key"]]
        differing = _bits(portable) != _bits(installed)
        if differing.any():
            assert case["case_identifier"] in exceptional
        for row, column in np.argwhere(differing):
            if portable[row, column] == installed[row, column] == 0.0:
                signed_zero += 1
            else:
                assert np.isfinite(portable[row, column]) and np.isfinite(installed[row, column])
                finite_nonzero += 1
                maximum_absolute = max(
                    maximum_absolute, abs(portable[row, column] - installed[row, column])
                )
                maximum_ulp = max(
                    maximum_ulp,
                    _ulp_distance(_bits(portable)[row, column], _bits(installed)[row, column]),
                )
        exact += int((~differing).sum())
        if case["extract_background_request"]:
            result = _run(case, arrays)
            assert result.background is not None
            _assert_bits(
                case["case_identifier"] + "/installed-background",
                arrays[case["installed_background_key"]],
                result.background,
            )
    assert exact == 3757
    assert finite_nonzero == 128
    assert signed_zero == 3
    assert maximum_absolute <= 5.329070518200751e-15
    assert maximum_ulp <= 144


def test_mask_threshold_fallback_and_reduction_contracts() -> None:
    data = np.array([[1.0, 2.0, 3.0], [10.0, 20.0, 30.0]], dtype=np.float64)
    mask = np.array([[0.0, 0.5, 1.0], [-1.0, 0.5, 2.0]], dtype=np.float64)
    include = _gwyddion_align_rows_statistics_result(
        data, method=1, masking_mode=1, direction=0, trim_fraction=0.05, mask=mask
    )
    exclude = _gwyddion_align_rows_statistics_result(
        data, method=1, masking_mode=0, direction=0, trim_fraction=0.05, mask=mask
    )
    ignored = _gwyddion_align_rows_statistics_result(
        data, method=1, masking_mode=2, direction=0, trim_fraction=0.05, mask=mask
    )
    assert not np.array_equal(_bits(include.corrected), _bits(exclude.corrected))
    assert _selected_row_values(data[0], mask[0], _GwyddionMaskMode.INCLUDE) == [2.0, 3.0]
    assert _selected_row_values(data[0], mask[0], _GwyddionMaskMode.EXCLUDE) == [1.0, 2.0]
    assert _selected_row_values(data[0], mask[0], _GwyddionMaskMode.IGNORE) == [1.0, 2.0, 3.0]
    assert _paired_differences(data, mask, _GwyddionMaskMode.INCLUDE, 0) == []
    assert _paired_differences(data, mask, _GwyddionMaskMode.EXCLUDE, 0) == [9.0, 18.0]
    assert ignored.correction_sequence.shape == (2,)
    assert _minimum_sample_count(3) == 2
    assert _trimmed_mean_or_median([1.0, 2.0, 9.0], 0.0) == 4.0
    assert _trimmed_mean_or_median([1.0, 2.0, 9.0], 0.5) == 2.0
    assert _trimmed_mean_or_median(list(range(10)), 0.05) == 4.5
    assert _trimmed_mean_or_median(list(range(11)), 0.05) == 5.0
    no_mask = _gwyddion_align_rows_statistics_result(
        data, method=2, masking_mode=0, direction=0, trim_fraction=0.05, mask=None
    )
    no_mask_ignore = _gwyddion_align_rows_statistics_result(
        data, method=2, masking_mode=2, direction=0, trim_fraction=0.05, mask=None
    )
    _assert_bits("no_mask_mode", no_mask.corrected, no_mask_ignore.corrected)
    assert _GwyddionMaskMode.EXCLUDE == 0
    assert _GwyddionMaskMode.INCLUDE == 1
    assert _GwyddionMaskMode.IGNORE == 2
    assert _GwyddionAlignRowsDirection.HORIZONTAL == 0
    assert _GwyddionAlignRowsDirection.VERTICAL == 1
    assert _GwyddionAlignRowsMethod.MEDIAN_OF_DIFFERENCES == 2


def test_zero_one_selection_fallbacks_and_vertical_transpose_contract() -> None:
    absolute_data = np.array(
        [[0.0, 70.0, 80.0, 90.0], [10.0, 100.0, 80.0, 90.0], [30.0, 70.0, 80.0, 90.0]],
        dtype=np.float64,
    )
    absolute_mask = np.array(
        [[1.0, 0.0, 0.0, 0.0], [1.0, 1.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0]],
        dtype=np.float64,
    )
    absolute = _gwyddion_align_rows_statistics_result(
        absolute_data,
        method=1,
        masking_mode=1,
        direction=0,
        trim_fraction=0.05,
        mask=absolute_mask,
    )
    _assert_bits(
        "absolute_zero_one_fallback",
        np.array([-30.0, 60.0, -30.0], dtype=np.float64),
        absolute.correction_sequence,
    )

    difference_data = np.arange(12, dtype=np.float64).reshape(3, 4)
    difference_mask = np.array(
        [[2.0, 0.0, 0.0, 0.0], [2.0, 0.0, 0.0, 0.0], [2.0, 0.0, 0.0, 0.0]],
        dtype=np.float64,
    )
    difference = _gwyddion_align_rows_statistics_result(
        difference_data,
        method=2,
        masking_mode=1,
        direction=0,
        trim_fraction=0.05,
        mask=difference_mask,
    )
    _assert_bits(
        "difference_zero_one_fallback",
        np.zeros(3, dtype=np.float64),
        difference.correction_sequence,
    )

    vertical = _gwyddion_align_rows_statistics_result(
        absolute_data,
        method=5,
        masking_mode=0,
        direction=1,
        trim_fraction=0.05,
        mask=absolute_mask,
    )
    transposed = _gwyddion_align_rows_statistics_result(
        absolute_data.T,
        method=5,
        masking_mode=0,
        direction=0,
        trim_fraction=0.05,
        mask=absolute_mask.T,
    )
    _assert_bits("vertical_transpose", vertical.corrected, transposed.corrected.T)


@pytest.mark.parametrize(
    "kwargs, error_type",
    [
        (
            {
                "data": np.array([1.0]),
                "method": 1,
                "masking_mode": 2,
                "direction": 0,
                "trim_fraction": 0.05,
            },
            ValueError,
        ),
        (
            {
                "data": np.array([[np.nan]]),
                "method": 1,
                "masking_mode": 2,
                "direction": 0,
                "trim_fraction": 0.05,
            },
            ValueError,
        ),
        (
            {
                "data": np.ones((2, 2)),
                "method": 99,
                "masking_mode": 2,
                "direction": 0,
                "trim_fraction": 0.05,
            },
            ValueError,
        ),
        (
            {
                "data": np.ones((2, 2)),
                "method": 1,
                "masking_mode": 3,
                "direction": 0,
                "trim_fraction": 0.05,
            },
            ValueError,
        ),
        (
            {
                "data": np.ones((2, 2)),
                "method": 1,
                "masking_mode": 2,
                "direction": 7,
                "trim_fraction": 0.05,
            },
            ValueError,
        ),
        (
            {
                "data": np.ones((2, 2)),
                "method": 1,
                "masking_mode": 2,
                "direction": 0,
                "trim_fraction": 0.6,
            },
            ValueError,
        ),
        (
            {
                "data": np.ones((2, 2)),
                "method": 1,
                "masking_mode": 2,
                "direction": 0,
                "trim_fraction": True,
            },
            TypeError,
        ),
        (
            {
                "data": np.ones((2, 2)),
                "method": 1,
                "masking_mode": 2,
                "direction": 0,
                "trim_fraction": 0.05,
                "mask": np.ones((3, 2)),
            },
            ValueError,
        ),
    ],
)
def test_invalid_contracts(kwargs: dict[str, Any], error_type: type[Exception]) -> None:
    with pytest.raises(error_type):
        _gwyddion_align_rows_statistics_result(**kwargs)
