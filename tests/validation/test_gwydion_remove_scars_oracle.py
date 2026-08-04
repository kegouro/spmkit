"""Oracle tests for the independent Remove Scars composition reference.

Verifies the compiled-evidence composition identities (standalone Mark mask
== Remove temporary mask, temporary mask unmutated, standalone Laplace ==
Remove output) from the frozen fixtures, and the independent composition
(mathematical Laplace over the independent Mark mask) consistency.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwydion" / "scars_laplace"
NPZ_PATH = FIXTURE_DIR / "scars_laplace_reference.npz"
JSON_PATH = FIXTURE_DIR / "scars_laplace_reference.json"

REMOVE_CASES = [
    "R01_positive", "R02_negative", "R03_both", "R04_no_detection",
    "R05_edge_touching", "R06_long_wide",
]

sys.path.insert(0, str(FIXTURE_DIR))
from oracle_remove_scars import oracle_remove_scars  # noqa: E402  # isort: skip

arrays = dict(np.load(NPZ_PATH, allow_pickle=False))
manifest = json.loads(JSON_PATH.read_text())


def test_compiled_composition_identities() -> None:
    for cid in REMOVE_CASES:
        assert np.array_equal(
            arrays[f"{cid}_probe_temp_mask"].view(np.uint64),
            arrays[f"{cid}_probe_standalone_mask"].view(np.uint64)), cid
        assert np.array_equal(
            arrays[f"{cid}_probe_temp_mask"].view(np.uint64),
            arrays[f"{cid}_probe_temp_mask_after"].view(np.uint64)), cid
        assert np.array_equal(
            arrays[f"{cid}_probe_corrected"].view(np.uint64),
            arrays[f"{cid}_probe_standalone_corrected"].view(np.uint64)), cid
        entry = manifest["per_case"][cid]
        assert entry["mask_identity"] is True, cid
        assert entry["composition_identity"] is True, cid
        assert entry["temp_mask_unmutated"] is True, cid


def test_independent_composition_matches_compiled_mask() -> None:
    for cid in REMOVE_CASES:
        ref = oracle_remove_scars(
            arrays[f"{cid}_probe_input"],
            compiled_standalone_mask=arrays[f"{cid}_probe_standalone_mask"],
            compiled_temp_mask=arrays[f"{cid}_probe_temp_mask"],
            compiled_standalone_laplace=arrays[
                f"{cid}_probe_standalone_corrected"],
            compiled_remove_result=arrays[f"{cid}_probe_corrected"])
        assert ref.mask_identity, cid
        assert ref.compiled_composition_identity, cid
        # the independent Mark mask is bitwise identical to the compiled one
        assert np.array_equal(
            ref.independent_temporary_mask.view(np.uint64),
            arrays[f"{cid}_probe_temp_mask"].view(np.uint64)), cid
        if cid != "R04_no_detection":
            assert not ref.mark_guard_triggered, cid
        else:
            assert ref.mark_guard_triggered, cid


def test_no_detection_path() -> None:
    ref = oracle_remove_scars(arrays["R04_no_detection_probe_input"])
    assert ref.mark_guard_triggered
    assert not np.any(ref.independent_temporary_mask == 1.0)
    assert np.array_equal(
        arrays["R04_no_detection_probe_corrected"].view(np.uint64),
        arrays["R04_no_detection_probe_input"].view(np.uint64))


def test_scar_pixel_counts() -> None:
    counts = {"R01": 16, "R02": 16, "R03": 32, "R05": 16, "R06": 48}
    for cid, expected in counts.items():
        full = next(c for c in REMOVE_CASES if c.startswith(cid + "_"))
        mask = arrays[f"{full}_probe_temp_mask"]
        assert int(np.count_nonzero(mask == 1.0)) == expected, cid


def test_oracle_never_reads_expected_outputs() -> None:
    import inspect

    import oracle_remove_scars as ors
    source = inspect.getsource(ors)
    assert "reference.json" not in source
    assert "reference.npz" not in source
    assert "np.load" not in source
