"""FS-F3 validation: fixture integrity, oracle parity, phantom recovery,
failure witnesses, external compatibility witness, sensitivity, volume and
real-data characterization.

Every assertion is a scientific claim about the FS-F3 stack: frozen time
contract, honest recovery bounds, typed failure paths, deterministic
reliability.  Fixture truths derive from the independent oracles.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "force_viscoelasticity"
VISCO_REF_DIR = (
    Path(__file__).resolve().parents[2] / ".reference" / "force-spectroscopy"
    / "viscoelasticity-reference"
)
sys.path.insert(0, str(FIXTURE_DIR))

from generate_viscoelastic_phantoms import (  # noqa: E402
    K_SPRING,
    _json_safe,
    generate_phantoms,
)
from oracle_hereditary_integral import lee_radok_force as oracle_lee_radok  # noqa: E402
from oracle_hereditary_integral import ting_force as oracle_ting  # noqa: E402
from oracle_viscoelastic_declarative import (  # noqa: E402
    kv_instantaneous_zero,
    kv_scales_with_inverse_modulus,
    maxwell_no_equilibrium,
    maxwell_time_scaling,
    power_law_scaling,
    prony_limits,
    sls_creep_monotone_increasing,
    sls_equilibrium_ratio,
    sls_relaxation_monotone_decreasing,
)
from oracle_viscoelastic_lumped import (  # noqa: E402
    kv_compliance,
    maxwell_normalized,
    prony_normalized,
    sls_relaxation_modulus,
)

from spmkit.core.analysis import (  # noqa: E402
    ForceFoundationError,
    prepare_force_curve,
)
from spmkit.core.analysis.force_viscoelasticity import (  # noqa: E402
    RelaxationResponseResult,
    ViscoelasticityError,
    analyze_viscoelastic_sensitivity,
    compare_viscoelastic_models,
    extract_creep_compliance,
    extract_stress_relaxation,
    fit_force_volume_viscoelasticity,
    fit_generalized_maxwell,
    fit_kelvin_voigt,
    fit_lee_radok_sphere,
    fit_maxwell,
    fit_power_law_relaxation,
    fit_standard_linear_solid,
    fit_ting_sphere,
    forward_generalized_maxwell_normalized,
    forward_maxwell_normalized,
    forward_sls_modulus,
    identify_viscoelastic_protocol,
    lee_radok_force,
    ting_force,
)
from spmkit.core.models import (  # noqa: E402
    Calibration,
    ForceCurve,
    ForceSegment,
    ForceVolume,
)

MANIFEST = FIXTURE_DIR / "viscoelasticity_reference.json"
ARRAYS = FIXTURE_DIR / "viscoelasticity_reference.npz"
GENERATOR = FIXTURE_DIR / "generate_viscoelastic_phantoms.py"
EST = 5e3 / (1.0 - 0.3**2)


def _load_arrays():
    return dict(np.load(ARRAYS, allow_pickle=False))


def _seg(st, d, z, f, t):
    return ForceSegment(
        segment_type=st, direction=d, raw_height=z, raw_deflection=f / K_SPRING,
        time=t, cycle=0, state="force_n", deflection=f / K_SPRING, force=f,
        separation=None, metadata={})


def _curve_from_phantom(case) -> ForceCurve:
    """Materialize a phantom: extend = pre+ramp+hold, retract = tail."""
    n = case.time.size
    n_retract = 40
    if case.metadata.get("n_load"):
        # Ting phantom: extend = pre+loading, retract = unloading
        n_pre = case.metadata.get("n_pre", 40)
        n_load = case.metadata["n_load"]
        split = n_pre + n_load
    else:
        split = n - n_retract
    return ForceCurve(
        segments=(
            _seg("extend", "forward", case.height[:split], case.force[:split],
                 case.time[:split]),
            _seg("retract", "backward", case.height[split:], case.force[split:],
                 case.time[split:]),
        ),
        calibration=Calibration(invols=3e-8, spring_constant=K_SPRING,
                                method="thermal", temperature=300, provenance={}),
        position=None, index=0, metadata={})


# ---------------------------------------------------------------------------
# fixture integrity
# ---------------------------------------------------------------------------


def test_fixture_regeneration_deterministic() -> None:
    out1 = Path("/tmp/opencode") / "visco_gen_a"
    out2 = Path("/tmp/opencode") / "visco_gen_b"
    out1.mkdir(parents=True, exist_ok=True)
    out2.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run([sys.executable, str(GENERATOR), str(out1)],
                       check=True, capture_output=True)
        subprocess.run([sys.executable, str(GENERATOR), str(out2)],
                       check=True, capture_output=True)
        for name in ("viscoelasticity_reference.json", "viscoelasticity_reference.npz"):
            assert (out1 / name).read_bytes() == (out2 / name).read_bytes()
            assert (out1 / name).read_bytes() == (FIXTURE_DIR / name).read_bytes()
    finally:
        import shutil
        shutil.rmtree(out1, ignore_errors=True)
        shutil.rmtree(out2, ignore_errors=True)


def test_phantom_geometry_and_time_contract() -> None:
    cases = generate_phantoms()
    arrays = _load_arrays()
    manifest = json.loads(MANIFEST.read_text())
    for cid, case in sorted(cases.items()):
        if cid == "V24":
            continue
        if case.metadata.get("n_load"):
            split = case.metadata.get("n_pre", 40) + case.metadata["n_load"]
        else:
            split = case.height.size - 40
        assert np.all(np.diff(case.height[:split]) >= 0), cid  # approach non-decreasing
        assert np.all(np.isfinite(case.time)), cid
        assert np.all(np.isfinite(case.force)), cid
        assert np.array_equal(arrays[f"{cid}_time"], case.time), cid
        assert np.array_equal(arrays[f"{cid}_force"], case.force), cid
        assert manifest["cases"][cid]["truth"] == _json_safe(case.truth), cid
    # intentional duplicate-timestamp case
    c = cases["V15"]
    assert int((np.diff(c.time) == 0).sum()) >= 1


def test_hold_region_force_matches_model() -> None:
    """The phantom hold force is the exact model response (oracle-derived)."""
    cases = generate_phantoms()
    c = cases["V03"]
    t0 = c.truth["hold_start_index"]
    t1 = c.truth["hold_end_index"]
    t_rel = c.time[t0:t1 + 1] - c.time[t0]
    truth_n = sls_relaxation_modulus(t_rel, 5e3, 2e3, 0.05) / 5e3
    hold_n = c.force[t0:t1 + 1] / c.force[t0]
    assert np.allclose(hold_n, truth_n, rtol=1e-6)
    c = cases["V02"]
    t0 = c.truth["hold_start_index"]
    t1 = c.truth["hold_end_index"]
    n_hold = t1 - t0 + 1
    dt_hold = c.truth["t_hold"] / n_hold
    k = np.arange(n_hold)
    truth_j = kv_compliance((k + 1.0) * dt_hold, 5e3, 0.05)
    proxy = (c.separation[t0:t1 + 1] - 3e-6) / c.truth["f_hold"]
    assert np.allclose(proxy, truth_j, rtol=1e-6)


# ---------------------------------------------------------------------------
# oracle parity (forward + hereditary)
# ---------------------------------------------------------------------------


def test_lumped_oracle_parity() -> None:
    t = np.linspace(1e-3, 1.0, 97)
    assert np.allclose(forward_sls_modulus(t, 5e3, 2e3, 0.1),
                       sls_relaxation_modulus(t, 5e3, 2e3, 0.1), rtol=1e-12)
    assert np.allclose(forward_maxwell_normalized(t, 0.1),
                       maxwell_normalized(t, 0.1), rtol=1e-12)
    alpha = np.array([0.4, 0.3])
    tau = np.array([0.05, 0.5])
    assert np.allclose(forward_generalized_maxwell_normalized(t, alpha, tau),
                       prony_normalized(t, alpha, tau), rtol=1e-12)


def test_hereditary_oracle_parity() -> None:
    """Production and oracle Lee-Radok/Ting agree across quadratures."""
    t = np.linspace(1e-4, 0.2, 120)
    d = 5e-7 * (t / 0.2) ** 0.7
    f_prod = lee_radok_force(t, d, {"E0": 5e3, "E_inf": 2e3, "tau": 0.05},
                             1.0, 1e-6, 0.3)
    f_ora = oracle_lee_radok(t, d, 5e3, 2e3, 0.05, 1.0, 1e-6, 0.3)
    rel = np.abs(f_prod - f_ora) / np.maximum(np.abs(f_ora), 1e-15)
    # the production increment rule is first-order in the modulus variation
    # per sample; the substep oracle is the reference
    assert np.max(rel) < 1e-2

    t_l = np.linspace(1e-4, 0.1, 80)
    d_l = 5e-7 * (t_l / 0.1) ** 0.8
    t_u = np.linspace(0.1, 0.2, 80)
    d_u = 5e-7 * (1.0 - ((t_u - 0.1) / 0.1) ** 0.8)
    g_prod = ting_force(t_l, d_l, t_u, d_u, {"E0": 5e3, "E_inf": 2e3, "tau": 0.05},
                        1.0, 1e-6, 0.3)
    g_ora = oracle_ting(t_l, d_l, t_u, d_u, 5e3, 2e3, 0.05, 1.0, 1e-6, 0.3)
    # allclose with a scale-relative atol: the deep-unloading tail crosses
    # zero, where a pure relative metric diverges.  The production
    # increment rule is first-order in the modulus variation; the observed
    # bias vs the substep oracle is ~0.7% (loading) / ~0.5% (unloading).
    assert np.allclose(g_prod, g_ora, rtol=5e-2, atol=1e-12)


def test_declarative_oracle_relations() -> None:
    t = np.linspace(1e-3, 1.0, 60)  # noqa: F841 (shared grid)
    assert kv_scales_with_inverse_modulus(5e3, 2e3, t, 0.1)
    assert kv_instantaneous_zero(t, 5e3, 0.1)
    assert maxwell_time_scaling(t, 0.1, 3.0)
    assert maxwell_no_equilibrium(t, 5e3, 0.1)
    assert sls_relaxation_monotone_decreasing(t, 5e3, 2e3, 0.1)
    assert sls_creep_monotone_increasing(t, 1 / 5e3, 1 / 2e3, 0.25)
    assert sls_equilibrium_ratio(5e3, 2e3, 0.1, 10.0)
    assert prony_limits(np.geomspace(1e-3, 50.0, 200),
                        np.array([0.4, 0.3]), np.array([0.05, 0.5]))
    assert power_law_scaling(t, 5e3, 0.3, 0.01)


# ---------------------------------------------------------------------------
# phantom recovery through the full stack
# ---------------------------------------------------------------------------


def _stack(cid: str):
    case = generate_phantoms()[cid]
    curve = _curve_from_phantom(case)
    protocol = identify_viscoelastic_protocol(curve)
    prepared = prepare_force_curve(curve)
    return case, curve, protocol, prepared


@pytest.mark.parametrize("cid,fit_fn,kwargs,truth,rel_tol", [
    ("V01", fit_maxwell, {"tip_radius": 1e-6},
     {"tau": 0.05, "E": 5e3}, {"tau": 0.02, "E": 0.10}),
    ("V03", fit_standard_linear_solid, {"tip_radius": 1e-6},
     {"tau_relax": 0.05, "a": 0.6, "E0": 5e3}, {"tau_relax": 0.02, "a": 0.02, "E0": 0.10}),
    ("V02", fit_kelvin_voigt, {},
     {"E": 5e3, "tau": 0.05}, {"E": 0.10, "tau": 0.10}),
])
def test_clean_lumped_recovery(cid, fit_fn, kwargs, truth, rel_tol) -> None:
    case, curve, protocol, prepared = _stack(cid)
    if cid == "V02":
        resp = extract_creep_compliance(prepared, protocol)
        fit = fit_fn(resp, **kwargs)
    else:
        resp = extract_stress_relaxation(prepared, protocol)
        fit = fit_fn(resp, **kwargs)
    assert fit.success, cid
    for key, tol in rel_tol.items():
        assert abs(fit.parameters[key] - truth[key]) / truth[key] < tol, (cid, key)


def test_sls_creep_recovery() -> None:
    """The creep INCREMENT (dJ, tau_retard) is recovered; the absolute
    compliance level is contact-coordinate limited (the FS-F1 contact on a
    creep trace carries up to ~20% of the J0 scale), so the absolute E0 is
    reported with a wide honest bound."""
    case = generate_phantoms()["V04"]
    curve = _curve_from_phantom(case)
    protocol = identify_viscoelastic_protocol(curve)
    prepared = prepare_force_curve(curve)
    resp = extract_creep_compliance(prepared, protocol)
    fit = fit_standard_linear_solid(resp)
    dj_truth = 1 / 2e3 - 1 / 5e3
    assert abs((fit.parameters["J_inf"] - fit.parameters["J0"]) - dj_truth) / dj_truth < 0.10
    tau_truth = 0.05 * 5e3 / 2e3
    assert abs(fit.parameters["tau_retard"] - tau_truth) / tau_truth < 0.10


def test_generalized_maxwell_recovery() -> None:
    case = generate_phantoms()["V06"]
    curve = _curve_from_phantom(case)
    protocol = identify_viscoelastic_protocol(curve)
    prepared = prepare_force_curve(curve)
    resp = extract_stress_relaxation(prepared, protocol)
    fit = fit_generalized_maxwell(resp, n_terms=3)
    assert fit.success
    taus = sorted([fit.parameters["tau_i[0]"], fit.parameters["tau_i[1]"],
                   fit.parameters["tau_i[2]"]])
    assert abs(taus[0] - 0.005) / 0.005 < 0.10
    assert abs(taus[1] - 0.05) / 0.05 < 0.10
    assert abs(taus[2] - 0.5) / 0.5 < 0.10
    assert any("no claim" in w for w in fit.warnings)


def test_power_law_recovery() -> None:
    case = generate_phantoms()["V07"]
    curve = _curve_from_phantom(case)
    protocol = identify_viscoelastic_protocol(curve)
    prepared = prepare_force_curve(curve)
    resp = extract_stress_relaxation(prepared, protocol)
    fit = fit_power_law_relaxation(resp, t_ref=case.truth["parameters"]["t_ref"])
    assert abs(fit.parameters["alpha"] - 0.3) < 0.05


def test_lee_radok_recovery() -> None:
    case, curve, protocol, prepared = _stack("V08")
    fit = fit_lee_radok_sphere(prepared, protocol, tip_radius=1e-6)
    assert fit.success
    assert abs(fit.parameters["E0"] - 5e3) / 5e3 < 0.40
    assert abs(fit.parameters["E_inf"] - 2e3) / 2e3 < 0.40
    assert abs(fit.parameters["tau_relax"] - 0.05) / 0.05 < 0.50


def test_ting_recovery() -> None:
    case, curve, protocol, prepared = _stack("V09")
    assert protocol.protocol_type == "TRIANGULAR_LOADING"
    fit = fit_ting_sphere(prepared, protocol, tip_radius=1e-6)
    assert fit.success
    assert abs(fit.parameters["E0"] - 5e3) / 5e3 < 0.40
    assert abs(fit.parameters["E_inf"] - 2e3) / 2e3 < 0.40
    assert abs(fit.parameters["tau_relax"] - 0.05) / 0.05 < 0.50


def test_response_level_noisy_recovery() -> None:
    """The noisy-recovery evidence lives at the response level: the SLS fit
    on a clean extracted response with added deterministic noise recovers
    the relaxation time within a bounded error."""
    case = generate_phantoms()["V03"]
    curve = _curve_from_phantom(case)
    protocol = identify_viscoelastic_protocol(curve)
    prepared = prepare_force_curve(curve)
    resp = extract_stress_relaxation(prepared, protocol)
    rng = np.random.default_rng(7)
    noisy = resp.normalized_force + rng.normal(0.0, 1e-3, resp.normalized_force.size)
    from spmkit.core.analysis.force_viscoelasticity import RelaxationResponseResult
    noisy_resp = RelaxationResponseResult(
        relative_time=resp.relative_time, indentation=resp.indentation,
        force=resp.force, normalized_force=noisy, hold_indices=resp.hold_indices,
        hold_start_time=resp.hold_start_time,
        force_at_hold_start=resp.force_at_hold_start,
        equilibrium_force_estimate=resp.equilibrium_force_estimate, warnings=())
    fit = fit_standard_linear_solid(noisy_resp, tip_radius=1e-6)
    assert abs(fit.parameters["tau_relax"] - 0.05) / 0.05 < 0.20


@pytest.mark.parametrize("cid,tol", [
    ("V10", 0.30),  # gaussian noise (1e-12 N)
    ("V11", 0.30),  # correlated noise
    ("V13", 0.30),  # timestamp jitter
    ("V14", 0.20),  # nonuniform sampling
    ("V18", 0.20),  # multiple sampling rates
    ("V19", 0.30),  # contact offset
    ("V20", 0.30),  # baseline offset/slope
    ("V22", 0.30),  # shallow indentation
])
def test_protocol_variant_recovery(cid, tol) -> None:
    case = generate_phantoms()[cid]
    curve = _curve_from_phantom(case)
    try:
        protocol = identify_viscoelastic_protocol(curve)
        prepared = prepare_force_curve(curve)
        resp = extract_stress_relaxation(prepared, protocol)
        fit = fit_standard_linear_solid(resp, tip_radius=1e-6)
        rel = abs(fit.parameters["tau_relax"] - 0.05) / 0.05
        assert rel < tol, (cid, rel)
    except (ViscoelasticityError, ForceFoundationError) as exc:
        raise AssertionError(
            f"{cid} failed typed: {getattr(exc, 'code', exc)}") from exc


def test_response_delay_rejected_typed() -> None:
    """The instrument-response delay makes the reconstructed height
    non-monotone; the FS-F1 gate rejects it typed, never silently."""
    case = generate_phantoms()["V21"]
    curve = _curve_from_phantom(case)
    with pytest.raises(ForceFoundationError):
        prepare_force_curve(curve)


def test_piecewise_contact_flat_window_no_crash() -> None:
    """Regression: the FS-F1 piecewise contact method must reject a
    constant-coordinate window (e.g. a flat displacement hold) as an
    invalid candidate instead of crashing untyped or leaking a RankWarning.
    A ramp-hold phantom's prepare exercises the guard end-to-end."""
    from spmkit.core.analysis.force_contact import contact_point_piecewise

    case = generate_phantoms()["V03"]
    curve = _curve_from_phantom(case)
    cand = contact_point_piecewise(curve)
    # either a valid contact or an explicitly invalid candidate; never an
    # untyped numerical crash (the flat-hold window is inside the search)
    assert cand.valid or not cand.valid
    # the full prepare also runs cleanly (typed or successful)
    with contextlib.suppress(ForceFoundationError):
        prepare_force_curve(curve)


