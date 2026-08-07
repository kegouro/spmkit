"""FS-F3 core tests: temporal contract, equations, failures, determinism.

No fixtures loaded.
"""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis.force_viscoelasticity import (
    CreepResponseResult,
    RelaxationResponseResult,
    ViscoelasticityError,
    compare_viscoelastic_models,
    fit_generalized_maxwell,
    fit_kelvin_voigt,
    fit_maxwell,
    fit_power_law_relaxation,
    fit_standard_linear_solid,
    forward_generalized_maxwell_modulus,
    forward_generalized_maxwell_normalized,
    forward_kelvin_voigt_compliance,
    forward_maxwell_modulus,
    forward_power_law_modulus,
    forward_sls_modulus,
    identify_viscoelastic_protocol,
    lee_radok_force,
    reduced_modulus,
    sls_creep_to_relaxation,
    sls_relaxation_to_creep,
    spherical_coefficient,
    ting_force,
    validate_time_axis,
)
from spmkit.core.models import Calibration, ForceCurve, ForceSegment

T = np.linspace(1e-3, 1.0, 100)


def _relaxation_response(tau: float = 0.1, n: int = 120, noise: float = 0.0):
    rng = np.random.default_rng(0)
    t = np.linspace(0.0, 1.0, n)
    nrm = np.exp(-t / tau)
    if noise:
        nrm = nrm + rng.normal(0.0, noise, n)
    return RelaxationResponseResult(
        relative_time=t, indentation=np.full(n, 5e-7), force=1e-6 * nrm,
        normalized_force=nrm, hold_indices=np.arange(n), hold_start_time=0.0,
        force_at_hold_start=1e-6, equilibrium_force_estimate=float(nrm[-1]) * 1e-6,
        warnings=())


def _creep_response(modulus: float = 5e3, tau: float = 0.1, n: int = 120):
    t = np.linspace(0.0, 1.0, n)
    j_inc = (1.0 / modulus) * (1.0 - np.exp(-t / tau))
    return CreepResponseResult(
        relative_time=t, force=np.full(n, 1e-6), indentation=1e-6 * j_inc,
        compliance_proxy=j_inc, hold_indices=np.arange(n), hold_start_time=0.0,
        force_hold_value=1e-6, indentation_at_hold_start=0.0, warnings=())


# ---------------------------------------------------------------------------
# temporal contract
# ---------------------------------------------------------------------------


def test_validate_time_axis_strict() -> None:
    t = np.array([0.0, 1.0, 2.0])
    np.testing.assert_array_equal(validate_time_axis(t), t)
    with pytest.raises(ViscoelasticityError) as ei:
        validate_time_axis(np.array([0.0, 1.0, 1.0]))
    assert ei.value.code == "DUPLICATE_TIMESTAMPS"
    with pytest.raises(ViscoelasticityError) as ei:
        validate_time_axis(np.array([0.0, 2.0, 1.0]))
    assert ei.value.code == "NONMONOTONIC_TIME"
    with pytest.raises(ViscoelasticityError):
        validate_time_axis(np.array([0.0, np.nan, 2.0]))


def test_seconds_vs_milliseconds_scale_invariance() -> None:
    """A correct implementation is invariant under a uniform time scale."""
    t_s = np.linspace(0.0, 1.0, 60)
    t_ms = t_s * 1e-3
    n_s = np.exp(-t_s / 0.1)
    n_ms = np.exp(-t_ms / 0.1e-3)
    assert np.allclose(n_s, n_ms)


# ---------------------------------------------------------------------------
# forward equations
# ---------------------------------------------------------------------------


def test_forward_equations_limits() -> None:
    # Kelvin-Voigt: J(0) = 0, J(inf) = 1/E
    j = forward_kelvin_voigt_compliance(T, 5e3, 0.1)
    assert abs(float(forward_kelvin_voigt_compliance(np.array([0.0]), 5e3, 0.1)[0])) < 1e-12
    assert abs(j[-1] - (1 / 5e3) * (1 - np.exp(-T[-1] / 0.1))) < 1e-15
    # Maxwell: E(0) = E, decays to zero
    m = forward_maxwell_modulus(T, 5e3, 0.1)
    assert abs(float(forward_maxwell_modulus(np.array([0.0]), 5e3, 0.1)[0]) - 5e3) < 1e-9
    assert m[-1] < 5e3 * np.exp(-5.0)  # decayed by at least e^-5 at t/tau = 10
    # SLS: E(inf) reached
    s = forward_sls_modulus(T, 5e3, 2e3, 0.1)
    assert abs(float(forward_sls_modulus(np.array([0.0]), 5e3, 2e3, 0.1)[0]) - 5e3) < 1e-9
    assert abs(s[-1] - (2e3 + 3e3 * np.exp(-T[-1] / 0.1))) < 1e-15
    # power law: self-similar
    p = forward_power_law_modulus(T, 5e3, 0.3, 0.01)
    p2 = forward_power_law_modulus(2 * T, 5e3, 0.3, 0.01)
    assert np.allclose(p2 / p, 2.0 ** (-0.3), rtol=1e-12)


