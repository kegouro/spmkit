"""Tests for the frozen-source defect record (S17_SMALL_XRES_1, xres=1)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwydion" / "step_block"
JSON_PATH = FIXTURE_DIR / "step_block_reference.json"
NPZ_PATH = FIXTURE_DIR / "step_block_reference.npz"


def test_defect_record_present_and_complete() -> None:
    manifest = json.loads(JSON_PATH.read_text())
    rec = manifest["source_defect"]
    assert rec["case_identifier"] == "S17_SMALL_XRES_1"
    assert rec["classification"] == "SOURCE_DEFECT"
    assert rec["sanitizer_category"] == "heap-buffer-overflow"
    functions = [f["function"] for f in rec["source_stack"]]
    assert "process_one_step_segment" in functions
    assert "construct_blocks" in functions
    files = {f["file"] for f in rec["source_stack"]}
    assert files == {"modules/process/blockstep.c"}
    assert rec["normal_output_undefined"] is True
    assert rec["parity_claim"] is False
    assert "xres < 2" in rec["required_future_guard"]


def test_defect_case_has_no_frozen_numerical_output() -> None:
    manifest = json.loads(JSON_PATH.read_text())
    arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())
    assert all(c["case_identifier"] != "S17_SMALL_XRES_1"
               for c in manifest["cases"])
    assert all("S17_SMALL_XRES_1" not in k for k in arrays)
    # the generator must never store an expected numerical output for the
    # defect case: if a future generator change adds one, this fails
    assert "S17_SMALL_XRES_1_probe_corrected" not in arrays


def test_normal_output_is_never_a_parity_source() -> None:
    # the manifest contains no corrected/block/shift arrays for the defect
    # case and the non-claims forbid parity with its undefined behaviour
    manifest = json.loads(JSON_PATH.read_text())
    joined = " ".join(manifest["non_claims"]).lower()
    assert "no parity with xres=1 undefined behavior" in joined
    assert "reject xres < 2" in joined