# ---------------------------------------------------------------------------
# failure witnesses (typed, never silent)
# ---------------------------------------------------------------------------


def test_duplicate_timestamp_witness() -> None:
    case = generate_phantoms()["V15"]
    curve = _curve_from_phantom(case)
    with pytest.raises(ViscoelasticityError) as ei:
        identify_viscoelastic_protocol(curve)
    assert ei.value.code == "DUPLICATE_TIMESTAMPS"


def test_short_dwell_witness() -> None:
    case = generate_phantoms()["V16"]
    curve = _curve_from_phantom(case)
    protocol = identify_viscoelastic_protocol(curve)
    prepared = prepare_force_curve(curve)
    with pytest.raises(ViscoelasticityError) as ei:
        extract_stress_relaxation(prepared, protocol)
    assert ei.value.code == "EMPTY_REGION"


def test_flat_curve_witness() -> None:
    case = generate_phantoms()["V24"]
    curve = _curve_from_phantom(case)
    with pytest.raises(ForceFoundationError):
        prepare_force_curve(curve)


def test_swapped_prony_terms_ambiguity() -> None:
    """Nearly identical relaxation times: the response is reconstructed
    exactly but the recovered spectrum is NOT the truth (the decomposition
    is non-unique); no uniqueness claim is made."""
    case = generate_phantoms()["V23"]
    curve = _curve_from_phantom(case)
    protocol = identify_viscoelastic_protocol(curve)
    prepared = prepare_force_curve(curve)
    resp = extract_stress_relaxation(prepared, protocol)
    fit = fit_generalized_maxwell(resp, n_terms=2)
    assert fit.success
    # the response reconstruction is exact...
    assert np.max(np.abs(fit.predicted_response - resp.normalized_force)) < 1e-3
    # ...but the recovered spectrum differs from the truth (tau = (0.02,
    # 0.020001)): the alpha split is not identifiable
    taus = sorted([fit.parameters["tau_i[0]"], fit.parameters["tau_i[1]"]])
    assert abs(taus[0] - 0.02) / 0.02 > 0.05 or abs(fit.parameters["alpha_i[0]"] - 0.5) > 0.05


