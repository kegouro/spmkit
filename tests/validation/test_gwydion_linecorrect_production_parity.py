"""Production parity: SPMKit kernels vs the frozen compiled-probe evidence.

For all 30 frozen cases, the production kernels are compared bitwise
against the compiled-probe arrays frozen in the fixtures.  Expectations
are loaded exclusively from the frozen NPZ/JSON; the oracle is NOT used
during production parity comparison.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from spmkit.core.analysis import gwydion_mark_inverted_rows, gwydion_step_line_correction
from spmkit.core.analysis._gwydion_mark_inverted_rows import (
    _gwydion_mark_inverted_rows_result,
)
from spmkit.core.analysis._gwydion_step_line_correction import (
    _gwydion_step_line_correction_result,
)
from spmkit.core.models.spmdata import SPMChannel

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwydion" / "linecorrect"
JSON_PATH = FIXTURE_DIR / "linecorrect_reference.json"
NPZ_PATH = FIXTURE_DIR / "linecorrect_reference.npz"

_manifest = json.loads(JSON_PATH.read_text())
_arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())


def _bits(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array, dtype=np.float64).view(np.uint64)


def _channel(data: np.ndarray) -> SPMChannel:
    return SPMChannel(
        name="parity",
        data=np.asarray(data, dtype=np.float64),
        unit="nm",
        x_range=float(data.shape[1]),
        y_range=float(data.shape[0]),
    )


def _scalar(case_id: str, label: str) -> float:
    case = next(c for c in _manifest["cases"]
                if c["case_identifier"] == case_id)
    return float.fromhex(case["scalars"][label]["hex"])


def _probe(case_id: str, label: str) -> np.ndarray:
    return _arrays[f"{case_id}_probe_{label}"]


# ---------------------------------------------------------------------------
# Step
# ---------------------------------------------------------------------------

_STEP_ARRAY_PAIRS = [
    ("row_statistic_raw_median", "row_statistics"),
    ("row_shift_zero_leveled", "zero_leveled_shifts"),
    ("field_after_initial_row_alignment", "field_after_row_alignment"),
    ("correction_scratch_pass1", "scratch_pass1"),
    ("field_after_pass1", "field_after_pass1"),
    ("correction_scratch_pass2", "scratch_pass2"),
    ("field_after_pass2", "field_after_pass2"),
    ("field_after_conservative_filter", "field_after_conservative_filter"),
    ("final_corrected_field", "final_corrected"),
    ("final_minus_input", "final_minus_input"),
    ("input_minus_final", "input_minus_final"),
]


def test_step_production_bitwise_parity_all_cases() -> None:
    arrays = 0
    elements = 0
    arrays_exact = 0
    elements_exact = 0
    for case in _manifest["cases"]:
        if case["family"] != "step":
            continue
        case_id = case["case_identifier"]
        trace = _gwydion_step_line_correction_result(
            _probe(case_id, "input"), trace=True)
        for label, attr in _STEP_ARRAY_PAIRS:
            probe = _probe(case_id, label)
            production = np.asarray(getattr(trace, attr), dtype=np.float64)
            if production.ndim == 2 and probe.ndim == 1:
                production = production.ravel()
            assert probe.shape == production.shape, (case_id, label)
            equal = bool(np.array_equal(_bits(probe), _bits(production)))
            arrays += 1
            elements += probe.size
            arrays_exact += int(equal)
            elements_exact += int(np.count_nonzero(
                _bits(probe) == _bits(production))) if not equal else probe.size
            assert equal, (case_id, label)
        assert trace.original_global_mean == _scalar(
            case_id, "original_global_mean"), case_id
        assert trace.mean_restoration_offset == _scalar(
            case_id, "final_mean_restoration_offset"), case_id
    assert arrays == 176, arrays
    assert elements == 5046, elements
    assert arrays_exact == 176
    assert elements_exact == 5046


def test_step_public_api_parity() -> None:
    for case in _manifest["cases"]:
        if case["family"] != "step":
            continue
        case_id = case["case_identifier"]
        channel = _channel(_probe(case_id, "input"))
        result = gwydion_step_line_correction(channel)
        frozen_final = _probe(case_id, "final_corrected_field")
        assert np.array_equal(_bits(result.data), _bits(frozen_final)), case_id
        # channel preservation and non-mutation
        assert result.name == "parity"
        assert result.unit == "nm"
        assert result.x_range == float(frozen_final.shape[1])
        assert result.y_range == float(frozen_final.shape[0])
        assert np.array_equal(_bits(channel.data),
                              _bits(_probe(case_id, "input")))


# ---------------------------------------------------------------------------
# Mark Inverted Rows
# ---------------------------------------------------------------------------


def _compare_mark_array(case_id: str, label: str, production: np.ndarray,
                       arrays: list[int], elements: list[int]) -> None:
    """Compare one production array against the frozen probe array and
    accumulate the campaign-equivalent array/element accounting."""
    probe = _probe(case_id, label)
    production = np.asarray(production, dtype=np.float64)
    assert probe.shape == production.shape, (case_id, label)
    assert np.array_equal(_bits(probe), _bits(production)), (case_id, label)
    arrays[0] += 1
    elements[0] += probe.size


def _compare_mark_array(case_id: str, label: str, production: np.ndarray,
                       arrays: list[int], elements: list[int]) -> None:
    """Compare one production array against the frozen probe array and
    accumulate the campaign-equivalent array/element accounting."""
    probe = _probe(case_id, label)
    production = np.asarray(production, dtype=np.float64)
    assert probe.shape == production.shape, (case_id, label)
    assert np.array_equal(_bits(probe), _bits(production)), (case_id, label)
    arrays[0] += 1
    elements[0] += probe.size


def test_mark_production_bitwise_parity_all_cases() -> None:
    # Accounting mirrors the frozen campaign comparison (59 arrays, 596
    # elements): guard cases contribute no arrays; no-negative cases
    # contribute the three stat arrays; detection cases additionally
    # contribute block sums, the generated mask and input-after; m12 adds
    # the existing-mask before/after pair.
    arrays = [0]
    elements = [0]
    for case in _manifest["cases"]:
        if case["family"] != "inverted":
            continue
        case_id = case["case_identifier"]
        existing = None
        if "existing_mask_before" in case["arrays"]:
            existing = _probe(case_id, "existing_mask_before").copy()
        result = _gwydion_mark_inverted_rows_result(
            _probe(case_id, "input"), existing_mask=existing)
        assert result.guard_triggered == (
            _scalar(case_id, "guard_triggered") != 0.0), case_id
        if result.guard_triggered:
            continue
        for label, attr in (("row_means", "row_means"),
                            ("row_rms", "row_rms"),
                            ("raw_correlation_weights", "raw_weights")):
            _compare_mark_array(case_id, label,
                                getattr(result, attr), arrays, elements)
        assert result.has_negative_weight == (
            _scalar(case_id, "has_negative_weight") != 0.0), case_id
        if not result.has_negative_weight:
            # no-negative early return: exactly the three stat arrays
            assert result.generated_mask is None, case_id
            assert result.would_create_mask is False, case_id
            assert result.would_overwrite_existing_mask is False, case_id
            continue
        _compare_mark_array(case_id, "block_summed_weights",
                            result.block_summed_weights, arrays, elements)
        assert result.anchor_index == int(
            _scalar(case_id, "anchor_index")), case_id
        assert result.anchor_weight == _scalar(
            case_id, "anchor_weight"), case_id
        production = np.asarray(result.generated_mask, dtype=np.float64)
        _compare_mark_array(case_id, "generated_binary_mask",
                            production, arrays, elements)

        def marked(mask: np.ndarray) -> list[int]:
            return [int(r) for r in range(mask.shape[0])
                    if np.any(mask[r] == 1.0)]
        assert marked(_probe(case_id, "generated_binary_mask")
                      ) == marked(production), case_id
        assert result.mask_max == _scalar(case_id, "mask_max"), case_id
        assert result.would_create_mask == (
            _scalar(case_id, "would_write_mask_when_no_existing_mask")
            != 0.0), case_id
        assert result.would_overwrite_existing_mask == (
            _scalar(case_id, "would_overwrite_existing_mask") != 0.0), case_id
        if "existing_mask_before" in case["arrays"]:
            _compare_mark_array(case_id, "existing_mask_before",
                                result.existing_mask_before, arrays, elements)
            assert result.existing_mask_after is not None, case_id
            _compare_mark_array(case_id, "existing_mask_after_overwrite",
                                result.existing_mask_after, arrays, elements)
        _compare_mark_array(case_id, "input_field_after_operation",
                            result.input_snapshot, arrays, elements)
        # scalars available on the detection path
        assert result.global_mean == _scalar(case_id, "global_mean"), case_id
        assert result.global_rms == _scalar(case_id, "global_rms"), case_id
    assert arrays[0] == 59, arrays
    assert elements[0] == 596, elements


def test_mark_public_api_adaptation() -> None:
    for case in _manifest["cases"]:
        if case["family"] != "inverted":
            continue
        case_id = case["case_identifier"]
        channel = _channel(_probe(case_id, "input"))
        mask = gwydion_mark_inverted_rows(channel)
        assert mask.shape == channel.data.shape
        assert mask.dtype == np.float64
        assert mask.flags.c_contiguous
        assert set(np.unique(mask)) <= {0.0, 1.0}
        mask_info = case["arrays"].get("generated_binary_mask")
        if mask_info and mask_info["count"]:
            frozen = _probe(case_id, "generated_binary_mask")
            assert np.array_equal(_bits(mask), _bits(frozen)), case_id
        else:
            # public adaptation: all-zero mask when Gwydion would create none
            assert np.all(mask == 0.0), case_id
        assert np.array_equal(_bits(channel.data),
                              _bits(_probe(case_id, "input"))), case_id
