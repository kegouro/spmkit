from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent / "fixtures/gwyddion/flat_disc_morphology"


def _hash(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(value.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(",".join(str(item) for item in value.shape).encode("ascii"))
    digest.update(b"\0")
    digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def test_flat_disc_fixture_integrity() -> None:
    manifest = json.loads((ROOT / "flat_disc_morphology_reference.json").read_text())
    assert manifest["schema_version"] == 1
    assert len(manifest["cases"]) == 12
    assert manifest["sizes_exercised"] == [2, 3, 4, 5, 30, 31]
    assert len(manifest["kernel_masks"]) == 30
    assert manifest["metrics"]["opening_bitwise_exact"] == "72/72"
    assert manifest["metrics"]["closing_bitwise_exact"] == "72/72"
    with np.load(ROOT / "flat_disc_morphology_reference.npz", allow_pickle=False) as data:
        assert len(data.files) == 186
        assert set(data.files) == set(manifest["fixture"]["array_hashes"])
        for name in data.files:
            array = data[name]
            assert array.ndim == 2 and array.flags.c_contiguous
            assert np.isfinite(array).all()
            assert _hash(array) == manifest["fixture"]["array_hashes"][name]
        assert data["input__singleton_row_1x7"].view(np.uint64)[0, 0] == 1 << 63