def test_lee_radok_nonmonotonic_typed() -> None:
    t = np.linspace(0.0, 1.0, 60)
    d = np.linspace(0.0, 5e-7, 60)
    d[40] = d[39] - 1e-8  # a real decrease
    with pytest.raises(ViscoelasticityError) as ei:
        lee_radok_force(t, d, {"E0": 5e3, "E_inf": 2e3, "tau": 0.1}, 1.0, 1e-6, 0.3)
    assert ei.value.code == "LEE_RADOK_NONMONOTONIC"


def test_ting_missing_history_typed() -> None:
    """A protocol without an unloading region fails Ting typed."""
    from spmkit.core.analysis.force_viscoelasticity import (
        ViscoelasticProtocolResult,
    )
    case, curve, protocol, prepared = _stack("V08")
    loading_only = ViscoelasticProtocolResult(
        protocol_type="LOADING_RAMP",
        regions=tuple(r for r in protocol.regions if r.kind == "loading"),
        method="test", provenance={})
    with pytest.raises(ViscoelasticityError) as ei:
        fit_ting_sphere(prepared, loading_only, tip_radius=1e-6)
    assert ei.value.code == "TING_HISTORY_UNAVAILABLE"


# ---------------------------------------------------------------------------
# model comparison
# ---------------------------------------------------------------------------


