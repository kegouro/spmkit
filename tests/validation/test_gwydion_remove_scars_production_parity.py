"""Production parity: Remove Scars composition vs the frozen evidence.

For all six frozen cases: the production temporary mask must be bitwise
equal to the frozen compiled mask, the production result must equal the
explicit production composition, and the corrected field must stay within
the per-case Laplace policy of the frozen compiled output (iterative
paths: max ULP <= 2 and max absolute difference <=
1.7763568394002505e-15, with the raw-bit ULP metric meaningful only
between nonzero operands).  The no-detection case must remain bitwise
unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from spmkit.core.analysis import (
    gwydion_interpolate_data_under_mask,
    gwydion_mark_scars,
    gwydion_remove_scars,
)
from spmkit.core.analysis._gwydion_remove_scars import _gwydion_remove_scars_result
from spmkit.core.models.spmdata import SPMChannel

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwydion" / "scars_laplace"
JSON_PATH = FIXTURE_DIR / "scars_laplace_reference.json"
NPZ_PATH = FIXTURE_DIR / "scars_laplace_reference.npz"

REMOVE_CASES = [
    "R01_positive", "R02_negative", "R03_both", "R04_no_detection",
    "R05_edge_touching", "R06_long_wide",
]

FROZEN_MAX_ABS = 1.7763568394002505e-15
FROZEN_MAX_ULP = 2

_manifest = json.loads(JSON_PATH.read_text())
_arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())


def _bits(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array, dtype=np.float64).view(np.uint64)


def _channel(data: np.ndarray) -> SPMChannel:
    return SPMChannel(
        name="parity", data=np.asarray(data, dtype=np.float64), unit="nm",
        x_range=float(data.shape[1]), y_range=float(data.shape[0]))


def _probe(case_id: str, label: str) -> np.ndarray:
    return _arrays[f"{case_id}_probe_{label}"]


def _metrics(probe: np.ndarray, out: np.ndarray) -> dict:
    """Four explicit comparison classes:

    1. bitwise-identical elements;
    2. signed-zero-only differences, reported separately;
    3. exact-zero versus finite-nonzero differences, governed by the frozen
       absolute-difference bound and the production residual guard (never
       silently discarded, never described as satisfying ULP <= 2);
    4. finite-nonzero differences, governed by the ordered-float ULP bound.

    ULP distance is not used as the compatibility metric across an
    exact-zero / finite-nonzero transition because it is not comparable to
    the local finite-nonzero ULP bound; that class is enforced separately
    by absolute error and residual.
    """
    pb = _bits(probe).ravel()
    ob = _bits(out).ravel()
    max_abs = 0.0
    max_ulp = 0
    signed_zero = 0
    zero_nonzero = 0
    for i in range(pb.size):
        if pb[i] == ob[i]:
            continue
        xor = int(pb[i]) ^ int(ob[i])
        if xor == 0x8000000000000000:
            signed_zero += 1
            continue
        pv = float(probe.ravel()[i])
        ov = float(out.ravel()[i])
        max_abs = max(max_abs, abs(pv - ov))
        if pv == 0.0 or ov == 0.0:
            zero_nonzero += 1
            continue
        max_ulp = max(max_ulp, abs(int(pb[i]) - int(ob[i])))
    return {"bitwise": int(np.count_nonzero(pb == ob)),
            "total": int(pb.size), "max_abs": max_abs, "max_ulp": max_ulp,
            "signed_zero": signed_zero, "zero_nonzero": zero_nonzero}


def test_temporary_mask_bitwise_identity() -> None:
    for case_id in REMOVE_CASES:
        inp = _probe(case_id, "input")
        result = _gwydion_remove_scars_result(inp)
        assert np.array_equal(
            _bits(result.temporary_mask),
            _bits(_probe(case_id, "temp_mask"))), case_id
        assert np.array_equal(
            _bits(result.temporary_mask),
            _bits(_probe(case_id, "standalone_mask"))), case_id
        assert np.array_equal(
            _bits(result.temporary_mask),
            _bits(_probe(case_id, "temp_mask_after"))), case_id
        assert not result.temporary_mask_mutation_evidence, case_id


def test_public_result_equals_explicit_composition() -> None:
    for case_id in REMOVE_CASES:
        inp = _probe(case_id, "input")
        out = gwydion_remove_scars(_channel(inp))
        mask = gwydion_mark_scars(_channel(inp))
        explicit = gwydion_interpolate_data_under_mask(_channel(inp), mask)
        assert np.array_equal(_bits(out.data), _bits(explicit.data)), case_id
        assert np.array_equal(
            _bits(out.data), _bits(_gwydion_remove_scars_result(inp)
                                   .corrected_field)), case_id


def test_corrected_within_frozen_laplace_policy() -> None:
    # frozen per-case zero/nonzero distribution: compiled values are exact
    # zero, production values have magnitude at most ~1.739e-15, and the
    # independent mathematical reference is exactly zero; these transitions
    # satisfy the frozen absolute bound, not the finite-nonzero ULP bound
    distribution = {"R01_positive": 16, "R02_negative": 16, "R03_both": 32,
                    "R04_no_detection": 0, "R05_edge_touching": 16,
                    "R06_long_wide": 48}
    total_zero_nonzero = 0
    for case_id in REMOVE_CASES:
        inp = _probe(case_id, "input")
        out = gwydion_remove_scars(_channel(inp))
        probe = _probe(case_id, "corrected")
        metrics = _metrics(probe, out.data)
        # the compiled composition identity (standalone Laplace == Remove)
        # is frozen in the fixtures
        assert np.array_equal(
            _bits(_probe(case_id, "standalone_corrected")),
            _bits(probe)), case_id
        assert metrics["zero_nonzero"] == distribution[case_id], (
            f"{case_id}: zero/nonzero count "
            f"{metrics['zero_nonzero']} != {distribution[case_id]}")
        assert metrics["signed_zero"] == 0, case_id
        total_zero_nonzero += metrics["zero_nonzero"]
        assert metrics["max_abs"] <= FROZEN_MAX_ABS, (
            f"{case_id}: maxabs {metrics['max_abs']}")
        # finite-nonzero ULP bound applies only to finite nonzero pairs
        assert metrics["max_ulp"] <= FROZEN_MAX_ULP, (
            f"{case_id}: maxulp {metrics['max_ulp']}")
    assert total_zero_nonzero == 128


def test_no_detection_bitwise_unchanged() -> None:
    inp = _probe("R04_no_detection", "input")
    out = gwydion_remove_scars(_channel(inp))
    assert np.array_equal(_bits(out.data), _bits(inp))
    assert np.array_equal(_bits(out.data), _bits(_probe("R04_no_detection",
                                                        "corrected")))


def test_input_non_mutation() -> None:
    for case_id in REMOVE_CASES:
        inp = _probe(case_id, "input")
        before = _bits(inp).copy()
        gwydion_remove_scars(_channel(inp))
        assert np.array_equal(_bits(inp), before), case_id
