"""FS-F2 core tests: contracts, equations, failures, determinism.

No fixtures loaded.
"""

from __future__ import annotations

import math
import pickle

import numpy as np
import pytest

from spmkit.core.analysis import (
    prepare_force_curve,
)
from spmkit.core.analysis.force_mechanics import (
    ForceMechanicsError,
    analyze_force_fit_sensitivity,
    bootstrap_force_fit,
    compare_contact_models,
    compute_indentation,
    diagnose_force_fit,
    fit_dmt,
    fit_flat_punch,
    fit_hertz_sphere,
    fit_jkr,
    fit_sneddon_cone,
    forward_model,
    select_contact_fit_window,
)
from spmkit.core.models import Calibration, ForceCurve, ForceSegment

N = 200
K = 10.0
ZC = 3e-6
DELTA = np.linspace(0.0, 1e-6, N)


def _model_curve(model: str = "hertz_sphere",
                params: dict | None = None, noise: float = 0.0) -> ForceCurve:
    if params is None:
        params = {"E": 5e3, "R": 1e-6, "poisson": 0.3}
    rng = np.random.default_rng(0)
    # FS-F1 trace convention: separation increases along the trace; the
    # contact is at sep = ZC; the indentation branch delta = max(0, sep-ZC);
    # height = separation + force/K stays strictly increasing because the
    # deflection grows slower than the piezo motion (indentation regime).
    sep = np.linspace(ZC - 2.0e-6, ZC + 1e-6, N)
    delta = np.maximum(0.0, sep - ZC)
    # zero force pre-contact: adhesive models are negative at delta == 0
    force = np.where(delta > 0.0, forward_model(model, delta, params), 0.0)
    if noise:
        force = force + rng.normal(0.0, noise, N)
    height = sep + force / K
    def seg(t, d, z, f):
        return ForceSegment(segment_type=t, direction=d, raw_height=z,
                            raw_deflection=f / K, time=None, cycle=0, state="force_n",
                            deflection=f / K, force=f, separation=None, metadata={})
    fr = force[::-1].copy()
    return ForceCurve(segments=(seg("extend", "forward", height, force),
                               seg("retract", "backward", height[::-1].copy(), fr)),
                      calibration=Calibration(invols=3e-8, spring_constant=K,
                                              method="thermal", temperature=300,
                                              provenance={}),
                      position=None, index=0, metadata={})


def _prepared(model: str = "hertz_sphere", noise: float = 0.0,
              params: dict | None = None):
    if params is None:
        params = {"E": 5e3, "R": 1e-6, "poisson": 0.3}
    return prepare_force_curve(_model_curve(model, params, noise))


def test_forward_equations_match_literature() -> None:
    est = 5e3 / (1 - 0.3**2)
    d = np.array([1e-7, 5e-7, 1e-6])
    assert np.allclose(forward_model("hertz_sphere", d, {"E": 5e3, "R": 1e-6, "poisson": 0.3}),
                       (4/3) * est * math.sqrt(1e-6) * d**1.5)
    assert np.allclose(
        forward_model("sneddon_cone", d, {"E": 5e3, "alpha": math.radians(20), "poisson": 0.3}),
                       (2 * math.tan(math.radians(20)) / math.pi) * est * d**2)
    assert np.allclose(forward_model("flat_punch", d, {"E": 5e3, "R": 1e-6, "poisson": 0.3}),
                       2 * est * 1e-6 * d)
    assert np.allclose(
        forward_model("dmt", d, {"E": 5e3, "R": 1e-6, "poisson": 0.3, "F_adh": 2e-9}),
                       (4/3) * est * math.sqrt(1e-6) * d**1.5 - 2e-9)


def test_jkr_reduces_to_hertz() -> None:
    d = np.linspace(1e-8, 1e-6, 50)
    j = forward_model("jkr", d, {"E": 5e3, "R": 1e-6, "poisson": 0.3, "w": 0.0})
    h = forward_model("hertz_sphere", d, {"E": 5e3, "R": 1e-6, "poisson": 0.3})
    assert np.allclose(j, h, rtol=1e-6)


def test_compute_indentation_contract() -> None:
    prepared = _prepared()
    ind = compute_indentation(prepared)
    assert ind.units == "m"
    # pre-contact samples are excluded by the mask; the valid branch is
    # the indentation (positive into the sample)
    assert np.all(ind.indentation[ind.valid] >= -1e-12)
    assert np.any(ind.indentation[~ind.valid] < 0.0)
    assert ind.valid.sum() > 0
    assert ind.contact_index == prepared.contact.selected.index


