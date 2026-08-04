"""Oracle tests for the independent Mark Scars reference.

Runs the independent oracle (fixtures/oracle_mark_scars.py) on the frozen
probe inputs and verifies bitwise agreement with the frozen probe masks and
classifications for all 22 Mark Scars cases.  Effective parameters are read
from the frozen manifest, never hardcoded here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwydion" / "scars_laplace"
NPZ_PATH = FIXTURE_DIR / "scars_laplace_reference.npz"
JSON_PATH = FIXTURE_DIR / "scars_laplace_reference.json"

MARK_CASES = [
    "C01_constant_field", "C02_positive_hard_seeded", "C03_negative_hard_seeded",
    "C04_both_polarities", "C05_soft_only_no_seed", "C06_hard_with_soft_shoulder",
    "C07_detached_soft_run", "C08_width_exactly_max", "C09_width_max_plus_one",
    "C10_length_exactly_min", "C11_length_min_minus_one", "C12_run_touching_edges",
    "C13_first_last_row", "C14_adjacent_bands_fmax", "C15_min_dims",
    "C16_threshold_sanitize", "C17_existing_replace", "C18_existing_union",
    "C19_existing_intersection", "C20_no_detection_existing",
    "C20b_no_detection_existing_union", "C21_signed_zero",
]

sys.path.insert(0, str(FIXTURE_DIR))
from oracle_mark_scars import oracle_mark_scars  # noqa: E402  # isort: skip

arrays = dict(np.load(NPZ_PATH, allow_pickle=False))
manifest = json.loads(JSON_PATH.read_text())
CASES = {c["case_identifier"]: c for c in manifest["cases"]}


def test_all_mark_cases_bitwise_exact() -> None:
    for full in MARK_CASES:
        case = CASES[full]
        ints = case["ints"]
        scalars = case["scalars"]
        existing = (arrays[f"{full}_probe_existing_before"]
                    if "existing_before" in case["arrays"] else None)
        ref = oracle_mark_scars(
            arrays[f"{full}_probe_input"],
            threshold_high=float.fromhex(scalars["threshold_high"]["hex"]),
            threshold_low=float.fromhex(scalars["threshold_low"]["hex"]),
            min_length=ints["min_len"],
            max_width=ints["max_width"],
            polarity=ints["polarity_enum"],
            existing_mask=existing,
            combine=bool(ints.get("combine", 0)),
            combine_type=ints.get("combine_type", 0))
        label = ("module_mask" if "module_mask" in case["arrays"]
                 else "kernel_mask")
        probe_mask = arrays[f"{full}_probe_{label}"]
        assert np.array_equal(
            probe_mask.view(np.uint64), ref.final_module_mask.view(np.uint64)), \
            f"{full}: mask not bitwise exact"
        assert ref.nonzero_count == int(np.count_nonzero(probe_mask)), full
        assert ref.mask_present == bool(np.any(probe_mask == 1.0)), full
        assert ref.mask_present == bool(ints["module_mask_present"]), full
        assert np.array_equal(
            arrays[f"{full}_probe_input"].view(np.uint64),
            arrays[f"{full}_probe_input_after"].view(np.uint64)), full
        if existing is not None:
            assert np.array_equal(
                existing.view(np.uint64),
                arrays[f"{full}_probe_existing_after"].view(np.uint64)), full
        # runs recorded by the oracle must be reconstructable from the mask
        rebuilt = []
        mask = probe_mask
        for i in range(mask.shape[0]):
            j = 0
            while j < mask.shape[1]:
                if mask[i, j] != 0.0:
                    start = j
                    while j < mask.shape[1] and mask[i, j] != 0.0:
                        j += 1
                    rebuilt.append((i, start, j - start))
                else:
                    j += 1
        assert sorted(rebuilt) == sorted(ref.marked_runs), full


def test_effective_threshold_sanitization() -> None:
    case = CASES["C16_threshold_sanitize"]
    ref = oracle_mark_scars(
        arrays["C16_threshold_sanitize_probe_input"],
        threshold_high=float.fromhex(case["scalars"]["threshold_high"]["hex"]),
        threshold_low=float.fromhex(case["scalars"]["threshold_low"]["hex"]),
        min_length=case["ints"]["min_len"],
        max_width=case["ints"]["max_width"],
        polarity=case["ints"]["polarity_enum"])
    assert ref.effective_threshold_high == 0.666
    assert ref.effective_threshold_low == 0.666
    assert float.fromhex(
        case["scalars"]["effective_threshold_high"]["hex"]) == 0.666
    assert float.fromhex(
        case["scalars"]["effective_threshold_low"]["hex"]) == 0.666


def test_runs_and_marked_rows() -> None:
    ref = oracle_mark_scars(
        arrays["C04_both_polarities_probe_input"],
        threshold_high=0.666, threshold_low=0.25, min_length=4, max_width=1,
        polarity=3)
    assert ref.marked_runs == ((3, 0, 10), (8, 0, 10))
    assert ref.nonzero_count == 20
    ref2 = oracle_mark_scars(
        arrays["C14_adjacent_bands_fmax_probe_input"],
        threshold_high=0.666, threshold_low=0.25, min_length=4, max_width=2,
        polarity=1)
    assert ref2.nonzero_count == 16
    assert {r[0] for r in ref2.marked_runs} == {3, 4}


def test_guard_paths() -> None:
    ref = oracle_mark_scars(
        arrays["C01_constant_field_probe_input"],
        threshold_high=0.666, threshold_low=0.25, min_length=2, max_width=1,
        polarity=3)
    assert ref.guard_triggered
    assert ref.guard_reason == "vertical rms == 0"
    assert ref.nonzero_count == 0
    assert not ref.mask_present
    ref2 = oracle_mark_scars(
        arrays["C15_min_dims_probe_input"],
        threshold_high=0.666, threshold_low=0.25, min_length=1, max_width=1,
        polarity=1)
    assert not ref2.guard_triggered
    assert ref2.nonzero_count == 2


def test_finite_input_policy() -> None:
    field = np.zeros((4, 4))
    field[1, 1] = np.nan
    try:
        oracle_mark_scars(field)
    except ValueError:
        pass
    else:
        raise AssertionError("NaN input must be rejected")
    field[1, 1] = np.inf
    try:
        oracle_mark_scars(field)
    except ValueError:
        pass
    else:
        raise AssertionError("Inf input must be rejected")


def test_oracle_never_reads_expected_outputs() -> None:
    import inspect

    import oracle_mark_scars as oms
    source = inspect.getsource(oms)
    assert "reference.json" not in source
    assert "reference.npz" not in source
    assert "np.load" not in source
