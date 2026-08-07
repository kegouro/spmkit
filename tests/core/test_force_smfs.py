"""FS-F4 core tests: polymer equations, extension contract, events,
kinetics, survival, population.  No fixtures loaded."""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis.force_smfs import (
    SmfsError,
    analyze_smfs_batch,
    analyze_smfs_event_population,
    bell_evans_pdf,
    bell_evans_rate,
    bell_evans_survival,
    compute_event_loading_rates,
    compute_molecular_extension,
    detect_unfolding_events,
    dhs_log_rate,
    estimate_force_clamp_survival,
    extensible_fjc_extension,
    extensible_wlc_force,
    fit_bell_evans,
    fit_dudko_hummer_szabo,
    fit_extensible_freely_jointed_chain,
    fit_extensible_worm_like_chain,
    fit_freely_jointed_chain,
    fit_worm_like_chain,
    fjc_extension,
    infer_contour_length_increments,
    langevin,
    quantify_unfolding_events,
    select_smfs_fit_windows,
    wlc_force,
)
from spmkit.core.analysis.force_smfs_models import KB, MolecularExtensionResult
from spmkit.core.models import Calibration, ForceCurve, ForceSegment

T = 298.0
LC, LP, B = 100e-9, 0.5e-9, 1e-9


def _wlc_data(x_max: float = 90e-9, n: int = 200, noise: float = 0.0,
              lc: float = LC, lp: float = LP):
    rng = np.random.default_rng(0)
    x = np.linspace(1e-9, x_max, n)
    f = wlc_force(x, lc, lp, T)
    if noise:
        f = f + rng.normal(0.0, noise, n)
    return x, f


# ---------------------------------------------------------------------------
# forward equations
# ---------------------------------------------------------------------------


def test_wlc_forward_limits() -> None:
    x = np.linspace(1e-9, 90e-9, 50)
    f = wlc_force(x, LC, LP, T)
    # low-force: F ~ (k_BT/Lp) x/Lc
    assert np.allclose(f[:5], (KB * T / LP) * (x[:5] / LC), rtol=1e-2)
    # monotone increasing
    assert np.all(np.diff(f) > 0)
    # singularity: x >= Lc raises
    with pytest.raises(SmfsError) as ei:
        wlc_force(np.array([LC, LC * 1.1]), LC, LP, T)
    assert ei.value.code == "POLYMER_SINGULARITY"
    with pytest.raises(SmfsError):
        wlc_force(x, LC, -1e-12, T)  # invalid persistence length


def test_ewlc_infinite_stiffness_limit() -> None:
    x = np.linspace(1e-9, 80e-9, 40)
    f_ewlc = extensible_wlc_force(x, LC, LP, 1e10, T)  # huge S
    f_wlc = wlc_force(x, LC, LP, T)
    assert np.allclose(f_ewlc, f_wlc, rtol=1e-4)
    with pytest.raises(SmfsError) as ei:
        extensible_wlc_force(np.array([0.5 * LC]), LC, LP, -1.0, T)
    assert ei.value.code == "INVALID_MODEL_PARAMETER"


def test_fjc_forward_limits() -> None:
    # x(0) = 0 and x -> Lc at high force
    x0 = fjc_extension(np.array([0.0]), LC, B, T)
    assert abs(float(x0[0])) < 1e-15
    xbig = fjc_extension(np.array([1e3 * KB * T / B]), LC, B, T)
    assert float(xbig[0]) > 0.99 * LC
    # tiny force: x ~ Lc y/3
    f_small = 1e-14
    y = f_small * B / (KB * T)
    x_small = fjc_extension(np.array([f_small]), LC, B, T)
    assert np.allclose(x_small, LC * y / 3.0, rtol=1e-3)


def test_langevin_stability() -> None:
    u = np.array([0.0, 1e-8, 0.5, 3.0, 1e4])
    L = langevin(u)
    assert np.all(np.isfinite(L))
    assert abs(float(L[0])) < 1e-15
    assert float(L[-1]) > 0.999


def test_efjc_infinite_stiffness_limit() -> None:
    f = np.linspace(1e-12, 1e-9, 40)
    x_efjc = extensible_fjc_extension(f, LC, B, 1e10, T)
    x_fjc = fjc_extension(f, LC, B, T)
    assert np.allclose(x_efjc, x_fjc, rtol=1e-4)