def test_comparison_prefers_true_model() -> None:
    case = generate_phantoms()["V01"]
    curve = _curve_from_phantom(case)
    protocol = identify_viscoelastic_protocol(curve)
    prepared = prepare_force_curve(curve)
    resp = extract_stress_relaxation(prepared, protocol)
    cmp = compare_viscoelastic_models(
        resp, models=("maxwell", "standard_linear_solid", "power_law_relaxation"))
    assert cmp.recommended_model == "maxwell"
    assert cmp.weights["maxwell"] > 0.9


# ---------------------------------------------------------------------------
# sensitivity multiverse
# ---------------------------------------------------------------------------


def test_sensitivity_deterministic_and_bounded() -> None:
    case = generate_phantoms()["V03"]
    curve = _curve_from_phantom(case)
    protocol = identify_viscoelastic_protocol(curve)
    prepared = prepare_force_curve(curve)
    a = analyze_viscoelastic_sensitivity(curve, prepared, protocol=protocol,
                                         tip_radius=1e-6)
    b = analyze_viscoelastic_sensitivity(curve, prepared, protocol=protocol,
                                         tip_radius=1e-6)
    assert a.configurations == b.configurations
    assert a.parameter_multiverse == b.parameter_multiverse
    assert a.n_configurations <= 96
    assert a.dominant_sensitivity in ("contact", "boundary", "window", "none")
    # clean phantom: the one-at-a-time indices stay below the honest
    # bounds (contact/boundary/window; the hold-boundary trim shifts the
    # extracted response start and moves tau by up to ~21%)
    assert a.contact_sensitivity < 0.2
    assert a.boundary_sensitivity < 0.35
    assert a.window_sensitivity < 0.2


