"""Fixture-integrity tests for the Gwydion 2.71 neighborhood-filters
campaign fixtures (Rank Filter, disc Median, Gaussian).

Verifies hardcoded hashes, exact execution/logical inventory, family and
classification counts, stored-array hashes, source/campaign/binary hashes,
distinct binaries, sanitizer flags and symbols, two-run determinism,
required non-claims, and no-duplicate-replay-arrays.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

MANIFEST_SHA256 = "25c9e9cbbe78c93ce36f283923479e976371004451b680cf4667bfb369d82a78"
NPZ_SHA256 = "ef8dfb2f5ebddc91ee3ef381e747e89e40cbd9c8bae06d95fa7cd59eff03cf8d"

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwyddion" / \
    "neighborhood_filters"
JSON_PATH = FIXTURE_DIR / "neighborhood_filters_reference.json"
NPZ_PATH = FIXTURE_DIR / "neighborhood_filters_reference.npz"

PROFILE = "COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_KERNEL_WITH_SOURCE_PINNED_ORCHESTRATION"

EXPECTED_BINARY_HASHES = {
    "bin/neighborhood_filters_probe":
        "6f4c5bd08283554113949bc7078cf440455595fbab08f9b668717c74b8655fa3",
    "bin/neighborhood_filters_probe.san":
        "a82121dafc8a7ff0a5b3f1855d8bc108f26b063a75b37529c954c6b01f093c5a",
}


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
    assert manifest["capability"] == "gwydion_neighborhood_filters"
    assert manifest["evidence_profile"] == PROFILE
    assert manifest["source_version"] == "2.71"
    assert manifest["gui_not_invoked"]
    assert manifest["mask_and_selection_excluded"]
    inv = manifest["inventory"]
    assert inv["physical_executions_per_build"] == 71
    assert inv["total_executions"] == 142
    assert inv["logical_cases"] == 71
    assert inv["family_counts"] == {"rank": 20, "median": 19, "gaussian": 20,
                                    "cross": 6, "footprint": 6}
    assert inv["canonical_numerical_cases"] == 59
    assert inv["public_tool_domain_cases"] == 55
    assert inv["library_domain_only_cases"] == 1
    assert inv["output_mode_cases"] == 3
    assert inv["relation_only_cases"] == 11
    assert inv["determinism_witnesses"] == 1
    assert len(manifest["execution_records"]) == 71
    cases = manifest["cases"]
    assert len(cases) == 71
    ids = [c["case_identifier"] for c in cases]
    assert len(ids) == len(set(ids))
    # every canonical case has stored arrays and bitwise source oracle
    for case in cases:
        if "source_oracle" in case:
            so = case["source_oracle"]
            assert so["result"]["arrays_bitwise_exact"], case["case_identifier"]
            assert so["input_non_mutation"], case["case_identifier"]
            assert case["stored_arrays"]
    assert manifest["fixture"]["source_oracle_bitwise"]
    for key, arr in arrays.items():
        assert _array_hash(arr) == manifest["fixture"]["array_hashes"][key]
        assert arr.dtype == np.float64


def test_binary_hashes_and_sanitizer() -> None:
    manifest, _ = _load()
    bh = manifest["binary_hashes"]
    assert bh == EXPECTED_BINARY_HASHES
    assert manifest["sanitizer"]["binaries_distinct"]
    flags = manifest["sanitizer"]["flags"]
    assert "-fsanitize=address,undefined" in flags
    assert "-fno-sanitize-recover=all" in flags
    symbols = manifest["sanitizer"]["symbols"]
    assert symbols == {"normal": 0, "sanitized": 15}
    scope = manifest["sanitizer"]["scope"]
    assert "not rebuilt with sanitizers" in scope
    assert manifest["sanitizer"]["sanitizer_findings"] == 0


def test_source_and_campaign_hashes() -> None:
    manifest, _ = _load()
    sh = manifest["source_hashes"]
    assert len(sh) == 16
    for rel in ("modules/process/rank-filter.c", "modules/tools/filter.c",
                "libprocess/filters-minmax.c", "libprocess/filters-convdeconv.c",
                "libprocess/elliptic.c", "libprocess/filters.c",
                "libgwyd" + "dion/gwymath-rank.c",
                "neighborhood_filters_behavior_probe.c",
                "run_neighborhood_filters_probe_campaign.sh"):
        assert rel in sh, rel
        assert len(sh[rel]) == 64
    ch = manifest["campaign_hashes"]
    assert len(ch) == 5


def test_two_run_deterministic_identity() -> None:
    manifest, _ = _load()
    assert manifest["evidence_roots"]["deterministic_identity"]


def test_no_duplicate_replay_arrays() -> None:
    _, arrays = _load()
    # the replay witness stores no canonical arrays in the NPZ
    assert not any("X06_DETERMINISTIC_REPLAY_probe_" in k for k in arrays)
    manifest, _ = _load()
    assert manifest["relations"]["determinism_replay"] == [
        "X06_DETERMINISTIC_REPLAY"]


def test_non_claims_present() -> None:
    manifest, _ = _load()
    text = "\n".join(manifest["non_claims"])
    for claim in ("no production implementation yet", "no mask support",
                  "no rectangular selection support", "no Mean capability",
                  "no public Minimum/Maximum capability",
                  "no morphology capability", "no frequency-domain filtering",
                  "no NaN/Inf compatibility", "no GUI black-box validation",
                  "no universal Gwydion build equivalence",
                  "dynamically linked helpers not sanitizer-rebuilt",
                  "no physical validation",
                  "no production tolerance selected"):
        assert claim in text, claim


def test_classification_coverage() -> None:
    manifest, _ = _load()
    from collections import Counter
    cls = Counter(c["classification"] for c in manifest["cases"])
    assert cls["PUBLIC_TOOL_DOMAIN_CASE"] == 55
    assert cls["LIBRARY_DOMAIN_ONLY_CASE"] == 1
    assert cls["OUTPUT_MODE_CASE"] == 3
    assert cls["CROSS_OPERATION_RELATION_CASE"] == 5
    assert cls["FOOTPRINT_RELATION_CASE"] == 6
    assert cls["DETERMINISM_WITNESS"] == 1
    # G05 is the library-only sigma=0 case
    g05 = next(c for c in manifest["cases"]
               if c["case_identifier"] == "G05_SIGMA_ZERO_LIBRARY")
    assert g05["classification"] == "LIBRARY_DOMAIN_ONLY_CASE"
    assert g05["res"] == 0