# ---------------------------------------------------------------------------
# molecular extension contract
# ---------------------------------------------------------------------------


def _prepared_curve(n_retract: int = 300):
    """A minimal prepared-style curve with a retract separation axis."""
    sep = np.linspace(2.9e-6, 3.09e-6, n_retract)
    f = np.linspace(0.0, 2e-10, n_retract)
    t = np.linspace(0.0, 1.0, n_retract)
    z_a = np.linspace(1e-6, 2.8e-6, 120)
    f_a = np.where(z_a > 2.5e-6, (z_a - 2.5e-6) * 1e-3, 0.0)
    t_a = np.linspace(-0.5, 0.0, 120)
    curve = ForceCurve(
        segments=(
            ForceSegment(segment_type="extend", direction="forward", raw_height=z_a,
                         raw_deflection=f_a / 10.0, time=t_a, cycle=0, state="force_n",
                         deflection=f_a / 10.0, force=f_a, separation=None, metadata={}),
            ForceSegment(segment_type="retract", direction="backward", raw_height=sep + f / 10.0,
                         raw_deflection=f / 10.0, time=t, cycle=0, state="force_n",
                         deflection=f / 10.0, force=f, separation=None, metadata={}),
        ),
        calibration=Calibration(invols=3e-8, spring_constant=10.0, method="thermal",
                                temperature=300, provenance={}),
        position=None, index=0, metadata={})
    return curve


def test_extension_reference_policies() -> None:
    from spmkit.core.analysis import prepare_force_curve
    curve = _prepared_curve()
    prepared = prepare_force_curve(curve)
    # offset policy
    ext = compute_molecular_extension(prepared, reference="offset", reference_value=3.0e-6)
    assert abs(ext.reference_coordinate - 3.0e-6) < 1e-15
    assert np.all(np.diff(ext.extension[ext.valid]) >= -1e-12)
    # index policy
    ext2 = compute_molecular_extension(prepared, reference="index", reference_value=100)
    assert ext2.reference_index == 100
    # pre_event policy (semantic alias)
    ext3 = compute_molecular_extension(prepared, reference="pre_event", reference_value=100)
    assert ext3.reference_policy == "pre_event"
    # unknown policy typed
    with pytest.raises(SmfsError) as ei:
        compute_molecular_extension(prepared, reference="auto")
    assert ei.value.code == "INVALID_REFERENCE_POLICY"
    # missing value typed
    with pytest.raises(SmfsError) as ei:
        compute_molecular_extension(prepared, reference="offset")
    assert ei.value.code == "UNRESOLVED_TETHER_ZERO"


def test_extension_estimator_zero_crossing() -> None:
    from spmkit.core.analysis import prepare_force_curve
    curve = _prepared_curve()
    prepared = prepare_force_curve(curve)
    ext = compute_molecular_extension(prepared, reference="estimator")
    assert ext.reference_policy == "estimator"
    assert np.isfinite(ext.reference_coordinate)
    assert any("estimator" in w for w in ext.warnings)


def test_smfs_fit_window_contract() -> None:
    x, f = _wlc_data()
    w = select_smfs_fit_windows(x, f, min_points=10)
    assert w.n_points >= 10
    assert w.included.sum() == w.n_points
    with pytest.raises(SmfsError) as ei:
        select_smfs_fit_windows(x, f, min_extension=1e-6)  # empty
    assert ei.value.code == "EMPTY_WINDOW"
    with pytest.raises(SmfsError) as ei:
        select_smfs_fit_windows(x, f, min_points=10**6)
    assert ei.value.code == "INSUFFICIENT_POINTS"


# ---------------------------------------------------------------------------
# polymer fits
# ---------------------------------------------------------------------------


def test_wlc_clean_recovery() -> None:
    x, f = _wlc_data()
    fit = fit_worm_like_chain(x, f, temperature=T)
    assert abs(fit.parameters["Lc"] - LC) / LC < 0.01
    assert abs(fit.parameters["Lp"] - LP) / LP < 0.01
    assert fit.condition_number > 0.0


def test_wlc_noisy_recovery() -> None:
    x, f = _wlc_data(noise=2e-13)
    fit = fit_worm_like_chain(x, f, temperature=T)
    assert abs(fit.parameters["Lc"] - LC) / LC < 0.05
    assert abs(fit.parameters["Lp"] - LP) / LP < 0.20


