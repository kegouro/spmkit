"""Tests for the structurally independent declarative Step Block oracle."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwydion" / "step_block"
NPZ_PATH = FIXTURE_DIR / "step_block_reference.npz"
JSON_PATH = FIXTURE_DIR / "step_block_reference.json"

sys.path.insert(0, str(FIXTURE_DIR))
from oracle_step_block_declarative import oracle_step_block_declarative  # noqa: E402  # isort: skip

_manifest = json.loads(JSON_PATH.read_text())
_arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())


def _probe(cid, label):
    return _arrays[f"{cid}_probe_{label}"]


def test_discrete_state_exact_for_all_valid_cases() -> None:
    for case in _manifest["cases"]:
        cid = case["case_identifier"]
        inp = _probe(cid, "input")
        decl = oracle_step_block_declarative(
            inp, threshold_param=case["threshold_param"],
            direction=case["direction"], xreal=case["xreal"], yreal=case["yreal"],
            compiled_corrected=_probe(cid, "corrected"),
            compiled_block_shifts=case["block_shifts"])
        assert decl.block_count == case["block_count"], cid
        assert decl.split_positions[0] == 0  # row 0 has no computed split
        # block topology: retained boundary rows match the manifest
        manifest_rows = [case["boundaries"][k] + 0 for k in range(case["block_count"])]
        decl_rows = [b[0] for b in decl.retained_boundaries]
        assert decl_rows == manifest_rows, cid
        # trimmed central multiset: sorted central values match the manifest
        # block shifts for analytical cases (exact integers)
        for k in range(decl.block_count):
            central = decl.trimmed_central_multiset[k]
            assert abs(sum(central) / len(central) -
                       case["block_shifts"][k]) < 1e-9, cid


def test_analytical_trimmed_mean_cases() -> None:
    # S23: 4 zeros + 8 fives + 4 tens -> central 8 fives -> mean exactly 5.0
    case = next(c for c in _manifest["cases"]
                if c["case_identifier"] == "S23_TRIMMED_MEAN_OUTLIERS")
    decl = oracle_step_block_declarative(
        _probe("S23_TRIMMED_MEAN_OUTLIERS", "input"),
        threshold_param=case["threshold_param"], direction="left_to_right",
        xreal=case["xreal"], yreal=case["yreal"])
    assert decl.trimmed_mean_sorted == (5.0,)
    assert decl.trimmed_central_multiset == ((5.0, 5.0, 5.0, 5.0, 5.0, 5.0,
                                              5.0, 5.0),)
    # S24: 4 zeros + 12 fives -> central 8 fives -> 5.0
    case = next(c for c in _manifest["cases"]
                if c["case_identifier"] == "S24_TRIMMED_MEAN_TIES")
    decl = oracle_step_block_declarative(
        _probe("S24_TRIMMED_MEAN_TIES", "input"),
        threshold_param=case["threshold_param"], direction="left_to_right",
        xreal=case["xreal"], yreal=case["yreal"])
    assert decl.trimmed_mean_sorted == (5.0,)


def test_lt_rtl_relationship() -> None:
    c2 = next(c for c in _manifest["cases"]
              if c["case_identifier"] == "S02_SINGLE_POSITIVE_STEP_LTR")
    c18 = next(c for c in _manifest["cases"]
               if c["case_identifier"] == "S18_RIGHT_TO_LEFT_SINGLE_STEP")
    a = oracle_step_block_declarative(
        _probe("S02_SINGLE_POSITIVE_STEP_LTR", "input"),
        threshold_param=c2["threshold_param"], direction="left_to_right",
        xreal=c2["xreal"], yreal=c2["yreal"])
    b = oracle_step_block_declarative(
        _probe("S18_RIGHT_TO_LEFT_SINGLE_STEP", "input"),
        threshold_param=c18["threshold_param"], direction="right_to_left",
        xreal=c18["xreal"], yreal=c18["yreal"])
    assert np.array_equal(a.corrected_field.view(np.uint64),
                          b.corrected_field.view(np.uint64))


def test_threshold_exact_behavior() -> None:
    case = next(c for c in _manifest["cases"]
                if c["case_identifier"] == "S11_THRESHOLD_EXACT")
    decl = oracle_step_block_declarative(
        _probe("S11_THRESHOLD_EXACT", "input"),
        threshold_param=case["threshold_param"], direction="left_to_right",
        xreal=case["xreal"], yreal=case["yreal"])
    assert decl.block_count == 0  # strict > : exact-equal jump not detected


def test_dy_nonunity_classification() -> None:
    c25 = next(c for c in _manifest["cases"]
               if c["case_identifier"] == "S22_DY_025")
    c30 = next(c for c in _manifest["cases"]
               if c["case_identifier"] == "S22_DY_300")
    a = oracle_step_block_declarative(
        _probe("S22_DY_025", "input"), threshold_param=c25["threshold_param"],
        direction="left_to_right", xreal=c25["xreal"], yreal=c25["yreal"])
    b = oracle_step_block_declarative(
        _probe("S22_DY_300", "input"), threshold_param=c30["threshold_param"],
        direction="left_to_right", xreal=c30["xreal"], yreal=c30["yreal"])
    # identical pixels -> identical corrected fields regardless of dy
    assert np.array_equal(a.corrected_field.view(np.uint64),
                          b.corrected_field.view(np.uint64))


def test_correction_identity_and_no_source_import() -> None:
    for case in _manifest["cases"]:
        cid = case["case_identifier"]
        inp = _probe(cid, "input")
        decl = oracle_step_block_declarative(
            inp, threshold_param=case["threshold_param"],
            direction=case["direction"], xreal=case["xreal"], yreal=case["yreal"])
        assert np.array_equal(
            (inp + decl.correction_field).view(np.uint64),
            decl.corrected_field.view(np.uint64)), cid
    # the declarative oracle must not import or call the source oracle
    import inspect

    import oracle_step_block_declarative as d
    source = inspect.getsource(d)
    assert "from oracle_step_block_source import" not in source
    assert "import oracle_step_block_source" not in source
    assert "np.load" not in source
    assert "reference.json" not in source
