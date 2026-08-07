"""Tests for the exact source-semantic Align Rows oracle.

All 62 canonical NUMERICAL_PARITY cases must reproduce the frozen compiled
probe bitwise for every source-observable quantity (corrected, background,
delta, shifts, per-row valid lists/counts/shifts/status).  The explicit
degree-0 and degree>=1 polynomial branches, all masking modes, insufficient
sample fallbacks, Match zero-weight behavior and signed-zero cases are
exercised.  Non-finite rejection is tested; the oracle must never read
fixture expected outputs or import production code.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import numpy as np

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwyddion" / \
    "align_rows_remaining"
NPZ_PATH = FIXTURE_DIR / "align_rows_remaining_reference.npz"
JSON_PATH = FIXTURE_DIR / "align_rows_remaining_reference.json"

sys.path.insert(0, str(FIXTURE_DIR))
from oracle_align_rows_source import oracle_align_rows_source  # noqa: E402  # isort: skip

_manifest = json.loads(JSON_PATH.read_text())
_arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())
_CASES = {c["case_identifier"]: c for c in _manifest["cases"]
          if c["classification"] == "NUMERICAL_PARITY"}
_METHODS = {"polynomial", "modus", "match"}
_MASKINGS = {"ignore", "include", "exclude"}


def _bits(a: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(a, dtype=np.float64).view(np.uint64)


def _probe(cid: str, label: str) -> np.ndarray:
    return _arrays[f"{cid}_probe_{label}"]


def test_all_62_numerical_cases_bitwise() -> None:
    for cid, case in sorted(_CASES.items()):
        inp = _probe(cid, "input")
        mask = _probe(cid, "input_mask") if case["mask_present"] else None
        ref = oracle_align_rows_source(
            inp, method=case["method"], degree=case["degree"],
            mask=mask, masking=case["masking"])
        assert ref.method == case["method"], cid
        assert ref.masking == case["masking"], cid
        assert ref.masking_enum == case["masking_enum"], cid
        assert ref.xres == case["dimensions"]["xres"], cid
        assert ref.yres == case["dimensions"]["yres"], cid
        # corrected / bg / delta / shifts bitwise
        assert np.array_equal(_bits(ref.corrected_field),
                              _probe(cid, "corrected").view(np.uint64)), cid
        assert np.array_equal(_bits(ref.background_field),
                              _probe(cid, "bg").view(np.uint64)), cid
        assert np.array_equal(_bits(ref.delta_field),
                              _probe(cid, "delta").view(np.uint64)), cid
        assert np.array_equal(_bits(ref.shifts),
                              _probe(cid, "shifts").view(np.uint64)), cid
        # row level
        assert ref.row_valid_counts == tuple(case["row_valid_counts"]), cid
        assert ref.row_status == tuple(case["row_status"]), cid
        # input / mask non-mutation
        assert np.array_equal(_bits(inp), _bits(_probe(cid, "input_after"))), \
            cid
        if case["mask_present"]:
            assert np.array_equal(_bits(mask), _bits(_probe(cid, "mask_after"))), \
                cid


def test_degree0_and_degree_ge1_branches_explicit() -> None:
    """Degree 0 must dispatch to the row-shift path, degree >= 1 to the
    Cholesky polynomial fit; both must pass bitwise."""
    deg0 = [c for c in _CASES.values()
            if c["method"] == "polynomial" and c["degree"] == 0]
    degge1 = [c for c in _CASES.values()
              if c["method"] == "polynomial" and c["degree"] >= 1]
    assert deg0 and degge1
    # degree-0 shifts are zero-levelled row statistics
    for case in deg0:
        cid = case["case_identifier"]
        ref = oracle_align_rows_source(
            _probe(cid, "input"), method="polynomial", degree=0,
            mask=_probe(cid, "input_mask") if case["mask_present"] else None,
            masking=case["masking"])
        assert abs(float(np.mean(ref.shifts))) < 1e-12, cid
        assert ref.poly_coefficients is None, cid
    # degree >= 1 exposes per-row coefficients
    for case in degge1[:3]:
        cid = case["case_identifier"]
        ref = oracle_align_rows_source(
            _probe(cid, "input"), method="polynomial", degree=case["degree"],
            mask=_probe(cid, "input_mask") if case["mask_present"] else None,
            masking=case["masking"])
        assert ref.poly_coefficients is not None, cid
        assert ref.poly_coefficients.shape == (
            case["dimensions"]["yres"], case["degree"] + 1), cid


def test_all_masking_modes() -> None:
    modes = {case["masking"] for case in _CASES.values()}
    assert modes == _MASKINGS
    for cid, case in _CASES.items():
        if not case["mask_present"]:
            continue
        ref = oracle_align_rows_source(
            _probe(cid, "input"), method=case["method"],
            degree=case["degree"], mask=_probe(cid, "input_mask"),
            masking=case["masking"])
        # valid lists are recomputed from the mask predicate
        assert ref.row_valid_counts == tuple(case["row_valid_counts"]), cid


def test_insufficient_and_no_valid_guards() -> None:
    # P14: degree 3 with 3 valid samples per row -> guard fails, row
    # corrected by -avg only
    ref = oracle_align_rows_source(
        _probe("P14_INSUFFICIENT_VALID_SAMPLES", "input"),
        method="polynomial", degree=3,
        mask=_probe("P14_INSUFFICIENT_VALID_SAMPLES", "input_mask"),
        masking="include")
    for i in range(ref.yres):
        assert ref.poly_coefficients[i, 1:].sum() == 0.0, i
    # U10: no valid samples under INCLUDE -> zero shifts, no correction
    ref = oracle_align_rows_source(
        _probe("U10_NO_VALID_SAMPLES", "input"), method="modus",
        mask=_probe("U10_NO_VALID_SAMPLES", "input_mask"),
        masking="include")
    assert np.array_equal(_bits(ref.shifts),
                          np.zeros(ref.shifts.size).view(np.uint64))
    assert np.array_equal(_bits(ref.corrected_field),
                          _bits(ref.input_snapshot))


def test_match_zero_weight_behavior() -> None:
    # pure-offset rows produce wsum==0 -> no correction (H01-H04, H12)
    for cid in ("H01_IDENTICAL_ROWS", "H02_SINGLE_ROW_OFFSET",
                "H03_SEQUENTIAL_OFFSETS", "H04_ALTERNATING_OFFSETS",
                "H12_YRES_ONE"):
        ref = oracle_align_rows_source(_probe(cid, "input"), method="match")
        assert np.array_equal(_bits(ref.corrected_field),
                              _bits(ref.input_snapshot)), cid
        assert all(w == 0.0 for w in (ref.match_pair_wsum0 or ())), cid


def test_signed_zero_cases() -> None:
    for cid in ("P17_SIGNED_ZERO_D0", "P17_SIGNED_ZERO_D1",
                "U12_SIGNED_ZERO", "H15_SIGNED_ZERO"):
        case = _CASES[cid]
        inp = _probe(cid, "input")
        ref = oracle_align_rows_source(
            inp, method=case["method"], degree=case["degree"],
            masking=case["masking"])
        assert np.array_equal(_bits(ref.corrected_field),
                              _probe(cid, "corrected").view(np.uint64)), cid


def test_non_finite_rejection() -> None:
    bad = np.array([[1.0, 2.0], [3.0, np.inf]])
    for method in ("polynomial", "modus", "match"):
        try:
            oracle_align_rows_source(bad, method=method)
        except ValueError as e:
            assert "finite" in str(e)
        else:
            raise AssertionError(f"{method} accepted non-finite input")
    nan = np.array([[1.0, np.nan], [3.0, 4.0]])
    try:
        oracle_align_rows_source(nan, method="polynomial")
    except ValueError as e:
        assert "finite" in str(e)
    else:
        raise AssertionError("polynomial accepted NaN input")


def test_no_fixture_reads_no_production_imports() -> None:
    src = inspect.getsource(sys.modules["oracle_align_rows_source"])
    for forbidden in ("reference.json", "reference.npz", "np.load",
                      "json.load", "spmkit", "campaign_checker",
                      "oracle_align_rows_declarative"):
        assert forbidden not in src, forbidden
    # oracle accepts no case identifiers: it must not branch on names
    assert "case_identifier" not in src