def test_wlc_singular_domain_typed() -> None:
    # the data must stay below the contour; the singular extension domain
    # raises through the forward model
    with pytest.raises(SmfsError):
        wlc_force(np.array([LC]), LC, LP, T)


def test_ewlc_clean_recovery_bounds() -> None:
    x = np.linspace(1e-9, 80e-9, 200)
    f = extensible_wlc_force(x, LC, LP, 1e-8, T)
    fit = fit_extensible_worm_like_chain(x, f, temperature=T)
    assert abs(fit.parameters["Lc"] - LC) / LC < 0.05
    assert abs(fit.parameters["Lp"] - LP) / LP < 0.20
    # the stretch modulus is weakly identifiable from a single branch
    # (documented); the response reconstruction must be accurate
    pred = extensible_wlc_force(x, fit.parameters["Lc"], fit.parameters["Lp"],
                                fit.parameters["S"], T)
    assert np.max(np.abs(pred - f)) / np.max(np.abs(f)) < 0.02


def test_fjc_clean_recovery() -> None:
    f = np.linspace(1e-13, 1e-9, 200)
    x = fjc_extension(f, LC, B, T)
    fit = fit_freely_jointed_chain(x, f, temperature=T)
    assert abs(fit.parameters["Lc"] - LC) / LC < 0.01
    assert abs(fit.parameters["b"] - B) / B < 0.02


def test_efjc_clean_recovery() -> None:
    f = np.linspace(1e-13, 1e-9, 200)
    x = extensible_fjc_extension(f, LC, B, 1e-8, T)
    fit = fit_extensible_freely_jointed_chain(x, f, temperature=T)
    assert abs(fit.parameters["Lc"] - LC) / LC < 0.01
    assert abs(fit.parameters["b"] - B) / B < 0.02


def test_polymer_fit_determinism() -> None:
    x, f = _wlc_data(noise=2e-13)
    a = fit_worm_like_chain(x, f, temperature=T)
    b = fit_worm_like_chain(x, f, temperature=T)
    assert a.parameters == b.parameters
    assert a.aicc == b.aicc


def test_polymer_comparison_prefers_true_model() -> None:
    x, f = _wlc_data()
    cmp = __import__("spmkit.core.analysis.force_smfs",
                     fromlist=["compare_polymer_models"]).compare_polymer_models(
        x, f, models=("worm_like_chain", "freely_jointed_chain"))
    assert cmp.recommended_model == "worm_like_chain"
    assert cmp.weights["worm_like_chain"] > 0.9


# ---------------------------------------------------------------------------
# events
# ---------------------------------------------------------------------------


def _sawtooth_extension(n: int = 400):
    """Clean single-event sawtooth on the extension axis."""
    lc1, lc2, lp = 100e-9, 200e-9, 0.5e-9
    x = np.linspace(0.0, 140e-9, n)
    f = np.zeros(n)
    for i, xi in enumerate(x):
        if xi <= 70e-9:
            f[i] = float(wlc_force(np.array([xi]), lc1, lp, T)[0])
        else:
            f[i] = float(wlc_force(np.array([xi]), lc2, lp, T)[0])
    sep = 3.0e-6 + x
    t = np.linspace(0.0, 1.0, n)
    return MolecularExtensionResult(
        extension=x, separation=sep, force=f, time=t,
        retract_indices=np.arange(n), reference_policy="offset",
        reference_coordinate=3.0e-6, reference_index=None, valid=np.ones(n, dtype=bool),
        provenance={})


def test_event_detection_tp_fp_fn() -> None:
    ext = _sawtooth_extension()
    ev = detect_unfolding_events(ext, noise_sigma=1e-13)
    assert len(ev.events) == 1  # one true positive
    e = ev.events[0]
    assert e.valid
    assert not e.is_final_detachment  # the force continues after the event
    assert e.rupture_force > 0.0
    # the detected index is within 3 samples of the truth (70e-9)
    idx = int(np.argmin(np.abs(ext.extension - 70e-9)))
    assert abs(e.event_index - idx) <= 3


