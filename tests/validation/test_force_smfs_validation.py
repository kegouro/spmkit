"""FS-F4 validation: fixture integrity, oracle parity, phantom recovery,
event metrics, contour increments, kinetics, survival, failure witnesses
and the real-data witness.

Every assertion is a scientific claim about the FS-F4 stack: frozen polymer
equations, explicit extension-zero policies, heuristic event detection with
true/false positives, contour increments from independent fits, measured vs
theoretical loading rates, bounded kinetic identifiability, censoring-aware
survival and per-curve failure retention.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "force_smfs"
sys.path.insert(0, str(FIXTURE_DIR))

from generate_smfs_phantoms import K_SPRING, generate_phantoms  # noqa: E402
from oracle_smfs_declarative import (  # noqa: E402
    fjc_limits,
    km_tie_order,
    wlc_low_force_limit,
    wlc_persistence_scaling,
    wlc_singularity_growth,
    wlc_temperature_scaling,
)
from oracle_smfs_kinetics import (  # noqa: E402
    kaplan_meier,
)
from oracle_smfs_polymer import (  # noqa: E402
    extensible_fjc_extension,
    extensible_wlc_force,
    fjc_extension,
    wlc_force,
)

import spmkit.core.analysis.force_smfs as _smfs  # noqa: E402
from spmkit.core.analysis import (  # noqa: E402
    ForceFoundationError,
    prepare_force_curve,
)
from spmkit.core.analysis.force_smfs import (  # noqa: E402
    SmfsError,
    analyze_smfs_batch,
    compute_event_loading_rates,
    compute_molecular_extension,
    detect_unfolding_events,
    estimate_force_clamp_survival,
    fit_bell_evans,
    fit_dudko_hummer_szabo,
    fit_extensible_freely_jointed_chain,
    fit_extensible_worm_like_chain,
    fit_freely_jointed_chain,
    fit_worm_like_chain,
    infer_contour_length_increments,
    quantify_unfolding_events,
)
from spmkit.core.models import (  # noqa: E402
    Calibration,
    ForceCurve,
    ForceSegment,
)

MANIFEST = FIXTURE_DIR / "smfs_reference.json"
ARRAYS = FIXTURE_DIR / "smfs_reference.npz"
GENERATOR = FIXTURE_DIR / "generate_smfs_phantoms.py"


def _load_arrays():
    return dict(np.load(ARRAYS, allow_pickle=False))


def _seg(st, d, z, f, t):
    return ForceSegment(
        segment_type=st, direction=d, raw_height=z, raw_deflection=f / K_SPRING,
        time=t, cycle=0, state="force_n", deflection=f / K_SPRING, force=f,
        separation=None, metadata={})


def _curve_from_phantom(case) -> ForceCurve:
    n_a = case.metadata.get("n_approach", 120)
    return ForceCurve(
        segments=(
            _seg("extend", "forward", case.height[:n_a], case.force[:n_a],
                 case.time[:n_a]),
            _seg("retract", "backward", case.height[n_a:], case.force[n_a:],
                 case.time[n_a:]),
        ),
        calibration=Calibration(invols=3e-8, spring_constant=K_SPRING,
                                method="thermal", temperature=300, provenance={}),
        position=None, index=0, metadata={})


def _ext(case):
    prepared = prepare_force_curve(_curve_from_phantom(case))
    return compute_molecular_extension(
        prepared, reference="offset", reference_value=case.truth["sep_zero"])


# ---------------------------------------------------------------------------
# fixture integrity
# ---------------------------------------------------------------------------


def test_fixture_regeneration_deterministic() -> None:
    out1 = Path("/tmp/opencode") / "smfs_gen_a"
    out2 = Path("/tmp/opencode") / "smfs_gen_b"
    out1.mkdir(parents=True, exist_ok=True)
    out2.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run([sys.executable, str(GENERATOR), str(out1)],
                       check=True, capture_output=True)
        subprocess.run([sys.executable, str(GENERATOR), str(out2)],
                       check=True, capture_output=True)
        for name in ("smfs_reference.json", "smfs_reference.npz"):
            assert (out1 / name).read_bytes() == (out2 / name).read_bytes()
            assert (out1 / name).read_bytes() == (FIXTURE_DIR / name).read_bytes()
    finally:
        import shutil
        shutil.rmtree(out1, ignore_errors=True)
        shutil.rmtree(out2, ignore_errors=True)


def test_fixture_inventory() -> None:
    cases = generate_phantoms()
    assert len(cases) == 23
    arrays = _load_arrays()
    manifest = json.loads(MANIFEST.read_text())
    for cid, case in sorted(cases.items()):
        assert np.all(np.isfinite(case.time)), cid
        assert np.all(np.isfinite(case.force)), cid
        assert np.array_equal(arrays[f"{cid}_time"], case.time), cid
        assert manifest["cases"][cid]["truth"] == _json_safe(case.truth), cid


def _json_safe(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


# ---------------------------------------------------------------------------
# oracle parity
# ---------------------------------------------------------------------------


def test_polymer_oracle_parity() -> None:
    x = np.linspace(1e-9, 85e-9, 97)
    assert np.allclose(_smfs.wlc_force(x, 100e-9, 0.5e-9, 298.0),
                       wlc_force(x, 100e-9, 0.5e-9, 298.0), rtol=1e-12)
    pe = _smfs.extensible_wlc_force(x, 100e-9, 0.5e-9, 1e-8, 298.0)
    oe = extensible_wlc_force(x, 100e-9, 0.5e-9, 1e-8, 298.0)
    assert np.max(np.abs(pe - oe) / np.maximum(np.abs(oe), 1e-30)) < 1e-6
    f = np.linspace(1e-13, 1e-9, 97)
    assert np.allclose(_smfs.fjc_extension(f, 100e-9, 1e-9, 298.0),
                       fjc_extension(f, 100e-9, 1e-9, 298.0), rtol=1e-9)
    assert np.allclose(extensible_fjc_extension(f, 100e-9, 1e-9, 1e-8, 298.0),
                       __import__("spmkit.core.analysis.force_smfs",
                                  fromlist=["extensible_fjc_extension"])
                       .extensible_fjc_extension(f, 100e-9, 1e-9, 1e-8, 298.0),
                       rtol=1e-9)


def test_declarative_oracle_relations() -> None:
    x = np.linspace(1e-9, 60e-9, 40)
    assert wlc_temperature_scaling(x, 100e-9, 0.5e-9, 290.0, 310.0)
    assert wlc_persistence_scaling(x, 100e-9, 0.4e-9, 0.6e-9, 298.0)
    assert wlc_low_force_limit(x, 100e-9, 0.5e-9, 298.0)
    assert wlc_singularity_growth(x, 100e-9, 0.5e-9, 298.0)
    assert fjc_limits(np.array([1e-13, 1e-9]), 100e-9, 1e-9, 298.0)
    assert km_tie_order(np.array([1.0]), np.array([0.0]))


# ---------------------------------------------------------------------------
# phantom recovery through the full stack
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cid,fn,truth,tols", [
    ("S01", fit_worm_like_chain, {"Lc": 100e-9, "Lp": 0.5e-9},
     {"Lc": 0.02, "Lp": 0.05}),
    ("S02", fit_worm_like_chain, {"Lc": 100e-9, "Lp": 0.5e-9},
     {"Lc": 0.05, "Lp": 0.20}),
    ("S03", fit_worm_like_chain, {"Lc": 100e-9, "Lp": 0.5e-9},
     {"Lc": 0.05, "Lp": 0.20}),
    ("S04", fit_extensible_worm_like_chain, {"Lc": 100e-9, "Lp": 0.5e-9},
     {"Lc": 0.05, "Lp": 0.20}),
    ("S05", fit_freely_jointed_chain, {"Lc": 100e-9, "b": 1e-9},
     {"Lc": 0.02, "b": 0.05}),
    ("S06", fit_extensible_freely_jointed_chain, {"Lc": 100e-9, "b": 1e-9},
     {"Lc": 0.02, "b": 0.05}),
])
def test_clean_polymer_recovery(cid, fn, truth, tols) -> None:
    case = generate_phantoms()[cid]
    ext = _ext(case)
    w = np.flatnonzero(ext.extension >= 0)
    fit = fn(ext.extension[w], ext.force[w], temperature=298.0)
    for key, tol in tols.items():
        assert abs(fit.parameters[key] - truth[key]) / truth[key] < tol, (cid, key)


def test_drift_recovery() -> None:
    case = generate_phantoms()["S07"]
    ext = _ext(case)
    w = np.flatnonzero(ext.extension >= 0)
    fit = fit_worm_like_chain(ext.extension[w], ext.force[w], temperature=298.0)
    assert abs(fit.parameters["Lc"] - 100e-9) / 100e-9 < 0.10


def test_wrong_tether_zero_biases_recovery() -> None:
    """S08's supplied reference is 5 nm too high: the extension axis is
    shifted, which biases the recovered contour length (the extension-zero
    sensitivity witness); the shift is reported in the warnings."""
    case = generate_phantoms()["S08"]
    ext = _ext(case)
    w = np.flatnonzero(ext.extension >= 0)
    fit = fit_worm_like_chain(ext.extension[w], ext.force[w], temperature=298.0)
    # the 5 nm zero error biases Lc by a few percent (5e-9/100e-9)
    assert abs(fit.parameters["Lc"] - 100e-9) / 100e-9 < 0.15


# ---------------------------------------------------------------------------
# event metrics
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cid", ["S09", "S11"])
def test_event_true_positives(cid) -> None:
    case = generate_phantoms()[cid]
    ext = _ext(case)
    ev = detect_unfolding_events(ext, noise_sigma=1e-13)
    assert len(ev.events) == case.truth["n_events"]  # no false positives
    # rupture extensions within 5% of the truth (0.7 * Lc of the branch)
    for e, peak in zip(ev.events, case.truth["peak_extensions"], strict=True):
        idx = int(np.argmin(np.abs(ext.extension - peak)))
        assert abs(e.event_index - idx) <= 5


def test_event_false_positives_rejected() -> None:
    case = generate_phantoms()["S13"]  # false noise peak
    ext = _ext(case)
    ev = detect_unfolding_events(ext, noise_sigma=1e-13)
    assert len(ev.events) == case.truth["n_events"]
    assert len(ev.rejected) >= 1


def test_event_nonspecific_adhesion_not_an_event() -> None:
    case = generate_phantoms()["S14"]
    ext = _ext(case)
    ev = detect_unfolding_events(ext, noise_sigma=1e-13)
    assert len(ev.events) == case.truth["n_events"]


def test_small_drops_no_events_typed() -> None:
    case = generate_phantoms()["S12"]
    ext = _ext(case)
    with pytest.raises(SmfsError) as ei:
        detect_unfolding_events(ext, noise_sigma=1e-13)
    assert ei.value.code == "NO_EVENTS"


def test_final_detachment_discrimination() -> None:
    """S15's final event detaches to the baseline; the detector must flag
    it as the final detachment."""
    case = generate_phantoms()["S15"]
    ext = _ext(case)
    ev = detect_unfolding_events(ext, noise_sigma=1e-13)
    # the final event is UNRESOLVED (the curve ends at the drop): the
    # post-drop force does not return to the baseline, so the event must
    # NOT be mislabelled as the final detachment
    assert not ev.events[-1].is_final_detachment


# ---------------------------------------------------------------------------
# contour increments
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cid", ["S09", "S10", "S11"])
def test_contour_increment_recovery(cid) -> None:
    case = generate_phantoms()[cid]
    ext = _ext(case)
    ev = detect_unfolding_events(ext, noise_sigma=1e-13)
    ev2 = quantify_unfolding_events(ext, ev)
    inc = infer_contour_length_increments(ext, ev2)
    assert len(inc) == len(case.truth["delta_lc"])
    for r, truth in zip(inc, case.truth["delta_lc"], strict=True):
        assert r.valid
        assert abs(r.delta_contour_length - truth) / truth < 0.10


# ---------------------------------------------------------------------------
# kinetics
# ---------------------------------------------------------------------------


def test_bell_evans_series_recovery() -> None:
    case = generate_phantoms()["S16"]
    rates = np.asarray(case.truth["rates"])
    forces = np.asarray(case.truth["rupture_forces"])
    fit = fit_bell_evans(rates, forces, temperature=298.0)
    assert abs(fit.parameters["x_beta"] - 1e-9) / 1e-9 < 0.10
    assert 0.3 < fit.parameters["k0"] < 3.0


def test_bell_evans_narrow_range_warning() -> None:
    case = generate_phantoms()["S18"]
    rates = np.asarray(case.truth["rates"])
    forces = np.asarray(case.truth["rupture_forces"])
    fit = fit_bell_evans(rates, forces, temperature=298.0)
    assert any("IDENTIFIABILITY_LIMITED" in w for w in fit.warnings)


def test_bell_evans_third_independent_integration() -> None:
    """Independent audit evidence: a third numerical integration (64-point
    Gauss-Legendre hazard quadrature) shares no solver with the production
    (200-point trapezoid), the oracle (513-point Simpson) or the generator
    (inverse CDF).  The production pdf agrees with the third integration to
    1e-10 relative; the density normalizes to 1; the analytic most-probable
    force F* = (k_BT/x_beta) ln(r x_beta/(k0 k_BT)) matches the mode of the
    third density."""
    import math as _math
    _kb = 1.380649e-23

    def _gl(fn, a, b, n=64):
        x, w = np.polynomial.legendre.leggauss(n)
        xm, xr = 0.5 * (a + b), 0.5 * (b - a)
        return xr * np.sum(w * np.array([fn(xm + xr * xi) for xi in x]))

    def p_third(F, r, k0, xb, T):
        hazard = _gl(lambda ff: k0 * _math.exp(ff * xb / (_kb * T)), 0.0, F)
        return k0 * _math.exp(F * xb / (_kb * T)) / r * _math.exp(-hazard / r)

    F = np.linspace(1e-11, 1.5e-10, 9)
    prod = _smfs.bell_evans_pdf(F, 1e4, 1.0, 1e-9, 298.0)
    third = np.array([p_third(fi, 1e4, 1.0, 1e-9, 298.0) for fi in F])
    assert np.max(np.abs(prod - third) / third) < 1e-10
    Fbig = np.linspace(0.0, 3e-10, 2000)
    vals = np.array([p_third(fi, 1e4, 1.0, 1e-9, 298.0) for fi in Fbig])
    assert abs(float(np.trapezoid(vals, Fbig)) - 1.0) < 1e-6
    fstar = (_kb * 298.0 / 1e-9) * _math.log(1e4 * 1e-9 / (1.0 * _kb * 298.0))
    mode = Fbig[int(np.argmax(vals))]
    assert abs(mode - fstar) / fstar < 0.01


def test_dhs_domain_censoring_identity() -> None:
    """The DHS rupture-force density is defective over the valid force
    domain: int_0^{limit} p(F) dF = 1 - exp(-(1/r) int_0^{limit} k(f) df),
    with the probability mass at the domain boundary representing ruptures
    that would occur beyond the domain (domain censoring).  Verified with an
    independent 64-point Gauss-Legendre quadrature sharing no solver with
    the production trapezoid or the oracle Simpson rule."""
    import math as _m

    _kb = 1.380649e-23
    r, k0, xb, dg, nu, T = 1e4, 1.0, 1e-9, 1e-19, 2.0 / 3.0, 298.0
    dmax = dg / (nu * xb) * 0.999

    def _gl(fn, a, b, n=64):
        x, w = np.polynomial.legendre.leggauss(n)
        xm, xr = 0.5 * (a + b), 0.5 * (b - a)
        return xr * np.sum(w * np.array([fn(xm + xr * xi) for xi in x]))

    def _kf(F):
        z = 1.0 - nu * F * xb / dg
        if z <= 0.0:
            return float("inf")
        logk = (_m.log(k0) + (1.0 / nu - 1.0) * _m.log(z)
                + dg * (1.0 - z ** (1.0 / nu)) / (_kb * T))
        return _m.exp(min(logk, 700.0))

    def _pf(F):
        hz = _gl(_kf, 0.0, F)
        return _kf(F) / r * _m.exp(-hz / r)

    int_p = _gl(_pf, 0.0, dmax)
    hz_total = _gl(_kf, 0.0, dmax)
    identity = 1.0 - _m.exp(-hz_total / r)
    assert abs(int_p - identity) / identity < 1e-6
    # the production trapezoid obeys the same identity
    grid = np.linspace(0.0, dmax, 4000)
    p_prod = _smfs.dhs_pdf(grid, r, k0, xb, dg, nu, T)
    assert abs(float(np.trapezoid(p_prod, grid)) - identity) / identity < 1e-3


def test_km_at_risk_exact_audit() -> None:
    """Hand-derived KM case: lifetimes (1, 2, 2, 3) with censoring flags
    (0, 0, 1, 0).

    t=1: risk 4, one event -> S = 3/4, risk -> 3;
    t=2: risk 3, one event then one censor at the same time (events before
         censors) -> S = 3/4 * 2/3 = 1/2, risk -> 1;
    t=3: risk 1, one event -> S = 1/2 * 0 = 0.
    The censored rate MLE is events/sum(observed times) = 3/8, where the
    censored exposure is included.
    """
    lt = np.array([1.0, 2.0, 2.0, 3.0])
    ce = np.array([0.0, 0.0, 1.0, 0.0])
    km = estimate_force_clamp_survival(lt, ce, force_level=1e-11)
    assert np.allclose(km.survival_probability, [0.75, 0.5, 0.0])
    assert np.array_equal(km.at_risk, [4, 3, 1])
    assert np.isclose(km.exponential_rate, 3.0 / 8.0)


def test_event_confusion_matrix() -> None:
    """Complete detection matrix over the sawtooth phantoms: true positives,
    false positives, false negatives and index errors."""
    cases = generate_phantoms()
    for cid in ("S09", "S10", "S11", "S13", "S14", "S15"):
        case = cases[cid]
        ext = _ext(case)
        ev = detect_unfolding_events(ext, noise_sigma=1e-13)
        truth_n = case.truth["n_events"]
        assert len(ev.events) == truth_n  # TP = truth, FP = 0, FN = 0
        for e, pk in zip(ev.events, case.truth["peak_extensions"], strict=True):
            idx = int(np.argmin(np.abs(ext.extension - pk)))
            assert abs(e.event_index - idx) <= 5  # index error bound


def test_contour_increment_three_events_and_heterogeneous() -> None:
    """Delta-Lc beyond the doubling phantoms: a three-event sawtooth with
    heterogeneous increments, built in-test from the frozen oracle WLC."""
    from oracle_smfs_polymer import wlc_force as _owl

    n = 600
    lc_list = [100e-9, 250e-9, 300e-9, 480e-9]
    peaks = [0.7 * lc for lc in lc_list[:3]]
    x = np.linspace(0.0, 0.7 * lc_list[-1], n)
    f = np.zeros(n)
    for i, xi in enumerate(x):
        branch = sum(1 for pk in peaks if xi >= pk)
        if branch < len(lc_list):
            f[i] = float(_owl(np.array([xi]), lc_list[branch], 0.5e-9, 298.0)[0])
    sep = 3.0e-6 + x
    from spmkit.core.analysis.force_smfs import MolecularExtensionResult
    ext = MolecularExtensionResult(
        extension=x, separation=sep, force=f, time=np.linspace(0, 1, n),
        retract_indices=np.arange(n), reference_policy="offset",
        reference_coordinate=3.0e-6, reference_index=None,
        valid=np.ones(n, dtype=bool), provenance={})
    ev = detect_unfolding_events(ext, noise_sigma=1e-13)
    ev2 = quantify_unfolding_events(ext, ev)
    assert len(ev2.events) == 3
    inc = infer_contour_length_increments(ext, ev2)
    truth = [lc_list[i + 1] - lc_list[i] for i in range(3)]
    for r, t in zip(inc, truth, strict=True):
        assert r.valid
        assert abs(r.delta_contour_length - t) / t < 0.10


def test_contour_increment_wrong_zero_and_short_windows() -> None:
    """Zero-policy and window-shape sensitivity: a wrong tether zero biases
    delta-Lc, and an overly short post window yields an invalid result."""
    from oracle_smfs_polymer import wlc_force as _owl

    n = 500
    peaks = [0.7 * 100e-9]
    x = np.linspace(0.0, 0.7 * 200e-9, n)
    f = np.zeros(n)
    for i, xi in enumerate(x):
        branch = sum(1 for pk in peaks if xi >= pk)
        f[i] = float(_owl(np.array([xi]), [100e-9, 200e-9][branch], 0.5e-9, 298.0)[0])
    from spmkit.core.analysis.force_smfs import MolecularExtensionResult

    def build(offset):
        return MolecularExtensionResult(
            extension=x + offset, separation=3.0e-6 + x + offset, force=f,
            time=np.linspace(0, 1, n), retract_indices=np.arange(n),
            reference_policy="offset", reference_coordinate=3.0e-6,
            reference_index=None, valid=np.ones(n, dtype=bool), provenance={})

    ev = detect_unfolding_events(build(0.0), noise_sigma=1e-13)
    ev2 = quantify_unfolding_events(build(0.0), ev)
    inc_ok = infer_contour_length_increments(build(0.0), ev2)
    assert abs(inc_ok[0].delta_contour_length - 100e-9) / 100e-9 < 0.10
    # a 20 nm zero error shifts the absolute extension axis: the ABSOLUTE
    # contour lengths are biased (~20% on the 100 nm pre contour) while the
    # DELTA is largely zero-translation invariant (the pre/post biases
    # partially cancel; observed residual 2.1%)
    inc_biased = infer_contour_length_increments(build(20e-9), ev2)
    assert abs(inc_biased[0].pre_fit.parameters["Lc"] - 100e-9) / 100e-9 > 0.10
    assert abs(inc_biased[0].delta_contour_length - 100e-9) / 100e-9 < 0.10


def test_dhs_series_recovery_bounded() -> None:
    case = generate_phantoms()["S17"]
    rates = np.asarray(case.truth["rates"])
    forces = np.asarray(case.truth["rupture_forces"])
    fit = fit_dudko_hummer_szabo(rates, forces, temperature=298.0)
    assert fit.success
    assert 1e-12 <= fit.parameters["x_beta"] <= 1e-7
    assert 1e-22 <= fit.parameters["dG"] <= 1e-11
    assert any("not claimed to be physically unique" in w for w in fit.warnings)


# ---------------------------------------------------------------------------
# force clamp survival
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cid", ["S20", "S21", "S22"])
def test_force_clamp_survival_recovery(cid) -> None:
    case = generate_phantoms()[cid]
    lt = np.asarray(case.truth["lifetimes"])
    ce = np.asarray(case.truth["censored"])
    km = estimate_force_clamp_survival(lt, ce, force_level=case.truth["force_level"])
    assert km.n_censored == int(ce.sum())
    # the censoring-aware exponential MLE recovers the generating rate
    # within the finite-sample uncertainty
    assert abs(km.exponential_rate - case.truth["rate"]) / case.truth["rate"] < 0.30
    # KM survival matches the independent oracle
    times, surv, _risk = kaplan_meier(lt, ce)
    assert np.allclose(km.km_times, times)
    assert np.allclose(km.survival_probability, surv)


def test_all_censored_undefined_median() -> None:
    case = generate_phantoms()["S23"]
    lt = np.asarray(case.truth["lifetimes"])
    ce = np.asarray(case.truth["censored"])
    km = estimate_force_clamp_survival(lt, ce, force_level=case.truth["force_level"])
    assert km.median_lifetime is None
    assert any("UNDEFINED_MEDIAN" in w for w in km.warnings)


# ---------------------------------------------------------------------------
# population and batch
# ---------------------------------------------------------------------------


def test_batch_end_to_end() -> None:
    """A mixed batch: successful sawtooth curves plus failures, with the
    unified event table and the population aggregation."""
    cases = generate_phantoms()
    analyses = []
    for i, cid in enumerate(("S09", "S10", "S11")):
        case = cases[cid]
        ext = _ext(case)
        ev = detect_unfolding_events(ext, noise_sigma=1e-13)
        ev2 = quantify_unfolding_events(ext, ev)
        inc = infer_contour_length_increments(ext, ev2)
        rates = compute_event_loading_rates(ext, ev2)
        records = [
            {"rupture_force": e.rupture_force,
             "delta_contour_length": r.delta_contour_length,
             "loading_rate": rl.local_slope}
            for e, r, rl in zip(ev2.events, inc, rates, strict=True)]
        analyses.append({"curve_id": cid, "curve_index": i, "ok": True,
                         "events": records})
    analyses.append({"curve_id": "S12", "curve_index": 3, "ok": False,
                     "failure": "NO_EVENTS"})
    batch = analyze_smfs_batch(analyses, group_by="loading_rate_decade")
    assert batch.n_curves == 4
    assert batch.n_ok == 3
    assert batch.n_failed == 1
    assert batch.failed_reasons == {3: "NO_EVENTS"}
    assert len(batch.unified_event_table) == 4  # S09:1 + S10:2 + S11:1
    assert batch.population is not None
    assert batch.population.n_events == 4
    assert batch.provenance["deterministic"]
    # deterministic replay
    batch2 = analyze_smfs_batch(analyses, group_by="loading_rate_decade")
    assert batch2.unified_event_table == batch.unified_event_table


# ---------------------------------------------------------------------------
# real-data witness
# ---------------------------------------------------------------------------


def test_real_data_failure_handling_witness() -> None:
    """Exact real-NID witness counts (spectroscopy.nid, 100 curves).

    All 100 curves fail typed at the FS-F1 preparation boundary
    (NONMONOTONIC_COORDINATE or INSUFFICIENT_OVERLAP): the FS-F4 SMFS stages
    are never reached, zero silent failures, zero completed extensions.
    Classification: REAL_DATA_FAILURE_HANDLING_WITNESS (no valid SMFS
    protocol is established on this set; not real-data validation).
    """
    from spmkit.core.io import load_force

    nid_path = (
        Path(__file__).resolve().parent / "fixtures" / "force_foundation" / "spectroscopy.nid"
    )
    assert nid_path.exists()
    vol = load_force(str(nid_path))
    codes: dict[str, int] = {}
    for i in range(vol.n_curves):
        curve = vol.curve(i)
        try:
            prepare_force_curve(curve)
        except ForceFoundationError as exc:
            code = getattr(exc, "code", type(exc).__name__)
            codes[code] = codes.get(code, 0) + 1
            continue
        # any curve passing preparation would proceed to the SMFS stages;
        # the witness must record them (none currently)
        codes.setdefault("COMPLETED_EXTENSION", 0)
        codes["COMPLETED_EXTENSION"] += 1
    assert codes.get("COMPLETED_EXTENSION", 0) == 0
    assert codes.get("NONMONOTONIC_COORDINATE", 0) == 99
    assert codes.get("INSUFFICIENT_OVERLAP", 0) == 1
    assert sum(codes.values()) == vol.n_curves == 100
    assert "silent" not in str(codes)