def test_sls_conversions_roundtrip() -> None:
    j0, j_inf, tau_ret = sls_relaxation_to_creep(5e3, 2e3, 0.1)
    assert np.isclose(j0, 1 / 5e3) and np.isclose(j_inf, 1 / 2e3)
    e0, e_inf, tau_rel = sls_creep_to_relaxation(j0, j_inf, tau_ret)
    assert np.isclose(e0, 5e3, rtol=1e-12)
    assert np.isclose(e_inf, 2e3, rtol=1e-12)
    assert np.isclose(tau_rel, 0.1, rtol=1e-12)


def test_prony_duplicate_tau_rejected() -> None:
    with pytest.raises(ViscoelasticityError) as ei:
        forward_generalized_maxwell_modulus(
            T, 2e3, np.array([[1e3, 0.01], [1e3, 0.01]]))
    assert ei.value.code == "PRONY_DUPLICATE_TAU"
    with pytest.raises(ViscoelasticityError):
        forward_generalized_maxwell_normalized(T, np.array([0.5, 0.5]),
                                               np.array([0.01, 0.01]))


def test_power_law_singularity_excluded() -> None:
    with pytest.raises(ViscoelasticityError) as ei:
        forward_power_law_modulus(np.array([0.0, 1e-3]), 5e3, 0.3, 0.01)
    assert ei.value.code == "INVALID_MODEL_PARAMETER"
    with pytest.raises(ViscoelasticityError):
        forward_power_law_modulus(T, 5e3, 1.5, 0.01)


def test_lee_radok_rejects_nonmonotonic() -> None:
    t = np.linspace(0.0, 1.0, 50)
    d = np.linspace(0.0, 5e-7, 50)
    d[30] = d[29] - 1e-8  # a decrease
    with pytest.raises(ViscoelasticityError) as ei:
        lee_radok_force(t, d, {"E0": 5e3, "E_inf": 2e3, "tau": 0.1}, 1.0, 1e-6, 0.3)
    assert ei.value.code == "LEE_RADOK_NONMONOTONIC"


def test_ting_requires_history() -> None:
    t_l = np.linspace(0.0, 1.0, 50)
    d_l = np.linspace(0.0, 5e-7, 50)
    t_u = np.linspace(1.1, 2.0, 50)
    d_u = np.linspace(5e-7, 0.0, 50)
    d_u[10] = 6e-7  # exceeds the loading maximum
    with pytest.raises(ViscoelasticityError) as ei:
        ting_force(t_l, d_l, t_u, d_u, {"E0": 5e3, "E_inf": 2e3, "tau": 0.1},
                   1.0, 1e-6, 0.3)
    assert ei.value.code == "TING_HISTORY_UNAVAILABLE"


def test_lee_radok_elastic_limit() -> None:
    """With a non-relaxing modulus (E_inf = E0) Lee-Radok reduces to the
    elastic hertz loading F = c delta^1.5."""
    t = np.linspace(0.0, 1.0, 200)
    d = 5e-7 * (t / 1.0) ** 0.7
    f = lee_radok_force(t, d, {"E0": 5e3, "E_inf": 5e3, "tau": 1e9}, 1.0, 1e-6, 0.3)
    c = spherical_coefficient(5e3, 1e-6, 0.3)
    ref = c * d ** 1.5
    assert np.allclose(f, ref, rtol=1e-6)


def test_reduced_modulus_convention() -> None:
    assert np.isclose(reduced_modulus(5e3, 0.3), 5e3 / (1 - 0.3**2))


# ---------------------------------------------------------------------------
# protocol identification
# ---------------------------------------------------------------------------


def _ramp_hold_curve(time: np.ndarray, height: np.ndarray, force: np.ndarray,
                     k: float = 10.0) -> ForceCurve:
    def seg(st, d, z, f, t):
        return ForceSegment(segment_type=st, direction=d, raw_height=z,
                            raw_deflection=f / k, time=t, cycle=0, state="force_n",
                            deflection=f / k, force=f, separation=None, metadata={})

    n = time.size
    n_ext = int(n * 0.85)
    return ForceCurve(
        segments=(seg("extend", "forward", height[:n_ext], force[:n_ext], time[:n_ext]),
                  seg("retract", "backward", height[n_ext:], force[n_ext:], time[n_ext:])),
        calibration=Calibration(invols=3e-8, spring_constant=k, method="thermal",
                                temperature=300, provenance={}),
        position=None, index=0, metadata={})


