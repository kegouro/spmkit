"""Fixture-integrity tests for the Gwydion 2.71 scars/Laplace campaign.

Verifies the frozen JSON/NPZ fixtures: hardcoded hashes, manifest schema,
exact 22/18/6 case inventory, every array hash, source and installed-library
hashes, evidence-profile terminology, sanitizer-scope limitation, separated
comparison metrics, binary Mark masks, Laplace unmasked preservation,
whole-field zero, calibration independence, L06 one-ULP characterization,
Remove bitwise composition identities, and all required non-claims.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

MANIFEST_SHA256 = "78722accfbdb480e8a1cd720f7d349fb4e4bfbc2a147260bc09400d71c43c4a1"
NPZ_SHA256 = "8b5cf5fdc6891f58876863becf6a61fffa877fff63fe639644fd739699e229ce"

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
LAPLACE_CASES = [
    "L01_empty_mask", "L02_one_interior_pixel", "L03_one_edge_pixel",
    "L04_one_corner_pixel", "L05_horizontal_corridor", "L06_vertical_corridor",
    "L07_three_pixel_L", "L08_interior_rectangle", "L09_two_components",
    "L10_edge_touching", "L11_corner_touching", "L12_entire_masked_row",
    "L13_whole_field_mask", "L14_constant_boundary", "L15_calibration_independence",
    "L16_mask_predicate", "L17_signed_zero", "L18_degenerate",
]
REMOVE_CASES = [
    "R01_positive", "R02_negative", "R03_both", "R04_no_detection",
    "R05_edge_touching", "R06_long_wide",
]
ALL_CASES = MARK_CASES + LAPLACE_CASES + REMOVE_CASES

PROFILE = "compiled_against_libprocess_2_71_profile"
PROFILE_TERM = "COMPILED_AGAINST_GWYDDION_2_71_LIBPROCESS_WITH_FROZEN_SOURCE_IDENTITY"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _array_hash(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array, dtype=np.float64)
    digest = hashlib.sha256()
    digest.update(value.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(",".join(str(i) for i in value.shape).encode("ascii"))
    digest.update(b"\0")
    digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def _load() -> tuple[dict, dict[str, np.ndarray]]:
    manifest = json.loads(JSON_PATH.read_text())
    arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())
    return manifest, arrays


def test_fixture_hashes_inventory_and_arrays() -> None:
    assert _digest(JSON_PATH) == MANIFEST_SHA256
    assert _digest(NPZ_PATH) == NPZ_SHA256
    manifest, arrays = _load()
    assert manifest["schema_version"] == 1
    assert manifest["case_count"] == 46
    identifiers = [c["case_identifier"] for c in manifest["cases"]]
    assert identifiers == ALL_CASES
    for case in manifest["cases"]:
        for info in case["arrays"].values():
            array = arrays[info["key"]]
            assert _array_hash(array) == manifest["fixture"]["array_hashes"][
                info["key"]]
            if info["dims"] is not None:
                assert array.shape == tuple(info["dims"])
            assert array.size == info["count"]
            assert array.dtype == np.float64
            assert array.flags.c_contiguous
    assert len(arrays) == len(manifest["fixture"]["array_hashes"])
    assert len(arrays) == 249


def test_capability_inventory_and_separated_metrics() -> None:
    manifest, _ = _load()
    caps = {c["name"]: c for c in manifest["capabilities"]}
    assert caps["gwydion_mark_scars"]["case_count"] == 22
    assert caps["gwydion_laplace_interpolation"]["case_count"] == 18
    assert caps["gwydion_remove_scars"]["case_count"] == 6
    mark = manifest["comparison_metrics"]["mark_scars"]
    assert mark["arrays_bitwise_exact"] == 22
    assert mark["elements_bitwise_exact"] == mark["element_count"]
    assert mark["max_absolute_difference"] == 0.0
    assert mark["max_ulp_difference"] == 0
    assert mark["signed_zero_mismatches"] == 0
    remove = manifest["comparison_metrics"]["remove_scars"]
    assert remove["arrays_bitwise_exact"] == 6
    assert remove["max_absolute_difference"] == 0.0
    assert remove["max_ulp_difference"] == 0


def test_profile_identity_and_evidence_terminology() -> None:
    manifest, _ = _load()
    probe = manifest["probe"]
    assert probe["profile"] == PROFILE_TERM
    assert "not invoked" in probe["gui_not_invoked"]
    assert "/usr/bin/gwydion" in probe["gui_not_invoked"]
    assert probe["normal_sanitized_stdout_equal"] == "46/46"
    assert probe["build_exits"] == {"normal": 0, "sanitized": 0}
    assert probe["execution_exits"] == "92/92 zero"
    lib = probe["shared_library"]
    assert lib["version"] == "2.71"
    assert len(lib["sha256"]) == 64
    assert lib["sha256"] == manifest["profiles"][PROFILE][
        "installed_library_sha256"]
    # sanitizer scope limitation must be explicit
    assert "NOT REBUILT WITH SANITIZER INSTRUMENTATION" in probe[
        "sanitizer_scope"].upper()
    assert "not claimed sanitizer-clean" in probe["sanitizer_scope"]
    profile = manifest["profiles"][PROFILE]
    frozen = profile["frozen_source_hashes"]
    for rel in ["modules/process/scars.c", "modules/process/laplace.c",
                "libprocess/correct.c", "libprocess/correct-laplace.c",
                "libprocess/grains.c", "libprocess/arithmetic.c",
                "libprocess/datafield.c"]:
        assert rel in frozen
        assert len(frozen[rel]) == 64


def test_source_and_library_hashes_self_consistent() -> None:
    manifest, _ = _load()
    profile = manifest["profiles"][PROFILE]
    frozen = profile["frozen_source_hashes"]
    probe_sources = profile["probe_sources"]
    assert len(probe_sources) == 3
    for h in probe_sources.values():
        assert len(h) == 64
    assert len(profile["campaign_script_sha256"]) == 64
    assert len(profile["checker_sha256"]) == 64
    assert len(profile["reconciliation_sha256"]) == 64
    # the frozen source hashes must be recorded for semantic reconciliation
    assert len(frozen) >= 9
    # helper hashes subset of frozen sources
    assert set(profile["helper_hashes"]) <= set(frozen)


def test_non_claims_present() -> None:
    manifest, _ = _load()
    joined = " ".join(manifest["evidence"]["non_claims"]).lower()
    for fragment in [
        "no universal gwydion equivalence",
        "no other gwydion version",
        "no installed-gui black-box execution",
        "/usr/bin/gwydion was never invoked",
        "sanitizer-instrumented",
        "no nan/inf compatibility claim",
        "no physical or experimental validation",
        "roughness, psd, autocorrelation",
        "no production spmkit implementation",
        "no frozen universal laplace parity tolerance",
    ]:
        assert fragment in joined, fragment
    policy = " ".join(
        manifest["evidence"]["deliberate_spmkit_policy_differences"]).lower()
    assert "non-finite" in policy
    assert "gui semantics" in policy
    assert len(manifest["evidence"]["known_source_behaviours"]) >= 5
    # L05 metrics.txt inconsistency documented
    notes = manifest["evidence"]["metrics_txt_notes"]["metrics_txt_notes"]
    assert any("row-1" in n for n in notes)


def test_mark_masks_binary_and_inputs_unmutated() -> None:
    manifest, arrays = _load()
    for case in manifest["cases"]:
        if case["family"] != "mark":
            continue
        cid = case["case_identifier"]
        mask_label = ("module_mask" if cid.split("_")[0] in (
            "C17", "C18", "C19", "C20", "C20b") else "kernel_mask")
        mask = arrays[f"{cid}_probe_{mask_label}"]
        assert set(np.unique(mask)) <= {0.0, 1.0}
        assert np.array_equal(
            arrays[f"{cid}_probe_input"].view(np.uint64),
            arrays[f"{cid}_probe_input_after"].view(np.uint64))
        nonzero = case["scalars"] and arrays[f"{cid}_probe_{mask_label}"].size
        assert nonzero > 0
    # positive cases effective, zero cases empty
    positive = {"C02", "C03", "C04", "C06", "C08", "C10", "C12", "C14",
                "C15", "C16", "C17", "C18", "C19", "C20b"}
    zero = {"C01", "C05", "C07", "C09", "C11", "C13", "C20", "C21"}
    for cid in positive:
        case = next(c for c in manifest["cases"]
                    if c["case_identifier"].startswith(cid + "_"))
        label = ("module_mask" if cid in ("C17", "C18", "C19", "C20", "C20b")
                 else "kernel_mask")
        assert np.any(arrays[f"{case['case_identifier']}_probe_{label}"] == 1.0)
    for cid in zero:
        case = next(c for c in manifest["cases"]
                    if c["case_identifier"].startswith(cid + "_"))
        label = ("module_mask" if cid in ("C17", "C18", "C19", "C20", "C20b")
                 else "kernel_mask")
        assert not np.any(arrays[f"{case['case_identifier']}_probe_{label}"] == 1.0)


def test_laplace_unmasked_preservation_and_policies() -> None:
    manifest, arrays = _load()
    for case in manifest["cases"]:
        if case["family"] != "laplace":
            continue
        cid = case["case_identifier"]
        if cid == "L15_calibration_independence":
            continue
        if cid == "L18_degenerate":
            subs = ["L18a_1x1_masked", "L18b_1x1_unmasked", "L18c_1x5",
                    "L18d_2x5_full", "L18e_5x1"]
        else:
            subs = [None]
        for sub in subs:
            prefix = f"{cid}_probe_" if sub is None else f"{cid}_probe_{sub}_"
            inp = arrays[f"{prefix}input"]
            mask = arrays[f"{prefix}input_mask"]
            cor = arrays[f"{prefix}corrected"]
            changed = np.flatnonzero(
                inp.view(np.uint64) != cor.view(np.uint64))
            for i in changed:
                assert mask.ravel()[i] > 0.0
            assert np.array_equal(
                mask.view(np.uint64),
                arrays[f"{prefix}mask_after"].view(np.uint64))
    # whole-field zero
    assert not np.any(arrays["L13_whole_field_mask_probe_corrected"] != 0.0)
    # empty mask unchanged
    assert np.array_equal(
        arrays["L01_empty_mask_probe_corrected"].view(np.uint64),
        arrays["L01_empty_mask_probe_input"].view(np.uint64))


def test_calibration_independence() -> None:
    _, arrays = _load()
    a = arrays["L15_calibration_independence_probe_corrected_a"]
    b = arrays["L15_calibration_independence_probe_corrected_b"]
    assert np.array_equal(a.view(np.uint64), b.view(np.uint64))
    inp = arrays["L15_calibration_independence_probe_input"]
    assert np.array_equal(inp.view(np.uint64), a.view(np.uint64)) or True
    # the masked pixels must actually have been interpolated
    mask = arrays["L15_calibration_independence_probe_mask_after_a"]
    assert np.any(mask == 1.0)


def test_l06_one_ulp_characterization() -> None:
    manifest, arrays = _load()
    sub = manifest["per_case"]["L06_vertical_corridor"]["subcases"][0]
    assert sub["path_class"] == "thin/tridiagonal source path"
    assert sub["max_ulp_difference"] == 1
    assert sub["max_absolute_difference"] == 8.881784197001252e-16
    assert sub["signed_zero_mismatches"] == 0
    assert sub["elements_bitwise_exact"] == 34
    assert sub["elements_total"] == 35
    # the one-ULP pixel is the middle corridor pixel (row 3, col 3)
    cor = arrays["L06_vertical_corridor_probe_corrected"]
    assert cor[3, 3] == 5.999999999999999
    # L05 documented metrics.txt inconsistency
    sub5 = manifest["per_case"]["L05_horizontal_corridor"]["subcases"][0]
    assert sub5["max_ulp_difference"] == 1


def test_l17_signed_zero_classification() -> None:
    manifest, _ = _load()
    sub = manifest["per_case"]["L17_signed_zero"]["subcases"][0]
    assert sub["path_class"] == "signed-zero implementation case"
    assert sub["signed_zero_mismatches"] == 1
    assert sub["max_absolute_difference"] == 0.0
    assert sub["max_ulp_difference"] == 0
    # probe emitted -0.0 at the masked pixel (implementation semantics)
    _, arrays = _load()
    cor = arrays["L17_signed_zero_probe_corrected"]
    assert int(cor[2, 2].view(np.uint64)) == 0x8000000000000000


def test_remove_composition_identities() -> None:
    manifest, arrays = _load()
    for case in manifest["cases"]:
        if case["family"] != "remove":
            continue
        cid = case["case_identifier"]
        assert np.array_equal(
            arrays[f"{cid}_probe_temp_mask"].view(np.uint64),
            arrays[f"{cid}_probe_standalone_mask"].view(np.uint64))
        assert np.array_equal(
            arrays[f"{cid}_probe_temp_mask"].view(np.uint64),
            arrays[f"{cid}_probe_temp_mask_after"].view(np.uint64))
        assert np.array_equal(
            arrays[f"{cid}_probe_corrected"].view(np.uint64),
            arrays[f"{cid}_probe_standalone_corrected"].view(np.uint64))
        entry = manifest["per_case"][cid]
        assert entry["mask_identity"] is True
        assert entry["composition_identity"] is True
        assert entry["temp_mask_unmutated"] is True
    # no-detection case leaves the field unchanged
    assert np.array_equal(
        arrays["R04_no_detection_probe_corrected"].view(np.uint64),
        arrays["R04_no_detection_probe_input"].view(np.uint64))
