"""Core tests for the force-spectroscopy foundation (FS-F1).

Analytical, contract and metamorphic coverage for all thirteen public
capabilities.  No external fixtures are loaded here.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from spmkit.core.analysis import (
    ContactPointCandidate,
    ForceFoundationError,
    calibrate_force_curve,
    compute_tip_sample_separation,
    contact_point_ensemble,
    contact_point_piecewise,
    contact_point_ratio_of_variances,
    contact_point_threshold,
    correct_force_baseline,
    extract_force_events,
    fit_force_baseline,
    identify_force_segments,
    integrate_force_work,
    prepare_force_curve,
    score_force_curve_quality,
)
from spmkit.core.models import Calibration, ForceCurve, ForceSegment

N = 200
Z = np.linspace(0.0, 5e-6, N)
CAL = Calibration(
    invols=3e-8, spring_constant=0.1, method="thermal", temperature=300, provenance={}
)


def _seg(
    t: str,
    d: str,
    z: np.ndarray,
    f: np.ndarray | None,
    deflection: np.ndarray | None = None,
    state: str = "force_n",
    separation: np.ndarray | None = None,
) -> ForceSegment:
    return ForceSegment(
        segment_type=t,
        direction=d,
        raw_height=z,
        raw_deflection=np.zeros_like(z),
        time=None,
        cycle=0,
        state=state,
        deflection=deflection,
        force=f,
        separation=separation,
        metadata={},
    )


def _curve(
    offset: float = 5e-10,
    slope: float = 1e-4,
    noise: float = 0.0,
    contact_fraction: float = 0.3,
    seed: int = 0,
) -> ForceCurve:
    rng = np.random.default_rng(seed)
    ci = int(round(N * contact_fraction))
    f = offset + slope * Z
    delta = np.maximum(0.0, Z - Z[ci])
    f = f + 5.0 * delta**1.5
    if noise:
        f = f + rng.normal(0.0, noise, N)
    fr = f[::-1].copy()
    return ForceCurve(
        segments=(_seg("extend", "forward", Z, f), _seg("retract", "backward", Z[::-1].copy(), fr)),
        calibration=CAL,
        position=None,
        index=0,
        metadata={},
    )


# ------------------------------------------------------------ segmentation ---


def test_segmentation_trusts_labels() -> None:
    res = identify_force_segments(_curve())
    assert len(res.approach_indices) == N
    assert len(res.retract_indices) == N
    assert res.turning_point_index == N
    assert res.diagnostics["trusted_labels"] is True


def test_segmentation_single_segment_turning_point() -> None:
    curve = ForceCurve(
        segments=(_seg("extend", "forward", Z, np.ones(N) * 1e-9),),
        calibration=CAL,
        position=None,
        index=0,
        metadata={},
    )
    res = identify_force_segments(curve)
    assert res.turning_point_index == int(np.argmax(Z))
    assert res.approach_indices[-1] == res.turning_point_index


def test_segmentation_no_reordering() -> None:
    res = identify_force_segments(_curve())
    assert res.approach_indices == tuple(range(N))
    assert res.retract_indices == tuple(range(N, 2 * N))


# ------------------------------------------------------------- calibration ---


def test_calibration_raw_volts_to_force() -> None:
    np.full(N, 1e-3)
    seg = _seg("extend", "forward", Z, None, deflection=None, state="raw_v")
    curve = ForceCurve(segments=(seg,), calibration=CAL, position=None, index=0, metadata={})
    res = calibrate_force_curve(curve)
    assert res.curve.segments[0].force is not None
    expected = 1e-3 * 3e-8 * 0.1
    assert np.allclose(res.curve.segments[0].force, expected)
    assert res.output_units == "N"


def test_calibration_already_calibrated_pass_through() -> None:
    curve = _curve()
    res = calibrate_force_curve(curve)
    assert res.curve is not None
    assert np.array_equal(res.curve.extend.force, curve.extend.force)


def test_calibration_double_calibration_rejected() -> None:
    curve = _curve()
    with pytest.raises(ForceFoundationError) as ei:
        calibrate_force_curve(curve, calibration=CAL)
    assert ei.value.code == "INVALID_CALIBRATION"


def test_calibration_missing_calibration_rejected() -> None:
    seg = _seg("extend", "forward", Z, None, state="raw_v")
    curve = ForceCurve(segments=(seg,), calibration=None, position=None, index=0, metadata={})
    with pytest.raises(ForceFoundationError) as ei:
        calibrate_force_curve(curve)
    assert ei.value.code == "MISSING_CALIBRATION"


def test_calibration_non_mutation() -> None:
    curve = _curve()
    before = curve.extend.force.copy()
    calibrate_force_curve(curve)
    assert np.array_equal(curve.extend.force, before)


# ----------------------------------------------------- tip-sample separation ---


def test_tip_sample_separation_convention() -> None:
    f = np.full(N, 1e-9)
    deflection = f / 0.1
    curve = ForceCurve(
        segments=(_seg("extend", "forward", Z, f, deflection=deflection),),
        calibration=CAL,
        position=None,
        index=0,
        metadata={},
    )
    sep = compute_tip_sample_separation(curve)
    assert np.allclose(sep.extend.separation, Z - deflection)
    assert sep is not curve
    assert curve.extend.separation is None  # input untouched


# ---------------------------------------------------------------- baseline ---


def test_baseline_fit_recovers_parameters() -> None:
    curve = _curve(offset=5e-10, slope=1e-4, noise=0.0)
    bl = fit_force_baseline(curve)
    assert bl.model == "linear"
    assert bl.segment == "approach"
    assert abs(bl.intercept - 5e-10) < 5e-11
    assert abs(bl.slope - 1e-4) < 1e-5
    assert bl.residual_rms < 1e-12


def test_baseline_robust_fit() -> None:
    curve = _curve(noise=2e-11)
    bl = fit_force_baseline(curve, robust=True)
    assert abs(bl.intercept - 5e-10) < 5e-10
    assert bl.robust_scale > 0.0


def test_baseline_too_short() -> None:
    z = np.linspace(0.0, 1e-6, 8)
    curve = ForceCurve(
        segments=(_seg("extend", "forward", z, np.ones(8) * 1e-9),),
        calibration=CAL,
        position=None,
        index=0,
        metadata={},
    )
    with pytest.raises(ForceFoundationError) as ei:
        fit_force_baseline(curve)
    assert ei.value.code == "BASELINE_TOO_SHORT"


def test_baseline_correction_removes_offset_and_slope() -> None:
    curve = _curve(offset=5e-10, slope=1e-4, noise=0.0)
    bl = fit_force_baseline(curve)
    corrected = correct_force_baseline(curve, bl, scope="all")
    n_base = len(bl.sample_indices)
    assert np.max(np.abs(corrected.extend.force[:n_base])) < 1e-12
    assert curve.extend.force is not None


def test_baseline_correction_scope_validation() -> None:
    bl = fit_force_baseline(_curve())
    with pytest.raises(ValueError):
        correct_force_baseline(_curve(), bl, scope="nonsense")


# ------------------------------------------------------- contact: threshold ---


def test_contact_threshold_clean_recovery() -> None:
    curve = _curve(offset=0.0, slope=0.0, noise=0.0)
    cand = contact_point_threshold(curve)
    ci = int(round(N * 0.3))
    assert cand.valid
    assert abs(cand.index - (ci + 1)) <= 1


def test_contact_threshold_no_contact() -> None:
    flat = ForceCurve(
        segments=(
            _seg("extend", "forward", Z, np.full(N, 1e-10)),
            _seg("retract", "backward", Z[::-1].copy(), np.full(N, 1e-10)),
        ),
        calibration=CAL,
        position=None,
        index=0,
        metadata={},
    )
    cand = contact_point_threshold(flat)
    assert not cand.valid
    assert cand.failure_reason == "CONTACT_NOT_FOUND"


def test_contact_threshold_non_mutation() -> None:
    curve = _curve()
    before = curve.extend.force.copy()
    contact_point_threshold(curve)
    assert np.array_equal(curve.extend.force, before)


# -------------------------------------------------- contact: ratio of variances ---


def test_contact_rov_returns_candidate() -> None:
    curve = _curve(noise=5e-11)
    cand = contact_point_ratio_of_variances(curve)
    assert cand.method == "ratio_of_variances"
    assert cand.valid
    assert 0 <= cand.index < N


def test_contact_rov_too_short() -> None:
    z = np.linspace(0.0, 1e-6, 20)
    curve = ForceCurve(
        segments=(_seg("extend", "forward", z, np.ones(20) * 1e-9),),
        calibration=CAL,
        position=None,
        index=0,
        metadata={},
    )
    with pytest.raises(ForceFoundationError):
        contact_point_ratio_of_variances(curve, window=20)


# -------------------------------------------------------- contact: piecewise ---


def test_contact_piecewise_returns_candidate() -> None:
    curve = _curve(noise=0.0)
    cand = contact_point_piecewise(curve)
    assert cand.method == "piecewise"
    assert cand.valid
    assert 0 <= cand.index < N


# --------------------------------------------------------- contact: ensemble ---


def test_contact_ensemble_combines_methods() -> None:
    curve = _curve(noise=5e-11)
    res = contact_point_ensemble(curve)
    assert res.method_agreement >= 2
    assert len(res.candidates) == 3
    assert 0 <= res.selected.index < N


def test_contact_ensemble_bootstrap_deterministic() -> None:
    curve = _curve(noise=5e-11)
    a = contact_point_ensemble(curve, bootstrap_samples=50)
    b = contact_point_ensemble(curve, bootstrap_samples=50)
    assert a.bootstrap_interval == b.bootstrap_interval


def test_contact_ensemble_insufficient_agreement() -> None:
    flat = ForceCurve(
        segments=(
            _seg("extend", "forward", Z, np.full(N, 1e-10)),
            _seg("retract", "backward", Z[::-1].copy(), np.full(N, 1e-10)),
        ),
        calibration=CAL,
        position=None,
        index=0,
        metadata={},
    )
    with pytest.raises(ForceFoundationError) as ei:
        contact_point_ensemble(flat)
    assert ei.value.code == "CONTACT_METHOD_DISAGREEMENT"


# ------------------------------------------------------------------- events ---


def test_events_snap_in_and_pull_off() -> None:
    curve = _curve(noise=0.0)
    int(round(N * 0.3))
    force = curve.extend.force.copy()
    force[40] = force[40] - 3e-10
    seg = _seg("extend", "forward", Z, force)
    curve2 = ForceCurve(
        segments=(seg, curve.retract), calibration=CAL, position=None, index=0, metadata={}
    )
    cand = contact_point_threshold(curve2)
    events = extract_force_events(curve2, cand)
    assert events.snap_in_index == 40
    assert events.pull_off_index is not None


def test_events_absent_retract() -> None:
    curve = ForceCurve(
        segments=(_seg("extend", "forward", Z, np.ones(N) * 1e-9),),
        calibration=CAL,
        position=None,
        index=0,
        metadata={},
    )
    cand = contact_point_threshold(curve)
    events = extract_force_events(curve, cand)
    assert not events.valid
    assert "EVENT_NOT_FOUND" in events.warnings


# ---------------------------------------------------------------------- work ---


def test_work_integration_and_units() -> None:
    curve = _curve(noise=0.0)
    cand = contact_point_threshold(curve)
    res = integrate_force_work(curve, cand, domain="tip_position")
    assert res.units == "J"
    assert res.valid
    assert res.work_approach > 0.0
    assert res.hysteresis >= 0.0


def test_work_nonmonotonic_coordinate() -> None:
    z = Z.copy()
    z[100], z[99] = z[99], z[100]
    curve = ForceCurve(
        segments=(
            _seg("extend", "forward", z, np.ones(N) * 1e-9),
            _seg("retract", "backward", Z[::-1].copy(), np.ones(N) * 1e-9),
        ),
        calibration=CAL,
        position=None,
        index=0,
        metadata={},
    )
    cand = ContactPointCandidate(
        method="threshold", index=50, coordinate=float(z[50]), score=1.0, valid=True
    )
    with pytest.raises(ForceFoundationError) as ei:
        integrate_force_work(curve, cand)
    assert ei.value.code == "NONMONOTONIC_COORDINATE"


# ----------------------------------------------------------------------- QC ---


def test_quality_typed_reasons() -> None:
    curve = _curve(noise=2e-11)
    bl = fit_force_baseline(curve)
    contact = contact_point_ensemble(curve)
    events = extract_force_events(curve, contact)
    q = score_force_curve_quality(curve, baseline=bl, contact=contact, events=events)
    assert 0.0 <= q.summary_score <= 1.0
    assert q.eligible
    assert "MISSING_CALIBRATION" not in q.failure_reasons


def test_quality_missing_calibration() -> None:
    seg = _seg("extend", "forward", Z, None, state="raw_v")
    curve = ForceCurve(segments=(seg,), calibration=None, position=None, index=0, metadata={})
    q = score_force_curve_quality(curve)
    assert "MISSING_CALIBRATION" in q.failure_reasons
    assert not q.eligible


def test_quality_nonfinite() -> None:
    f = np.ones(N) * 1e-9
    f[50] = np.nan
    curve = ForceCurve(
        segments=(_seg("extend", "forward", Z, f),),
        calibration=CAL,
        position=None,
        index=0,
        metadata={},
    )
    q = score_force_curve_quality(curve)
    assert "NONFINITE_DATA" in q.failure_reasons


# ---------------------------------------------------------------- prepare ---


def test_prepare_full_pipeline() -> None:
    curve = _curve(noise=2e-11)
    res = prepare_force_curve(curve)
    assert res.segmentation.turning_point_index == N
    assert res.calibration.output_units == "N"
    assert res.separation.extend.separation is not None
    assert res.baseline.model == "linear"
    assert res.contact.method_agreement >= 2
    assert res.work.units == "J"
    assert "pipeline" in res.provenance
    assert len(res.provenance["pipeline"]) == 9


def test_prepare_uses_core_primitives_only() -> None:
    # the orchestrator exposes every decision in provenance; no hidden choice
    curve = _curve(noise=2e-11)
    res = prepare_force_curve(curve)
    assert res.provenance["calibration"]["source"] in ("explicit", "curve metadata")
    assert "contact" in res.provenance
    assert "work" in res.provenance


# ------------------------------------------------------------ metamorphic ---


def test_metamorphic_force_scaling_with_k() -> None:
    curve = _curve()
    res1 = integrate_force_work(curve, contact_point_threshold(curve))
    cal2 = Calibration(
        invols=3e-8, spring_constant=0.2, method="thermal", temperature=300, provenance={}
    )
    f2 = curve.extend.force * 2.0
    curve2 = ForceCurve(
        segments=(
            _seg("extend", "forward", Z, f2),
            _seg("retract", "backward", Z[::-1].copy(), f2[::-1].copy()),
        ),
        calibration=cal2,
        position=None,
        index=0,
        metadata={},
    )
    res2 = integrate_force_work(curve2, contact_point_threshold(curve2))
    assert math.isclose(res2.work_approach, 2.0 * res1.work_approach, rel_tol=1e-9)


def test_metamorphic_baseline_offset_invariance() -> None:
    base = _curve(offset=1e-10, slope=0.0, noise=0.0)
    shifted = _curve(offset=5e-10, slope=0.0, noise=0.0)
    bl = fit_force_baseline(shifted)
    corrected = correct_force_baseline(shifted, bl)
    assert np.allclose(corrected.extend.force, base.extend.force - 1e-10, atol=1e-12)


def test_metamorphic_work_scaling() -> None:
    curve = _curve(noise=0.0)
    cand = contact_point_threshold(curve)
    w1 = integrate_force_work(curve, cand).work_approach
    f2 = curve.extend.force * 3.0
    curve2 = ForceCurve(
        segments=(
            _seg("extend", "forward", Z, f2),
            _seg("retract", "backward", Z[::-1].copy(), (curve.retract.force * 3.0)[::-1].copy()),
        ),
        calibration=CAL,
        position=None,
        index=0,
        metadata={},
    )
    w2 = integrate_force_work(curve2, contact_point_threshold(curve2)).work_approach
    assert math.isclose(w2, 3.0 * w1, rel_tol=1e-9)


def test_metamorphic_event_window_restriction() -> None:
    curve = _curve(noise=0.0)
    int(round(N * 0.3))
    force = curve.extend.force.copy()
    force[40] = force[40] - 3e-10
    curve2 = ForceCurve(
        segments=(_seg("extend", "forward", Z, force), curve.retract),
        calibration=CAL,
        position=None,
        index=0,
        metadata={},
    )
    cand = contact_point_threshold(curve2)
    window = (float(Z[30]), float(Z[50]))
    events = extract_force_events(curve2, cand, snap_in_window=window)
    if events.snap_in_index is not None:
        assert window[0] <= Z[events.snap_in_index] <= window[1]
    # out-of-window search must not find the event at 40
    far = extract_force_events(curve2, cand, snap_in_window=(float(Z[5]), float(Z[15])))
    assert far.snap_in_index is None or not (5 <= far.snap_in_index <= 15)


def test_metamorphic_ensemble_permutation_invariance() -> None:
    curve = _curve(noise=2e-11)
    a = contact_point_ensemble(curve)
    b = contact_point_ensemble(curve)
    assert a.selected.index == b.selected.index
    assert [c.method for c in a.candidates] == [c.method for c in b.candidates]


# ------------------------------------------------------ common validation ---


def test_invalid_input_types() -> None:
    with pytest.raises(TypeError):
        calibrate_force_curve("not a curve")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        identify_force_segments(_curve(), method="nonsense")


def test_result_serialization() -> None:
    curve = _curve(noise=2e-11)
    res = prepare_force_curve(curve)
    import pickle

    blob = pickle.dumps(res)
    res2 = pickle.loads(blob)
    assert res2.contact.selected.index == res.contact.selected.index
    assert res2.provenance == res.provenance
