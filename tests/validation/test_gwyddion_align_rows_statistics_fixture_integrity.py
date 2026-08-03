from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent / "fixtures/gwyddion/align_rows_statistics"
MANIFEST_SHA256 = "be6f6b91f063c57f882e57f8aa685f1845c6ccfc41b82365f0c648e7ac98781f"
NPZ_SHA256 = "0098e804597440419fd1eea2914ddccd7bbb5412c8691a8e3c34f0538983119e"


def _digest(file_path: Path) -> str:
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def _array_hash(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array, dtype=np.float64)
    digest = hashlib.sha256()
    digest.update(value.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(",".join(str(item) for item in value.shape).encode("ascii"))
    digest.update(b"\0")
    digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def _bits(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array, dtype=np.float64).view(np.uint64)


def _subtraction_in_order(input_data: np.ndarray, corrected: np.ndarray) -> np.ndarray:
    result = np.empty_like(input_data, order="C")
    for row in range(input_data.shape[0]):
        for column in range(input_data.shape[1]):
            result[row, column] = input_data[row, column] - corrected[row, column]
    return result


def _load() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    manifest = json.loads((ROOT / "align_rows_statistics_reference.json").read_text())
    with np.load(ROOT / "align_rows_statistics_reference.npz", allow_pickle=False) as archive:
        arrays = {name: archive[name].copy(order="C") for name in archive.files}
    return manifest, arrays


def test_fixture_hashes_inventory_and_deterministic_loading() -> None:
    assert _digest(ROOT / "align_rows_statistics_reference.json") == MANIFEST_SHA256
    assert _digest(ROOT / "align_rows_statistics_reference.npz") == NPZ_SHA256
    manifest, first = _load()
    _, second = _load()
    assert manifest["schema_version"] == 1
    assert manifest["capability"] == "gwyddion_align_rows_statistics"
    assert manifest["case_count"] == 64
    assert manifest["method_counts"] == {
        "Median": 16,
        "Median of differences": 16,
        "Trimmed mean": 16,
        "Trimmed mean of differences": 16,
    }
    cases = manifest["cases"]
    assert len(cases) == 64
    assert len({case["case_identifier"] for case in cases}) == 64
    assert set(first) == set(manifest["fixture"]["array_hashes"])
    assert set(first) == set(second)
    for name, array in first.items():
        assert array.dtype == np.float64 and array.flags.c_contiguous
        assert array.ndim == 2 and np.isfinite(array).all()
        assert _array_hash(array) == manifest["fixture"]["array_hashes"][name]
        assert np.array_equal(_bits(array), _bits(second[name]))


def test_profile_identity_exception_scope_and_background_relations() -> None:
    manifest, arrays = _load()
    assert manifest["profiles"]["portable_source_semantics"]["candidate_output_sha256"] == (
        "7da7283019d698089d1a9cca4cec712860529fce42c2cb0752c2b136ecd1cb30"
    )
    assert manifest["profiles"]["installed_gwyddion_2_71_fast_math_profile"][
        "canonical_reference_sha256"
    ] == ("e2fa6d094acc5ec04f87901aa345244f9d22e70577d25f963a8cdb74363e457e")
    assert manifest["profiles"]["installed_gwyddion_2_71_fast_math_profile"]["module_sha256"] == (
        "c21d52375807ae096e34a3469c2f20c4c66ea3197479e13215a6d7b9d465b451"
    )
    assert manifest["evidence"]["installed_build_diagnosis"] == [
        "INSTALLED_BUILD_ROOT_CAUSE_CONFIRMED",
        "V3_NOT_JUSTIFIED",
    ]

    mismatching_cases: set[str] = set()
    finite_nonzero = signed_zero = nan = infinity = exact_arrays = exact_elements = 0
    background_arrays = background_elements = mutation_matches = 0
    for case in manifest["cases"]:
        input_data = arrays[case["input_key"]]
        portable = arrays[case["portable_corrected_key"]]
        installed = arrays[case["installed_corrected_key"]]
        assert input_data.shape == (case["rows"], case["columns"])
        assert _bits(input_data).ravel().tolist() == [
            int(value, 16) for value in case["input_bits"]
        ]
        if case["mask_key"] is None:
            assert case["mask_bits"] is None
        else:
            assert _bits(arrays[case["mask_key"]]).ravel().tolist() == [
                int(value, 16) for value in case["mask_bits"]
            ]
        portable_bits = _bits(portable)
        installed_bits = _bits(installed)
        differing = portable_bits != installed_bits
        exact_elements += int((~differing).sum())
        exact_arrays += int(not differing.any())
        if differing.any():
            mismatching_cases.add(case["case_identifier"])
        for row, column in np.argwhere(differing):
            left = portable[row, column]
            right = installed[row, column]
            if np.isnan(left) or np.isnan(right):
                nan += 1
            elif np.isinf(left) or np.isinf(right):
                infinity += 1
            elif left == right == 0.0:
                signed_zero += 1
            else:
                finite_nonzero += 1
        portable_mutated = bool((_bits(portable) != _bits(input_data)).any())
        installed_mutated = bool((_bits(installed) != _bits(input_data)).any())
        mutation_matches += int(portable_mutated == installed_mutated == case["installed_mutated"])
        if case["extract_background_request"]:
            portable_background = arrays[case["portable_background_key"]]
            installed_background = arrays[case["installed_background_key"]]
            assert np.array_equal(_bits(portable_background), _bits(installed_background))
            assert np.array_equal(
                _bits(portable_background), _bits(_subtraction_in_order(input_data, portable))
            )
            assert np.array_equal(
                _bits(installed_background), _bits(_subtraction_in_order(input_data, installed))
            )
            background_arrays += 1
            background_elements += portable_background.size
    assert exact_arrays == 61
    assert exact_elements == 3757
    assert finite_nonzero == 128
    assert signed_zero == 3
    assert nan == infinity == 0
    assert mismatching_cases == {
        "median__plateaus_signed_zero__10",
        "median_of_differences__irregular__11",
        "trimmed_mean_of_differences__irregular__11",
    }
    assert background_arrays == 8 and background_elements == 504
    assert mutation_matches == 64
    exceptions = manifest["comparison_metrics"]["authorized_exceptions"]
    assert {item["case_identifier"] for item in exceptions} == mismatching_cases
    assert sum(item["finite_nonzero_count"] for item in exceptions) == 128
    assert sum(item["signed_zero_only_count"] for item in exceptions) == 3
    assert (
        manifest["comparison_metrics"]["corrected"]["max_absolute_difference"]
        == 5.329070518200751e-15
    )
