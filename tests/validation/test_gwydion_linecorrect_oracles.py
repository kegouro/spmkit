"""Oracle tests for the Gwydion 2.71 linecorrect campaign.

Every probe observable frozen in the fixtures is recomputed by the
independent oracles and compared bitwise for all 30 cases.  The tests
never derive probe expectations from oracle output: expectations come
exclusively from the frozen compiled-probe fixtures.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwydion" / "linecorrect"
JSON_PATH = FIXTURE_DIR / "linecorrect_reference.json"
NPZ_PATH = FIXTURE_DIR / "linecorrect_reference.npz"


def _load_module(name: str, filename: str):
    import sys

    spec = importlib.util.spec_from_file_location(name, str(FIXTURE_DIR / filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses require the module registration
    spec.loader.exec_module(module)
    return module


step_oracle = _load_module("lc_oracle_step", "oracle_step_line_correction.py")
mark_oracle = _load_module("lc_oracle_mark", "oracle_mark_inverted_rows.py")

_manifest = json.loads(JSON_PATH.read_text())
_arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())


def _bits(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array, dtype=np.float64).view(np.uint64)


def _case(case_id: str) -> dict:
    return next(c for c in _manifest["cases"]
                if c["case_identifier"] == case_id)


def _probe_array(case_id: str, label: str) -> np.ndarray:
    return _arrays[f"{case_id}_probe_{label}"]


def _probe_scalar(case_id: str, label: str) -> float:
    return float.fromhex(_case(case_id)["scalars"][label]["hex"])


STEP_STAGE_LABELS = [
    "row_statistic_raw_median",
    "row_shift_zero_leveled",
    "field_after_initial_row_alignment",
    "correction_scratch_pass1",
    "field_after_pass1",
    "correction_scratch_pass2",
    "field_after_pass2",
    "field_after_conservative_filter",
    "final_corrected_field",
    "final_minus_input",
    "input_minus_final",
]

STEP_SCALAR_LABELS = ["original_global_mean", "final_mean_restoration_offset"]


def test_step_oracle_matches_probe_all_cases() -> None:
    for case_id in [c["case_identifier"] for c in _manifest["cases"]
                    if c["family"] == "step"]:
        probe_input = _probe_array(case_id, "input")
        ref = step_oracle.oracle_step_line_correction(probe_input)
        # scalars
        assert _probe_scalar(case_id, "original_global_mean") == ref.original_global_mean
        assert (_probe_scalar(case_id, "final_mean_restoration_offset")
                == ref.final_mean_restoration_offset)
        # stage arrays (probe 1-D diffs are flat)
        for label in STEP_STAGE_LABELS:
            probe = _probe_array(case_id, label)
            oracle = getattr(ref, {
                "row_statistic_raw_median": "raw_row_statistics",
                "row_shift_zero_leveled": "zero_leveled_row_shifts",
                "field_after_initial_row_alignment":
                    "field_after_initial_row_alignment",
                "correction_scratch_pass1": "correction_scratch_pass1",
                "field_after_pass1": "field_after_pass1",
                "correction_scratch_pass2": "correction_scratch_pass2",
                "field_after_pass2": "field_after_pass2",
                "field_after_conservative_filter":
                    "field_after_conservative_filter",
                "final_corrected_field": "final_corrected_field",
                "final_minus_input": "final_minus_input",
                "input_minus_final": "input_minus_final",
            }[label])
            oracle = np.asarray(oracle, dtype=np.float64)
            if oracle.ndim == 2 and probe.ndim == 1:
                oracle = oracle.ravel()
            assert probe.shape == oracle.shape, (case_id, label)
            assert np.array_equal(_bits(probe), _bits(oracle)), (
                case_id, label)


def test_mark_oracle_matches_probe_all_cases() -> None:
    for case_id in [c["case_identifier"] for c in _manifest["cases"]
                    if c["family"] == "inverted"]:
        probe_input = _probe_array(case_id, "input")
        existing = None
        case = _case(case_id)
        if "existing_mask_before" in case["arrays"]:
            existing = _probe_array(case_id, "existing_mask_before")
        ref = mark_oracle.oracle_mark_inverted_rows(probe_input, existing)

        assert _probe_scalar(case_id, "global_mean") == ref.global_mean
        assert _probe_scalar(case_id, "global_rms") == ref.global_rms

        probe_guard = _probe_scalar(case_id, "guard_triggered") != 0.0
        assert probe_guard == ref.guard_triggered

        if ref.guard_triggered:
            continue

        assert np.array_equal(
            _bits(_probe_array(case_id, "row_means")),
            _bits(np.asarray(ref.row_means, dtype=np.float64)))
        assert np.array_equal(
            _bits(_probe_array(case_id, "row_rms")),
            _bits(np.asarray(ref.row_rms, dtype=np.float64)))
        assert np.array_equal(
            _bits(_probe_array(case_id, "raw_correlation_weights")),
            _bits(np.asarray(ref.raw_weights, dtype=np.float64)))
        assert (_probe_scalar(case_id, "has_negative_weight") != 0.0
                ) == bool(ref.has_negative_weight)

        if not ref.has_negative_weight:
            assert case["arrays"]["block_summed_weights"]["count"] == 0
            assert _probe_scalar(case_id, "anchor_index") == -1.0
            assert _probe_scalar(case_id, "would_write_mask_when_no_existing_mask") == 0.0
            assert _probe_scalar(case_id, "would_overwrite_existing_mask") == 0.0
            continue

        assert np.array_equal(
            _bits(_probe_array(case_id, "block_summed_weights")),
            _bits(np.asarray(ref.block_summed_weights, dtype=np.float64)))
        assert int(_probe_scalar(case_id, "anchor_index")) == int(ref.anchor_index)
        assert _probe_scalar(case_id, "anchor_weight") == float(ref.anchor_weight)
        assert np.array_equal(
            _bits(_probe_array(case_id, "generated_binary_mask")),
            _bits(np.asarray(ref.generated_mask, dtype=np.float64)))
        assert _probe_scalar(case_id, "mask_max") == float(ref.mask_max)
        assert (_probe_scalar(case_id, "would_write_mask_when_no_existing_mask")
                != 0.0) == bool(ref.would_create_mask)
        assert (_probe_scalar(case_id, "would_overwrite_existing_mask")
                != 0.0) == bool(ref.would_overwrite_existing_mask)

        # existing-mask semantics
        if ref.existing_mask_before is not None:
            assert np.array_equal(
                _bits(_probe_array(case_id, "existing_mask_before")),
                _bits(np.asarray(ref.existing_mask_before, dtype=np.float64)))
            if ref.existing_mask_after is not None:
                assert np.array_equal(
                    _bits(_probe_array(case_id, "existing_mask_after_overwrite")),
                    _bits(np.asarray(ref.existing_mask_after, dtype=np.float64)))
            else:
                assert np.array_equal(
                    _bits(_probe_array(case_id, "existing_mask_after_operation")),
                    _bits(np.asarray(ref.existing_mask_after, dtype=np.float64)))

        # input non-mutation
        assert np.array_equal(
            _bits(_probe_array(case_id, "input_field_after_operation")),
            _bits(np.asarray(ref.input_after, dtype=np.float64)))


def test_mark_marked_row_sets_and_classifications() -> None:
    """Exact marked-row sets, early-return paths, anchors and overwrite
    classifications for every Mark Inverted case."""
    expectations = {
        "m01_all_positive": ("no_negative_early_return", []),
        "m02_one_inverted_interior": ("detection", [1]),
        "m03_first_inverted": ("detection", [0]),
        "m04_last_inverted": ("detection", [4]),
        "m05_two_consecutive_inverted": ("detection", [2, 3]),
        "m06_alternating": ("detection", [0, 1, 3]),
        "m07_constant_field": ("guard", []),
        "m08_constant_row": ("no_negative_early_return", []),
        "m09_tie_anchor": ("detection", [2, 3]),
        "m10_2x5": ("guard", []),
        "m10_3x2": ("guard", []),
        "m10_3x3": ("detection", [0, 1]),
        "m11_existing_mask_no_inverted": ("no_negative_early_return", []),
        "m12_existing_mask_with_inverted_row": ("detection", [1]),
    }
    for case_id, (path, rows) in expectations.items():
        probe_input = _probe_array(case_id, "input")
        existing = None
        case = _case(case_id)
        if "existing_mask_before" in case["arrays"]:
            existing = _probe_array(case_id, "existing_mask_before")
        ref = mark_oracle.oracle_mark_inverted_rows(probe_input, existing)
        assert ref.guard_triggered == (path == "guard"), case_id
        assert ref.early_return_no_negative == (path == "no_negative_early_return"), case_id
        if path == "detection":
            assert ref.generated_mask is not None
            marked = [int(r) for r in range(ref.generated_mask.shape[0])
                      if np.any(ref.generated_mask[r] == 1.0)]
            assert marked == rows, case_id
            assert int(ref.anchor_index) >= 0, case_id
            assert bool(ref.would_create_mask), case_id
        if path == "no_negative_early_return":
            assert ref.generated_mask is None, case_id
            assert not ref.would_create_mask, case_id
        if path == "guard":
            assert ref.row_means is None, case_id


def test_s11_and_m12_specific_behaviour() -> None:
    # s11: pass 2 changes exactly the middle row, columns 5..10
    p1 = _probe_array("s11_pass2_change", "field_after_pass1")
    p2 = _probe_array("s11_pass2_change", "field_after_pass2")
    changed = np.flatnonzero(_bits(p1).ravel() != _bits(p2).ravel())
    assert list(changed) == [21 + c for c in range(5, 11)]
    # m12: existing mask fully replaced by the generated mask
    m12 = _case("m12_existing_mask_with_inverted_row")
    generated = _probe_array("m12_existing_mask_with_inverted_row",
                             "generated_binary_mask")
    before = _probe_array("m12_existing_mask_with_inverted_row",
                          "existing_mask_before")
    after = _probe_array("m12_existing_mask_with_inverted_row",
                         "existing_mask_after_overwrite")
    assert not np.array_equal(_bits(before), _bits(generated))
    assert np.array_equal(_bits(after), _bits(generated))
    assert m12["scalars"]["would_overwrite_existing_mask"]["hex"] == "0x1p+0"