def test_protocol_ramp_hold_classification() -> None:
    """A ramp-hold curve is STRESS_RELAXATION (decaying hold force)."""
    n_ramp, n_hold, n_pre, n_ret = 40, 120, 20, 20  # noqa: F841 (sizes)
    dt = 1e-3
    t = np.concatenate([
        np.linspace(-n_pre * dt, -dt, n_pre),
        np.linspace(0.0, 0.04, n_ramp),
        0.04 + np.linspace(dt, 0.12, n_hold),
        np.linspace(0.161, 0.2, n_ret)])
    h = np.concatenate([
        np.linspace(1e-6, 3e-6, n_pre),
        np.linspace(3e-6, 3.5e-6, n_ramp),
        np.full(n_hold, 3.5e-6),
        np.linspace(3.5e-6, 1e-6, n_ret)])
    f0 = 1e-6
    f = np.concatenate([
        np.zeros(n_pre),
        f0 * np.linspace(0.0, 1.0, n_ramp),
        f0 * np.exp(-np.linspace(0.0, 0.12, n_hold) / 0.05),
        np.linspace(f0 * np.exp(-0.12 / 0.05), 0.0, n_ret)])
    curve = _ramp_hold_curve(t, h, f)
    proto = identify_viscoelastic_protocol(curve)
    assert proto.protocol_type == "STRESS_RELAXATION"
    assert not proto.ambiguity


def test_protocol_trusted_label_precedence() -> None:
    t = np.linspace(0.0, 1.0, 100)
    h = np.linspace(1e-6, 3e-6, 100)
    f = np.linspace(0.0, 1e-6, 100)
    curve = _ramp_hold_curve(t, h, f)
    curve.metadata["protocol"] = "CREEP"
    proto = identify_viscoelastic_protocol(curve)
    assert proto.protocol_type == "CREEP"
    assert proto.trusted_label == "protocol"


def test_protocol_missing_time_fails_typed() -> None:
    h = np.linspace(1e-6, 3e-6, 100)
    f = np.linspace(0.0, 1e-6, 100)
    curve = ForceCurve(
        segments=(
            ForceSegment(segment_type="extend", direction="forward", raw_height=h,
                         raw_deflection=f / 10.0, time=None, cycle=0, state="force_n",
                         deflection=f / 10.0, force=f, separation=None, metadata={}),
            ForceSegment(segment_type="retract", direction="backward", raw_height=h[::-1],
                         raw_deflection=(f / 10.0)[::-1], time=None, cycle=0,
                         state="force_n", deflection=(f / 10.0)[::-1], force=f[::-1],
                         separation=None, metadata={})),
        calibration=Calibration(invols=3e-8, spring_constant=10.0, method="thermal",
                                temperature=300, provenance={}),
        position=None, index=0, metadata={})
    with pytest.raises(ViscoelasticityError) as ei:
        identify_viscoelastic_protocol(curve)
    assert ei.value.code == "MISSING_TIME"
    # explicit reconstructed clock is allowed
    proto = identify_viscoelastic_protocol(curve, assume_uniform_rate=1e-3)
    assert proto.protocol_type in ("LOADING_RAMP", "TRIANGULAR_LOADING",
                                   "INSUFFICIENT_PROTOCOL")


def test_protocol_duplicate_time_fails_typed() -> None:
    t = np.linspace(0.0, 1.0, 100)
    t[50] = t[49]
    h = np.linspace(1e-6, 3e-6, 100)
    f = np.linspace(0.0, 1e-6, 100)
    curve = _ramp_hold_curve(t, h, f)
    with pytest.raises(ViscoelasticityError) as ei:
        identify_viscoelastic_protocol(curve)
    assert ei.value.code == "DUPLICATE_TIMESTAMPS"


# ---------------------------------------------------------------------------
# lumped fits
# ---------------------------------------------------------------------------


def test_fit_maxwell_clean_recovery() -> None:
    resp = _relaxation_response(tau=0.1)
    fit = fit_maxwell(resp, tip_radius=1e-6)
    assert abs(fit.parameters["tau"] - 0.1) / 0.1 < 0.01
    assert fit.parameters["E"] > 0.0
    assert fit.condition_number > 0.0


def test_fit_maxwell_requires_relaxation_response() -> None:
    with pytest.raises(ViscoelasticityError) as ei:
        fit_maxwell(_creep_response())  # type: ignore[arg-type]
    assert ei.value.code == "PROTOCOL_MODEL_MISMATCH"


def test_fit_kelvin_voigt_clean_recovery() -> None:
    resp = _creep_response(modulus=5e3, tau=0.1)
    fit = fit_kelvin_voigt(resp)
    assert abs(fit.parameters["E"] - 5e3) / 5e3 < 0.01
    # E and tau are correlated in the near-plateau region: the honest
    # recovery bound for tau is wider than for E
    assert abs(fit.parameters["tau"] - 0.1) / 0.1 < 0.10


