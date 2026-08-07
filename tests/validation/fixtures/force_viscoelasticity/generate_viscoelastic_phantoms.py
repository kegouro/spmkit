"""Deterministic FS-F3 viscoelastic phantoms (oracle-driven).

Every force trace derives from the independent oracles
(oracle_viscoelastic_lumped, oracle_hereditary_integral) so the fixture
truth is never computed by production code.  Curve construction follows the
FS-F1/FS-F2 coordinate conventions:

- height = piezo/sensor position; the approach height is non-decreasing
  (flat during a displacement hold, which the FS-F1 quality gate accepts);
- separation = height - force/k (FS-F1 convention);
- indentation = separation - contact coordinate (FS-F2 convention);
- time axes in seconds; a ramp-hold curve is a single "extend" segment.

Relaxation phantoms carry the exact model force in the HOLD region
(F(t) = F0 * E_rel(t)/E_rel(0)); the ramp is an elastic-following
approximation (documented; the extraction only uses the hold).  Creep
phantoms hold the force constant while the indentation follows the model
compliance.  Lee-Radok and Ting phantoms carry the oracle hereditary
integrals over loading (and unloading) branches.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from oracle_hereditary_integral import lee_radok_force, ting_force
from oracle_viscoelastic_lumped import (
    kv_compliance,
    maxwell_normalized,
    prony_normalized,
    sls_creep_compliance,
    sls_relaxation_modulus,
)

DEFAULT_SEED = 20260807
K_SPRING = 10.0
ZC = 3e-6
R_TIP = 1e-6
POISSON = 0.3


@dataclass
class ViscoPhantom:
    case_id: str
    model: str
    protocol: str
    time: np.ndarray
    height: np.ndarray
    force: np.ndarray
    separation: np.ndarray
    contact_index: int
    contact_coordinate: float
    truth: dict
    expected_recovery: bool = True
    expected_ambiguity: bool = False
    expected_failure: str | None = None
    metadata: dict = field(default_factory=dict)


def _elastic_peak(delta0: float | np.ndarray, e0: float) -> np.ndarray:
    """F0 = (4/3) sqrt(R) E* delta0^1.5 with E* = E0/(1-nu^2)."""
    est = e0 / (1.0 - POISSON**2)
    return (4.0 / 3.0) * math.sqrt(R_TIP) * est * np.asarray(delta0, dtype=np.float64) ** 1.5


def build_relaxation(
    case_id: str, model: str, params: dict, delta0: float,
    t_ramp: float, t_hold: float, *,
    n_ramp: int = 60, n_hold: int = 220, n_pre: int = 40, n_retract: int = 40,
    seed: int = DEFAULT_SEED, noise: float = 0.0, correlated: bool = False,
    drift: float = 0.0, jitter: float = 0.0, nonuniform: bool = False,
    duplicate_time: bool = False, hold_fraction: float = 1.0,
    sampling_switch: bool = False, contact_offset: int = 0,
    baseline_offset: float = 0.0, baseline_slope: float = 0.0,
    response_delay: int = 0, expected_recovery: bool = True,
    expected_ambiguity: bool = False, expected_failure: str | None = None,
) -> ViscoPhantom:
    """Ramp-hold relaxation phantom (Maxwell / SLS / Prony / power law)."""
    rng = np.random.default_rng(seed)
    n_hold_use = max(2, int(n_hold * hold_fraction))

    def e_rel(t: np.ndarray) -> np.ndarray:
        if model == "maxwell":
            return params["E"] * maxwell_normalized(t, params["tau"])
        if model == "sls":
            return sls_relaxation_modulus(t, params["E0"], params["E_inf"], params["tau"])
        if model == "generalized_maxwell":
            # E(t) = E_inf + E * sum(alpha_i exp(-t/tau_i))
            return params["E_inf"] + params["E"] * (
                prony_normalized(t, params["alpha"], params["tau_i"])
                - (1.0 - float(np.sum(params["alpha"]))))
        if model == "power_law":
            # anchored at t_ref; the response below t_ref is the flat
            # reference plateau (documented; the fit uses t >= t_ref)
            t_use = np.maximum(t, params["t_ref"])
            return params["E_ref"] * np.power(t_use / params["t_ref"], -params["alpha"])
        raise ValueError(model)

    # time axis
    t_ramp_arr = np.linspace(0.0, t_ramp, n_ramp)
    dt_hold = t_hold / n_hold
    if sampling_switch:
        dt2 = dt_hold * 3.0
        n1 = n_hold_use // 2
        t_hold_arr = np.concatenate([
            np.arange(n1, dtype=float) * dt_hold,
            dt_hold * n1 + np.arange(n_hold_use - n1, dtype=float) * dt2])
    elif nonuniform:
        steps = rng.uniform(0.5, 1.5, n_hold_use - 1)
        t_hold_arr = np.concatenate([[0.0], np.cumsum(steps * dt_hold)])
    else:
        t_hold_arr = np.arange(n_hold_use, dtype=float) * dt_hold
    t_hold_arr = t_hold_arr + dt_hold  # start after the ramp end (no duplicate)
    t_retract = np.linspace(t_ramp + float(t_hold_arr[-1]) + dt_hold,
                            t_ramp + float(t_hold_arr[-1]) + dt_hold + t_hold / 3.0,
                            n_retract)
    dt_pre = t_ramp / n_ramp
    t_pre = np.linspace(-n_pre * dt_pre, -dt_pre, n_pre)  # strictly increasing
    t = np.concatenate([t_pre, t_ramp_arr, t_ramp + t_hold_arr, t_retract])
    t[n_pre:] = t[n_pre:] - t[n_pre]  # start at 0 at the pre-contact start
    if jitter > 0.0:
        for _ in range(20):
            cand = t.copy()
            cand[n_pre + 1:] = cand[n_pre + 1:] + rng.normal(0.0, jitter,
                                                             cand[n_pre + 1:].size)
            if np.all(np.diff(cand[n_pre:]) > 0.0):
                t = cand
                break
        else:  # pragma: no cover - jitter too large for the grid
            t[n_pre + 1:] = t[n_pre + 1:] + rng.normal(0.0, jitter,
                                                       t[n_pre + 1:].size)
            t = np.maximum.accumulate(t)
    if duplicate_time:
        t[n_pre + n_ramp + 2] = t[n_pre + n_ramp + 1]
    if np.any(np.diff(t) < 0.0):
        t = np.maximum.accumulate(t)

    # separation and indentation (the piezo height stays CONSTANT during
    # the hold: sep_hold = h_hold - f_hold/k grows as the force relaxes,
    # which the FS-F1 quality gate accepts because the height is flat)
    sep_pre = np.linspace(ZC - 2e-6, ZC, n_pre)
    sep_ramp = np.linspace(ZC, ZC + delta0, n_ramp)
    sep_hold0 = ZC + delta0

    # force: elastic-following ramp, exact model response in the hold
    t_rel = t[n_pre + n_ramp: n_pre + n_ramp + n_hold_use]
    t_rel = t_rel - t_rel[0]
    e0 = float(e_rel(np.array([0.0]))[0])
    f_peak = _elastic_peak(delta0, e0)
    f_ramp = f_peak * ((sep_ramp - ZC) / delta0) ** 1.5 \
        * e_rel(t_ramp_arr) / e0
    f_hold = f_peak * e_rel(t_rel) / e0
    f_retract = f_hold[-1] * np.linspace(1.0, 0.05, n_retract)
    f = np.concatenate([np.zeros(n_pre), f_ramp, f_hold, f_retract])
    sep_nominal = np.concatenate([
        sep_pre, sep_ramp, np.full(n_hold_use, sep_hold0),
        np.linspace(sep_hold0, ZC, n_retract)])
    f = f + baseline_offset + baseline_slope * sep_nominal
    if drift:
        f = f + drift * np.arange(f.size, dtype=float)
    if response_delay:
        f = np.concatenate([np.full(response_delay, f[0]), f[:-response_delay]])
    f_clean = f.copy()
    if noise:
        raw = rng.normal(0.0, noise, f.size)
        if correlated:
            kernel = np.ones(5) / 5
            raw = np.convolve(raw, kernel, mode="same")
        f = f + raw
    h_hold = sep_hold0 + f_clean[n_pre + n_ramp] / K_SPRING
    sep_hold = h_hold - f_clean[n_pre + n_ramp: n_pre + n_ramp + n_hold_use] / K_SPRING
    sep_retract = np.linspace(float(sep_hold[-1]), ZC, n_retract)
    sep = np.concatenate([sep_pre, sep_ramp, sep_hold, sep_retract])
    # the recorded piezo position is the CLEAN position (the noise lives on
    # the force channel only); the derived separation then jitters within
    # the FS-F1 work-integral tolerance instead of failing its gate
    height = sep + f_clean / K_SPRING
    contact_index = int(n_pre + n_ramp - 1 + 1) + contact_offset  # last pre-contact sample
    contact_index = min(max(contact_index, 2), height.size - 3)
    truth = {
        "model": model, "protocol": "STRESS_RELAXATION",
        "parameters": params, "delta0": delta0,
        "contact_index": contact_index, "contact_coordinate": float(ZC),
        "t_ramp": t_ramp, "t_hold": t_hold, "n_hold": n_hold_use,
        "hold_start_index": n_pre + n_ramp, "hold_end_index": n_pre + n_ramp + n_hold_use - 1,
        "expected_recovery": expected_recovery, "expected_ambiguity": expected_ambiguity,
        "expected_failure": expected_failure,
    }
    return ViscoPhantom(
        case_id=case_id, model=model, protocol="STRESS_RELAXATION",
        time=t, height=height, force=f, separation=sep,
        contact_index=contact_index, contact_coordinate=float(ZC), truth=truth,
        expected_recovery=expected_recovery, expected_ambiguity=expected_ambiguity,
        expected_failure=expected_failure,
        metadata={"noise": noise, "correlated": correlated, "drift": drift,
                  "jitter": jitter, "nonuniform": nonuniform,
                  "duplicate_time": duplicate_time, "hold_fraction": hold_fraction,
                  "sampling_switch": sampling_switch, "contact_offset": contact_offset,
                  "baseline_offset": baseline_offset, "baseline_slope": baseline_slope,
                  "response_delay": response_delay, "seed": seed})


def build_creep(case_id: str, model: str, params: dict, f_hold: float,
                t_ramp: float, t_hold: float, *,
                n_ramp: int = 60, n_hold: int = 220, n_pre: int = 40,
                n_retract: int = 40, seed: int = DEFAULT_SEED, noise: float = 0.0,
                expected_recovery: bool = True) -> ViscoPhantom:
    """Force-hold creep phantom (Kelvin-Voigt / SLS creep)."""
    rng = np.random.default_rng(seed)
    t_ramp_arr = np.linspace(0.0, t_ramp, n_ramp)
    dt_hold = t_hold / n_hold
    t_hold_arr = (np.arange(n_hold, dtype=float) + 1.0) * dt_hold
    t_retract = np.linspace(t_ramp + float(t_hold_arr[-1]) + dt_hold,
                            t_ramp + float(t_hold_arr[-1]) + dt_hold + t_hold / 3.0,
                            n_retract)
    dt_pre = t_ramp / n_ramp
    t_pre = np.linspace(-n_pre * dt_pre, -dt_pre, n_pre)
    t = np.concatenate([t_pre, t_ramp_arr, t_ramp + t_hold_arr, t_retract])
    t[n_pre:] = t[n_pre:] - t[n_pre]

    def compliance(tt: np.ndarray) -> np.ndarray:
        if model == "kelvin_voigt":
            return kv_compliance(tt, params["E"], params["tau"])
        if model == "sls_creep":
            return sls_creep_compliance(tt, params["J0"], params["J_inf"], params["tau"])
        raise ValueError(model)

    t_rel = t_hold_arr
    delta_hold = f_hold * compliance(t_rel)  # J(t) = delta/F
    delta_ramp = np.linspace(0.0, float(delta_hold[0]), n_ramp)
    e_eff = params["E"] if model == "kelvin_voigt" else 1.0 / params["J0"]
    sep_ramp = ZC + delta_ramp
    sep_hold = ZC + delta_hold
    sep_retract = np.linspace(float(sep_hold[-1]), ZC, n_retract)
    sep = np.concatenate([np.linspace(ZC - 2e-6, ZC, n_pre), sep_ramp,
                          sep_hold, sep_retract])
    ramp_frac = delta_ramp / max(float(delta_ramp[-1]), 1e-300)
    f_ramp = _elastic_peak(delta_ramp, e_eff) * np.minimum(1.0, ramp_frac)
    f_ramp = np.clip(f_ramp, 0.0, f_hold)
    f = np.concatenate([np.zeros(n_pre), f_ramp,
                        np.full(n_hold, f_hold),
                        np.linspace(f_hold, 0.05 * f_hold, n_retract)])
    f_clean = f.copy()
    if noise:
        f = f + rng.normal(0.0, noise, f.size)
    height = sep + f_clean / K_SPRING
    contact_index = n_pre
    truth = {
        "model": model, "protocol": "CREEP", "parameters": params,
        "f_hold": f_hold, "contact_index": contact_index,
        "contact_coordinate": float(ZC), "t_ramp": t_ramp, "t_hold": t_hold,
        "hold_start_index": n_pre + n_ramp,
        "hold_end_index": n_pre + n_ramp + n_hold - 1,
        "expected_recovery": expected_recovery,
    }
    return ViscoPhantom(
        case_id=case_id, model=model, protocol="CREEP", time=t, height=height,
        force=f, separation=sep, contact_index=contact_index,
        contact_coordinate=float(ZC), truth=truth,
        expected_recovery=expected_recovery, metadata={"noise": noise, "seed": seed})


def build_lee_radok(case_id: str, params: dict, t_end: float, delta_max: float, *,
                    n: int = 200, n_pre: int = 40, n_retract: int = 40,
                    seed: int = DEFAULT_SEED, noise: float = 0.0,
                    expected_recovery: bool = True) -> ViscoPhantom:
    """Monotonic spherical loading with the oracle Lee-Radok integral."""
    rng = np.random.default_rng(seed)
    t_load = np.linspace(0.0, t_end, n)
    delta = delta_max * (t_load / t_end) ** 0.7
    # the oracle already yields the exact force (the SLS parameters enter
    # through the relaxation modulus; young=1.0 fixes only the coefficient)
    f = lee_radok_force(t_load, delta, params["E0"], params["E_inf"],
                        params["tau"], 1.0, R_TIP, POISSON)
    if noise:
        f = f + rng.normal(0.0, noise, f.size)
    dt_load = t_end / n
    t_retract = np.linspace(t_end + dt_load, t_end + dt_load + t_end / 3.0, n_retract)
    dt_pre = t_end / n
    t_pre = np.linspace(-n_pre * dt_pre, -dt_pre, n_pre)
    t = np.concatenate([t_pre, t_load, t_retract])
    t[n_pre:] = t[n_pre:] - t[n_pre]
    sep_load = ZC + delta
    sep = np.concatenate([np.linspace(ZC - 2e-6, ZC, n_pre), sep_load,
                          np.linspace(float(sep_load[-1]), ZC, n_retract)])
    f_retract = np.linspace(float(f[-1]), 0.05 * float(f[-1]), n_retract)
    f = np.concatenate([np.zeros(n_pre), f, f_retract])
    height = sep + f / K_SPRING
    truth = {"model": "lee_radok", "protocol": "LOADING_RAMP",
             "parameters": params, "delta_max": delta_max, "t_end": t_end,
             "contact_index": n_pre, "contact_coordinate": float(ZC),
             "expected_recovery": expected_recovery}
    return ViscoPhantom(
        case_id=case_id, model="lee_radok", protocol="LOADING_RAMP",
        time=t, height=height, force=f, separation=sep, contact_index=n_pre,
        contact_coordinate=float(ZC), truth=truth,
        expected_recovery=expected_recovery,
        metadata={"noise": noise, "seed": seed})


def build_ting(case_id: str, params: dict, t_load: float, t_unload: float,
               delta_max: float, *, n_load: int = 150, n_unload: int = 150,
               n_pre: int = 40, n_post: int = 20, seed: int = DEFAULT_SEED,
               noise: float = 0.0, expected_recovery: bool = True) -> ViscoPhantom:
    """Triangular loading/unloading with the oracle Ting integral.

    The extend segment carries the loading branch (monotone height); the
    retract segment carries the unloading branch in physical order
    (decreasing height, increasing time)."""
    rng = np.random.default_rng(seed)
    t_l = np.linspace(0.0, t_load, n_load)
    d_l = delta_max * (t_l / t_load) ** 0.8
    t_u = np.linspace(t_load, t_load + t_unload, n_unload)
    d_u = delta_max * (1.0 - ((t_u - t_load) / t_unload) ** 0.8)
    f_l = lee_radok_force(t_l, d_l, params["E0"], params["E_inf"], params["tau"],
                          1.0, R_TIP, POISSON)
    f_all = ting_force(t_l, d_l, t_u, d_u, params["E0"], params["E_inf"],
                       params["tau"], 1.0, R_TIP, POISSON)
    f_u = f_all[n_load:]
    if noise:
        f_l = f_l + rng.normal(0.0, noise, f_l.size)
        f_u = f_u + rng.normal(0.0, noise, f_u.size)
    # extend segment: pre-contact + loading
    dt_pre = t_load / n_load
    t_pre = np.linspace(-n_pre * dt_pre, -dt_pre, n_pre)
    t_ext = np.concatenate([t_pre, t_l])
    t_ext[n_pre:] = t_ext[n_pre:] - t_ext[n_pre]
    sep_ext = np.concatenate([np.linspace(ZC - 2e-6, ZC, n_pre), ZC + d_l])
    f_ext = np.concatenate([np.zeros(n_pre), f_l])
    h_ext = sep_ext + f_ext / K_SPRING
    # retract segment: unloading in physical order (decreasing height);
    # the time axis continues from the loading branch (absolute times)
    t_ret = t_u
    sep_ret = ZC + d_u
    f_ret = f_u
    h_ret = sep_ret + f_ret / K_SPRING
    truth = {"model": "ting", "protocol": "TRIANGULAR_LOADING",
             "parameters": params, "delta_max": delta_max,
             "t_load": t_load, "t_unload": t_unload,
             "contact_index": n_pre, "contact_coordinate": float(ZC),
             "expected_recovery": expected_recovery}
    return ViscoPhantom(
        case_id=case_id, model="ting", protocol="TRIANGULAR_LOADING",
        time=np.concatenate([t_ext, t_ret]), height=np.concatenate([h_ext, h_ret]),
        force=np.concatenate([f_ext, f_ret]),
        separation=np.concatenate([sep_ext, sep_ret]),
        contact_index=n_pre, contact_coordinate=float(ZC), truth=truth,
        expected_recovery=expected_recovery,
        metadata={"noise": noise, "seed": seed, "n_load": n_load,
                  "n_unload": n_unload})


def build_flat(case_id: str = "V24") -> ViscoPhantom:
    """Failed-preparation flat curve (no contact branch)."""
    n = 200
    t = np.arange(n, dtype=float) * 1e-4
    sep = np.linspace(ZC - 2e-6, ZC + 1e-6, n)
    f = np.full(n, 5e-10)
    height = sep + f / K_SPRING
    truth = {"model": "none", "protocol": "INSUFFICIENT_PROTOCOL",
             "parameters": {}, "contact_index": 0, "contact_coordinate": float(ZC),
             "expected_recovery": False, "expected_failure": "CONTACT_NOT_FOUND"}
    return ViscoPhantom(
        case_id=case_id, model="none", protocol="INSUFFICIENT_PROTOCOL",
        time=t, height=height, force=f, separation=sep, contact_index=0,
        contact_coordinate=float(ZC), truth=truth, expected_recovery=False,
        expected_failure="CONTACT_NOT_FOUND", metadata={})


def generate_phantoms(seed: int = DEFAULT_SEED) -> dict[str, ViscoPhantom]:
    cases: dict[str, ViscoPhantom] = {}
    e0 = 5e3
    e_inf = 2e3
    tau = 0.05
    delta0 = 5e-7
    t_ramp = 0.002
    t_hold = 0.5

    cases["V01"] = build_relaxation(
        "V01", "maxwell", {"E": e0, "tau": tau}, delta0, t_ramp, t_hold)
    cases["V02"] = build_creep(
        "V02", "kelvin_voigt", {"E": e0, "tau": tau}, f_hold=1e-6, t_ramp=t_ramp,
        t_hold=t_hold)
    cases["V03"] = build_relaxation(
        "V03", "sls", {"E0": e0, "E_inf": e_inf, "tau": tau}, delta0, t_ramp, t_hold)
    cases["V04"] = build_creep(
        "V04", "sls_creep", {"J0": 1 / e0, "J_inf": 1 / e_inf, "tau": tau * e0 / e_inf},
        f_hold=1e-6, t_ramp=t_ramp, t_hold=t_hold)
    cases["V05"] = build_relaxation(
        "V05", "generalized_maxwell",
        {"E_inf": e_inf, "E": e0 - e_inf, "alpha": np.array([0.6, 0.4]),
         "tau_i": np.array([0.01, 0.2])}, delta0, t_ramp, t_hold)
    cases["V06"] = build_relaxation(
        "V06", "generalized_maxwell",
        {"E_inf": e_inf, "E": e0 - e_inf, "alpha": np.array([0.5, 0.3, 0.2]),
         "tau_i": np.array([0.005, 0.05, 0.5])}, delta0, t_ramp, t_hold)
    cases["V07"] = build_relaxation(
        "V07", "power_law", {"E_ref": e0, "alpha": 0.3, "t_ref": t_ramp + 1e-6},
        delta0, t_ramp, t_hold)
    cases["V08"] = build_lee_radok(
        "V08", {"E0": e0, "E_inf": e_inf, "tau": tau}, t_end=0.2, delta_max=5e-7)
    cases["V09"] = build_ting(
        "V09", {"E0": e0, "E_inf": e_inf, "tau": tau}, t_load=0.1, t_unload=0.1,
        delta_max=5e-7)
    # variants
    cases["V10"] = build_relaxation(
        "V10", "sls", {"E0": e0, "E_inf": e_inf, "tau": tau}, delta0, t_ramp, t_hold,
        noise=1e-12, seed=seed + 1)
    cases["V11"] = build_relaxation(
        "V11", "sls", {"E0": e0, "E_inf": e_inf, "tau": tau}, delta0, t_ramp, t_hold,
        noise=1e-12, correlated=True, seed=seed + 2)
    cases["V12"] = build_relaxation(
        "V12", "sls", {"E0": e0, "E_inf": e_inf, "tau": tau}, delta0, t_ramp, t_hold,
        drift=1e-13)
    cases["V13"] = build_relaxation(
        "V13", "sls", {"E0": e0, "E_inf": e_inf, "tau": tau}, delta0, t_ramp, t_hold,
        jitter=1e-5, seed=seed + 3)
    cases["V14"] = build_relaxation(
        "V14", "sls", {"E0": e0, "E_inf": e_inf, "tau": tau}, delta0, t_ramp, t_hold,
        nonuniform=True, seed=seed + 4)
    cases["V15"] = build_relaxation(
        "V15", "sls", {"E0": e0, "E_inf": e_inf, "tau": tau}, delta0, t_ramp, t_hold,
        duplicate_time=True, expected_failure="DUPLICATE_TIMESTAMPS")
    cases["V16"] = build_relaxation(
        "V16", "sls", {"E0": e0, "E_inf": e_inf, "tau": tau}, delta0, t_ramp, t_hold,
        hold_fraction=0.02, expected_recovery=False,
        expected_failure="EMPTY_REGION")
    cases["V17"] = build_relaxation(
        "V17", "sls", {"E0": e0, "E_inf": e_inf, "tau": tau}, delta0, t_ramp, t_hold,
        hold_fraction=0.25, expected_recovery=True)
    cases["V18"] = build_relaxation(
        "V18", "sls", {"E0": e0, "E_inf": e_inf, "tau": tau}, delta0, t_ramp, t_hold,
        sampling_switch=True)
    cases["V19"] = build_relaxation(
        "V19", "sls", {"E0": e0, "E_inf": e_inf, "tau": tau}, delta0, t_ramp, t_hold,
        contact_offset=3)
    cases["V20"] = build_relaxation(
        "V20", "sls", {"E0": e0, "E_inf": e_inf, "tau": tau}, delta0, t_ramp, t_hold,
        baseline_offset=1e-11, baseline_slope=1e-7)
    cases["V21"] = build_relaxation(
        "V21", "sls", {"E0": e0, "E_inf": e_inf, "tau": tau}, delta0, t_ramp, t_hold,
        response_delay=3, expected_recovery=False,
        expected_failure="NONMONOTONIC_COORDINATE")
    cases["V22"] = build_relaxation(
        "V22", "sls", {"E0": e0, "E_inf": e_inf, "tau": tau}, delta0 * 0.05, t_ramp,
        t_hold, expected_recovery=True)
    cases["V23"] = build_relaxation(
        "V23", "generalized_maxwell",
        {"E_inf": e_inf, "E": e0 - e_inf, "alpha": np.array([0.5, 0.5]),
         "tau_i": np.array([0.02, 0.020001])}, delta0, t_ramp, t_hold,
        expected_recovery=True, expected_ambiguity=True)
    cases["V24"] = build_flat("V24")
    return cases


def _json_safe(obj: object) -> object:
    """Recursively convert numpy scalars/arrays to JSON-safe values."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def serialize(cases: dict[str, ViscoPhantom], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    cases_meta: dict[str, dict[str, object]] = {}
    manifest: dict[str, object] = {
        "schema_version": 1, "family": "force_viscoelasticity_phantoms",
        "seed": DEFAULT_SEED, "units": {"time": "s", "force": "N", "height": "m",
                                        "separation": "m", "indentation": "m",
                                        "modulus": "Pa", "viscosity": "Pa*s"},
        "cases": cases_meta,
    }
    arrays: dict[str, np.ndarray] = {}
    for cid, case in sorted(cases.items()):
        cases_meta[cid] = {
            "model": case.model, "protocol": case.protocol,
            "truth": _json_safe(case.truth),
            "expected_recovery": case.expected_recovery,
            "expected_ambiguity": case.expected_ambiguity,
            "expected_failure": case.expected_failure, "metadata": case.metadata,
            "contact_index": case.contact_index,
            "contact_coordinate": case.contact_coordinate,
        }
        arrays[f"{cid}_time"] = case.time
        arrays[f"{cid}_height"] = case.height
        arrays[f"{cid}_force"] = case.force
        arrays[f"{cid}_separation"] = case.separation
    (out_dir / "viscoelasticity_reference.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    payload = {k: np.ascontiguousarray(v, dtype=np.float64)
               for k, v in sorted(arrays.items())}
    np.savez_compressed(out_dir / "viscoelasticity_reference.npz", **payload)  # type: ignore[arg-type]


if __name__ == "__main__":
    import sys

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    serialize(generate_phantoms(), out)
    print("viscoelastic phantoms written to", out)