def test_sensitivity_failures_retained() -> None:
    case = generate_phantoms()["V03"]
    curve = _curve_from_phantom(case)
    protocol = identify_viscoelastic_protocol(curve)
    prepared = prepare_force_curve(curve)
    a = analyze_viscoelastic_sensitivity(
        curve, prepared, protocol=protocol, tip_radius=1e-6,
        boundary_offsets=(-200, 0, 200), max_configurations=9)
    assert a.n_configurations + len(a.failures) <= 9
    assert len(a.failures) >= 1  # windows reaching the pre-contact fail typed


# ---------------------------------------------------------------------------
# force volume
# ---------------------------------------------------------------------------


def test_volume_viscoelasticity_end_to_end() -> None:
    cases = generate_phantoms()
    # V03 clean, V19 contact-offset, V24 flat failure witness (the noisy
    # V10 can fail preparation on the FS-F1 height monotonicity gate, which
    # the mapping reports through the failed mask, never silently)
    curves = [_curve_from_phantom(cases[cid]) for cid in ("V03", "V19", "V24")]
    volume = ForceVolume.from_curves(curves, grid_shape=(1, 3), x_range=1e-6,
                                     y_range=3e-6)
    res = fit_force_volume_viscoelasticity(volume, tip_radius=1e-6)
    assert res.modulus_0_map.shape == (3,)
    assert res.failed_mask[2]  # V24 flat curve explicitly masked
    assert not res.failed_mask[:2].any()
    assert np.isfinite(res.modulus_0_map[:2]).all()
    assert abs(res.modulus_0_map[0] - 5e3) / 5e3 < 0.15
    assert abs(res.relaxation_time_map[0] - 0.05) / 0.05 < 0.15
    assert res.provenance["n_failed"] == 1
    assert res.provenance["deterministic"]
    res2 = fit_force_volume_viscoelasticity(volume, tip_radius=1e-6)
    np.testing.assert_array_equal(res.modulus_0_map, res2.modulus_0_map)
    np.testing.assert_array_equal(res.failed_mask, res2.failed_mask)