def test_fit_window_contract() -> None:
    prepared = _prepared()
    ind = compute_indentation(prepared)
    window = select_contact_fit_window(prepared, ind, min_indentation=0.0,
                                       min_points=10)
    assert window.n_points >= 10
    assert window.included.sum() == window.n_points
    with pytest.raises(ForceMechanicsError):
        select_contact_fit_window(prepared, ind, max_indentation=-1e-9)
    with pytest.raises(ForceMechanicsError):
        select_contact_fit_window(prepared, ind, min_points=10**6)


@pytest.mark.parametrize("model,fit_fn,kwargs,truth_key", [
    ("hertz_sphere", fit_hertz_sphere, {"tip_radius": 1e-6}, "E"),
    ("sneddon_cone", fit_sneddon_cone, {"half_angle": math.radians(20.0)}, "E"),
    ("flat_punch", fit_flat_punch, {"punch_radius": 1e-6}, "E"),
])
def test_clean_parameter_recovery(model, fit_fn, kwargs, truth_key) -> None:
    params = {"E": 5e3, "R": 1e-6, "poisson": 0.3, "alpha": math.radians(20.0)}
    if model == "sneddon_cone":
        params = {"E": 5e3, "alpha": math.radians(20.0), "poisson": 0.3}
    prepared = _prepared(model, 0.0, params)
    ind = compute_indentation(prepared)
    window = select_contact_fit_window(prepared, ind, min_indentation=0.0, min_points=10)
    fit = fit_fn(prepared, ind, window, **kwargs)
    assert fit.success
    # E is recovered within a few percent: the FS-F1 contact point lands
    # within ~1 sample of the truth (1.5e-8 m), and the indentation-axis
    # offset biases the stiffness by ~1% on clean data
    assert abs(fit.parameters["E"] - 5e3) / 5e3 < 0.05


def test_dmt_clean_recovery() -> None:
    params = {"E": 5e3, "R": 1e-6, "poisson": 0.3, "F_adh": 2e-9}
    prepared = _prepared("dmt", 0.0, params)
    ind = compute_indentation(prepared)
    # the window trims the snap-in/pre-contact region: the FS-F1 contact
    # ensemble lands up to ~10 samples off on snap-in curves, which biases
    # adhesive-model parameters (documented limitation of this batch)
    window = select_contact_fit_window(prepared, ind, min_indentation=1.8e-7,
                                       min_points=10)
    fit = fit_dmt(prepared, ind, window, tip_radius=1e-6)
    assert abs(fit.parameters["E"] - 5e3) / 5e3 < 0.3
    assert abs(fit.parameters["F_adh"] - 2e-9) < 1.5e-9


def test_jkr_clean_recovery() -> None:
    params = {"E": 5e3, "R": 1e-6, "poisson": 0.3, "w": 1e-3}
    prepared = _prepared("jkr", 0.0, params)
    ind = compute_indentation(prepared)
    # same snap-in trim as the DMT case (see test_dmt_clean_recovery)
    window = select_contact_fit_window(prepared, ind, min_indentation=2e-7,
                                       min_points=10)
    fit = fit_jkr(prepared, ind, window, tip_radius=1e-6)
    assert fit.success
    assert abs(fit.parameters["E"] - 5e3) / 5e3 < 0.2
    assert abs(fit.parameters["w"] - 1e-3) / 1e-3 < 0.3


def test_invalid_geometry_typed_failures() -> None:
    prepared = _prepared()
    ind = compute_indentation(prepared)
    window = select_contact_fit_window(prepared, ind, min_points=10)
    with pytest.raises(ForceMechanicsError) as ei:
        fit_hertz_sphere(prepared, ind, window, tip_radius=-1e-6)
    assert ei.value.code == "INVALID_RADIUS"
    with pytest.raises(ForceMechanicsError) as ei:
        fit_sneddon_cone(prepared, ind, window, half_angle=math.pi / 2)
    assert ei.value.code == "INVALID_ANGLE"
    with pytest.raises(ForceMechanicsError) as ei:
        fit_hertz_sphere(prepared, ind, window, tip_radius=1e-6, poisson=0.6)
    assert ei.value.code == "INVALID_POISSON_RATIO"
    with pytest.raises(ForceMechanicsError) as ei:
        fit_dmt(prepared, ind, window, tip_radius=1e-6, F_adh_initial=-1e-9)
    assert ei.value.code == "INVALID_ADHESION_PARAMETER"


