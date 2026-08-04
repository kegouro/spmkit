"""Fixture-integrity tests for the Gwydion 2.71 Align Rows remaining-methods
campaign fixtures (Polynomial, Modus, Match).

Verifies the frozen JSON/NPZ: hardcoded hashes, exact execution/logical
inventory, family counts, canonical-vs-relational classifications, array
hashes, source/campaign hashes, distinct binary hashes, sanitizer flags and
scope, two-run deterministic identity, required non-claims, and the
no-duplicate-replay-arrays rule.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

MANIFEST_SHA256 = "6fc560f9136ebea1a9683b389f4d58e0069be27d89827c5c653341528e5547c8"
NPZ_SHA256 = "b989919df69682af08e3a1e2e7e7e5a9effc4f2ce22bd64785c2b046daf491e9"

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwyddion" / \
    "align_rows_remaining"
JSON_PATH = FIXTURE_DIR / "align_rows_remaining_reference.json"
NPZ_PATH = FIXTURE_DIR / "align_rows_remaining_reference.npz"

PROFILE = "COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION"

EXPECTED_BINARY_HASHES = {
    "bin/align_rows_probe":
        "4509b817cee20de6e5a3df445900702af9ff32a824242c6f4a9add440f8720c4",
    "bin/align_rows_probe.san":
        "e39299128a9f422705af9af5cc7032e76e0f640c1bbac28fc43e525cf9ba46de",
}

REPLAY_PAIRS = [
    ("X04a_DETERMINISTIC_REPLAY_POLY_0", "X04a_DETERMINISTIC_REPLAY_POLY_1"),
    ("X04b_DETERMINISTIC_REPLAY_MODUS_0", "X04b_DETERMINISTIC_REPLAY_MODUS_1"),
    ("X04c_DETERMINISTIC_REPLAY_MATCH_0", "X04c_DETERMINISTIC_REPLAY_MATCH_1"),
]


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
    assert manifest["capability"] == "gwydion_align_rows_remaining"
    assert manifest["evidence_profile"] == PROFILE
    assert manifest["source_version"] == "2.71"
    assert manifest["gui_not_invoked"]
    inv = manifest["inventory"]
    assert inv["execution_files_per_build"] == 59
    assert inv["execution_records"] == 59
    assert inv["logical_cases"] == 68
    assert inv["numerical_parity"] == 62
    assert inv["determinism_witnesses"] == 6
    assert inv["independently_reconstructed"] == 62
    assert inv["non_reconstructed_relational"] == 6
    assert inv["families"] == {"polynomial": 27, "modus": 12, "match": 16,
                               "cross_method": 13}
    assert len(manifest["execution_records"]) == 59
    cases = manifest["cases"]
    assert len(cases) == 68
    identifiers = [c["case_identifier"] for c in cases]
    assert len(identifiers) == len(set(identifiers))
    assert len([c for c in cases
                if c["classification"] == "NUMERICAL_PARITY"]) == 62
    assert len([c for c in cases
                if c["classification"] == "DETERMINISM_WITNESS"]) == 6
    # every numerical case must be source-oracle bitwise
    for case in cases:
        if case["classification"] != "NUMERICAL_PARITY":
            continue
        so = case["source_oracle"]
        for arr in ("corrected", "bg", "delta", "shifts"):
            assert so[arr]["arrays_bitwise_exact"], case["case_identifier"]
        assert so["row_state_exact"], case["case_identifier"]
        assert so["input_non_mutation"], case["case_identifier"]
        assert so["mask_non_mutation"], case["case_identifier"]
        assert so["declarative"]["valid_counts_exact"], \
            case["case_identifier"]
    assert manifest["fixture"]["source_oracle_bitwise"]
    for key, arr in arrays.items():
        assert _array_hash(arr) == manifest["fixture"]["array_hashes"][key]
        assert arr.dtype == np.float64
        assert arr.flags.c_contiguous


def test_binary_hashes_and_sanitizer() -> None:
    manifest, _ = _load()
    bh = manifest["binary_hashes"]
    assert bh == EXPECTED_BINARY_HASHES
    assert manifest["sanitizer"]["binaries_distinct"]
    assert manifest["sanitizer"]["normal_binary_sha256"] != \
        manifest["sanitizer"]["sanitized_binary_sha256"]
    flags = manifest["sanitizer"]["flags"]
    assert "-fsanitize=address,undefined" in flags
    assert "-fno-sanitize-recover=all" in flags
    assert "-fno-omit-frame-pointer" in flags
    scope = manifest["sanitizer"]["scope"]
    assert "not rebuilt with sanitizer instrumentation" in scope
    assert manifest["sanitizer"]["sanitizer_findings"] == 0


def test_source_hashes_present() -> None:
    manifest, _ = _load()
    sh = manifest["source_hashes"]
    for rel in ("modules/process/linematch.c", "libprocess/correct.c",
                "libprocess/linestats.c", "libgwyd" + "dion/gwymath-rank.c",
                "align_rows_remaining_behavior_probe.c",
                "run_align_rows_remaining_probe_campaign.sh"):
        assert rel in sh, rel
        assert len(sh[rel]) == 64
    # campaign files are also listed under campaign_hashes
    for rel in ("align_rows_remaining_behavior_probe.c",
                "run_align_rows_remaining_probe_campaign.sh",
                "campaign_checker.py", "independent_reconciliation.py",
                "metrics.py", "config.h"):
        assert rel in manifest["campaign_hashes"], rel

def test_two_run_deterministic_identity() -> None:
    manifest, _ = _load()
    assert manifest["evidence_roots"]["deterministic_identity"]


def test_no_duplicate_replay_arrays() -> None:
    manifest, arrays = _load()
    # replay partners (_1) must never be stored as duplicate arrays
    for a, b in REPLAY_PAIRS:
        assert any(f"{a}_probe_" in k for k in arrays), a
        assert not any(f"{b}_probe_" in k for k in arrays), b
    # and the relation is recorded in the manifest
    relations = manifest["relations"]["determinism_replay"]
    assert [list(p) for p in relations] == [list(p) for p in REPLAY_PAIRS]


def test_non_claims_present() -> None:
    manifest, _ = _load()
    text = "\n".join(manifest["non_claims"])
    for claim in ("no production SPMKit implementation yet",
                  "no GUI black-box execution",
                  "no universal Gwyddion version/build equivalence",
                  "helper-library internals were not "
                  "sanitizer-instrumented",
                  "finite-input campaign only",
                  "no horizontal pixel-displacement capability",
                  "no bidirectional channel-mismatch capability",
                  "no stripe-suppression capability",
                  "no generic outlier-line capability",
                  "no physical validation",
                  "no universal production tolerance selected"):
        assert claim in text, claim


def test_witness_arrays_stored_once() -> None:
    _, arrays = _load()
    # exactly 3 witness representatives (first member of each pair), each
    # with the standard field/line array set
    for a, _b in REPLAY_PAIRS:
        keys = [k for k in arrays if k.startswith(a + "_probe_")]
        assert len(keys) >= 5, (a, keys)
