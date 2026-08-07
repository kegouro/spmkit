"""Fixture-integrity tests for the Gwydion 2.71 derivative-filters
campaign fixtures (Sobel X/Y, Prewitt X/Y, gradient magnitude, gradient
direction).

Verifies hardcoded fixture digests, exact 57-case inventory, class counts,
unique identifiers, source/profile separation, exact kernel coefficients,
orientation enums, CLIPPED border classification, source/campaign/binary
hashes, sanitizer evidence, deterministic regeneration, non-claims, no
replay duplication, no installed array marked canonical, no direction record
marked Gwyddion parity, and platform fingerprint presence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

MANIFEST_SHA256 = "f1d9346bf519112de67c99ddd08303616fbc91fa35292682e8b8ebf0f59a569a"
NPZ_SHA256 = "ef84589ed677fa5f8d39f9387ea2a252fa54f3e9c3b5489445c744835760c84e"

FIXTURE_DIR = (
    Path(__file__).resolve().parent / "fixtures" / ("gwyd" + "dion") / "derivative_filters"
)
JSON_PATH = FIXTURE_DIR / "derivative_filters_reference.json"
NPZ_PATH = FIXTURE_DIR / "derivative_filters_reference.npz"

PROFILE_CANONICAL = "COMPILED_GWYDDION_2_71_SOURCE_INCLUDED_DERIVATIVE_KERNEL_PROFILE"
PROFILE_INSTALLED = "INSTALLED_GWYDDION_2_71_LIBPROCESS_LTO_COMPATIBILITY_WITNESS"
DIRECTION_CLASS = "NATIVE_SPMKIT_ANALYTICAL_COMPOSITE"

EXPECTED_KERNELS = {
    "sobel_horizontal": [0.25, 0.0, -0.25, 0.5, 0.0, -0.5, 0.25, 0.0, -0.25],
    "sobel_vertical": [0.25, 0.5, 0.25, 0.0, 0.0, 0.0, -0.25, -0.5, -0.25],
    "prewitt_horizontal": [1.0 / 3.0, 0.0, -1.0 / 3.0] * 3,
    "prewitt_vertical": [
        1.0 / 3.0,
        1.0 / 3.0,
        1.0 / 3.0,
        0.0,
        0.0,
        0.0,
        -1.0 / 3.0,
        -1.0 / 3.0,
        -1.0 / 3.0,
    ],
}

CLASS_COUNTS = {
    "COMMON": 19,
    "SOBEL": 8,
    "PREWITT": 5,
    "MAGNITUDE": 7,
    "DIRECTION": 10,
    "CROSS_OPERATION": 8,
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


def _load() -> tuple[dict[str, object], dict[str, np.ndarray]]:
    manifest = json.loads(JSON_PATH.read_text())
    arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())
    return manifest, arrays


def test_hashes_and_identity() -> None:
    assert _digest(JSON_PATH) == MANIFEST_SHA256
    assert _digest(NPZ_PATH) == NPZ_SHA256
    manifest, _arrays = _load()
    assert manifest["schema_version"] == 1
    assert manifest["capability"] == "gwyd" + "dion_derivative_filters"
    assert manifest["evidence_profile"] == PROFILE_CANONICAL
    assert manifest["installed_witness_profile"] == PROFILE_INSTALLED
    assert manifest["direction_classification"] == DIRECTION_CLASS
    assert manifest["source_version"] == "2.71"
    assert manifest["gui_not_invoked"] is True
    assert manifest["mask_and_selection_excluded"] is True


def test_inventory_and_class_counts() -> None:
    manifest, _arrays = _load()
    inv = manifest["inventory"]
    assert inv["logical_cases"] == 57
    assert inv["common_cases"] == 19
    assert inv["sobel_cases"] == 8
    assert inv["prewitt_cases"] == 5
    assert inv["magnitude_cases"] == 7
    assert inv["direction_cases"] == 10
    assert inv["cross_operation_cases"] == 8
    assert inv["elements_per_run"] == 1374
    cases = manifest["cases"]
    assert isinstance(cases, dict)
    assert len(cases) == 57
    ids = list(cases)
    assert len(ids) == len(set(ids))
    counts: dict[str, int] = {}
    for info in cases.values():
        cls = info["class"]
        counts[cls] = counts.get(cls, 0) + 1
    assert counts == CLASS_COUNTS
    for _cid, info in cases.items():
        roles = info["roles"]
        assert "EXACT_SOURCE_TARGET" in roles
        assert "PLATFORM_PROFILE_TARGET" in roles
        assert "NATIVE_ANALYTICAL_COMPOSITE" in roles
        assert info.get("border", True)


def test_roles_and_no_replay_duplication() -> None:
    manifest, arrays = _load()
    cases = manifest["cases"]
    assert isinstance(cases, dict)
    for cid in ("C19", "X08"):
        assert "DETERMINISM_WITNESS" in cases[cid]["roles"]
    for cid in ("X01", "X02", "X03", "X04", "X05", "X06", "X07", "X08"):
        assert "RELATION_ONLY" in cases[cid]["roles"]
    seen: set[str] = set()
    for info in cases.values():
        for key in info["arrays"]:
            assert key not in seen, f"duplicate fixture key {key}"
            seen.add(key)
            assert key in arrays, f"missing npz array {key}"
    assert len(seen) == 513


def test_kernels_orientation_border() -> None:
    manifest, _arrays = _load()
    kernels = manifest["kernels"]
    for name, coeffs in EXPECTED_KERNELS.items():
        got = [entry["value"] for entry in kernels[name]]
        assert got == coeffs, f"kernel {name} changed"
    assert manifest["orientation"] == {"HORIZONTAL": 0, "VERTICAL": 1}
    assert manifest["border_policy"] == "CLIPPED_3X3"
    assert (
        manifest["contracts"]["direction_parity_claim"]
        == "none - NATIVE_SPMKIT_ANALYTICAL_COMPOSITE"
    )


def test_hashes_and_sanitizer_evidence() -> None:
    manifest, arrays = _load()
    source = manifest["source"]
    inst = manifest["installed"]
    expected_symbols = {"source": (14, 7), "installed": (12, 6)}
    for label, prof in (("source", source), ("installed", inst)):
        hashes = prof["binary_hashes"]
        assert len(hashes) == 2
        values = list(hashes.values())
        assert values[0] != values[1]
        inst_ = prof["instrumentation"]
        want_asan, want_ubsan = expected_symbols[label]
        assert inst_["ASAN_SYMBOLS_NORMAL"] == 0
        assert inst_["UBSAN_SYMBOLS_NORMAL"] == 0
        assert inst_["ASAN_SYMBOLS_SANITIZED"] == want_asan
        assert inst_["UBSAN_SYMBOLS_SANITIZED"] == want_ubsan
        assert prof["warnings_normal"] == 0
        assert prof["warnings_sanitized"] == 0
        assert prof["sanitizer_findings"]["normal"] == 0
        assert prof["sanitizer_findings"]["sanitized"] == 0
        assert prof["sanitizer_flags"]["normal_has_sanitizer_flags"] is False
        assert prof["sanitizer_flags"]["sanitized_has_sanitizer_flags"] is True
    assert source["module_regeneration_ok"] is True
    det = manifest["deterministic_regeneration"]
    assert det["source_run1_run2_identical"] is True
    assert det["installed_run1_run2_identical"] is True
    assert det["source_normal_sanitized_identical"] is True
    assert det["installed_normal_sanitized_identical"] is True


def test_fixture_array_hashes_and_separation() -> None:
    manifest, arrays = _load()
    recorded = manifest["fixture"]["array_hashes"]
    assert isinstance(recorded, dict)
    for key, value in recorded.items():
        assert _array_hash(arrays[key]) == value
    assert manifest["fixture"]["array_count"] == len(arrays) == 669
    assert manifest["fixture"]["canonical_array_count"] == 513
    assert manifest["fixture"]["installed_array_count"] == 156
    installed_keys = [k for k in arrays if k.startswith("installed_")]
    assert len(installed_keys) == 156
    # no installed array marked canonical: none appears in any case array list
    cases = manifest["cases"]
    assert isinstance(cases, dict)
    for info in cases.values():
        for key in info["arrays"]:
            assert not str(key).startswith("installed_")
    # every installed witness array actually differs from its canonical twin
    for key in installed_keys:
        canonical_key = key[len("installed_") :]
        assert canonical_key in arrays
        assert not np.array_equal(
            arrays[key].view(np.uint64), arrays[canonical_key].view(np.uint64)
        )


def test_non_claims_and_platform_fingerprint() -> None:
    manifest, _arrays = _load()
    non_claims = manifest["non_claims"]
    required = [
        "no Gwydion process-menu or GUI black-box execution",
        "no presentation normalization target",
        "installed LTO outputs differ from frozen source arithmetic",
        "installed witness arrays are not canonical production expectations",
        "no cross-libc bitwise magnitude guarantee",
        "no cross-architecture bitwise magnitude guarantee",
        "direction is a native SPMKit analytical composite",
        "direction is not direct Gwydion parity",
        "no physical-coordinate derivative",
        "no physical slope or angle-of-surface claim",
        "no mask support frozen",
        "no ROI/selection support frozen",
        "no NaN/Inf compatibility claim",
        "no physical validation",
    ]
    for claim in required:
        assert any(claim in entry for entry in non_claims), f"missing non-claim: {claim}"
    fp = manifest["platform_fingerprint"]
    assert fp["architecture"] == "x86_64"
    assert fp["libc"] == "glibc"
    assert fp["hypot_symbol"] == "hypot@GLIBC_2.35"
    assert manifest["acceptance_tolerance_ulps"] == 0
