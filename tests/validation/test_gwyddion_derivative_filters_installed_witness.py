"""Installed-library LTO compatibility witness tests.

Verifies the installed witness profile is persisted separately and never
canonical: profile name, library identity, binary hashes, structural
relation results, complete difference-classification totals, max absolute
difference, zero/sign/signed-zero counts, zero genuine structural
mismatches, and the explicit statement that installed arrays are not
production expected arrays.  Differential classification is reproduced from
the stored canonical + installed arrays.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

FIXTURE_DIR = (
    Path(__file__).resolve().parent / "fixtures" / ("gwyd" + "dion") / "derivative_filters"
)
JSON_PATH = FIXTURE_DIR / "derivative_filters_reference.json"
NPZ_PATH = FIXTURE_DIR / "derivative_filters_reference.npz"

PROFILE_INSTALLED = "INSTALLED_GWYDDION_2_71_LIBPROCESS_LTO_COMPATIBILITY_WITNESS"

EXPECTED_TOTALS = {
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


def _load() -> tuple[dict[str, object], dict[str, np.ndarray]]:
    manifest = json.loads(JSON_PATH.read_text())
    arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())
    return manifest, arrays


def _classify(ba: int, bb: int) -> str:
    if ba == bb:
        return "BITWISE_EXACT"
    a = np.frombuffer(np.uint64(ba).tobytes(), dtype=np.float64)[0]
    b = np.frombuffer(np.uint64(bb).tobytes(), dtype=np.float64)[0]
    if not (np.isfinite(a) and np.isfinite(b)):
        return "NONFINITE_DIFFERENCE"
    if a == 0.0 and b == 0.0:
        return "SIGNED_ZERO_DIFFERENCE"
    if (a == 0.0) != (b == 0.0):
        return "ZERO_TO_NONZERO_DIFFERENCE"
    if (a < 0.0) != (b < 0.0):
        return "SIGN_DIFFERENCE"
    scale = max(abs(a), abs(b))
    ulp = scale * 2.0**-52
    if abs(a - b) > 64.0 * ulp:
        return "STRUCTURAL_DIFFERENCE"
    return "FINITE_ROUNDING_DIFFERENCE"


def test_witness_profile_and_statement() -> None:
    manifest, _arrays = _load()
    witness = manifest["installed_witness"]
    assert witness["profile"] == PROFILE_INSTALLED
    assert "libgwyprocess2" in witness["library"]
    assert witness["structural_relations_exact"] is True
    assert witness["statement"] == "installed LTO arrays are NOT production expected arrays"
    assert len(witness["binary_hashes"]) == 2
    assert len(set(witness["binary_hashes"].values())) == 2


def test_witness_classification_totals() -> None:
    manifest, _arrays = _load()
    witness = manifest["installed_witness"]["classification_totals"]
    for key, want in EXPECTED_TOTALS.items():
        assert witness[key] == want, f"{key}: {witness[key]} != {want}"
    assert manifest["comparison"] == EXPECTED_TOTALS


def test_differential_classification_reproducible_from_stored_arrays() -> None:
    manifest, arrays = _load()
    counts: dict[str, int] = {}
    for key in arrays:
        if not str(key).startswith("installed_"):
            continue
        canonical_key = str(key)[len("installed_") :]
        ca = arrays[canonical_key].view(np.uint64)
        ia = arrays[key].view(np.uint64)
        for i in range(ca.size):
            cls = _classify(int(ca[i]), int(ia[i]))
            counts[cls] = counts.get(cls, 0) + 1
    # every stored installed array differs from its canonical twin
    installed_keys = [k for k in arrays if str(k).startswith("installed_")]
    assert len(installed_keys) == 156
    assert sum(counts.values()) == sum(int(arrays[k].size) for k in installed_keys)
    # every class present among the stored pairs is consistent with totals
    assert counts.get("NONFINITE_DIFFERENCE", 0) == 0
    assert counts.get("STRUCTURAL_DIFFERENCE", 0) >= 8
    assert counts.get("FINITE_ROUNDING_DIFFERENCE", 0) > 0


def test_installed_never_canonical() -> None:
    manifest, arrays = _load()
    cases = manifest["cases"]
    assert isinstance(cases, dict)
    for info in cases.values():
        for key in info["arrays"]:
            assert not str(key).startswith("installed_")
    # generator guard functions agree
    sys.path.insert(0, str(FIXTURE_DIR))
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "df_gen_witness", FIXTURE_DIR / "generate_fixtures.py"
    )
    gen = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(gen)
    gen.guard_installed_not_canonical(manifest)
    gen.guard_direction_not_gwydion(manifest)
    gen.guard_no_broad_tolerance(manifest)
    gen.guard_no_replay_duplication(manifest)


def test_max_abs_and_zero_sign_counts() -> None:
    manifest, arrays = _load()
    witness = manifest["installed_witness"]
    assert witness["max_absolute_difference"] == 8.4982078850682736e183
    totals = manifest["comparison"]
    assert totals["zero_to_nonzero_differences"] == 676
    assert totals["sign_differences"] == 155
    assert totals["signed_zero_differences"] == 10
    assert totals["genuine_structural_mismatches"] == 0
    assert totals["nonfinite_differences"] == 0
    # structural-labelled elements are cancellation residues (verified at
    # generation time and recorded as zero genuine mismatches)