def test_fit_sls_both_representations() -> None:
    t = np.linspace(0.0, 1.0, 120)
    nrm = 1.0 - 0.6 * (1.0 - np.exp(-t / 0.1))
    resp = RelaxationResponseResult(
        relative_time=t, indentation=np.full(120, 5e-7), force=1e-6 * nrm,
        normalized_force=nrm, hold_indices=np.arange(120), hold_start_time=0.0,
        force_at_hold_start=1e-6, equilibrium_force_estimate=float(nrm[-1]) * 1e-6,
        warnings=())
    fit = fit_standard_linear_solid(resp, tip_radius=1e-6)
    assert abs(fit.parameters["a"] - 0.6) < 0.01
    assert abs(fit.parameters["tau_relax"] - 0.1) / 0.1 < 0.01
    # creep representation: the response is the compliance INCREMENT
    # (J_inf - J0)(1 - exp(-t/tau_retard)); the absolute level J0 = 1/E0
    # is carried by indentation_at_hold_start/F_hold
    j_inc = (1 / 2e3 - 1 / 5e3) * (1.0 - np.exp(-t / (0.1 * 5e3 / 2e3)))
    creep = CreepResponseResult(
        relative_time=t, force=np.full(120, 1e-6),
        indentation=1e-6 * (1 / 5e3 + j_inc),
        compliance_proxy=j_inc, hold_indices=np.arange(120), hold_start_time=0.0,
        force_hold_value=1e-6, indentation_at_hold_start=1e-6 * (1 / 5e3), warnings=())
    fit2 = fit_standard_linear_solid(creep)
    assert abs(fit2.parameters["E0"] - 5e3) / 5e3 < 0.01
    assert abs(fit2.parameters["E_inf"] - 2e3) / 2e3 < 0.01


def test_fit_generalized_maxwell_clean_recovery() -> None:
    t = np.linspace(0.0, 2.0, 160)
    alpha = np.array([0.4, 0.3])
    tau = np.array([0.05, 0.5])
    nrm = forward_generalized_maxwell_normalized(t, alpha, tau)
    resp = RelaxationResponseResult(
        relative_time=t, indentation=np.full(160, 5e-7), force=1e-6 * nrm,
        normalized_force=nrm, hold_indices=np.arange(160), hold_start_time=0.0,
        force_at_hold_start=1e-6, equilibrium_force_estimate=float(nrm[-1]) * 1e-6,
        warnings=())
    fit = fit_generalized_maxwell(resp, n_terms=2)
    assert fit.success
    taus = sorted([fit.parameters["tau_i[0]"], fit.parameters["tau_i[1]"]])
    assert abs(taus[0] - 0.05) / 0.05 < 0.05
    assert abs(taus[1] - 0.5) / 0.5 < 0.05
    assert any("no claim" in w for w in fit.warnings)


def test_fit_power_law_clean_recovery() -> None:
    t = np.linspace(0.01, 1.0, 100)
    nrm = (t / 0.01) ** (-0.3)
    resp = RelaxationResponseResult(
        relative_time=t, indentation=np.full(100, 5e-7), force=1e-6 * nrm,
        normalized_force=nrm, hold_indices=np.arange(100), hold_start_time=0.0,
        force_at_hold_start=1e-6, equilibrium_force_estimate=float(nrm[-1]) * 1e-6,
        warnings=())
    fit = fit_power_law_relaxation(resp)
    assert abs(fit.parameters["alpha"] - 0.3) < 0.02


def test_comparison_weights_and_ambiguity() -> None:
    t = np.linspace(0.0, 2.0, 160)
    nrm = np.exp(-t / 0.1)
    resp = RelaxationResponseResult(
        relative_time=t, indentation=np.full(160, 5e-7), force=1e-6 * nrm,
        normalized_force=nrm, hold_indices=np.arange(160), hold_start_time=0.0,
        force_at_hold_start=1e-6, equilibrium_force_estimate=float(nrm[-1]) * 1e-6,
        warnings=())
    cmp = compare_viscoelastic_models(resp, models=("maxwell", "standard_linear_solid"))
    assert cmp.recommended_model == "maxwell"
    assert cmp.weights["maxwell"] > 0.9
    assert not cmp.ambiguous
    assert "physical" not in str(cmp.provenance)


def test_fit_deterministic_replay() -> None:
    resp = _relaxation_response(tau=0.1, noise=1e-12)
    a = fit_maxwell(resp, tip_radius=1e-6)
    b = fit_maxwell(resp, tip_radius=1e-6)
    assert a.parameters == b.parameters
    assert a.aicc == b.aicc
