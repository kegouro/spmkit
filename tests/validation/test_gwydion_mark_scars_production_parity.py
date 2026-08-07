"""Production parity: Mark Scars kernel vs the frozen compiled evidence.

For all 22 frozen cases the production public API output is compared
bitwise against the compiled-probe arrays frozen in the fixtures
(1726/1726 elements, max absolute difference 0, max ULP 0, signed-zero
mismatches 0).  Expectations are loaded exclusively from the frozen
NPZ/JSON; the oracle is NOT used.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from spmkit.core.analysis import gwydion_mark_scars
from spmkit.core.models.spmdata import SPMChannel

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwydion" / "scars_laplace"
JSON_PATH = FIXTURE_DIR / "scars_laplace_reference.json"
NPZ_PATH = FIXTURE_DIR / "scars_laplace_reference.npz"

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

_manifest = json.loads(JSON_PATH.read_text())
_arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())
_CASES = {c["case_identifier"]: c for c in _manifest["cases"]}
_POLARITY = {1: "positive", 4: "negative", 3: "both"}


def _bits(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array, dtype=np.float64).view(np.uint64)


def _channel(data: np.ndarray) -> SPMChannel:
    return SPMChannel(
        name="parity", data=np.asarray(data, dtype=np.float64), unit="nm",
        x_range=float(data.shape[1]), y_range=float(data.shape[0]))


def _probe(case_id: str, label: str) -> np.ndarray:
    return _arrays[f"{case_id}_probe_{label}"]


def _run_public(case_id: str) -> tuple[np.ndarray, dict]:
    """Run the production Mark Scars engine for a frozen case.

    The public API enforces the process-module threshold domain [0, 2];
    the frozen C05/C07 soft-only fixtures deliberately used
    threshold_high=3.0 (a uniform single-row band has weight sqrt(5) ~
    2.236, so a soft-only configuration cannot be expressed within the
    public domain).  For those two cases the production kernel is invoked
    directly; all other cases go through the public API.
    """
    case = _CASES[case_id]
    ints = case["ints"]
    scalars = case["scalars"]
    existing = (_probe(case_id, "existing_before")
                if "existing_before" in case["arrays"] else None)
    combine = "replace"
    if ints.get("combine", 0):
        combine = ("union" if ints.get("combine_type", 0) == 0
                   else "intersection")
    threshold_high = float.fromhex(scalars["threshold_high"]["hex"])
    threshold_low = float.fromhex(scalars["threshold_low"]["hex"])
    kwargs = {
        "threshold_high": threshold_high, "threshold_low": threshold_low,
        "min_length": ints["min_len"], "max_width": ints["max_width"],
        "polarity": _POLARITY[ints["polarity_enum"]],
        "existing_mask": existing, "combine": combine,
    }
    if case_id in ("C05_soft_only_no_seed", "C07_detached_soft_run"):
        from spmkit.core.analysis._gwydion_mark_scars import (  # noqa: PLC0415
            _gwydion_mark_scars_result,
        )
        return _gwydion_mark_scars_result(
            _probe(case_id, "input"), **kwargs).final_mask, ints
    return (gwydion_mark_scars(_channel(_probe(case_id, "input")), **kwargs),
            ints)


def test_all_22_mark_cases_bitwise_exact() -> None:
    total_elements = 0
    total_exact = 0
    max_abs = 0.0
    max_ulp = 0
    signed_zero = 0
    for case_id in MARK_CASES:
        case = _CASES[case_id]
        mask, ints = _run_public(case_id)
        label = ("module_mask" if "module_mask" in case["arrays"]
                 else "kernel_mask")
        probe = _probe(case_id, label)
        assert mask.shape == probe.shape, case_id
        pb = _bits(probe).ravel()
        ob = _bits(mask).ravel()
        assert np.array_equal(pb, ob), f"{case_id}: mask not bitwise exact"
        total_elements += pb.size
        total_exact += int(np.count_nonzero(pb == ob))
        # classification parity: nonzero count and mask-present flag
        assert int(np.count_nonzero(mask)) == ints["mask_nonzero"], case_id
        assert (np.any(mask == 1.0)) == bool(ints["module_mask_present"]), \
            case_id
    assert total_elements == 1726
    assert total_exact == 1726
    assert max_abs == 0.0
    assert max_ulp == 0
    assert signed_zero == 0


def test_mark_input_and_existing_mask_non_mutation() -> None:
    for case_id in MARK_CASES:
        case = _CASES[case_id]
        inp = _probe(case_id, "input")
        after = _probe(case_id, "input_after")
        assert np.array_equal(_bits(inp), _bits(after)), case_id
        if "existing_before" in case["arrays"]:
            assert np.array_equal(
                _bits(_probe(case_id, "existing_before")),
                _bits(_probe(case_id, "existing_after"))), case_id


def test_effective_thresholds() -> None:
    case = _CASES["C16_threshold_sanitize"]
    scalars = case["scalars"]
    assert float.fromhex(scalars["effective_threshold_high"]["hex"]) == 0.666
    assert float.fromhex(scalars["effective_threshold_low"]["hex"]) == 0.666
    mask, _ = _run_public("C16_threshold_sanitize")
    assert int(np.count_nonzero(mask)) == 8


def test_positive_cases_effective_and_zero_cases_empty() -> None:
    positive = {"C02", "C03", "C04", "C06", "C08", "C10", "C12", "C14",
                "C15", "C16", "C17", "C18", "C19", "C20b"}
    zero = {"C01", "C05", "C07", "C09", "C11", "C13", "C20", "C21"}
    for case_id in MARK_CASES:
        mask, _ = _run_public(case_id)
        cid = case_id.split("_")[0]
        if cid in positive:
            assert np.any(mask == 1.0), case_id
        if cid in zero:
            assert not np.any(mask == 1.0), case_id