def test_event_detection_rejects_noise_peak() -> None:
    ext = _sawtooth_extension()
    f = ext.force.copy()
    peak = int(np.argmin(np.abs(ext.extension - 5e-9)))
    f[peak] += float(np.max(f)) * 0.01  # a 1% spike (below the 5-sigma drop)
    ext2 = MolecularExtensionResult(
        extension=ext.extension, separation=ext.separation, force=f, time=ext.time,
        retract_indices=ext.retract_indices, reference_policy="offset",
        reference_coordinate=3.0e-6, reference_index=None,
        valid=ext.valid, provenance={})
    ev = detect_unfolding_events(ext2, noise_sigma=1e-13)
    assert len(ev.events) == 1  # the noise peak is not a false positive
    assert len(ev.rejected) >= 1  # retained with the reason


def test_event_detection_no_events_typed() -> None:
    x = np.linspace(0.0, 90e-9, 300)
    f = wlc_force(x, LC, LP, T)  # smooth branch, no events
    ext = MolecularExtensionResult(
        extension=x, separation=3.0e-6 + x, force=f, time=np.linspace(0, 1, 300),
        retract_indices=np.arange(300), reference_policy="offset",
        reference_coordinate=3.0e-6, reference_index=None,
        valid=np.ones(300, dtype=bool), provenance={})
    with pytest.raises(SmfsError) as ei:
        detect_unfolding_events(ext, noise_sigma=1e-13)
    assert ei.value.code == "NO_EVENTS"


def test_contour_increment_from_independent_fits() -> None:
    ext = _sawtooth_extension()
    ev = detect_unfolding_events(ext, noise_sigma=1e-13)
    ev2 = quantify_unfolding_events(ext, ev)
    inc = infer_contour_length_increments(ext, ev2)
    assert len(inc) == 1
    r = inc[0]
    assert r.valid
    assert abs(r.delta_contour_length - 100e-9) / 100e-9 < 0.10
    assert r.pre_fit is not None and r.post_fit is not None
    assert abs(r.pre_fit.parameters["Lc"] - 100e-9) / 100e-9 < 0.10
    assert abs(r.post_fit.parameters["Lc"] - 200e-9) / 200e-9 < 0.10


def test_loading_rates_measured_vs_theoretical() -> None:
    ext = _sawtooth_extension()
    ev = detect_unfolding_events(ext, noise_sigma=1e-13)
    ev2 = quantify_unfolding_events(ext, ev)
    rates = compute_event_loading_rates(ext, ev2, pulling_velocity=1e-6,
                                        effective_stiffness=1e-4)
    r = rates[0]
    assert r.local_slope > 0.0  # force rises before the rupture
    assert r.units == "N/s"
    # the theoretical rate is reported separately, never substituted
    assert r.theoretical_rate is not None
    assert abs(r.theoretical_rate - 1e-10) < 1e-30
    assert r.measured


def test_loading_rates_require_time() -> None:
    ext = _sawtooth_extension()
    ext2 = MolecularExtensionResult(
        extension=ext.extension, separation=ext.separation, force=ext.force,
        time=None, retract_indices=ext.retract_indices, reference_policy="offset",
        reference_coordinate=3.0e-6, reference_index=None, valid=ext.valid,
        provenance={})
    ev = detect_unfolding_events(ext2, noise_sigma=1e-13)
    ev2 = quantify_unfolding_events(ext2, ev)
    with pytest.raises(SmfsError) as ei:
        compute_event_loading_rates(ext2, ev2)
    assert ei.value.code == "NONFINITE_INPUT"


# ---------------------------------------------------------------------------
# kinetics
# ---------------------------------------------------------------------------


def test_bell_evans_forward() -> None:
    # S(0) = 1 and the pdf integrates approximately to 1 at a high rate
    f = np.linspace(0.0, 2e-10, 400)
    s = bell_evans_survival(f, 1e4, 1.0, 1e-9, T)
    assert abs(float(s[0]) - 1.0) < 1e-9
    p = bell_evans_pdf(f, 1e4, 1.0, 1e-9, T)
    integral = float(np.trapezoid(p, f))
    assert 0.9 < integral < 1.1
    # the rate is dimensionless-consistent
    k = bell_evans_rate(np.array([1e-9]), 1.0, 1e-9, T)
    assert np.isfinite(k).all()


