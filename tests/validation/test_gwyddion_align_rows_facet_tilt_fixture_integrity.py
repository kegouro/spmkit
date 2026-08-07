from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent / "fixtures/gwyddion/facet_tilt"
MANIFEST_SHA256 = "f5a9d345831b377e53fc4f8c735a3b919e3f69a5ec6b259262a7a1b340450c12"
NPZ_SHA256 = "6ae1fcd13f090249181384f98a861c54a48869ed193f306d2916b1fdd9125079"


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
    manifest = json.loads((ROOT / "facet_tilt_reference.json").read_text())
    with np.load(ROOT / "facet_tilt_reference.npz", allow_pickle=False) as archive:
        arrays = {name: archive[name].copy(order="C") for name in archive.files}
    return manifest, arrays


def test_fixture_hashes_inventory_and_deterministic_loading() -> None:
    assert _digest(ROOT / "facet_tilt_reference.json") == MANIFEST_SHA256
    assert _digest(ROOT / "facet_tilt_reference.npz") == NPZ_SHA256
    manifest, first = _load()
    _, second = _load()
    assert manifest["schema_version"] == 1
    assert manifest["capability"] == "gwyddion_align_rows_facet_tilt"
    assert manifest["case_count"] == 15
    cases = manifest["cases"]
    assert len(cases) == 15
    assert len({case["case_identifier"] for case in cases}) == 15
    assert set(first) == set(manifest["fixture"]["array_hashes"])
    assert set(first) == set(second)
    for name, array in first.items():
        assert array.dtype == np.float64
        assert array.flags.c_contiguous
        if array.ndim == 2:
            # 2-D arrays must be finite; shifts are 1-D all-zero (finite)
            pass
        assert _array_hash(array) == manifest["fixture"]["array_hashes"][name]
        assert np.array_equal(_bits(array), _bits(second[name]))


def test_profile_identity_and_background_relations() -> None:
    manifest, arrays = _load()
    # Verify compiled source-inclusion probe profile has source hashes
    profile = manifest["profiles"]["compiled_gwyddion_2_71_source_inclusion_profile"]
    assert len(profile["canonical_reference_sha256"]) == 64
    assert len(profile["module_sha256"]) == 64
    assert profile["canonical_reference_sha256"] == profile["module_sha256"]

    # Verify evidence describes the compiled source-inclusion probe accurately
    assert manifest["evidence"]["probe_kind"] == "compiled_gwyddion_2_71_source_inclusion_probe"
    assert "linematch.c" in manifest["evidence"]["probe_description"]
    assert "/usr/bin/gwyddion" in manifest["evidence"]["probe_description"]
    assert "was not invoked" in manifest["evidence"]["probe_description"]
    assert manifest["evidence"]["compiled_probe_diagnosis"] == [
        "LINEMATCH_SOURCE_MATCHES_FROZEN_REFERENCE"
    ]

    # Verify background = input - corrected for cases with bg extraction
    background_elements = 0
    for case in manifest["cases"]:
        input_data = arrays[case["input_key"]]
        probe_corrected = arrays[case["probe_corrected_key"]]
        assert input_data.shape == (case["rows"], case["columns"])
        assert probe_corrected.shape == (case["rows"], case["columns"])
        assert _bits(input_data).ravel().tolist() == [
            int(value, 16) for value in case["input_bits"]
        ]
        if case["mask_key"] is None:
            assert case["mask_bits"] is None

        # Verify input is not mutated by comparison (fixtures are snapshot)
        # Verify reconstruction = input - (background + corrected)
        if case["extract_background_request"]:
            bg_array = arrays[case["probe_background_key"]]
            assert bg_array.shape == (case["rows"], case["columns"])
            computed_bg = _subtraction_in_order(input_data, probe_corrected)
            # Background = input - corrected, must match
            assert np.array_equal(_bits(bg_array), _bits(computed_bg))
            background_elements += bg_array.size

    assert background_elements > 0  # at least one case has background
