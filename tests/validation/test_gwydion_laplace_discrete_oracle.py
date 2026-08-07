"""Oracle tests for the independent mathematical Laplace reference.

Runs the independent discrete boundary-value oracle
(fixtures/oracle_laplace_discrete.py) on the frozen probe inputs and
verifies: bitwise agreement on the exact-path cases, the classified
source-rounding cases (L05/L06 one ULP), the iterative-approximation cases
(L10/L11/L12 within the frozen measured bounds), the whole-field policy,
the calibration pair, and the signed-zero implementation-semantics case.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwydion" / "scars_laplace"
NPZ_PATH = FIXTURE_DIR / "scars_laplace_reference.npz"
JSON_PATH = FIXTURE_DIR / "scars_laplace_reference.json"

LAPLACE_CASES = [
    "L01_empty_mask", "L02_one_interior_pixel", "L03_one_edge_pixel",
    "L04_one_corner_pixel", "L05_horizontal_corridor", "L06_vertical_corridor",
    "L07_three_pixel_L", "L08_interior_rectangle", "L09_two_components",
    "L10_edge_touching", "L11_corner_touching", "L12_entire_masked_row",
    "L13_whole_field_mask", "L14_constant_boundary", "L15_calibration_independence",
    "L16_mask_predicate", "L17_signed_zero", "L18_degenerate",
]

sys.path.insert(0, str(FIXTURE_DIR))
from oracle_laplace_discrete import oracle_laplace_discrete  # noqa: E402  # isort: skip

arrays = dict(np.load(NPZ_PATH, allow_pickle=False))
manifest = json.loads(JSON_PATH.read_text())
PER_CASE = manifest["per_case"]


def _subcases(cid: str) -> list[str | None]:
    if cid == "L18_degenerate":
        return ["L18a_1x1_masked", "L18b_1x1_unmasked", "L18c_1x5",
                "L18d_2x5_full", "L18e_5x1"]
    return [None]


def _key(cid: str, sub: str | None, label: str) -> str:
    return f"{cid}_probe_{label}" if sub is None else f"{cid}_probe_{sub}_{label}"


def test_exact_path_cases_bitwise() -> None:
    for cid in ["L01_empty_mask", "L02_one_interior_pixel",
                "L03_one_edge_pixel", "L04_one_corner_pixel",
                "L07_three_pixel_L", "L08_interior_rectangle",
                "L09_two_components", "L13_whole_field_mask",
                "L14_constant_boundary", "L16_mask_predicate"]:
        for sub in _subcases(cid):
            ref = oracle_laplace_discrete(
                arrays[_key(cid, sub, "input")],
                arrays[_key(cid, sub, "input_mask")],
                probe_corrected=arrays[_key(cid, sub, "corrected")])
            assert ref.elements_bitwise_exact == ref.elements_total, sub
            assert ref.unmasked_mutation_count == 0, sub
            assert ref.signed_zero_mismatches == 0, sub


def test_corridor_one_ulp_characterization() -> None:
    for cid in ["L05_horizontal_corridor", "L06_vertical_corridor"]:
        sub = PER_CASE[cid]["subcases"][0]
        assert sub["max_ulp_difference"] == 1, cid
        assert sub["max_absolute_difference"] == 8.881784197001252e-16, cid
        assert sub["path_class"] == "thin/tridiagonal source path", cid
        ref = oracle_laplace_discrete(
            arrays[f"{cid}_probe_input"],
            arrays[f"{cid}_probe_input_mask"],
            probe_corrected=arrays[f"{cid}_probe_corrected"])
        assert ref.max_ulp_difference == 1
        assert ref.max_absolute_difference == 8.881784197001252e-16
        # the deviation is in the probe (source tridiagonal rounding); the
        # mathematical reference reproduces the exact ramp
        cor = ref.corrected_float64
        if cid == "L06_vertical_corridor":
            assert cor[3, 3] == 6.0
            assert arrays[f"{cid}_probe_corrected"][3, 3] == 5.999999999999999
        else:
            assert cor[2, 3] == 5.0
            assert arrays[f"{cid}_probe_corrected"][2, 3] == 4.999999999999999


def test_iterative_cases_within_frozen_bounds() -> None:
    for cid in ["L10_edge_touching", "L11_corner_touching",
                "L12_entire_masked_row"]:
        sub = PER_CASE[cid]["subcases"][0]
        assert sub["max_ulp_difference"] <= 2, cid
        assert sub["max_absolute_difference"] <= 1.8e-15, cid
        assert sub["path_class"] == "iterative sparse/dense source path", cid
        ref = oracle_laplace_discrete(
            arrays[f"{cid}_probe_input"],
            arrays[f"{cid}_probe_input_mask"],
            probe_corrected=arrays[f"{cid}_probe_corrected"])
        assert ref.unmasked_mutation_count == 0, cid
        assert float(ref.mathematical_residual) < 1e-75, cid


def test_whole_field_and_empty_policies() -> None:
    ref = oracle_laplace_discrete(
        arrays["L13_whole_field_mask_probe_input"],
        arrays["L13_whole_field_mask_probe_input_mask"])
    assert ref.whole_field_mask
    assert ref.singular_policy_applied
    assert not np.any(ref.corrected_float64 != 0.0)
    ref2 = oracle_laplace_discrete(
        arrays["L01_empty_mask_probe_input"],
        arrays["L01_empty_mask_probe_input_mask"])
    assert ref2.empty_mask
    assert np.array_equal(
        ref2.corrected_float64.view(np.uint64),
        arrays["L01_empty_mask_probe_input"].view(np.uint64))


def test_calibration_independence_pair() -> None:
    sub = PER_CASE["L15_calibration_independence"]["subcases"][0]
    assert sub["path_class"] == "calibration-independence pair"
    a = arrays["L15_calibration_independence_probe_corrected_a"]
    b = arrays["L15_calibration_independence_probe_corrected_b"]
    assert np.array_equal(a.view(np.uint64), b.view(np.uint64))
    ref = oracle_laplace_discrete(
        arrays["L15_calibration_independence_probe_input"],
        arrays["L15_calibration_independence_probe_mask_after_a"])
    assert ref.elements_bitwise_exact == ref.elements_total


def test_signed_zero_classification() -> None:
    sub = PER_CASE["L17_signed_zero"]["subcases"][0]
    assert sub["path_class"] == "signed-zero implementation case"
    assert sub["signed_zero_mismatches"] == 1
    assert sub["max_absolute_difference"] == 0.0
    assert sub["max_ulp_difference"] == 0
    ref = oracle_laplace_discrete(
        arrays["L17_signed_zero_probe_input"],
        arrays["L17_signed_zero_probe_input_mask"],
        probe_corrected=arrays["L17_signed_zero_probe_corrected"])
    # values are equal (0.0 == -0.0); the sign differs at the masked pixel
    assert ref.max_absolute_difference == 0.0
    assert ref.signed_zero_mismatches == 1
    assert ref.unmasked_mutation_count == 0
    probe_bits = arrays["L17_signed_zero_probe_corrected"].view(np.uint64)
    assert int(probe_bits[2, 2]) == 0x8000000000000000


def test_degenerate_subcases() -> None:
    ref = oracle_laplace_discrete(
        arrays["L18_degenerate_probe_L18a_1x1_masked_input"],
        arrays["L18_degenerate_probe_L18a_1x1_masked_input_mask"])
    assert ref.whole_field_mask
    assert ref.corrected_float64[0, 0] == 0.0
    ref_b = oracle_laplace_discrete(
        arrays["L18_degenerate_probe_L18b_1x1_unmasked_input"],
        arrays["L18_degenerate_probe_L18b_1x1_unmasked_input_mask"])
    assert ref_b.empty_mask
    assert ref_b.corrected_float64[0, 0] == 7.0
    for sub in ["L18c_1x5", "L18e_5x1"]:
        refc = oracle_laplace_discrete(
            arrays[f"L18_degenerate_probe_{sub}_input"],
            arrays[f"L18_degenerate_probe_{sub}_input_mask"],
            probe_corrected=arrays[f"L18_degenerate_probe_{sub}_corrected"])
        assert refc.elements_bitwise_exact == refc.elements_total, sub


def test_mask_predicate_strict_positive() -> None:
    ref = oracle_laplace_discrete(
        arrays["L16_mask_predicate_probe_input"],
        arrays["L16_mask_predicate_probe_input_mask"])
    assert len(ref.masked_coordinates) == 7
    # pixels with mask 0.0 and -1.0 are fixed and bitwise unchanged
    assert ref.unmasked_mutation_count == 0
    mask = arrays["L16_mask_predicate_probe_input_mask"]
    for i in range(mask.size):
        if mask.ravel()[i] <= 0.0:
            assert ref.corrected_float64.ravel()[i] == \
                arrays["L16_mask_predicate_probe_input"].ravel()[i]


def test_oracle_never_reads_expected_outputs() -> None:
    import inspect

    import oracle_laplace_discrete as old
    source = inspect.getsource(old)
    assert "reference.json" not in source
    assert "reference.npz" not in source
    assert "np.load" not in source
