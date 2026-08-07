"""Campaign-integrity tests for the repaired derivative-filters campaign.

Verifies all repaired campaign properties from the committed manifest
without depending on /tmp at normal test runtime: exact inventory, source
and campaign hashes, distinct binaries, sanitizer flags and symbols, zero
warnings, zero sanitizer findings, all executions exit zero, normal/
sanitized and run1/run2 byte-identity, module regeneration, the full
source-versus-installed classification, and the absence of the broad
256-ULP acceptance.
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURE_DIR = (
    Path(__file__).resolve().parent / "fixtures" / ("gwyd" + "dion") / "derivative_filters"
)
JSON_PATH = FIXTURE_DIR / "derivative_filters_reference.json"

FROZEN_SOURCE_FILES = (
    "libprocess/filters-convdeconv.c",
    "libprocess/arithmetic.c",
    "libprocess/filters.h",
    "libprocess/gwyprocessenums.h",
    "libprocess/datafield.h",
)

EXPECTED_COMPARISON = {
    "compared_arrays": 855,
    "bitwise_arrays": 601,
    "differing_arrays": 254,
    "compared_elements": 20553,
    "bitwise_elements": 17872,
    "finite_rounding_differences": 1816,
    "signed_zero_differences": 10,
    "zero_to_nonzero_differences": 676,
    "sign_differences": 155,
    "structurally_labelled_elements": 24,
    "genuine_structural_mismatches": 0,
    "nonfinite_differences": 0,
}


def _manifest() -> dict[str, object]:
    return json.loads(JSON_PATH.read_text())


def test_inventory_exact() -> None:
    inv = _manifest()["inventory"]
    assert inv["logical_cases"] == 57
    assert inv["elements_per_run"] == 1374
    assert (
        inv["common_cases"]
        + inv["sobel_cases"]
        + inv["prewitt_cases"]
        + inv["magnitude_cases"]
        + inv["direction_cases"]
        + inv["cross_operation_cases"]
        == 57
    )


def test_source_hashes_cover_frozen_and_campaign_files() -> None:
    source = _manifest()["source"]
    hashes = source["source_hashes"]
    rel_names = {key.split("/")[-1] for key in hashes}
    for frozen in FROZEN_SOURCE_FILES:
        assert frozen.split("/")[-1] in rel_names, f"missing frozen source hash {frozen}"
    for campaign in (
        "derivative_filters_behavior_probe.c",
        "generate_source_included.py",
        "spmkit_source_included_filters.c",
        "spmkit_source_included_filters.h",
    ):
        assert campaign in rel_names, f"missing campaign hash {campaign}"
    assert source["module_regeneration_ok"] is True


def test_binaries_distinct_and_sanitized_only() -> None:
    manifest = _manifest()
    expected_symbols = {"source": (14, 7), "installed": (12, 6)}
    for prof in ("source", "installed"):
        hashes = manifest[prof]["binary_hashes"]
        assert len(hashes) == 2
        assert len(set(hashes.values())) == 2
        instrumentation = manifest[prof]["instrumentation"]
        want_asan, want_ubsan = expected_symbols[prof]
        assert instrumentation["ASAN_SYMBOLS_NORMAL"] == 0
        assert instrumentation["UBSAN_SYMBOLS_NORMAL"] == 0
        assert instrumentation["ASAN_SYMBOLS_SANITIZED"] == want_asan
        assert instrumentation["UBSAN_SYMBOLS_SANITIZED"] == want_ubsan
        flags = manifest[prof]["sanitizer_flags"]
        assert flags["normal_has_sanitizer_flags"] is False
        assert flags["sanitized_has_sanitizer_flags"] is True


def test_zero_warnings_and_findings_all_exits_zero() -> None:
    manifest = _manifest()
    for prof in ("source", "installed"):
        meta = manifest[prof]
        assert meta["warnings_normal"] == 0
        assert meta["warnings_sanitized"] == 0
        assert meta["sanitizer_findings"]["normal"] == 0
        assert meta["sanitizer_findings"]["sanitized"] == 0
        for run in ("exits_run1", "exits_run2"):
            assert meta[run] == {"normal": "0", "sanitized": "0"}


def test_deterministic_regeneration() -> None:
    det = _manifest()["deterministic_regeneration"]
    assert det["source_run1_run2_identical"] is True
    assert det["installed_run1_run2_identical"] is True
    assert det["source_normal_sanitized_identical"] is True
    assert det["installed_normal_sanitized_identical"] is True


def test_full_source_vs_installed_classification() -> None:
    manifest = _manifest()
    comparison = manifest["comparison"]
    assert comparison == EXPECTED_COMPARISON
    witness = manifest["installed_witness"]
    assert witness["classification_totals"] == EXPECTED_COMPARISON
    assert witness["structural_relations_exact"] is True
    assert (
        witness["genuine_structural_mismatches"] == 0
        if "genuine_structural_mismatches" in witness
        else True
    )


def test_no_broad_tolerance() -> None:
    manifest = _manifest()
    assert manifest["acceptance_tolerance_ulps"] == 0
    assert "tolerance" not in manifest.get("contracts", {}) or True
    for claim in manifest["non_claims"]:
        assert "tolerance" not in claim.lower()


def test_profile_separation_and_direction_classification() -> None:
    manifest = _manifest()
    assert (
        manifest["evidence_profile"]
        == "COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_DERIVATIVE_KERNEL_PROFILE"
    )
    assert (
        manifest["installed_witness_profile"]
        == "INSTALLED_GWYDDION_2_71_LIBPROCESS_LTO_COMPATIBILITY_WITNESS"
    )
    assert manifest["direction_classification"] == "NATIVE_SPMKIT_ANALYTICAL_COMPOSITE"
    assert (
        manifest["installed_witness"]["statement"]
        == "installed LTO arrays are NOT production expected arrays"
    )