def test_bell_evans_recovery() -> None:
    # deterministic quantile sample from the BE pdf at several rates
    rng = np.random.default_rng(3)
    rates = np.geomspace(1e3, 1e6, 4)
    forces = []
    rate_list = []
    for r in rates:
        grid = np.linspace(0.0, 2.5e-10, 2000)
        p = bell_evans_pdf(grid, r, 1.0, 1e-9, T)
        cdf = np.cumsum(p) * (grid[1] - grid[0])
        cdf = cdf / cdf[-1]
        u = rng.random(40)
        forces.extend(np.interp(u, cdf, grid))
        rate_list.extend([r] * 40)
    fit = fit_bell_evans(np.asarray(rate_list), np.asarray(forces), temperature=T)
    assert abs(fit.parameters["x_beta"] - 1e-9) / 1e-9 < 0.10
    assert 0.3 < fit.parameters["k0"] < 3.0


def test_bell_evans_invalid_domains() -> None:
    with pytest.raises(SmfsError) as ei:
        fit_bell_evans(np.array([1e3, 1e4]), np.array([1e-10, 1e-10]), temperature=-5.0)
    assert ei.value.code == "INVALID_MODEL_PARAMETER"
    with pytest.raises(SmfsError):
        fit_bell_evans(np.array([-1e3, 1e4]), np.array([1e-10, 1e-10]))


def test_dhs_forward_and_bell_limit() -> None:
    # at tiny barrier the DHS rate approaches the BE rate
    f = 5e-11
    k_dhs = dhs_log_rate(f, 1.0, 1e-9, 1e-12, 2.0 / 3.0, T)
    k_be = np.log(float(bell_evans_rate(np.array([f]), 1.0, 1e-9, T)[0]))
    assert abs(k_dhs - k_be) < 1e-6
    # domain violation typed
    with pytest.raises(SmfsError) as ei:
        fit_dudko_hummer_szabo(np.array([1e3, 1e4, 1e5, 1e6, 1e7]),
                               np.array([1e-10] * 5), nu=0.4)
    assert ei.value.code == "INVALID_MODEL_PARAMETER"


def test_dhs_recovery_bounds() -> None:
    # deterministic quantile sample from the DHS pdf
    rng = np.random.default_rng(5)
    rates = np.geomspace(1e3, 1e6, 4)
    forces, rate_list = [], []
    for r in rates:
        grid = np.linspace(0.0, 1.4e-10, 3000)
        from spmkit.core.analysis.force_smfs import dhs_pdf
        p = dhs_pdf(grid, r, 1.0, 1e-9, 1e-19, 2.0 / 3.0, T)
        cdf = np.cumsum(p) * (grid[1] - grid[0])
        cdf = cdf / cdf[-1]
        u = rng.random(30)
        forces.extend(np.interp(u, cdf, grid))
        rate_list.extend([r] * 30)
    fit = fit_dudko_hummer_szabo(np.asarray(rate_list), np.asarray(forces),
                                 temperature=T)
    assert fit.success
    # the energy-landscape parameters are weakly identifiable (the fit can
    # land at the physical bounds on a finite sample): the honest evidence
    # is the RESPONSE reconstruction plus the documented non-uniqueness
    assert 1e-12 <= fit.parameters["x_beta"] <= 1e-7
    assert 1e-22 <= fit.parameters["dG"] <= 1e-11
    assert any("not claimed to be physically unique" in w for w in fit.warnings)
    # the predicted per-rate median forces reproduce the data within 30%
    med_data = np.array([float(np.median(forces[i * 30:(i + 1) * 30]))
                         for i in range(4)])
    grid = np.linspace(0.0, 1.5e-10, 400)
    med_pred = np.empty(4)
    for i, r in enumerate(rates):
        pdf = dhs_pdf(grid, r, fit.parameters["k0"], fit.parameters["x_beta"],
                      fit.parameters["dG"], 2.0 / 3.0, T)
        cdf = np.cumsum(pdf)
        cdf = cdf / cdf[-1]
        med_pred[i] = float(np.interp(0.5, cdf, grid))
    assert np.max(np.abs(med_pred - med_data) / med_data) < 0.30


# ---------------------------------------------------------------------------
# force clamp survival
# ---------------------------------------------------------------------------