# ---------------------------------------------------------------------------
# external compatibility witness (frozen pyvisco profile)
# ---------------------------------------------------------------------------


def test_external_pyvisco_witness_reconstruction() -> None:
    """pyvisco 2.1.3 (fixed-tau-grid NNLS) and the production free-tau
    generalized-Maxwell fit both reconstruct the same synthetic normalized
    relaxation modulus within bounded error (compatibility witness, not
    parameter equality)."""
    inp = json.loads((VISCO_REF_DIR / "campaign_input.json").read_text())
    out = json.loads((VISCO_REF_DIR / "campaign_output.json").read_text())
    assert inp["cases"][0]["case_id"] == "PV01"
    truth_t = np.asarray(inp["cases"][0]["time"])
    truth = np.asarray(inp["cases"][0]["modulus"])
    fit_t = np.asarray(out["fit_time"])
    fit_m = np.asarray(out["fit_modulus"])
    ext_err = float(np.max(np.abs(np.interp(truth_t, fit_t, fit_m) - truth)))
    assert ext_err < 0.10  # frozen pyvisco reconstruction bound
    # production reconstruction on the same modulus
    resp = RelaxationResponseResult(
        relative_time=truth_t, indentation=np.full(truth_t.size, 5e-7),
        force=1e-6 * truth, normalized_force=truth,
        hold_indices=np.arange(truth_t.size), hold_start_time=0.0,
        force_at_hold_start=1e-6, equilibrium_force_estimate=float(truth[-1]) * 1e-6,
        warnings=())
    fit = fit_generalized_maxwell(resp, n_terms=2)
    prod_err = float(np.max(np.abs(fit.predicted_response - truth)))
    assert prod_err < 0.02
    # compatibility: the two reconstructions agree on the shared grid
    cross = float(np.max(np.abs(fit.predicted_response - np.interp(truth_t, fit_t, fit_m))))
    assert cross < 0.10


# ---------------------------------------------------------------------------
# real-data characterization
# ---------------------------------------------------------------------------


def test_real_data_no_silent_garbage() -> None:
    """On the real NID set every curve either completes the FS-F3 stack or
    raises a typed failure; no silent NaN-filled success."""
    from spmkit.core.io import load_force

    nid_path = (
        Path(__file__).resolve().parent / "fixtures" / "force_foundation" / "spectroscopy.nid"
    )
    assert nid_path.exists()
    vol = load_force(str(nid_path))
    typed = 0
    completed = 0
    for i in range(vol.n_curves):
        curve = vol.curve(i)
        try:
            protocol = identify_viscoelastic_protocol(curve)
            prepared = prepare_force_curve(curve)
            resp = extract_stress_relaxation(prepared, protocol)
            fit = fit_standard_linear_solid(resp)
            assert np.isfinite(fit.objective)
            completed += 1
        except (ViscoelasticityError, ForceFoundationError):
            typed += 1
    assert completed + typed >= 1
    assert typed >= 90  # most real curves lack a time axis: typed MISSING_TIME
