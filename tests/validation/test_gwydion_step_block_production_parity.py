"""Production parity: gwydion_step_block_correction vs the frozen compiled
campaign (28 valid NUMERICAL_PARITY cases) plus the source-defect guard."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from spmkit.core.analysis import gwydion_step_block_correction
from spmkit.core.analysis._gwydion_step_block import _gwydion_step_block_result
from spmkit.core.models.spmdata import SPMChannel

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwydion" / "step_block"
JSON_PATH = FIXTURE_DIR / "step_block_reference.json"
NPZ_PATH = FIXTURE_DIR / "step_block_reference.npz"

_manifest = json.loads(JSON_PATH.read_text())
_arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())


def _bits(a: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(a, dtype=np.float64).view(np.uint64)


def _probe(cid: str, label: str) -> np.ndarray:
    return _arrays[f"{cid}_probe_{label}"]


def test_all_28_valid_cases_public_bitwise() -> None:
    total = 0
    for case in _manifest["cases"]:
        cid = case["case_identifier"]
        inp = _probe(cid, "input")
        ch = SPMChannel(name="parity", data=inp, unit="nm",
                        x_range=float(inp.shape[1]),
                        y_range=float(inp.shape[0]))
        out = gwydion_step_block_correction(
            ch, threshold=case["threshold_param"], direction=case["direction"])
        compiled = _probe(cid, "corrected")
        assert np.array_equal(_bits(out.data), _bits(compiled)), cid
        total += compiled.size
        # context preservation
        assert out.name == ch.name and out.unit == ch.unit
        assert out.x_range == ch.x_range and out.y_range == ch.y_range
        # input non-mutation
        assert np.array_equal(_bits(inp), _bits(_probe(cid, "input_after"))), cid
    assert total == sum(c["dimensions"]["xres"] * c["dimensions"]["yres"]
                       for c in _manifest["cases"])


def test_diagnostic_state_parity() -> None:
    max_abs = 0.0
    max_ulp = 0
    for case in _manifest["cases"]:
        cid = case["case_identifier"]
        inp = _probe(cid, "input")
        dy = case["yreal"] / inp.shape[0]
        ref = _gwydion_step_block_result(
            inp, threshold=case["threshold_param"],
            direction=case["direction"], dy=dy)
        # effective threshold
        assert ref.effective_threshold == case["effective_threshold"], cid
        # masks
        assert np.array_equal(
            _bits(ref.discontinuity_mask),
            _probe(cid, "mask_discontinuity").view(np.uint64)), cid
        assert np.array_equal(
            _bits(ref.preview_mask_blocks),
            _probe(cid, "mask_blocks").view(np.uint64)), cid
        # block topology and shifts
        assert ref.block_count == case["block_count"], cid
        for k in range(ref.block_count):
            assert ref.retained_blocks[k][0] == case["boundaries"][k], cid
            assert ref.retained_blocks[k][1] == case["split_positions"][k], cid
            assert ref.retained_blocks[k][2] == case["block_shifts"][k], cid
            assert np.array_equal(
                _bits(ref.shift_samples_raw[k]),
                _probe(cid, f"tm_{k}_raw").view(np.uint64)), cid
            assert np.array_equal(
                _bits(ref.shift_samples_selected[k]),
                _probe(cid, f"tm_{k}_sel").view(np.uint64)), cid
            assert ref.retained_sums[k] == \
                ref.retained_blocks[k][2] * ref.retained_count, cid
        # sentinel
        assert ref.sentinel == (inp.shape[0] + 1, inp.shape[1], 0.0), cid
        # correction reconstruction (signed-zero field excluded: the delta
        # of an all-negative-zero field loses the sign, see S14 below)
        if cid != "S14_SIGNED_ZERO":
            assert np.array_equal(
                _bits(ref.corrected_field),
                _bits(inp + ref.correction_field)), cid
        # signed-zero classification: the signed-zero case has no delta
        if cid == "S14_SIGNED_ZERO":
            assert ref.block_count == 0
            assert np.array_equal(_bits(ref.corrected_field), _bits(inp))
        # finite-nonzero/zero ULP bounds: all comparisons are bitwise here
        pb = _bits(_probe(cid, "corrected")).ravel()
        ob = _bits(ref.corrected_field).ravel()
        for i in range(pb.size):
            if pb[i] != ob[i]:
                xor = int(pb[i]) ^ int(ob[i])
                if xor == 0x8000000000000000:
                    continue
                max_abs = max(max_abs, abs(float(_probe(cid, "corrected").ravel()[i])
                                           - float(ref.corrected_field.ravel()[i])))
                if float(_probe(cid, "corrected").ravel()[i]) != 0.0 and \
                        float(ref.corrected_field.ravel()[i]) != 0.0:
                    max_ulp = max(max_ulp, abs(int(pb[i]) - int(ob[i])))
    assert max_abs == 0.0
    assert max_ulp == 0


def test_no_input_mutation_any_case() -> None:
    for case in _manifest["cases"]:
        cid = case["case_identifier"]
        inp = _probe(cid, "input")
        before = _bits(inp).copy()
        gwydion_step_block_correction(
            _SPMChannelOf(inp), threshold=case["threshold_param"],
            direction=case["direction"])
        assert np.array_equal(_bits(inp), before), cid


def _SPMChannelOf(inp: np.ndarray) -> SPMChannel:
    return SPMChannel(name="parity", data=inp, unit="nm",
                      x_range=float(inp.shape[1]),
                      y_range=float(inp.shape[0]))


def test_source_defect_guard() -> None:
    # manifest classification
    assert _manifest["source_defect"]["case_identifier"] == "S17_SMALL_XRES_1"
    assert _manifest["source_defect"]["classification"] == "SOURCE_DEFECT"
    assert _manifest["source_defect"]["normal_output_undefined"] is True
    assert _manifest["source_defect"]["parity_claim"] is False
    # no numerical fixture arrays for the defect case
    assert all("S17_SMALL_XRES_1" not in k for k in _arrays)
    # public API rejects xres=1
    with pytest.raises(ValueError) as exc:
        gwydion_step_block_correction(_SPMChannelOf(np.zeros((8, 1))))
    assert "xres < 2" in str(exc.value)