def test_km_survival_truth() -> None:
    # hand-computed case: lifetimes (1, 2, 3) all events
    lt = np.array([1.0, 2.0, 3.0])
    ce = np.array([0.0, 0.0, 0.0])
    km = estimate_force_clamp_survival(lt, ce, force_level=1e-11)
    assert km.n_events == 3
    assert km.n_censored == 0
    # S(1) = 2/3, S(2) = 1/3, S(3) = 0
    assert np.allclose(km.survival_probability, [2 / 3, 1 / 3, 0.0])
    assert km.median_lifetime == 2.0
    # exponential MLE: 3 / (1+2+3) = 0.5
    assert np.isclose(km.exponential_rate, 0.5)


def test_km_right_censoring_preserved() -> None:
    lt = np.array([1.0, 2.0, 5.0, 5.0])
    ce = np.array([0.0, 0.0, 0.0, 1.0])
    km = estimate_force_clamp_survival(lt, ce, force_level=1e-11)
    assert km.n_censored == 1
    # at t=1: S = 3/4; at t=2: S = 3/4 * 2/3 = 1/2; at t=5: one event among
    # 2 at risk -> S = 1/2 * 1/2 = 1/4 (the censor leaves the risk set
    # afterwards)
    assert np.allclose(km.survival_probability, [3 / 4, 1 / 2, 1 / 4])
    # the censored observation is not discarded from the rate MLE:
    # 3 uncensored events over the total time 13
    assert np.isclose(km.exponential_rate, 3.0 / 13.0)


def test_km_tie_order_deterministic() -> None:
    lt = np.array([1.0, 1.0, 2.0])
    ce = np.array([0.0, 1.0, 0.0])  # event and censor at the same time
    km = estimate_force_clamp_survival(lt, ce, force_level=1e-11)
    # the event at t=1 lowers the survival before the censor reduces the
    # at-risk count: S(1) = 2/3
    assert np.allclose(km.survival_probability[0], 2 / 3)


def test_km_undefined_median() -> None:
    lt = np.array([1.0, 2.0, 3.0])
    ce = np.array([1.0, 1.0, 1.0])  # all censored
    km = estimate_force_clamp_survival(lt, ce, force_level=1e-11)
    assert km.median_lifetime is None
    assert km.exponential_rate is None
    assert any("UNDEFINED_MEDIAN" in w for w in km.warnings)
    with pytest.raises(SmfsError) as ei:
        estimate_force_clamp_survival(np.array([1.0, -2.0]), np.array([0.0, 0.0]),
                                      force_level=1e-11)
    assert ei.value.code == "CENSORING_INVALID"


# ---------------------------------------------------------------------------
# population and batch
# ---------------------------------------------------------------------------


def test_population_aggregation_and_ambiguity() -> None:
    records = [
        {"rupture_force": 1e-10, "delta_contour_length": 1e-7, "loading_rate": 1e3},
        {"rupture_force": 1.2e-10, "delta_contour_length": 1e-7, "loading_rate": 1e3},
        {"rupture_force": 1.1e-10, "delta_contour_length": 1e-7, "loading_rate": 1e6},
    ]
    pop = analyze_smfs_event_population(records, group_by="none")
    assert pop.n_events == 3
    assert pop.ambiguous  # too few events for a population claim
    assert any("no molecular-identity claim" in w for w in pop.warnings)
    with pytest.raises(SmfsError) as ei:
        analyze_smfs_event_population([])
    assert ei.value.code == "INSUFFICIENT_EVENTS"


def test_batch_retains_failures() -> None:
    batch = analyze_smfs_batch([
        {"curve_id": "A", "ok": True, "events": [
            {"rupture_force": 1e-10, "delta_contour_length": 1e-7,
             "loading_rate": 1e3}]},
        {"curve_id": "B", "curve_index": 1, "ok": False, "failure": "MISSING_TIME"},
        {"curve_id": "C", "curve_index": 2, "ok": False, "failure": "NO_EVENTS"},
    ], group_by="none")
    assert batch.n_curves == 3
    assert batch.n_ok == 1
    assert batch.n_failed == 2
    assert batch.failed_reasons == {1: "MISSING_TIME", 2: "NO_EVENTS"}
    assert len(batch.unified_event_table) == 1
    assert batch.unified_event_table[0]["curve_id"] == "A"
    assert batch.provenance["deterministic"]
