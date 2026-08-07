"""Production parity: Laplace interpolation kernel vs the frozen evidence.

For all 18 cases and subcases the production output is compared with the
frozen compiled arrays and with the frozen mathematical-reference metrics.
Source-compatible paths are bitwise; the retained generic (iterative)
paths must remain within the frozen campaign limits (max ULP <= 2, max
absolute difference <= 1.7763568394002505e-15).  Exact whole-field,
empty-mask, calibration and unmasked-preservation policies are asserted,
as is the L17 compiled signed-zero behavior.  These are frozen campaign
limits, not a universal API tolerance.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from spmkit.core.analysis import gwydion_interpolate_data_under_mask
from spmkit.core.analysis._gwydion_laplace import _gwydion_laplace_result
from spmkit.core.models.spmdata import SPMChannel

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "gwydion" / "scars_laplace"
JSON_PATH = FIXTURE_DIR / "scars_laplace_reference.json"
NPZ_PATH = FIXTURE_DIR / "scars_laplace_reference.npz"

LAPLACE_CASES = [
    "L01_empty_mask", "L02_one_interior_pixel", "L03_one_edge_pixel",
    "L04_one_corner_pixel", "L05_horizontal_corridor", "L06_vertical_corridor",
    "L07_three_pixel_L", "L08_interior_rectangle", "L09_two_components",
    "L10_edge_touching", "L11_corner_touching", "L12_entire_masked_row",
    "L13_whole_field_mask", "L14_constant_boundary", "L15_calibration_independence",
    "L16_mask_predicate", "L17_signed_zero", "L18_degenerate",
]

FROZEN_MAX_ABS = 1.7763568394002505e-15
FROZEN_MAX_ULP = 2

_manifest = json.loads(JSON_PATH.read_text())
_arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())
_PER_CASE = _manifest["per_case"]


def _bits(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array, dtype=np.float64).view(np.uint64)


def _channel(data: np.ndarray) -> SPMChannel:
    return SPMChannel(
        name="parity", data=np.asarray(data, dtype=np.float64), unit="nm",
        x_range=float(data.shape[1]), y_range=float(data.shape[0]))


def _probe(case_id: str, label: str) -> np.ndarray:
    return _arrays[f"{case_id}_probe_{label}"]


def _probe_key(case_id: str, sub: str | None, label: str) -> np.ndarray:
    return _arrays[_key(case_id, sub, label)]


def _subcases(case_id: str) -> list[tuple[str | None, str, str, str]]:
    """(subcase, corrected label, input label, mask label)."""
    if case_id == "L15_calibration_independence":
        # the probe emits no input_mask for L15; mask_after_a is the
        # unmutated mask
        return [("", "corrected_a", "input", "mask_after_a")]
    if case_id == "L18_degenerate":
        return [(sub, "corrected", "input", "input_mask")
                for sub in ("L18a_1x1_masked", "L18b_1x1_unmasked",
                            "L18c_1x5", "L18d_2x5_full", "L18e_5x1")]
    return [(None, "corrected", "input", "input_mask")]


def _key(case_id: str, sub: str | None, label: str) -> str:
    return (f"{case_id}_probe_{label}" if not sub
            else f"{case_id}_probe_{sub}_{label}")


def _metrics(probe: np.ndarray, out: np.ndarray) -> dict:
    """Four explicit comparison classes:

    1. bitwise-identical elements;
    2. signed-zero-only differences (+0.0 versus -0.0), reported separately;
    3. exact-zero versus finite-nonzero differences, governed by the frozen
       absolute-difference bound and the production residual guard;
    4. finite-nonzero differences, governed by the ordered-float ULP bound.

    ULP distance is not used as the compatibility metric across an
    exact-zero / finite-nonzero transition because it is not comparable to
    the local finite-nonzero ULP bound; that class is enforced separately
    by absolute error and residual, and is never silently discarded.
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


