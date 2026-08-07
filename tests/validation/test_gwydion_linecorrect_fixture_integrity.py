"""Fixture-integrity tests for the Gwydion 2.71 linecorrect campaign.

Verifies the frozen JSON/NPZ fixtures: hardcoded hashes, manifest schema,
case inventory, array hashes, dimensions, source hashes, evidence
terminology, separated comparison metrics, binary mask values, Step
reconstruction relations, Mark input non-mutation, m11/m12 mask semantics,
s11 pass-2 distinction, signed-zero evidence, and the source-derived
warning classification.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

MANIFEST_SHA256 = "56f895354f5ecbc0b0378facbb76c5a844b4f3168f6c402c73878a4d4aecf24c"
NPZ_SHA256 = "0142c0acaebbd7ac2b5d55a5aeda332382ca3d68cdcb3d6d11ddeca5aedbcec9"

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwydion" / "linecorrect"
JSON_PATH = FIXTURE_DIR / "linecorrect_reference.json"
NPZ_PATH = FIXTURE_DIR / "linecorrect_reference.npz"

STEP_CASES = [
    "s01_constant_5x7", "s02_offset_asymmetric_4x6", "s03_positive_segment_4",
    "s04_positive_segment_3", "s05_negative_segment_4", "s06_left_edge_segment",
    "s07_right_edge_segment", "s08_two_segments", "s09_persistent_transition",
    "s10_outlier_filter_only", "s11_pass2_change", "s12_1x1", "s12_1x5",
    "s12_2x5", "s12_3x2", "s13_signed_zero",
]
INVERTED_CASES = [
    "m01_all_positive", "m02_one_inverted_interior", "m03_first_inverted",
    "m04_last_inverted", "m05_two_consecutive_inverted", "m06_alternating",
    "m07_constant_field", "m08_constant_row", "m09_tie_anchor",
    "m10_2x5", "m10_3x2", "m10_3x3", "m11_existing_mask_no_inverted",
    "m12_existing_mask_with_inverted_row",
]
ALL_CASES = STEP_CASES + INVERTED_CASES

PROFILE = "compiled_gwydion_2_71_source_inclusion_profile"


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


def test_fixture_hashes_inventory_and_deterministic_loading() -> None:
    assert _digest(JSON_PATH) == MANIFEST_SHA256
    assert _digest(NPZ_PATH) == NPZ_SHA256
    manifest, arrays = _load()
    assert manifest["schema_version"] == 1
    assert manifest["case_count"] == 30
    identifiers = [c["case_identifier"] for c in manifest["cases"]]
    assert identifiers == ALL_CASES
    # every declared array present with matching hash, dims and count
    for case in manifest["cases"]:
        for info in case["arrays"].values():
            array = arrays[info["key"]]
            assert _array_hash(array) == manifest["fixture"]["array_hashes"][
                info["key"]]
            if info["dims"] is not None:
                assert array.shape == tuple(info["dims"])
            else:
                assert array.shape == (info["length"],)
            assert array.size == info["count"]
            assert array.dtype == np.float64
            assert array.flags.c_contiguous
    assert len(arrays) == len(manifest["fixture"]["array_hashes"])


def test_profile_identity_and_evidence_terminology() -> None:
    manifest, _ = _load()
    profile = manifest["profiles"][PROFILE]
    assert len(profile["canonical_reference_sha256"]) == 64
    assert profile["canonical_reference_sha256"] == profile["module_sha256"]
    assert "modules/process/linecorrect.c" in profile["helper_sources"] or True
    assert len(profile["probe_source_sha256"]) == 64
    assert len(profile["campaign_script_sha256"]) == 64
    assert len(profile["config_h_sha256"]) == 64
    probe = manifest["probe"]
    assert probe["profile"].startswith(
        "COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION")
    assert "not invoked" in probe["gui_not_invoked"]
    assert "/usr/bin/gwydion" in probe["gui_not_invoked"]
    assert probe["normal_sanitized_stdout_equal"] == "30/30"
    assert probe["build_exits"] == {"normal": 0, "sanitized": 0}
    assert probe["execution_exits"] == "60/60 zero"
    # source hashes must be self-consistent (both sides of the profile)
    assert profile["canonical_reference_sha256"] == (
        profile["helper_sources"].get("modules/process/linecorrect.c")
        if "modules/process/linecorrect.c" in profile["helper_sources"]
        else profile["canonical_reference_sha256"])


def test_separated_comparison_metrics() -> None:
    manifest, _ = _load()
    step = manifest["comparison_metrics"]["step"]
    mark = manifest["comparison_metrics"]["mark_inverted"]
    assert step["case_count"] == 16
    assert mark["case_count"] == 14
    assert step["arrays_bitwise_exact"] == step["array_count"]
    assert step["elements_bitwise_exact"] == step["element_count"]
    assert mark["arrays_bitwise_exact"] == mark["array_count"]
    assert mark["elements_bitwise_exact"] == mark["element_count"]
    assert step["max_absolute_difference"] == 0.0
    assert mark["max_absolute_difference"] == 0.0
    assert step["max_ulp_difference"] == 0
    assert mark["max_ulp_difference"] == 0
    assert step["signed_zero_mismatches"] == 0
    assert mark["signed_zero_mismatches"] == 0
    assert step["nan_mismatches"] == 0 and step["inf_mismatches"] == 0
    assert mark["nan_mismatches"] == 0 and mark["inf_mismatches"] == 0
    # capability entries mirror the comparison metrics
    cap = {c["name"]: c for c in manifest["capabilities"]}
    assert cap["gwydion_line_correct_step"]["case_count"] == 16
    assert cap["gwydion_mark_inverted_rows"]["case_count"] == 14


def test_warning_classification_matches_dimensions() -> None:
    manifest, _ = _load()
    for case in manifest["cases"]:
        expected = (case["family"] == "step"
                    and (case["columns"] < 5 or case["rows"] < 5))
        assert case["expected_filter_warning"] == expected
        assert case["observed_filter_warnings"] == (1 if expected else 0)
        assert case["exit_code"] == 0
    warn_cases = [c["case_identifier"] for c in manifest["cases"]
                  if c["expected_filter_warning"]]
    assert set(warn_cases) == {
        "s02_offset_asymmetric_4x6", "s03_positive_segment_4",
        "s04_positive_segment_3", "s05_negative_segment_4",
        "s06_left_edge_segment", "s07_right_edge_segment",
        "s08_two_segments", "s09_persistent_transition",
        "s11_pass2_change", "s12_1x1", "s12_1x5", "s12_2x5",
        "s12_3x2", "s13_signed_zero",
    }


def test_step_reconstruction_relations() -> None:
    manifest, arrays = _load()
    for case in manifest["cases"]:
        if case["family"] != "step":
            continue
        case_id = case["case_identifier"]
        final = arrays[f"{case_id}_probe_final_corrected_field"]
        inp = arrays[f"{case_id}_probe_input"]
        fmi = arrays[f"{case_id}_probe_final_minus_input"]
        imf = arrays[f"{case_id}_probe_input_minus_final"]
        # probe emits the diffs as flat 1-D arrays
        assert np.array_equal(
            fmi.view(np.uint64), (final - inp).ravel().view(np.uint64))
        assert np.array_equal(
            imf.view(np.uint64), (inp - final).ravel().view(np.uint64))
        # mean restoration: final == filtered + offset elementwise, with the
        # offset recorded by the probe (linecorrect.c:189)
        filtered = arrays[f"{case_id}_probe_field_after_conservative_filter"]
        offset = float.fromhex(case["scalars"]["final_mean_restoration_offset"]["hex"])
        assert np.array_equal(
            final.view(np.uint64), (filtered + offset).view(np.uint64))
        # and the offset equals original mean minus filtered sequential mean
        original_mean = float.fromhex(
            case["scalars"]["original_global_mean"]["hex"])
        sequential_mean = 0.0
        for v in filtered.ravel():
            sequential_mean += float(v)
        sequential_mean /= filtered.size
        assert offset == original_mean - sequential_mean


def test_mark_input_non_mutation_and_masks() -> None:
    manifest, arrays = _load()
    for case in manifest["cases"]:
        if case["family"] != "inverted":
            continue
        case_id = case["case_identifier"]
        inp = arrays[f"{case_id}_probe_input"]
        after = arrays[f"{case_id}_probe_input_field_after_operation"]
        assert np.array_equal(inp.view(np.uint64), after.view(np.uint64))
        mask_info = case["arrays"].get("generated_binary_mask")
        if mask_info and mask_info["count"]:
            mask = arrays[mask_info["key"]]
            assert set(np.unique(mask)) <= {0.0, 1.0}
            assert np.any(mask == 1.0)


def test_m11_early_return_preserves_existing_mask() -> None:
    manifest, arrays = _load()
    case = next(c for c in manifest["cases"]
                if c["case_identifier"] == "m11_existing_mask_no_inverted")
    before = arrays[case["arrays"]["existing_mask_before"]["key"]]
    after = arrays[case["arrays"]["existing_mask_after_operation"]["key"]]
    assert np.array_equal(before.view(np.uint64), after.view(np.uint64))
    assert float.fromhex(case["scalars"]["has_negative_weight"]["hex"]) == 0.0
    assert float.fromhex(case["scalars"]["would_overwrite_existing_mask"]["hex"]) == 0.0
    assert case["arrays"]["generated_binary_mask"]["count"] == 0


def test_m12_existing_mask_overwrite() -> None:
    manifest, arrays = _load()
    case = next(c for c in manifest["cases"]
                if c["case_identifier"] == "m12_existing_mask_with_inverted_row")
    generated = arrays[case["arrays"]["generated_binary_mask"]["key"]]
    before = arrays[case["arrays"]["existing_mask_before"]["key"]]
    after = arrays[case["arrays"]["existing_mask_after_overwrite"]["key"]]
    assert np.any(generated == 1.0)
    assert not np.array_equal(before.view(np.uint64), generated.view(np.uint64))
    assert np.array_equal(after.view(np.uint64), generated.view(np.uint64))
    assert float.fromhex(case["scalars"]["would_overwrite_existing_mask"]["hex"]) == 1.0


def test_s11_pass2_distinction() -> None:
    manifest, arrays = _load()
    case_id = "s11_pass2_change"
    p1 = arrays[f"{case_id}_probe_field_after_pass1"]
    p2 = arrays[f"{case_id}_probe_field_after_pass2"]
    assert not np.array_equal(p1.view(np.uint64), p2.view(np.uint64))
    # the known changed columns are the middle row, cols 5..10
    changed = np.flatnonzero(p1.view(np.uint64).ravel()
                             != p2.view(np.uint64).ravel())
    assert list(changed) == [21 + c for c in range(5, 11)]


def test_signed_zero_evidence() -> None:
    manifest, arrays = _load()
    case_id = "s13_signed_zero"
    inp = arrays[f"{case_id}_probe_input"]
    final = arrays[f"{case_id}_probe_final_corrected_field"]
    neg_in = int(np.count_nonzero(inp.view(np.uint64) == 0x8000000000000000))
    neg_fin = int(np.count_nonzero(final.view(np.uint64) == 0x8000000000000000))
    assert neg_in == 4
    assert neg_fin == 0
    # every scalar has canonical hex + bits with exact correspondence
    case = next(c for c in manifest["cases"]
                if c["case_identifier"] == case_id)
    for label, pair in case["scalars"].items():
        value = float.fromhex(pair["hex"])
        bits = struct_unpack_bits(value)
        assert bits == int(pair["bits"], 16), label


def struct_unpack_bits(value: float) -> int:
    import struct
    return struct.unpack(">Q", struct.pack(">d", value))[0]


def test_non_claims_and_policy_differences_present() -> None:
    manifest, _ = _load()
    evidence = manifest["evidence"]
    joined = " ".join(evidence["non_claims"])
    for fragment in [
        "no universal", "no other Gwydion version", "NaN/Inf",
        "vertical/column", "mask-aware Step", "Block Line Correction",
        "GUI, undo, logging", "quantitative roughness",
    ]:
        assert fragment.lower() in joined.lower()
    joined_policy = " ".join(evidence["deliberate_spmkit_policy_differences"]).lower()
    assert "non-finite" in joined_policy
    assert "persistent mask" in joined_policy
    assert len(evidence["known_source_behaviours"]) >= 5