def test_non_mutation_and_independent_outputs() -> None:
    prepared = _prepared(noise=1e-12)
    force_before = prepared.curve.extend.force.copy()
    ind = compute_indentation(prepared)
    window = select_contact_fit_window(prepared, ind, min_points=10)
    fit = fit_hertz_sphere(prepared, ind, window, tip_radius=1e-6)
    assert np.array_equal(prepared.curve.extend.force, force_before)
    # residuals are independent storage: mutating them does not touch the
    # input force or the predicted force
    fit.residuals[0] = 123.0  # type: ignore[index]
    assert prepared.curve.extend.force[window.start_index] != 123.0
    assert fit.predicted_force[0] != 123.0


def test_result_serialization() -> None:
    prepared = _prepared(noise=1e-12)
    ind = compute_indentation(prepared)
    window = select_contact_fit_window(prepared, ind, min_points=10)
    fit = fit_hertz_sphere(prepared, ind, window, tip_radius=1e-6)
    blob = pickle.dumps(fit)
    fit2 = pickle.loads(blob)
    assert fit2.model == fit.model
    assert fit2.parameters == fit.parameters


def test_model_comparison_no_physical_truth() -> None:
    prepared = _prepared("hertz_sphere", 1e-12)
    ind = compute_indentation(prepared)
    window = select_contact_fit_window(prepared, ind, min_points=10)
    cmp = compare_contact_models(prepared, ind, window, tip_radius=1e-6)
    assert cmp.n_compared == len(cmp.fits)
    assert all(0.0 <= w <= 1.0 for w in cmp.weights.values())
    # comparison is model-relative: no physical-truth claim is made
    assert "physical" not in cmp.provenance
    assert cmp.provenance.get("criterion") in ("aicc", "aic", "bic")


def test_comparison_retains_failed_candidate() -> None:
    """A candidate whose geometry validation fails is retained as a
    warning and excluded from the ranking; the comparison still returns."""
    prepared = _prepared("hertz_sphere", 1e-12)
    ind = compute_indentation(prepared)
    window = select_contact_fit_window(prepared, ind, min_points=10)
    cmp = compare_contact_models(prepared, ind, window, tip_radius=1e-6,
                                 models=("hertz_sphere", "sneddon_cone"),
                                 half_angle=math.pi / 2)
    assert cmp.n_compared == 1
    assert any("INVALID_ANGLE" in w for w in cmp.warnings)
    assert cmp.recommended_model == "hertz_sphere"


def test_sensitivity_deterministic_and_bounded() -> None:
    prepared = _prepared("hertz_sphere", 1e-12)
    a = analyze_force_fit_sensitivity(prepared, tip_radius=1e-6)
    b = analyze_force_fit_sensitivity(prepared, tip_radius=1e-6)
    assert a.n_configurations == b.n_configurations
    assert a.parameter_multiverse == b.parameter_multiverse
    assert a.n_configurations <= 512


def test_multiverse_max_configuration_guard() -> None:
    """Configurations beyond the guard are counted as skipped, never
    silently dropped or run."""
    prepared = _prepared("hertz_sphere", 1e-12)
    sens = analyze_force_fit_sensitivity(
        prepared, contact_offsets=tuple(range(-10, 11)),
        fit_window_variants=(0.0, 0.1, 0.2), max_configurations=8,
        tip_radius=1e-6)
    assert sens.n_configurations + len(sens.failures) <= 8
    assert sens.n_skipped > 0


def test_sensitivity_multiverse_covers_contact_branch() -> None:
    """The multiverse fits the contact branch (same convention as
    compute_indentation): every configuration's modulus stays close to the
    base fit, and the one-at-a-time indices are small on a clean curve."""
    prepared = _prepared("hertz_sphere", 1e-12)
    ind = compute_indentation(prepared)
    window = select_contact_fit_window(prepared, ind, min_indentation=0.0, min_points=10)
    base = fit_hertz_sphere(prepared, ind, window, tip_radius=1e-6)
    sens = analyze_force_fit_sensitivity(prepared, tip_radius=1e-6)
    assert sens.n_configurations > 0
    for p in sens.parameter_multiverse:
        assert np.isfinite(p["E"])
        assert abs(p["E"] - base.parameters["E"]) / base.parameters["E"] < 0.30
    # clean curve: neither contact nor window sensitivity is high
    assert sens.dominant_sensitivity in ("none", "contact", "window")
    assert sens.contact_sensitivity < 0.2
    assert sens.window_sensitivity < 0.2


