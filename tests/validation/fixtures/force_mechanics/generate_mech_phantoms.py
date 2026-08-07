"""Deterministic mechanical phantoms for FS-F2.

Phantoms are defined in the INDENTATION domain: a chosen indentation grid
delta, force F = model(delta) with exact truth parameters, and the derived
channels separation = zc - delta and height = separation + F/k (k = spring
constant).  This makes the force-indentation relation exactly the frozen
model equation, so clean recovery is well posed.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

DEFAULT_SEED = 20260806
K_SPRING = 10.0
N = 200
DELTA_MAX = 1e-6
ZC = 3e-6


@dataclass
class MechPhantom:
    case_id: str
    model: str
    delta: np.ndarray
    force: np.ndarray
    height: np.ndarray
    separation: np.ndarray
    contact_index: int
    truth: dict
    expected_recovery: bool = True
    expected_ambiguity: bool = False
    expected_failure: str | None = None
    metadata: dict = field(default_factory=dict)


def forward(model: str, delta: np.ndarray, params: dict) -> np.ndarray:
    est = params["E"] / (1.0 - params["poisson"] ** 2)
    delta = np.asarray(delta, dtype=np.float64)
    if model == "hertz_sphere":
        return (4.0 / 3.0) * est * math.sqrt(params["R"]) * delta ** 1.5
    if model == "sneddon_cone":
        return (2.0 * math.tan(params["alpha"]) / math.pi) * est * delta ** 2.0
    if model == "flat_punch":
        return 2.0 * est * params["R"] * delta
    if model == "dmt":
        return (4.0 / 3.0) * est * math.sqrt(params["R"]) * delta ** 1.5 - params["F_adh"]
    if model == "jkr":
        # monotone loading branch parametrized by the contact radius a
        # (same equations as the analytical oracle; independent code)
        r = params["R"]
        w = params["w"]
        dmax = float(np.max(delta)) if delta.size else 0.0
        if dmax <= 0.0:
            return np.zeros_like(delta)
        c = math.sqrt(2 * math.pi * w / est)
        a0 = (2 * math.pi * w * r**2 / est) ** (1.0 / 3.0) if w > 0.0 else 0.0
        a_lo = max(a0, 1e-12)
        a_hi = a_lo
        while a_hi**2 / r - c * math.sqrt(a_hi) < dmax:
            a_hi *= 2.0
        a = np.linspace(a_lo, a_hi, 4096)
        d = a**2 / r - c * np.sqrt(a)
        f = 4 * est * a**3 / (3 * r) - np.sqrt(8 * math.pi * w * est * a**3)
        return np.interp(delta, d, f, left=0.0, right=float(f[-1]))
    raise ValueError(model)


def build(case_id: str, model: str, params: dict, seed: int = DEFAULT_SEED,
          noise: float = 0.0, correlated: bool = False, force_offset: float = 0.0,
          residual_slope: float = 0.0, contact_offset: int = 0,
          truncate: float | None = None, saturation: float | None = None,
          heteroscedastic: bool = False, outlier: tuple[int, float] | None = None,
          expected_recovery: bool = True, expected_ambiguity: bool = False,
          expected_failure: str | None = None, delta_max: float = DELTA_MAX,
          n: int = N) -> MechPhantom:
    """Build on the SEPARATION axis in the FS-F1 trace convention.

    The separation increases along the trace: pre-contact (force-free) from
    sep = ZC - 2*delta_max up to the contact at sep = ZC, then the
    indentation branch delta = max(0, sep - ZC) with force = model(delta).
    The piezo height = separation + force/k stays strictly increasing
    because the cantilever deflection grows more slowly than the piezo
    motion in the indentation regime (F/k << delta).  Indentation =
    separation - contact_coordinate is positive past the contact.  Both the
    height and the separation are monotone, so the FS-F1 preparation
    pipeline (quality gate + work integral) accepts the curve.
    """
    rng = np.random.default_rng(seed)
    h_c = ZC
    sep_lo = h_c - 2.0 * delta_max          # pre-contact region (2x margin)
    sep_hi = h_c + delta_max
    separation = np.linspace(sep_lo, sep_hi, n)
    delta = np.maximum(0.0, separation - h_c)
    # adhesive models are negative at delta == 0 (jump at the contact);
    # the pre-contact region must carry zero force or the FS-F1 baseline
    # correction would subtract the adhesion from the whole branch
    f = np.where(delta > 0.0, forward(model, delta, params), 0.0)
    f = f + force_offset + residual_slope * separation
    if noise:
        raw = rng.normal(0.0, noise, n)
        if correlated:
            kernel = np.ones(5) / 5
            raw = np.convolve(raw, kernel, mode="same")
        if heteroscedastic:
            raw = raw * (1.0 + delta / max(delta_max, 1e-30))
        f = f + raw
    if outlier is not None:
        f[outlier[0]] = f[outlier[0]] + outlier[1]
    if saturation is not None:
        f = np.clip(f, None, saturation)
    height = separation + f / K_SPRING
    contact_index = int(np.flatnonzero(separation >= h_c)[0]) + contact_offset
    contact_index = min(max(contact_index, 2), n - 3)
    truth = {
        "model": model,
        "parameters": params,
        "contact_index": contact_index,
        "contact_coordinate": h_c,
        "delta_max": delta_max,
        "noise_sigma": noise,
        "force_offset": force_offset,
        "residual_slope": residual_slope,
        "expected_recovery": expected_recovery,
        "expected_ambiguity": expected_ambiguity,
        "expected_failure": expected_failure,
    }
    return MechPhantom(
        case_id=case_id, model=model, delta=delta, force=f, height=height,
        separation=separation, contact_index=contact_index, truth=truth,
        expected_recovery=expected_recovery, expected_ambiguity=expected_ambiguity,
        expected_failure=expected_failure,
        metadata={"noise": noise, "correlated": correlated,
                  "force_offset": force_offset, "residual_slope": residual_slope,
                  "contact_offset": contact_offset, "truncate": truncate,
                  "saturation": saturation, "seed": seed},
    )


def generate_phantoms(seed: int = DEFAULT_SEED) -> dict[str, MechPhantom]:
    cases: dict[str, MechPhantom] = {}
    R = 1e-6
    # Indentation-regime (weak-branch) parameters: the cantilever deflection
    # grows more slowly than the piezo motion (F/k << delta), so the
    # separation keeps increasing past the contact and the indentation
    # = separation - contact_coordinate is positive on the contact branch.
    E = 5e3
    nu = 0.3
    alpha = math.radians(20.0)
    cases["M01"] = build("M01", "hertz_sphere", {"E": E, "R": R, "poisson": nu})
    cases["M02"] = build("M02", "sneddon_cone", {"E": E, "alpha": alpha, "poisson": nu})
    cases["M03"] = build("M03", "flat_punch", {"E": E, "R": R, "poisson": nu})
    cases["M04"] = build("M04", "dmt", {"E": E, "R": R, "poisson": nu, "F_adh": 2e-9})
    cases["M05"] = build("M05", "jkr", {"E": E, "R": R, "poisson": nu, "w": 1e-3})
    cases["M06"] = build("M06", "hertz_sphere", {"E": E, "R": R, "poisson": nu},
                         noise=2e-12, seed=seed + 1)
    cases["M07"] = build("M07", "hertz_sphere", {"E": E, "R": R, "poisson": nu},
                         noise=2e-12, correlated=True, seed=seed + 2)
    cases["M08"] = build("M08", "sneddon_cone", {"E": E, "alpha": alpha, "poisson": nu},
                         force_offset=1e-10, residual_slope=1e-6)
    cases["M09"] = build("M09", "hertz_sphere", {"E": E, "R": R, "poisson": nu},
                         contact_offset=3, expected_recovery=True)
    cases["M10"] = build("M10", "hertz_sphere", {"E": E, "R": R, "poisson": nu},
                         noise=1e-12, outlier=(60, 8e-12))
    cases["M11"] = build("M11", "hertz_sphere", {"E": E, "R": R, "poisson": nu},
                         saturation=5e-9, expected_failure="SATURATED_SIGNAL")
    cases["M12"] = build("M12", "hertz_sphere", {"E": E, "R": R, "poisson": nu},
                         delta_max=2e-7, expected_recovery=True)
    cases["M13"] = build("M13", "hertz_sphere", {"E": E, "R": R, "poisson": nu},
                         noise=2e-12, heteroscedastic=True)
    cases["M14"] = build("M14", "sneddon_cone", {"E": E, "alpha": alpha, "poisson": nu},
                         noise=1e-12)
    # misspecification: fit a hertz model to cone data
    cases["M15"] = build("M15", "sneddon_cone", {"E": E, "alpha": alpha, "poisson": nu},
                         noise=0.0, expected_recovery=False,
                         expected_failure="MODEL_MISSPECIFIED")
    # ambiguity: dmt vs hertz over a short window; the honest comparison
    # prefers dmt (its fit is exact), so no ambiguity is expected
    cases["M16"] = build("M16", "dmt", {"E": E, "R": R, "poisson": nu, "F_adh": 5e-10},
                         delta_max=1e-7, expected_ambiguity=False)
    # bound case: very shallow indentation with noise; the contact branch
    # is too weak for the FS-F1 contact ensemble (typed failure witness)
    cases["M17"] = build("M17", "hertz_sphere", {"E": E, "R": R, "poisson": nu},
                         delta_max=2e-8, noise=1e-10, seed=seed + 5,
                         expected_recovery=False,
                         expected_failure="CONTACT_NOT_FOUND")
    # failed preparation case: flat curve (no contact branch); separation
    # and height stay monotone increasing so the FS-F1 eligibility gate and
    # the work integral pass and only the contact detection fails.
    sep_flat = np.linspace(ZC - 2e-6, ZC + 1e-6, N)
    flat_f = np.full(N, 5e-10)
    height_flat = sep_flat + flat_f / K_SPRING
    cases["M18"] = MechPhantom(
        case_id="M18", model="none", delta=np.zeros(N), force=flat_f,
        height=height_flat, separation=sep_flat, contact_index=0,
        truth={"model": "none", "parameters": {}, "contact_index": 0,
               "contact_coordinate": ZC, "delta_max": 1e-6, "noise_sigma": 0.0,
               "force_offset": 5e-10, "residual_slope": 0.0,
               "expected_recovery": False, "expected_ambiguity": False,
               "expected_failure": "CONTACT_NOT_FOUND"},
        expected_recovery=False, expected_failure="CONTACT_NOT_FOUND",
        metadata={})
    return cases


def serialize(cases: dict[str, MechPhantom], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    arrays: dict[str, np.ndarray] = {}
    cases_meta: dict[str, dict[str, object]] = {}
    manifest: dict[str, object] = {
        "schema_version": 1, "family": "force_mechanics_phantoms",
        "seed": DEFAULT_SEED, "units": {"force": "N", "height": "m",
        "separation": "m", "indentation": "m", "modulus": "Pa"},
        "cases": cases_meta,
    }
    for cid, case in sorted(cases.items()):
        cases_meta[cid] = {
            "model": case.model, "truth": case.truth,
            "expected_recovery": case.expected_recovery,
            "expected_ambiguity": case.expected_ambiguity,
            "expected_failure": case.expected_failure, "metadata": case.metadata,
            "contact_index": case.contact_index,
        }
        arrays[f"{cid}_force"] = case.force
        arrays[f"{cid}_height"] = case.height
        arrays[f"{cid}_separation"] = case.separation
    (out_dir / "force_mechanics_reference.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    payload = {k: np.ascontiguousarray(v, dtype=np.float64)
               for k, v in sorted(arrays.items())}
    # numpy 2.5 stubs type savez_compressed kwargs narrowly; the fixture is
    # not part of the production package, so the stub quirk is ignored here
    np.savez_compressed(out_dir / "force_mechanics_reference.npz", **payload)  # type: ignore[arg-type]


if __name__ == "__main__":
    import sys

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    serialize(generate_phantoms(), out)
    print("mechanical phantoms written to", out)
