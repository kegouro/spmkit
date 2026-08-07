"""Tests for the exact source-semantic Step Block oracle.

All 28 valid numerical cases must reproduce the frozen compiled probe
bitwise; xres=1 rejection and finite-input policy are tested; the oracle
must never read fixture expected outputs or import production code.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwydion" / "step_block"
NPZ_PATH = FIXTURE_DIR / "step_block_reference.npz"
JSON_PATH = FIXTURE_DIR / "step_block_reference.json"

sys.path.insert(0, str(FIXTURE_DIR))
from oracle_step_block_source import oracle_step_block_source  # noqa: E402  # isort: skip

_manifest = json.loads(JSON_PATH.read_text())
_arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())
_CASES = {c["case_identifier"]: c for c in _manifest["cases"]}


def _bits(a):
    return np.ascontiguousarray(a, dtype=np.float64).view(np.uint64)


def _probe(cid, label):
    return _arrays[f"{cid}_probe_{label}"]


def test_all_28_valid_cases_bitwise() -> None:
    for case in _manifest["cases"]:
        cid = case["case_identifier"]
        inp = _probe(cid, "input")
        ref = oracle_step_block_source(
            inp, threshold_param=case["threshold_param"],
            direction=case["direction"], xreal=case["xreal"], yreal=case["yreal"])
        # effective threshold
        assert ref.effective_threshold == case["effective_threshold"], cid
        # block count and topology
        assert ref.block_count == case["block_count"], cid
        for k in range(ref.block_count):
            assert ref.retained_blocks[k][0] == case["boundaries"][k], cid
            assert ref.retained_blocks[k][1] == case["split_positions"][k], cid
            assert ref.retained_blocks[k][2] == case["block_shifts"][k], cid
            # trimmed-mean state vs the frozen compiled emissions
            assert np.array_equal(
                _bits(ref.per_block_shifts_raw[k]),
                _probe(cid, f"tm_{k}_raw").view(np.uint64)), cid
            assert np.array_equal(
                _bits(ref.per_block_shifts_selected[k]),
                _probe(cid, f"tm_{k}_sel").view(np.uint64)), cid
            # retained sum == trimmed mean * retained count (exact for the
            # integer-valued retained campaign blocks)
            assert ref.per_block_retained_sum[k] == \
                ref.retained_blocks[k][2] * ref.retained_count, cid
        # corrected field bitwise
        assert np.array_equal(
            _bits(ref.corrected_field),
            _probe(cid, "corrected").view(np.uint64)), cid
        # masks bitwise
        assert np.array_equal(
            _bits(ref.preview_mask_discontinuity),
            _probe(cid, "mask_discontinuity").view(np.uint64)), cid
        assert np.array_equal(
            _bits(ref.preview_mask_blocks),
            _probe(cid, "mask_blocks").view(np.uint64)), cid
        # input non-mutation
        assert not ref.input_mutation_evidence, cid
        assert np.array_equal(_bits(ref.input_snapshot),
                              _probe(cid, "input_after").view(np.uint64)), cid


def test_xres_one_rejected() -> None:
    try:
        oracle_step_block_source(np.zeros((8, 1)), threshold_param=2.0,
                                 direction="left_to_right", xreal=1.0, yreal=8.0)
    except ValueError as exc:
        assert "xres < 2" in str(exc)
    else:
        raise AssertionError("xres=1 must be rejected (frozen-source defect)")


def test_finite_input_rejected() -> None:
    field = np.zeros((8, 8))
    field[2, 2] = np.nan
    try:
        oracle_step_block_source(field, threshold_param=2.0,
                                 direction="left_to_right", xreal=8.0, yreal=8.0)
    except ValueError:
        pass
    else:
        raise AssertionError("NaN input must be rejected")
    field[2, 2] = np.inf
    try:
        oracle_step_block_source(field, threshold_param=2.0,
                                 direction="left_to_right", xreal=8.0, yreal=8.0)
    except ValueError:
        pass
    else:
        raise AssertionError("Inf input must be rejected")


def test_oracle_never_reads_fixture_outputs() -> None:
    import inspect

    import oracle_step_block_source as o
    source = inspect.getsource(o)
    assert "reference.json" not in source
    assert "reference.npz" not in source
    assert "np.load" not in source


def test_no_production_imports() -> None:
    import inspect

    import oracle_step_block_source as o
    source = inspect.getsource(o)
    assert "spmkit.core" not in source
