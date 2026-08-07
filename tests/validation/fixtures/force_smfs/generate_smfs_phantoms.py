"""Deterministic FS-F4 SMFS phantoms (oracle-driven).

Every polymer branch and event series derives from the independent oracles.
Curve construction follows the FS-F1/FS-F2 coordinate conventions: the
retract segment carries the pull (separation increasing, time increasing,
force = polymer response); the molecular extension is x = separation -
sep_zero with the tether zero sep_zero recorded in the truth.  The extend
segment is a generic approach (monotone height) so the FS-F1 preparation
accepts the curve.

Protocol classes per case: "retract_force_extension", "ramped_loading",
"force_clamp", "array_only" (no curve; pure event series).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from oracle_smfs_kinetics import dhs_pdf
from oracle_smfs_polymer import (
    extensible_fjc_extension,
    extensible_wlc_force,
    fjc_extension,
    wlc_force,
)

DEFAULT_SEED = 20260808
K_SPRING = 10.0
KB = 1.380649e-23


@dataclass
class SmfsPhantom:
    case_id: str
    protocol: str
    model: str
    time: np.ndarray
    height: np.ndarray
    force: np.ndarray
    separation: np.ndarray
    truth: dict
    expected_recovery: bool = True
    expected_failure: str | None = None
    metadata: dict = field(default_factory=dict)


def _seg(st: str, d: str, z: np.ndarray, f: np.ndarray, t: np.ndarray):
    # type: (...) -> object
    from spmkit.core.models import ForceSegment
    from spmkit.core.models.force import SegmentType
    st_lit: SegmentType = st  # type: ignore[assignment]
    return ForceSegment(
        segment_type=st_lit, direction=d, raw_height=z, raw_deflection=f / K_SPRING,
        time=t, cycle=0, state="force_n", deflection=f / K_SPRING, force=f,
        separation=None, metadata={})


def build_polymer_curve(
    case_id: str, model: str, params: dict, sep_zero: float, x_max: float,
    *, n: int = 300, n_approach: int = 120, t_pull: float = 1.0,
    noise: float = 0.0, correlated: bool = False, drift: float = 0.0,
    truncate: float | None = None, seed: int = DEFAULT_SEED,
    expected_recovery: bool = True, expected_failure: str | None = None,
) -> SmfsPhantom:
    """Retract force-extension branch with a polymer model."""
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, x_max, n)
    if truncate is not None:
        keep = x <= truncate
        x = x[keep]
    if model == "worm_like_chain":
        f = wlc_force(x, params["Lc"], params["Lp"], params.get("T", 298.0))
    elif model == "extensible_worm_like_chain":
        f = extensible_wlc_force(x, params["Lc"], params["Lp"], params["S"],
                                 params.get("T", 298.0))
    elif model == "freely_jointed_chain":
        f = np.linspace(0.0, 1e-9, x.size)
        f = f / np.max(f) * params.get("F_max", 1e-9)
        x = fjc_extension(f, params["Lc"], params["b"], params.get("T", 298.0))
    elif model == "extensible_freely_jointed_chain":
        f = np.linspace(0.0, 1e-9, x.size)
        f = f / np.max(f) * params.get("F_max", 1e-9)
        x = extensible_fjc_extension(f, params["Lc"], params["b"], params["Sk"],
                                     params.get("T", 298.0))
    else:
        raise ValueError(model)
    if noise:
        raw = rng.normal(0.0, noise, f.size)
        if correlated:
            kernel = np.ones(5) / 5
            raw = np.convolve(raw, kernel, mode="same")
        f = f + raw
    if drift:
        f = f + drift * np.arange(f.size, dtype=float)
    # the retract carries a slack region before the tether loads
    # (extension < 0 there); the slack is the tether's own scale so the
    # polymer branch keeps a healthy sample count.  For the WLC/eWLC the
    # force is re-evaluated on the ACTUAL extension grid of the retract;
    # for the FJC/eFJC the extension is the closed-form function of the
    # force, so the separation grid is built from the FJC extensions.
    slack = 100e-9
    if model in ("worm_like_chain", "extensible_worm_like_chain"):
        sep = np.linspace(sep_zero - slack, sep_zero + x_max, f.size)
        x_eff = sep - sep_zero
        f = np.where(x_eff > 0.0,
                     wlc_force(x_eff, params["Lc"], params["Lp"],
                               params.get("T", 298.0))
                     if model == "worm_like_chain" else
                     extensible_wlc_force(x_eff, params["Lc"], params["Lp"],
                                          params["S"], params.get("T", 298.0)),
                     0.0)
    else:
        x = fjc_extension(f, params["Lc"], params["b"], params.get("T", 298.0)) \
            if model == "freely_jointed_chain" else \
            extensible_fjc_extension(f, params["Lc"], params["b"], params["Sk"],
                                    params.get("T", 298.0))
        x = x * (x_max / max(float(np.max(x)), 1e-30))
        sep = np.linspace(sep_zero - slack, sep_zero + x_max, f.size)
        x_eff = sep - sep_zero
        # invert the FJC on the uniform extension grid: the force is found
        # by a deterministic bisection on the monotone x(F)
        f_new = np.zeros(f.size)
        for i, xi in enumerate(x_eff):
            if xi <= 0.0:
                continue
            f_lo, f_hi = 0.0, float(np.max(f)) * 4.0
            for _ in range(80):
                fm = 0.5 * (f_lo + f_hi)
                xm = fjc_extension(np.array([fm]), params["Lc"], params["b"],
                                   params.get("T", 298.0))[0] \
                    * (x_max / max(float(np.max(x)), 1e-30))
                if model == "extensible_freely_jointed_chain":
                    xm = extensible_fjc_extension(
                        np.array([fm]), params["Lc"], params["b"], params["Sk"],
                        params.get("T", 298.0))[0] \
                        * (x_max / max(float(np.max(x)), 1e-30))
                if xm > xi:
                    f_hi = fm
                else:
                    f_lo = fm
            f_new[i] = 0.5 * (f_lo + f_hi)
        f = f_new
    t = np.linspace(0.0, t_pull, f.size)
    height = sep + f / K_SPRING
    # approach segment with a genuine surface contact (the tip lands, the
    # force rises past the contact) so the FS-F1 preparation succeeds
    z_contact = 2.5e-6
    z_surf = 2.8e-6
    z_a = np.linspace(1.0e-6, z_surf, n_approach)
    f_a = np.where(z_a > z_contact, (z_a - z_contact) * 1e-3, 0.0)
    t_a = np.linspace(-0.5, 0.0, n_approach)
    truth = {
        "model": model, "protocol": "retract_force_extension",
        "parameters": params, "sep_zero": float(sep_zero), "x_max": float(x_max),
        "n_pull": int(f.size), "expected_recovery": expected_recovery,
        "expected_failure": expected_failure,
    }
    return SmfsPhantom(
        case_id=case_id, protocol="retract_force_extension", model=model,
        time=np.concatenate([t_a, t]), height=np.concatenate([z_a, height]),
        force=np.concatenate([f_a, f]), separation=np.concatenate([z_a, sep]),
        truth=truth, expected_recovery=expected_recovery,
        expected_failure=expected_failure,
        metadata={"noise": noise, "correlated": correlated, "drift": drift,
                  "seed": seed, "n_approach": n_approach, "n_pull": int(f.size)})


def _mk_curve(ext: object, ret: object) -> object:
    from spmkit.core.models import Calibration, ForceCurve
    return ForceCurve(
        segments=(ext, ret),  # type: ignore[arg-type]
        calibration=Calibration(invols=3e-8, spring_constant=K_SPRING,
                                method="thermal", temperature=300, provenance={}),
        position=None, index=0, metadata={})


def build_sawtooth(
    case_id: str, lc_list: list[float], lp: float, sep_zero: float,
    x_max: float, *, n: int = 400, t_pull: float = 1.0, temperature: float = 298.0,
    noise: float = 0.0, seed: int = DEFAULT_SEED, small_drops: bool = False,
    false_peak: bool = False, nonspecific: bool = False,
    unresolved_final: bool = False, expected_recovery: bool = True,
    expected_failure: str | None = None,
) -> SmfsPhantom:
    """Sawtooth retract with successive WLC branches of growing contour."""
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, x_max, n)
    n_events = len(lc_list) - 1
    # rupture extensions: branch i ruptures at 70% of ITS contour (the
    # strongly nonlinear WLC regime), so each post-event branch spans a
    # meaningful fraction of its contour for the delta-Lc fits
    f = np.zeros(n)
    branch_of = np.zeros(n, dtype=int)
    drop_f: list[float] = []
    peak_ext: list[float] = []
    for i in range(n_events):
        x_peak = 0.7 * lc_list[i]
        peak_ext.append(x_peak)
        f_peak = float(wlc_force(np.array([x_peak]), lc_list[i], lp, temperature)[0])
        f_next = float(wlc_force(np.array([x_peak]), lc_list[i + 1], lp, temperature)[0])
        drop_f.append(f_peak - f_next)
    x_max = 0.7 * lc_list[-1]  # the last branch reaches its own nonlinear regime
    # build the branch force on the extension grid; the final event
    # switches to the detached state (force 0)
    for i, xi in enumerate(x):
        branch = 0
        for k, pk in enumerate(peak_ext):
            if xi >= pk:
                branch = k + 1
        branch_of[i] = branch
        if branch <= n_events:
            f[i] = float(wlc_force(np.array([xi]), lc_list[branch], lp, temperature)[0])
        else:
            f[i] = 0.0  # after the final event: detached
    f = f * np.where(x >= 0.0, 1.0, 0.0)
    if false_peak:
        # a spurious noise peak before the first event
        idx = int(n * 0.05)
        f[idx] = f[idx] + float(np.max(f)) * 0.05
    if nonspecific:
        # a broad adhesion bump near the start (slow, not an unfolding drop)
        idx0 = int(n * 0.02)
        idx1 = int(n * 0.08)
        f[idx0:idx1] += float(np.max(f)) * 0.06
    if unresolved_final:
        # the final event's post branch is not resolved (the curve ends at
        # the last drop)
        f[x >= peak_ext[-1]] = f[x >= peak_ext[-1]]
        f[x >= x_max * 0.95] = 0.0
    if noise:
        f = f + rng.normal(0.0, noise, n)
    slack = 100e-9
    sep = np.linspace(sep_zero - slack, sep_zero + x_max, n)
    x_eff = sep - sep_zero
    # re-evaluate the polymer on the ACTUAL extension grid of the retract
    f = np.zeros(n)
    for i, xi in enumerate(x_eff):
        if xi <= 0.0:
            continue
        branch = 0
        for k, pk in enumerate(peak_ext):
            if xi >= pk:
                branch = k + 1
        if branch <= n_events:
            f[i] = float(wlc_force(np.array([xi]), lc_list[branch], lp,
                                   temperature)[0])
    t = np.linspace(0.0, t_pull, n)
    height = sep + f / K_SPRING
    n_a = 120
    z_contact = 2.5e-6
    z_surf = 2.8e-6
    z_a = np.linspace(1.0e-6, z_surf, n_a)
    f_a = np.where(z_a > z_contact, (z_a - z_contact) * 1e-3, 0.0)
    t_a = np.linspace(-0.5, 0.0, n_a)
    # truth: the rupture indices = the x positions where the branch changes
    truth = {
        "model": "sawtooth", "protocol": "retract_force_extension",
        "lc_list": lc_list, "lp": lp, "sep_zero": float(sep_zero),
        "temperature": temperature, "x_max": float(x_max),
        "peak_extensions": peak_ext, "force_drops": drop_f,
        "delta_lc": [lc_list[i + 1] - lc_list[i] for i in range(n_events)],
        "n_events": n_events, "expected_recovery": expected_recovery,
        "expected_failure": expected_failure,
    }
    return SmfsPhantom(
        case_id=case_id, protocol="retract_force_extension", model="sawtooth",
        time=np.concatenate([t_a, t]), height=np.concatenate([z_a, height]),
        force=np.concatenate([f_a, f]),
        separation=np.concatenate([z_a, sep]),
        truth=truth, expected_recovery=expected_recovery,
        expected_failure=expected_failure,
        metadata={"noise": noise, "seed": seed, "n_pull": n,
                  "false_peak": false_peak, "nonspecific": nonspecific,
                  "unresolved_final": unresolved_final})


def build_kinetic_series(
    case_id: str, model: str, params: dict, rates: np.ndarray, *,
    temperature: float = 298.0, events_per_rate: int = 40,
    seed: int = DEFAULT_SEED, narrow_range: bool = False,
    expected_recovery: bool = True, expected_failure: str | None = None,
) -> SmfsPhantom:
    """Deterministic Bell-Evans / DHS rupture-force series (inverse-CDF
    sampling from the oracle pdf at deterministic quantiles)."""
    rng = np.random.default_rng(seed)  # noqa: F841 (kept for API parity)
    forces: list[float] = []
    rate_list: list[float] = []
    u = (np.arange(events_per_rate) + 0.5) / events_per_rate
    for r in rates:
        if model == "bell_evans":
            k0, xb = params["k0"], params["x_beta"]
            # inverse CDF of the BE survival
            # S(F) = exp(-k0 kBT/(r xb)(exp(F xb/kBT) - 1)) = u
            F = (KB * temperature / xb) * np.log(
                1.0 - r * xb * np.log(u) / (k0 * KB * temperature))
        elif model == "dudko_hummer_szabo":
            # deterministic quantile sampling via a fine CDF grid
            k0, xb, dg, nu = (params["k0"], params["x_beta"],
                              params["dG"], params.get("nu", 2.0 / 3.0))
            grid = np.linspace(0.0, float(dg / (nu * xb)) * 0.99, 4000)
            pdf = dhs_pdf(grid, r, k0, xb, dg, nu, temperature)
            cdf = np.cumsum(pdf) * (grid[1] - grid[0])
            cdf = cdf / cdf[-1]
            F = np.interp(u, cdf, grid)
        else:
            raise ValueError(model)
        forces.extend(float(fi) for fi in F)
        rate_list.extend([float(r)] * events_per_rate)
    forces_a = np.asarray(forces)
    rates_a = np.asarray(rate_list)
    truth = {
        "model": model, "protocol": "ramped_loading",
        "parameters": params, "temperature": temperature,
        "rates": rates_a.tolist(), "rupture_forces": forces_a.tolist(),
        "n_events": int(forces_a.size), "expected_recovery": expected_recovery,
        "expected_failure": expected_failure,
        "rate_span": float(np.max(rates_a) / np.min(rates_a)),
    }
    return SmfsPhantom(
        case_id=case_id, protocol="ramped_loading", model=model,
        time=np.array([]), height=np.array([]), force=forces_a,
        separation=rates_a, truth=truth, expected_recovery=expected_recovery,
        expected_failure=expected_failure,
        metadata={"seed": seed, "events_per_rate": events_per_rate,
                  "narrow_range": narrow_range})


def build_force_clamp(
    case_id: str, rate_at_force: float, force_level: float, n: int, *,
    t_max: float = 5.0, temperature: float = 298.0, seed: int = DEFAULT_SEED,
    all_censored: bool = False, mixed: bool = False,
    expected_recovery: bool = True, expected_failure: str | None = None,
) -> SmfsPhantom:
    """Force-clamp lifetime series from the exponential distribution with
    right censoring at t_max."""
    rng = np.random.default_rng(seed)
    u = rng.random(n)
    if all_censored:
        lt = np.full(n, t_max)
        ce = np.ones(n)
    else:
        lt = -np.log(1.0 - u) / rate_at_force
        ce = (lt >= t_max).astype(float)
        lt = np.minimum(lt, t_max)
    truth = {
        "model": "force_clamp", "protocol": "force_clamp",
        "rate": rate_at_force, "force_level": force_level,
        "temperature": temperature, "lifetimes": lt.tolist(),
        "censored": ce.tolist(), "t_max": t_max, "n": n,
        "expected_recovery": expected_recovery, "expected_failure": expected_failure,
    }
    return SmfsPhantom(
        case_id=case_id, protocol="force_clamp", model="force_clamp",
        time=lt, height=ce, force=np.full(n, force_level),
        separation=np.full(n, float("nan")), truth=truth,
        expected_recovery=expected_recovery, expected_failure=expected_failure,
        metadata={"seed": seed, "mixed": mixed})


def generate_phantoms(seed: int = DEFAULT_SEED) -> dict[str, SmfsPhantom]:
    cases: dict[str, SmfsPhantom] = {}
    Lc1, Lp1 = 100e-9, 0.5e-9
    sep0 = 3.0e-6

    x_max = 0.9 * Lc1  # the nonlinear regime separates (Lc, Lp)
    cases["S01"] = build_polymer_curve(
        "S01", "worm_like_chain", {"Lc": Lc1, "Lp": Lp1}, sep0, x_max)
    cases["S02"] = build_polymer_curve(
        "S02", "worm_like_chain", {"Lc": Lc1, "Lp": Lp1}, sep0, x_max,
        noise=2e-12, seed=seed + 1)
    cases["S03"] = build_polymer_curve(
        "S03", "worm_like_chain", {"Lc": Lc1, "Lp": Lp1}, sep0, x_max,
        noise=2e-12, correlated=True, seed=seed + 2)
    cases["S04"] = build_polymer_curve(
        "S04", "extensible_worm_like_chain",
        {"Lc": Lc1, "Lp": Lp1, "S": 1e-8}, sep0, x_max)
    cases["S05"] = build_polymer_curve(
        "S05", "freely_jointed_chain",
        {"Lc": Lc1, "b": 1e-9, "F_max": 1e-9}, sep0, x_max)
    cases["S06"] = build_polymer_curve(
        "S06", "extensible_freely_jointed_chain",
        {"Lc": Lc1, "b": 1e-9, "Sk": 1e-8, "F_max": 1e-9}, sep0, x_max)
    cases["S07"] = build_polymer_curve(
        "S07", "worm_like_chain", {"Lc": Lc1, "Lp": Lp1}, sep0, x_max,
        drift=2e-14, seed=seed + 3)
    cases["S08"] = build_polymer_curve(
        "S08", "worm_like_chain", {"Lc": Lc1, "Lp": Lp1}, sep0 + 5e-9, x_max,
        expected_recovery=True)  # wrong zero supplied: recovery is biased
        # by the 5 nm offset (extension-zero sensitivity witness)

    cases["S09"] = build_sawtooth(
        "S09", [100e-9, 200e-9], Lp1, sep0, 140e-9)
    cases["S10"] = build_sawtooth(
        "S10", [100e-9, 200e-9, 320e-9], Lp1, sep0, 224e-9)
    cases["S11"] = build_sawtooth(
        "S11", [100e-9, 210e-9], Lp1, sep0, 147e-9, noise=2e-12, seed=seed + 4)
    cases["S12"] = build_sawtooth(
        "S12", [100e-9, 101e-9], Lp1, sep0, 70.7e-9, small_drops=True,
        expected_recovery=False, expected_failure="NO_EVENTS")
    cases["S13"] = build_sawtooth(
        "S13", [100e-9, 200e-9], Lp1, sep0, 140e-9, false_peak=True,
        seed=seed + 5)
    cases["S14"] = build_sawtooth(
        "S14", [100e-9, 200e-9], Lp1, sep0, 140e-9, nonspecific=True,
        seed=seed + 6)
    cases["S15"] = build_sawtooth(
        "S15", [100e-9, 200e-9, 300e-9], Lp1, sep0, 210e-9,
        unresolved_final=True)

    rates = np.geomspace(1e3, 1e6, 4)
    cases["S16"] = build_kinetic_series(
        "S16", "bell_evans", {"k0": 1.0, "x_beta": 1e-9}, rates)
    cases["S17"] = build_kinetic_series(
        "S17", "dudko_hummer_szabo",
        {"k0": 1.0, "x_beta": 1e-9, "dG": 1e-19}, rates)
    cases["S18"] = build_kinetic_series(
        "S18", "bell_evans", {"k0": 1.0, "x_beta": 1e-9},
        np.geomspace(1e5, 1.1e5, 3), narrow_range=True,
        expected_failure="IDENTIFIABILITY_LIMITED")
    cases["S19"] = build_kinetic_series(
        "S19", "dudko_hummer_szabo",
        {"k0": 1.0, "x_beta": 1e-9, "dG": 1e-19},
        np.geomspace(1e5, 1.1e5, 3), narrow_range=True,
        expected_failure="IDENTIFIABILITY_LIMITED")

    cases["S20"] = build_force_clamp("S20", rate_at_force=2.0, force_level=2e-11, n=60)
    cases["S21"] = build_force_clamp(
        "S21", rate_at_force=2.0, force_level=2e-11, n=60, seed=seed + 7)
    cases["S22"] = build_force_clamp(
        "S22", rate_at_force=2.0, force_level=2e-11, n=40, t_max=0.5,
        seed=seed + 8)
    cases["S23"] = build_force_clamp(
        "S23", rate_at_force=2.0, force_level=2e-11, n=30, all_censored=True,
        expected_recovery=False, expected_failure="UNDEFINED_MEDIAN")
    return cases


def serialize(cases: dict[str, SmfsPhantom], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    cases_meta: dict[str, dict[str, object]] = {}
    manifest: dict[str, object] = {
        "schema_version": 1, "family": "force_smfs_phantoms",
        "seed": DEFAULT_SEED, "units": {"time": "s", "force": "N", "height": "m",
                                        "separation": "m", "extension": "m",
                                        "loading_rate": "N/s"},
        "cases": cases_meta,
    }
    arrays: dict[str, np.ndarray] = {}
    for cid, case in sorted(cases.items()):
        cases_meta[cid] = {
            "model": case.model, "protocol": case.protocol,
            "truth": _json_safe(case.truth),
            "expected_recovery": case.expected_recovery,
            "expected_failure": case.expected_failure, "metadata": case.metadata,
        }
        arrays[f"{cid}_time"] = case.time
        arrays[f"{cid}_height"] = case.height
        arrays[f"{cid}_force"] = case.force
        arrays[f"{cid}_separation"] = case.separation
    (out_dir / "smfs_reference.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    payload = {k: np.ascontiguousarray(v, dtype=np.float64)
               for k, v in sorted(arrays.items())}
    np.savez_compressed(out_dir / "smfs_reference.npz", **payload)  # type: ignore[arg-type]


def _json_safe(obj: object) -> object:
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


if __name__ == "__main__":
    import sys

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    serialize(generate_phantoms(), out)
    print("SMFS phantoms written to", out)
