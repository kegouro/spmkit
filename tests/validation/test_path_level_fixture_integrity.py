from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent / "fixtures/gwyddion/path_level"


def _canonical_hash(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(value.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(",".join(str(item) for item in value.shape).encode("ascii"))
    digest.update(b"\0")
    digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def test_path_level_fixture_integrity() -> None:
    manifest = json.loads((ROOT / "path_level_reference.json").read_text())
    assert manifest["schema_version"] == 1
    assert manifest["capability"] == "gwyddion_path_level"
    assert len(manifest["bases"]) == 18
    assert len(manifest["cases"]) == 72
    assert manifest["thicknesses"] == [1, 2, 3, 128]
    assert manifest["metrics"]["exact_elements"] == "4652/4652"
    assert manifest["metrics"]["external_oracle_arrays"] == "72/72 bitwise"
    assert manifest["line_order_discriminator"]["outputs_differ"] is True
    assert len({case["case_id"] for case in manifest["cases"]}) == 72
    assert all(len(case["lines_hex"]) == 4 * case["line_count"] for case in manifest["cases"])
    assert all(
        len(case["normalized_endpoints"]) == 4 * case["line_count"]
        for case in manifest["cases"]
    )
    external_artifacts = manifest["evidence"]["source_hashes"]["external_artifacts"]
    assert external_artifacts["canonical_reference.json"] == (
        "5dcbd07836de0d6cd856dbfe620f7c24edded25a993c17472746b09e80902d84"
    )
    assert manifest["evidence"]["source_hashes"]["oracle_artifacts"]["path_level_oracle.py"] == (
        "9b4ec65ba67777c211ab08c73d91bf523ee5082f04ce0424ea4f1fe569ae58f1"
    )
    with np.load(ROOT / "path_level_reference.npz", allow_pickle=False) as archive:
        assert len(archive.files) == 90
        assert set(archive.files) == set(manifest["fixture"]["array_hashes"])
        for name in archive.files:
            array = archive[name]
            assert array.dtype == np.float64
            assert array.ndim == 2 and array.flags.c_contiguous
            assert np.isfinite(array).all()
            assert _canonical_hash(array) == manifest["fixture"]["array_hashes"][name]
        assert archive["input__singleton_row_1x9_horizontal"].view(np.uint64)[0, 0] == 1 << 63
        for base in manifest["bases"]:
            assert base["input_key"] in archive.files
            assert list(archive[base["input_key"]].shape) == base["shape"]
        for case in manifest["cases"]:
            assert case["output_key"] in archive.files
            assert archive[case["output_key"]].shape == archive[
                f"input__{case['base_id']}"
            ].shape