def test_bootstrap_block_residual_robust_window_length() -> None:
    """The block-residual strategy runs deterministically even when the
    window length is not a multiple of the block size (regression: the
    reshape previously raised an untyped ValueError)."""
    prepared = _prepared("hertz_sphere", 1e-12)
    ind = compute_indentation(prepared)
    # trim so the window length is not a multiple of the block size (5)
    window = select_contact_fit_window(prepared, ind, min_indentation=5e-8,
                                       min_points=10)
    assert window.n_points % 5 != 0, "window length must not be a block multiple"
    a = bootstrap_force_fit((prepared, ind, window, "hertz_sphere"),
                            samples=12, seed=3, strategy="block_residual",
                            tip_radius=1e-6)
    b = bootstrap_force_fit((prepared, ind, window, "hertz_sphere"),
                            samples=12, seed=3, strategy="block_residual",
                            tip_radius=1e-6)
    assert a.parameter_samples == b.parameter_samples
    assert a.n_success >= 10


def test_diagnose_computes_covariance_metrics() -> None:
    """The diagnostic's condition number and parameter-correlation metrics
    are computed from the fit covariance, not placeholder zeros."""
    prepared = _prepared("hertz_sphere", 1e-12)
    ind = compute_indentation(prepared)
    window = select_contact_fit_window(prepared, ind, min_indentation=0.0,
                                       min_points=10)
    fit = fit_hertz_sphere(prepared, ind, window, tip_radius=1e-6)
    diag = diagnose_force_fit(fit)
    assert diag.condition_metric > 0.0
    assert 0.0 <= diag.parameter_correlation_max <= 1.0


def test_bootstrap_deterministic_replay() -> None:
    prepared = _prepared("hertz_sphere", 1e-12)
    ind = compute_indentation(prepared)
    window = select_contact_fit_window(prepared, ind, min_points=10)
    a = bootstrap_force_fit((prepared, ind, window, "hertz_sphere"),
                            samples=50, seed=7, tip_radius=1e-6)
    b = bootstrap_force_fit((prepared, ind, window, "hertz_sphere"),
                            samples=50, seed=7, tip_radius=1e-6)
    assert a.parameter_samples == b.parameter_samples
    assert a.percentile_intervals == b.percentile_intervals


def test_bootstrap_insufficient_success() -> None:
    prepared = _prepared("hertz_sphere", 1e-9)
    ind = compute_indentation(prepared)
    window = select_contact_fit_window(prepared, ind, min_points=10)
    # an impossible success fraction is rejected deterministically
    with pytest.raises(ForceMechanicsError) as ei:
        bootstrap_force_fit((prepared, ind, window, "hertz_sphere"),
                            samples=20, seed=0, tip_radius=1e-6,
                            min_success_fraction=1.5)
    assert ei.value.code == "BOOTSTRAP_INSUFFICIENT_SUCCESS"


def test_diagnose_returns_policy_status() -> None:
    prepared = _prepared("hertz_sphere", 1e-12)
    ind = compute_indentation(prepared)
    window = select_contact_fit_window(prepared, ind, min_points=10)
    fit = fit_hertz_sphere(prepared, ind, window, tip_radius=1e-6)
    sens = analyze_force_fit_sensitivity(prepared, tip_radius=1e-6)
    diag = diagnose_force_fit(fit, sensitivity=sens)
    assert diag.summary_status in ("ok", "review")
    assert isinstance(diag.residual_rms, float)


def test_fit_requires_prepared_input() -> None:
    with pytest.raises(TypeError):
        compute_indentation("not prepared")  # type: ignore[arg-type]
    from spmkit.core.analysis.force_mechanics_errors import ForceMechanicsError

    # a raw curve without preparation is not fit-eligible
    curve = _model_curve()
    with pytest.raises(ForceMechanicsError) as ei:
        compute_indentation(_unprepared_placeholder(curve))  # type: ignore[arg-type]
    assert ei.value.code == "CURVE_NOT_FIT_ELIGIBLE"


def _unprepared_placeholder(curve):
    """A minimal prepared-like object whose quality is not eligible."""
    from spmkit.core.analysis import score_force_curve_quality
    from spmkit.core.analysis.force_prepare import ForcePreparationResult
    from spmkit.core.analysis.force_preprocessing import identify_force_segments

    q = score_force_curve_quality(curve)
    seg = identify_force_segments(curve)
    return ForcePreparationResult(
        curve=curve, segmentation=seg, calibration=None,  # type: ignore[arg-type]
        separation=curve, baseline=None, baseline_corrected=curve,
        contact=None, events=None, work=None, quality=q, provenance={},
    )