def test_all_laplace_cases_within_frozen_limits() -> None:
    exact_paths = {"L01_empty_mask", "L02_one_interior_pixel",
                   "L03_one_edge_pixel", "L04_one_corner_pixel",
                   "L05_horizontal_corridor", "L06_vertical_corridor",
                   "L07_three_pixel_L", "L08_interior_rectangle",
                   "L09_two_components", "L13_whole_field_mask",
                   "L14_constant_boundary", "L15_calibration_independence",
                   "L16_mask_predicate", "L17_signed_zero", "L18_degenerate"}
    for case_id in LAPLACE_CASES:
        for sub, cor_label, inp_label, mask_label in _subcases(case_id):
            inp = _probe_key(case_id, sub, inp_label)
            mask = _probe_key(case_id, sub, mask_label)
            probe = _probe_key(case_id, sub, cor_label)
            out = gwydion_interpolate_data_under_mask(_channel(inp), mask)
            metrics = _metrics(probe, out.data)
            label = sub or case_id
            assert metrics["zero_nonzero"] == 0, (
                f"{label}: {metrics['zero_nonzero']} exact-zero/nonzero "
                f"transitions (Laplace retained cases have none)")
            assert metrics["max_abs"] <= FROZEN_MAX_ABS, (
                f"{label}: maxabs {metrics['max_abs']}")
            assert metrics["max_ulp"] <= FROZEN_MAX_ULP, (
                f"{label}: maxulp {metrics['max_ulp']}")
            # bitwise requirement for the source-compatible path classes
            if case_id in exact_paths:
                assert metrics["bitwise"] == metrics["total"], (
                    f"{label}: expected bitwise, got "
                    f"{metrics['bitwise']}/{metrics['total']}")
            # frozen per-case compiled-vs-math bounds also bound production:
            # production-to-math <= frozen max_abs implies
            # production-to-compiled <= frozen max_abs + compiled-to-math
            frozen = _PER_CASE[case_id]["subcases"][0]
            assert metrics["max_abs"] <= 2 * frozen["max_absolute_difference"], \
                f"{label}: exceeds frozen per-case scale"


def test_exact_policies() -> None:
    # whole-field mask -> zeros
    out = gwydion_interpolate_data_under_mask(
        _channel(_probe("L13_whole_field_mask", "input")),
        _probe("L13_whole_field_mask", "input_mask"))
    assert not np.any(out.data != 0.0)
    # empty mask -> bitwise unchanged
    out = gwydion_interpolate_data_under_mask(
        _channel(_probe("L01_empty_mask", "input")),
        _probe("L01_empty_mask", "input_mask"))
    assert np.array_equal(_bits(out.data),
                          _bits(_probe("L01_empty_mask", "input")))
    # calibration independence
    a = _probe("L15_calibration_independence", "corrected_a")
    b = _probe("L15_calibration_independence", "corrected_b")
    assert np.array_equal(_bits(a), _bits(b))
    out_a = gwydion_interpolate_data_under_mask(
        _channel(_probe("L15_calibration_independence", "input")),
        _probe("L15_calibration_independence", "mask_after_a"))
    assert np.array_equal(_bits(out_a.data), _bits(a))
    # unmasked pixels preserved bitwise (all cases)
    for case_id in LAPLACE_CASES:
        if case_id == "L15_calibration_independence":
            continue
        for sub, _cor, inp_label, mask_label in _subcases(case_id):
            inp = _probe_key(case_id, sub, inp_label)
            mask = _probe_key(case_id, sub, mask_label)
            out = gwydion_interpolate_data_under_mask(_channel(inp), mask)
            for i in range(inp.size):
                if mask.ravel()[i] <= 0.0:
                    assert out.data.ravel()[i] == inp.ravel()[i], (
                        f"{case_id}/{sub}: unmasked pixel mutated")


def test_l17_compiled_signed_zero_behavior() -> None:
    inp = _probe("L17_signed_zero", "input")
    mask = _probe("L17_signed_zero", "input_mask")
    out = gwydion_interpolate_data_under_mask(_channel(inp), mask)
    # production must reproduce the compiled -0.0 at the masked pixel
    assert int(out.data[2, 2].view(np.uint64)) == 0x8000000000000000
    assert int(_probe("L17_signed_zero", "corrected")[2, 2].view(np.uint64)) \
        == 0x8000000000000000


def test_convergence_diagnostics_and_residuals() -> None:
    """The 1e-13 threshold is a production convergence and numerical-
    quality guard for the frozen campaign, not compiled-residual parity.
    The compiled probe residuals were measured during the campaign
    (metrics.txt: residual_max <= 7.1e-15) but are not stored in the
    current persistent JSON/NPZ fixtures; exact compiled-residual parity
    is not claimed.  The persistent contract enforces output-distance
    metrics (above) and this independent mathematical residual guard; the
    per-case 4 * max_abs scale is a documented reference, not a frozen
    compiled-residual bound.  Note L11's production residual is
    approximately twice the compiled residual at the float64 floor."""
    for case_id in ["L08_interior_rectangle", "L09_two_components",
                    "L10_edge_touching", "L11_corner_touching",
                    "L12_entire_masked_row", "L14_constant_boundary",
                    "L16_mask_predicate"]:
        inp = _probe(case_id, "input")
        mask = _probe(case_id, "input_mask")
        result = _gwydion_laplace_result(inp, mask)
        assert result.max_residual <= 1e-13, case_id
        frozen = _PER_CASE[case_id]["subcases"][0]
        assert result.max_residual <= 4 * frozen["max_absolute_difference"] \
            + 1e-13, case_id
        assert result.unmasked_mutation_count == 0, case_id
        assert not result.mask_mutation_evidence, case_id
        assert not result.input_mutation_evidence, case_id
        assert all(it >= 0 for it in result.iteration_counts), case_id
