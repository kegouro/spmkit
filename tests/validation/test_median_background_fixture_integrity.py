"""Integrity checks for frozen Gwyddion 2.71 Median Background evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "gwyddion" / "median_background"
_NPZ_PATH = _FIXTURE_DIR / "median_background_reference.npz"
_MANIFEST_PATH = _FIXTURE_DIR / "median_background_reference.json"
_EXPECTED_CASES = [
    "wide_r1",
    "wide_r2",
    "wide_r3",
    "wide_r4",
    "wide_r20",
    "tall_r1",
    "tall_r2",
    "tall_r3",
    "tall_r4",
    "tall_r20",
    "constant_r1",
    "constant_r3",
    "constant_r20",
    "signed_r1",
    "signed_r2",
    "signed_r3",
    "signed_r20",
    "singleton_1x1_r1",
    "singleton_1x1_r3",
    "singleton_1x1_r20",
    "singleton_1x1_r1024",
    "singleton_row_r1",
    "singleton_row_r3",
    "singleton_row_r20",
    "singleton_column_r1",
    "singleton_column_r3",
    "singleton_column_r20",
    "impulse_positive_r1",
    "impulse_positive_r2",
    "impulse_positive_r3",
    "impulse_negative_r1",
    "impulse_negative_r2",
    "impulse_negative_r3",
    "monotonic_r1",
    "monotonic_r2",
    "monotonic_r3",
]
_EXPECTED_RADIUS_INVENTORY = {
    "1": {"active_count": 9, "backend": "direct", "rank": 4, "resolution": 3},
    "2": {"active_count": 21, "backend": "direct", "rank": 10, "resolution": 5},
    "3": {"active_count": 37, "backend": "radixtree", "rank": 18, "resolution": 7},
    "4": {"active_count": 69, "backend": "radixtree", "rank": 34, "resolution": 9},
    "20": {"active_count": 1313, "backend": "radixtree", "rank": 656, "resolution": 41},
    "1024": {
        "active_count": 3297401,
        "backend": "radixtree",
        "rank": 1648700,
        "resolution": 2049,
    },
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_array_hash(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(contiguous.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(",".join(str(value) for value in contiguous.shape).encode("ascii"))
    digest.update(b"\0")
    digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def _load_manifest() -> dict[str, object]:
    with _MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_arrays_read_only() -> dict[str, np.ndarray]:
    arrays: dict[str, np.ndarray] = {}
    with np.load(_NPZ_PATH, allow_pickle=False) as archive:
        for name in archive.files:
            array = np.ascontiguousarray(archive[name]).copy(order="C")
            array.setflags(write=False)
            arrays[name] = array
    return arrays


def _cases(manifest: dict[str, object]) -> list[dict[str, object]]:
    return manifest["cases"]


def test_manifest_schema_and_identity() -> None:
    manifest = _load_manifest()

    assert manifest["schema_version"] == 1
    assert manifest["capability"] == "gwyddion_median_background"
    assert manifest["operation"] == "median_bg"
    assert manifest["reference_software"] == {"name": "Gwyddion", "version": "2.71"}
    assert manifest["fixture"]["case_count"] == 36
    assert manifest["oracle"]["canonical_source_array_hash_count"] == 180
    assert len(manifest["oracle"]["canonical_source_array_hashes"]) == 180
    assert "manifest_self_hash" not in manifest["fixture"]
    serialized = json.dumps(manifest, sort_keys=True)
    forbidden_markers = (
        "/" + "tmp/",
        "/" + "home/",
        "." + "reference",
        "_" + "_" + "pycache__",
    )
    assert not any(marker in serialized for marker in forbidden_markers)


def test_case_order_is_exact() -> None:
    manifest = _load_manifest()

    assert [case["name"] for case in _cases(manifest)] == _EXPECTED_CASES


def test_fixture_exists_and_hash_matches_manifest() -> None:
    manifest = _load_manifest()

    assert _NPZ_PATH.is_file()
    assert _sha256_file(_NPZ_PATH) == manifest["fixture"]["npz_sha256"]


def test_fixture_contains_exactly_108_arrays() -> None:
    arrays = _load_arrays_read_only()

    assert len(arrays) == 108


def test_fixture_contains_exactly_three_arrays_per_case() -> None:
    manifest = _load_manifest()
    arrays = _load_arrays_read_only()

    for case in _cases(manifest):
        names = set(case["arrays"].values())
        assert len(names) == 3
        assert names <= arrays.keys()


def test_fixture_array_names_are_exact() -> None:
    arrays = _load_arrays_read_only()
    expected_names = {
        f"{role}__{case}"
        for case in _EXPECTED_CASES
        for role in ("input", "background", "corrected")
    }

    assert set(arrays) == expected_names


def test_fixture_array_dtypes_are_float64() -> None:
    arrays = _load_arrays_read_only()

    assert all(array.dtype == np.float64 for array in arrays.values())


def test_fixture_arrays_are_two_dimensional() -> None:
    arrays = _load_arrays_read_only()

    assert all(array.ndim == 2 for array in arrays.values())


def test_fixture_arrays_are_c_contiguous() -> None:
    arrays = _load_arrays_read_only()

    assert all(array.flags.c_contiguous for array in arrays.values())


def test_fixture_arrays_are_finite() -> None:
    arrays = _load_arrays_read_only()

    assert all(np.isfinite(array).all() for array in arrays.values())


def test_fixture_shapes_match_manifest() -> None:
    manifest = _load_manifest()
    arrays = _load_arrays_read_only()

    for case in _cases(manifest):
        expected_shape = tuple(case["shape"])
        for name in case["arrays"].values():
            assert arrays[name].shape == expected_shape


def test_fixture_canonical_hashes_match_manifest() -> None:
    manifest = _load_manifest()
    arrays = _load_arrays_read_only()

    for case in _cases(manifest):
        for role, name in case["arrays"].items():
            assert _canonical_array_hash(arrays[name]) == case["canonical_hashes"][role]


def test_fixture_helper_returns_read_only_arrays() -> None:
    arrays = _load_arrays_read_only()

    assert all(not array.flags.writeable for array in arrays.values())


def test_background_and_corrected_shapes_match_input() -> None:
    manifest = _load_manifest()
    arrays = _load_arrays_read_only()

    for case in _cases(manifest):
        input_array = arrays[case["arrays"]["input"]]
        background = arrays[case["arrays"]["background"]]
        corrected = arrays[case["arrays"]["corrected"]]
        assert background.shape == input_array.shape
        assert corrected.shape == input_array.shape


def test_fixture_reconstruction_contract() -> None:
    manifest = _load_manifest()
    arrays = _load_arrays_read_only()
    reconstruction = manifest["acceptance_contract"]["reconstruction"]

    for case in _cases(manifest):
        input_array = arrays[case["arrays"]["input"]]
        background = arrays[case["arrays"]["background"]]
        corrected = arrays[case["arrays"]["corrected"]]
        np.testing.assert_allclose(
            input_array,
            background + corrected,
            atol=reconstruction["absolute_tolerance"],
            rtol=reconstruction["relative_tolerance"],
        )


def test_input_does_not_share_memory_with_outputs() -> None:
    manifest = _load_manifest()
    arrays = _load_arrays_read_only()

    for case in _cases(manifest):
        input_array = arrays[case["arrays"]["input"]]
        background = arrays[case["arrays"]["background"]]
        corrected = arrays[case["arrays"]["corrected"]]
        assert not np.shares_memory(input_array, background)
        assert not np.shares_memory(input_array, corrected)


def test_radius_and_backend_inventory_is_exact() -> None:
    manifest = _load_manifest()

    assert manifest["campaign"]["radius_inventory"] == _EXPECTED_RADIUS_INVENTORY
    assert {case["rank_backend_reference"] for case in _cases(manifest)} == {
        "direct",
        "radixtree",
    }


def test_evidence_classification_is_exact() -> None:
    manifest = _load_manifest()

    assert manifest["evidence_classification"] == {
        "external_probe": "EXECUTABLE_EXTERNAL_REFERENCE",
        "freeze_audit": "MEDIAN_BACKGROUND_ORACLE_FREEZE_APPROVED",
        "independent_oracle": "INDEPENDENT_PYTHON_ORACLE",
        "spmkit_implementation": "NOT_YET_IMPLEMENTED",
    }


def test_acceptance_contract_is_exact() -> None:
    manifest = _load_manifest()
    contract = manifest["acceptance_contract"]

    assert contract["background_comparison"] == "bitwise exact float64 equality"
    assert contract["corrected_comparison"] == "bitwise exact float64 equality"
    assert contract["output_dtype"] == "float64"
    assert contract["output_shape"] == "identical to input"
    assert contract["output_c_contiguous"] == "required"
    assert contract["output_finiteness"] == "required for finite inputs in this fixture"
    assert contract["input_mutation"] == "forbidden"
    assert contract["reconstruction"] == {
        "absolute_tolerance": 1e-15,
        "relation": "input == background + corrected",
        "relative_tolerance": 0.0,
    }
    assert contract["no_acceptance_relaxation"] == (
        "no acceptance relaxation may be introduced merely to satisfy tests"
    )


def test_fixture_contains_no_oracle_or_reference_arrays() -> None:
    arrays = _load_arrays_read_only()

    assert all(not name.startswith(("oracle_", "reference_")) for name in arrays)
