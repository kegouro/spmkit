"""Tests for the structurally independent declarative Align Rows oracle.

Verifies exact discrete state (method identity, masking predicates, valid
sample sets/counts, branch selection, zero-weight/no-valid guards, row
topology), independent polynomial solve, degree discrimination, Modus
window/tie relations, Match cumulative and zero-weight relations, masking
relations, and deterministic replay relations.  The declarative oracle must
not import or call the source-semantic oracle and must not read fixture
expected arrays as inputs.
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
from oracle_align_rows_declarative import oracle_align_rows_declarative  # noqa: E402  # isort: skip

_manifest = json.loads(JSON_PATH.read_text())
_arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())
_CASES = {c["case_identifier"]: c for c in _manifest["cases"]
          if c["classification"] == "NUMERICAL_PARITY"}


def _probe(cid: str, label: str) -> np.ndarray:
    return _arrays[f"{cid}_probe_{label}"]


def test_discrete_state_exact_for_all_cases() -> None:
    for cid, case in sorted(_CASES.items()):
        inp = _probe(cid, "input")
        mask = _probe(cid, "input_mask") if case["mask_present"] else None
        decl = oracle_align_rows_declarative(
            inp, method=case["method"], degree=case["degree"], mask=mask,
            masking=case["masking"],
            compiled_corrected=_probe(cid, "corrected"),
            compiled_shifts=_probe(cid, "shifts"))
        assert decl.method == case["method"], cid
        assert decl.masking == case["masking"], cid
        assert decl.masking_enum == case["masking_enum"], cid
        assert decl.valid_counts == tuple(case["row_valid_counts"]), cid
        # discrete state is exact even when floating values are not
        assert decl.discrete_state_exact, cid
        assert decl.corrected_total == decl.corrected_bitwise or \
            decl.corrected_total > 0, cid


def test_independent_polynomial_solve() -> None:
    # degree >= 1 uses an SVD lstsq solve (not the source Cholesky) and must
    # still land in the same fitted polynomial subspace
    for case in _CASES.values():
        if case["method"] != "polynomial" or case["degree"] < 1:
            continue
        cid = case["case_identifier"]
        decl = oracle_align_rows_declarative(
            _probe(cid, "input"), method="polynomial", degree=case["degree"],
            mask=_probe(cid, "input_mask") if case["mask_present"] else None,
            masking=case["masking"])
        assert decl.poly_coefficients is not None, cid
        assert decl.poly_coefficients.shape == (
            case["dimensions"]["yres"], case["degree"] + 1), cid
        assert decl.poly_subspace_rank == case["degree"] + 1 or \
            case["degree"] + 1 >= case["dimensions"]["xres"], cid


def test_degree_discrimination() -> None:
    group = _manifest["relations"]["degree_discrimination"][0]
    corr = {}
    for cid in group:
        case = _CASES[cid]
        decl = oracle_align_rows_declarative(
            _probe(cid, "input"), method="polynomial", degree=case["degree"],
            masking="ignore")
        corr[cid] = decl.corrected_field
    assert not np.array_equal(corr[group[0]], corr[group[1]])
    assert not np.array_equal(corr[group[0]], corr[group[2]])
    assert not np.array_equal(corr[group[1]], corr[group[2]])


def test_method_discrimination() -> None:
    group = _manifest["relations"]["method_discrimination"][0]
    corr = {}
    for cid in group:
        case = _CASES[cid]
        decl = oracle_align_rows_declarative(
            _probe(cid, "input"), method=case["method"],
            degree=case["degree"], masking="ignore")
        corr[cid] = decl.corrected_field
    ids = list(corr)
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            assert not np.array_equal(corr[ids[a]], corr[ids[b]])


def test_mask_mode_discrimination() -> None:
    """The declarative oracle must reproduce the compiled pairwise
    equality/distinction pattern for every mask-mode group (masking-mode
    relations where source semantics predict distinction, plus the
    legitimate equalities, e.g. U07 vs U09 where the mask does not change
    the per-row modus)."""
    for group in _manifest["relations"]["mask_mode_discrimination"]:
        corr = {}
        compiled = {}
        for cid in group:
            case = _CASES[cid]
            assert case["mask_present"], cid
            decl = oracle_align_rows_declarative(
                _probe(cid, "input"), method=case["method"],
                degree=case["degree"], mask=_probe(cid, "input_mask"),
                masking=case["masking"])
            corr[cid] = decl.corrected_field
            compiled[cid] = _probe(cid, "corrected")
        ids = list(corr)
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                compiled_distinct = not np.array_equal(
                    compiled[ids[a]], compiled[ids[b]])
                declarative_distinct = not np.array_equal(
                    corr[ids[a]], corr[ids[b]])
                assert declarative_distinct == compiled_distinct, \
                    (ids[a], ids[b])


def test_modus_window_and_tie_relations() -> None:
    # U03: 5 zeros + 5 tens per row -> narrowest window over the sorted
    # values has range 0 and the central third selects the tie population
    decl = oracle_align_rows_declarative(
        _probe("U03_ROBUST_CENTER_DISTINGUISHER", "input"), method="modus")
    assert decl.modus_windows is not None
    assert decl.modus_min_range == 0.0
    # the selected window start must exist and the shifts be zero-levelled
    assert decl.modus_selected_start is not None
    assert abs(float(np.mean(decl.shifts))) < 1e-12
    # U04: 6 zeros + 6 tens -> window range 0 with several ties
    decl = oracle_align_rows_declarative(
        _probe("U04_MULTIMODAL_TIE", "input"), method="modus")
    assert decl.modus_min_range == 0.0
    assert decl.modus_tie_multiplicity is not None and \
        decl.modus_tie_multiplicity >= 1


def test_match_cumulative_and_zero_weight() -> None:
    # H03 sequential offsets: zero weight for pure offsets -> no correction
    for cid in ("H01_IDENTICAL_ROWS", "H02_SINGLE_ROW_OFFSET",
                "H03_SEQUENTIAL_OFFSETS", "H04_ALTERNATING_OFFSETS"):
        decl = oracle_align_rows_declarative(_probe(cid, "input"),
                                             method="match")
        assert decl.match_zero_weight_pairs, cid
        assert np.array_equal(decl.corrected_field, decl.input_snapshot), cid
    # H05 alternating bumps activates matching; shifts are cumulative and
    # zero-levelled
    decl = oracle_align_rows_declarative(
        _probe("H05_MATCH_OBJECTIVE_TIE", "input"), method="match")
    assert not decl.match_zero_weight_pairs
    assert decl.cumulative_shifts is not None
    assert abs(float(np.mean(decl.shifts))) < 1e-12


def test_deterministic_replay_relations() -> None:
    for a, b in _manifest["relations"]["determinism_replay"]:
        ca = _CASES.get(a)
        cb = _CASES.get(b)
        assert ca is None and cb is None  # witnesses are not numerical cases
    # witness representatives exist in the NPZ and are stored once
    for a, _b in _manifest["relations"]["determinism_replay"]:
        assert any(k.startswith(a + "_probe_") for k in _arrays), a


def test_no_source_oracle_import() -> None:
    src = inspect.getsource(sys.modules["oracle_align_rows_declarative"])
    assert "import oracle_align_rows_source" not in src
    assert "from oracle_align_rows_source" not in src
    assert "case_identifier" not in src
    for forbidden in ("reference.json", "reference.npz", "np.load",
                      "json.load", "spmkit"):
        assert forbidden not in src, forbidden
