"""Fixture-integrity tests for the Gwydion 2.71 Step Block campaign fixtures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

MANIFEST_SHA256 = "57fc818b5f1e0e0144ec8e267884ae61ed9e96f5b91a36a8b56dd78d9375175b"
NPZ_SHA256 = "ada1847ffc96ac53d3fb92af976040da8f9e5634a7137df634a0e4bc591f62c8"

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwydion" / "step_block"
JSON_PATH = FIXTURE_DIR / "step_block_reference.json"
NPZ_PATH = FIXTURE_DIR / "step_block_reference.npz"

VALID_CASES = [
    "S01_CONSTANT", "S02_SINGLE_POSITIVE_STEP_LTR", "S03_SINGLE_NEGATIVE_STEP_LTR",
    "S04_TWO_SEPARATED_STEPS", "S05_ALTERNATING_BLOCK_OFFSETS",
    "S06_EARLIEST_FULL_WIDTH_BOUNDARY", "S07_LATEST_FULL_WIDTH_BOUNDARY",
    "S08_MINIMUM_INTERIOR_BLOCK", "S09_EQUAL_COMPETING_CANDIDATES",
    "S10_SUB_THRESHOLD", "S11_THRESHOLD_EXACT", "S12_NON_SQUARE_WIDE",
    "S13_NON_SQUARE_TALL", "S14_SIGNED_ZERO", "S15_YRES_ONE",
    "S16_YRES_TWO_FULL_WIDTH_STEP", "S17_SMALL_XRES_2", "S17_SMALL_XRES_3",
    "S17_SMALL_XRES_4", "S18_RIGHT_TO_LEFT_SINGLE_STEP",
    "S19_PARTIAL_WIDTH_STEP_LTR", "S19b_PARTIAL_WIDTH_REJECTED",
    "S20_PARTIAL_WIDTH_STEP_RTL", "S21_CORRECTION_RECONSTRUCTION",
    "S22_DY_025", "S22_DY_300", "S23_TRIMMED_MEAN_OUTLIERS",
    "S24_TRIMMED_MEAN_TIES",
]
PROFILE = "COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _array_hash(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array, dtype=np.float64)
    d = hashlib.sha256()
    d.update(value.dtype.str.encode("ascii"))
    d.update(b"\0")
    d.update(",".join(str(i) for i in value.shape).encode("ascii"))
    d.update(b"\0")
    d.update(value.tobytes(order="C"))
    return d.hexdigest()


def _load():
    manifest = json.loads(JSON_PATH.read_text())
    arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())
    return manifest, arrays


def test_hashes_inventory_and_arrays() -> None:
    assert _digest(JSON_PATH) == MANIFEST_SHA256
    assert _digest(NPZ_PATH) == NPZ_SHA256
    manifest, arrays = _load()
    assert manifest["schema_version"] == 1
    assert manifest["capability"] == "gwydion_step_block_correction"
    assert manifest["evidence_profile"] == PROFILE
    assert manifest["case_inventory"] == {"total": 29, "numerical_parity": 28,
                                          "source_defect": 1}
    identifiers = [c["case_identifier"] for c in manifest["cases"]]
    assert identifiers == VALID_CASES
    for case in manifest["cases"]:
        assert case["classification"] == "NUMERICAL_PARITY"
        src = case["source_oracle"]
        assert src["corrected"]["arrays_bitwise_exact"]
        assert src["effective_threshold_bitwise"]
        assert src["block_state_exact"]
        assert src["input_non_mutation"]
        assert src["mask_discontinuity"]["arrays_bitwise_exact"]
        assert src["mask_blocks"]["arrays_bitwise_exact"]
    for key, arr in arrays.items():
        assert _array_hash(arr) == manifest["fixture"]["array_hashes"][key]
        assert arr.dtype == np.float64
        assert arr.flags.c_contiguous
    assert manifest["fixture"]["source_oracle_bitwise"]


def test_no_defect_numerical_arrays() -> None:
    manifest, arrays = _load()
    assert manifest["source_defect"]["case_identifier"] == "S17_SMALL_XRES_1"
    assert manifest["source_defect"]["classification"] == "SOURCE_DEFECT"
    assert manifest["source_defect"]["normal_output_undefined"]
    assert not manifest["source_defect"]["parity_claim"]
    assert manifest["source_defect"]["dimensions"] == {"xres": 1, "yres": 8}
    assert any(f["function"] == "process_one_step_segment"
               and f["line"] == 395
               for f in manifest["source_defect"]["source_stack"])
    assert any(f["function"] == "construct_blocks" and f["line"] == 475
               for f in manifest["source_defect"]["source_stack"])
    assert "reject xres < 2" in manifest["source_defect"]["required_future_guard"]
    for key in arrays:
        assert "S17_SMALL_XRES_1" not in key, f"defect numerical array frozen: {key}"
    for case in manifest["cases"]:
        assert case["case_identifier"] != "S17_SMALL_XRES_1"


def test_profile_and_sanitizer_scope() -> None:
    manifest, _ = _load()
    assert manifest["gui_not_invoked"] is True
    assert "not rebuilt with sanitizer instrumentation" in \
        manifest["sanitizer_scope"]
    assert "not invoked" in str(manifest.get("gui_not_invoked")) or \
        manifest["gui_not_invoked"] is True
    joined = " ".join(manifest["non_claims"]).lower()
    for fragment in ["no parity with xres=1 undefined behavior",
                     "future spmkit production must reject xres < 2",
                     "no universal gwyd" + "dion version/build equivalence",
                     "no installed-gui black-box execution",
                     "not sanitizer-instrumented",
                     "no physical or experimental validation",
                     "no universal numerical tolerance frozen"]:
        assert fragment in joined, fragment


def test_binary_preview_masks_and_reconstruction() -> None:
    manifest, arrays = _load()
    for case in manifest["cases"]:
        cid = case["case_identifier"]
        for label in ("mask_discontinuity", "mask_blocks"):
            vals = arrays[f"{cid}_probe_{label}"]
            assert set(np.unique(vals)) <= {0.0, 1.0}, (cid, label)
        inp = arrays[f"{cid}_probe_input"]
        after = arrays[f"{cid}_probe_input_after"]
        assert np.array_equal(inp.view(np.uint64), after.view(np.uint64)), cid
        # correction reconstruction: corrected == input + delta
        corrected = arrays[f"{cid}_probe_corrected"]
        delta = arrays[f"{cid}_probe_delta"]
        if cid == "S14_SIGNED_ZERO":
            # all-negative-zero field: delta = (-0.0) - (-0.0) = +0.0 loses
            # the sign; the reconstruction identity holds as values only
            assert np.array_equal(corrected, inp + delta), cid
            continue
        assert np.array_equal(
            corrected.view(np.uint64),
            (inp + delta).view(np.uint64)), cid
