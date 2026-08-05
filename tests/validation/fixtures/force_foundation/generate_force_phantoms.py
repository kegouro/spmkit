"""Deterministic shared force-phantom family for the SPMKit force foundation
(FS-F1).

Generates force curves with known ground truth for:

  * segment split (approach/retract indices, turning point);
  * calibrated force (when generated in raw volts);
  * tip-sample separation;
  * baseline parameters (intercept, slope, residual noise scale);
  * contact index and physical coordinate;
  * event forces and indices (snap-in, pull-off, ruptures);
  * integrated work (closed form where possible);
  * expected QC failure reasons.

Physics is expressed in SI units (height in m, force in N, deflection in m,
spring constant in N/m, InVOLS in m/V).  A deterministic seed makes every
phantom reproducible.  The generator is not tuned to any single estimator:
the contact branch is a documented piecewise/Hertz-like model and the truth
follows the construction parameters exactly.

The generator never imports production code; production never imports the
generator or its fixtures.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

DEFAULT_SEED = 20260805
BASELINE_OFFSET = 5.0e-10  # N
BASELINE_SLOPE = 1.0e-4  # N/m
CONTACT_COEFF = 5.0  # N / m^1.5 (Hertz-like branch)
K_SPRING = 0.1  # N/m
INVOLS = 3.0e-8  # m/V
N = 200  # samples per segment (default)
Z_MIN, Z_MAX = 0.0, 5.0e-6  # height range (m)
NOISE_SIGMA = 2.0e-11  # N (default gaussian noise scale)


@dataclass(frozen=True)
class PhantomTruth:
    approach_indices: tuple[int, ...]
    retract_indices: tuple[int, ...]
    turning_point_index: int
    contact_index_approach: int
    contact_coordinate: float
    baseline_intercept: float
    baseline_slope: float
    baseline_noise_sigma: float
    snap_in_index: int | None = None
    snap_in_force: float | None = None
    pull_off_index: int | None = None
    pull_off_force: float | None = None
    rupture_forces: tuple[float, ...] = ()
    work_approach: float = 0.0
    work_retract: float = 0.0
    work_hysteresis: float = 0.0
    expected_qc_failures: tuple[str, ...] = ()
    calibration_invols: float | None = None
    calibration_k: float | None = None
    is_raw_volts: bool = False


@dataclass
class PhantomCase:
    case_id: str
    kind: str
    approach_height: np.ndarray
    approach_force: np.ndarray  # force_n (or raw volts when is_raw_volts)
    retract_height: np.ndarray | None
    retract_force: np.ndarray | None
    is_raw_volts: bool = False
    invols: float = INVOLS
    spring_constant: float = K_SPRING
    truth: PhantomTruth = field(
        default_factory=lambda: PhantomTruth((), (), 0, 0, 0.0, 0.0, 0.0, 0.0)
    )


def _gauss(rng: np.random.Generator, n: int, sigma: float) -> np.ndarray:
    return rng.normal(0.0, sigma, n)


def _correlated(rng: np.random.Generator, n: int, sigma: float, width: int = 5) -> np.ndarray:
    raw = rng.normal(0.0, sigma, n + width)
    kernel = np.ones(width) / width
    return np.convolve(raw, kernel, mode="valid")[:n]


def _contact_branch(
    z: np.ndarray, zc: float, offset: float, slope: float, coeff: float = CONTACT_COEFF
) -> np.ndarray:
    """Piecewise model: linear baseline + Hertz-like 3/2 contact branch."""
    out = offset + slope * z
    delta = z - zc
    contact = delta > 0.0
    out[contact] = offset + slope * z[contact] + coeff * delta[contact] ** 1.5
    return out


def _make_curve(
    rng: np.random.Generator,
    n: int,
    z_min: float,
    z_max: float,
    offset: float,
    slope: float,
    contact_fraction: float,
    noise_sigma: float,
    coeff: float = CONTACT_COEFF,
    correlated: bool = False,
    snap_in: tuple[int, float] | None = None,
    pull_off: tuple[int, float] | None = None,
    retract_branch: str = "mirror",
    rupture_forces: tuple[float, ...] = (),
    saturation: float | None = None,
    flat_turn: int = 0,
    lag_plateau: int = 0,
    nonmonotonic: int | None = None,
    hysteresis_scale: float = 0.0,
):
    """Build approach/retract height+force with truth.

    Returns (z_appr, f_appr, z_retr, f_retr, contact_idx, baseline_noise_scale).
    """
    z = np.linspace(z_min, z_max, n)
    if flat_turn:
        z = np.sort(np.concatenate([z[: n - flat_turn], np.full(flat_turn, z_max)]))
    if lag_plateau:
        z = np.concatenate([z[: n - lag_plateau], np.full(lag_plateau, z[-1])])
    contact_idx = int(round(n * contact_fraction))
    f = _contact_branch(z, z[contact_idx], offset, slope, coeff)
    noise = _correlated(rng, n, noise_sigma) if correlated else _gauss(rng, n, noise_sigma)
    f = f + noise
    if snap_in is not None:
        si_idx, si_force = snap_in
        f[si_idx] = f[si_idx] + si_force
    if saturation is not None:
        f = np.clip(f, -saturation, saturation)
    if nonmonotonic is not None:
        z = z.copy()
        z[nonmonotonic], z[nonmonotonic - 1] = z[nonmonotonic - 1], z[nonmonotonic]
    # retract
    z_r = z[::-1].copy()
    if retract_branch == "mirror":
        f_r = f[::-1].copy()
    else:  # hysteresis: softened retract branch
        f_r = _contact_branch(
            z_r, z_r[n - 1 - contact_idx], offset, slope, coeff * (1.0 - hysteresis_scale)
        )
        f_r = f_r + _gauss(rng, n, noise_sigma)
    if pull_off is not None:
        po_idx, po_force = pull_off
        # pull-off is the most negative force: set a deep minimum at po_idx
        f_r[po_idx] = f_r[po_idx] + po_force
    for rf in rupture_forces:
        # rupture steps: subtract a step after the pull-off region
        idx = int(round(n * 0.75))
        f_r[idx:] = f_r[idx:] + rf
    if saturation is not None:
        f_r = np.clip(f_r, -saturation, saturation)
    return z, f, z_r, f_r, contact_idx, noise_sigma


def _closed_form_work(z: np.ndarray, f: np.ndarray, zc: float) -> float:
    """Closed-form-ish work over the contact region (Hertz-like 3/2 branch).

    For the noiseless branch F = offset + slope*z + c*delta^1.5 the work over
    [zc, z_max] is the integral of the full branch; the baseline part cancels
    in the hysteresis difference, and the contact part integrates to
    (2/5) c (z_max - zc)^2.5.  For the discrete phantom the truth is the
    trapezoid of the noiseless arrays restricted to the contact domain.
    """
    mask = z >= zc
    if mask.sum() < 2:
        return 0.0
    return float(np.trapezoid(f[mask], z[mask]))


def generate_phantoms(seed: int = DEFAULT_SEED) -> dict[str, PhantomCase]:
    rng = np.random.default_rng(seed)
    cases: dict[str, PhantomCase] = {}
    n = N

    def add(
        case_id: str,
        kind: str,
        z_a: np.ndarray,
        f_a: np.ndarray,
        z_r: np.ndarray | None,
        f_r: np.ndarray | None,
        contact_idx: int,
        offset: float,
        slope: float,
        noise_sigma: float,
        snap_in: tuple[int, float] | None = None,
        pull_off: tuple[int, float] | None = None,
        ruptures: tuple[float, ...] = (),
        work_truth: tuple[float, float, float] | None = None,
        qc_failures: tuple[str, ...] = (),
        is_raw: bool = False,
        invols: float = INVOLS,
        k: float = K_SPRING,
    ) -> None:
        # estimator-consistent truth: the first sample whose model force
        # deviates above the baseline (the physical surface sits between the
        # last baseline sample and this index)
        n_actual = int(z_a.size)
        contact_idx_est = min(contact_idx + 1, n_actual - 1)
        zc = float(z_a[contact_idx_est])
        truth = PhantomTruth(
            approach_indices=tuple(range(n_actual)),
            retract_indices=(tuple(range(n_actual, 2 * n_actual)) if z_r is not None else ()),
            turning_point_index=n_actual,
            contact_index_approach=contact_idx_est,
            contact_coordinate=zc,
            baseline_intercept=offset,
            baseline_slope=slope,
            baseline_noise_sigma=noise_sigma,
            snap_in_index=snap_in[0] if snap_in else None,
            snap_in_force=snap_in[1] if snap_in else None,
            pull_off_index=(n + pull_off[0]) if pull_off else None,
            pull_off_force=pull_off[1] if pull_off else None,
            rupture_forces=ruptures,
            expected_qc_failures=qc_failures,
            calibration_invols=invols if is_raw else None,
            calibration_k=k if is_raw else None,
            is_raw_volts=is_raw,
        )
        if work_truth is not None:
            object.__setattr__(truth, "work_approach", work_truth[0])
            object.__setattr__(truth, "work_retract", work_truth[1])
            object.__setattr__(truth, "work_hysteresis", work_truth[2])
        cases[case_id] = PhantomCase(
            case_id=case_id,
            kind=kind,
            approach_height=z_a,
            approach_force=f_a,
            retract_height=z_r,
            retract_force=f_r,
            is_raw_volts=is_raw,
            invols=invols,
            spring_constant=k,
            truth=truth,
        )

    # ---- baseline/contact family ------------------------------------------
    z, f, z_r, f_r, ci, ns = _make_curve(rng, n, Z_MIN, Z_MAX, 0.0, 0.0, 0.3, 0.0)
    wa = _closed_form_work(z, f, float(z[ci]))
    wr = _closed_form_work(z_r, f_r, float(z_r[n - 1 - ci]))
    add(
        "P01", "clean_contact", z, f, z_r, f_r, ci, 0.0, 0.0, 0.0, work_truth=(wa, wr, abs(wa - wr))
    )

    z, f, z_r, f_r, ci, ns = _make_curve(rng, n, Z_MIN, Z_MAX, 3e-10, 0.0, 0.3, 0.0)
    wa = _closed_form_work(z, f, float(z[ci]))
    wr = _closed_form_work(z_r, f_r, float(z_r[n - 1 - ci]))
    add(
        "P02",
        "baseline_offset_positive",
        z,
        f,
        z_r,
        f_r,
        ci,
        3e-10,
        0.0,
        0.0,
        work_truth=(wa, wr, abs(wa - wr)),
    )

    z, f, z_r, f_r, ci, ns = _make_curve(rng, n, Z_MIN, Z_MAX, -3e-10, 0.0, 0.3, 0.0)
    add("P03", "baseline_offset_negative", z, f, z_r, f_r, ci, -3e-10, 0.0, 0.0)

    z, f, z_r, f_r, ci, ns = _make_curve(rng, n, Z_MIN, Z_MAX, 1e-10, 1.5e-4, 0.3, 0.0)
    add("P04", "baseline_slope_positive", z, f, z_r, f_r, ci, 1e-10, 1.5e-4, 0.0)

    z, f, z_r, f_r, ci, ns = _make_curve(rng, n, Z_MIN, Z_MAX, 1e-10, -1.2e-4, 0.3, 0.0)
    add("P05", "baseline_slope_negative", z, f, z_r, f_r, ci, 1e-10, -1.2e-4, 0.0)

    z, f, z_r, f_r, ci, ns = _make_curve(rng, n, Z_MIN, Z_MAX, 5e-10, 1e-4, 0.3, 0.0)
    add("P06", "temporal_drift_linear", z, f, z_r, f_r, ci, 5e-10, 1e-4, 0.0)

    # ---- noise family ------------------------------------------------------
    z, f, z_r, f_r, ci, ns = _make_curve(rng, n, Z_MIN, Z_MAX, 5e-10, 1e-4, 0.3, NOISE_SIGMA)
    add("P07", "gaussian_noise", z, f, z_r, f_r, ci, 5e-10, 1e-4, NOISE_SIGMA)

    z, f, z_r, f_r, ci, ns = _make_curve(
        rng, n, Z_MIN, Z_MAX, 5e-10, 1e-4, 0.3, NOISE_SIGMA, correlated=True
    )
    add("P08", "correlated_noise", z, f, z_r, f_r, ci, 5e-10, 1e-4, NOISE_SIGMA)

    # ---- calibration -------------------------------------------------------
    z, f, z_r, f_r, ci, ns = _make_curve(rng, n, Z_MIN, Z_MAX, 5e-10, 1e-4, 0.3, 0.0)
    raw_v = f / (K_SPRING * INVOLS)
    raw_v_r = f_r / (K_SPRING * INVOLS)
    add("P09", "calibration_scaling", z, raw_v, z_r, raw_v_r, ci, 5e-10, 1e-4, 0.0, is_raw=True)

    # ---- geometry / turning point ------------------------------------------
    z, f, z_r, f_r, ci, ns = _make_curve(
        rng, n, Z_MIN, Z_MAX, 5e-10, 1e-4, 0.3, 0.0, lag_plateau=12
    )
    add("P10", "approach_retract_lag", z, f, z_r, f_r, ci, 5e-10, 1e-4, 0.0)

    z, f, z_r, f_r, ci, ns = _make_curve(rng, n, Z_MIN, Z_MAX, 5e-10, 1e-4, 0.3, 0.0, flat_turn=16)
    add("P11", "flat_turning_point", z, f, z_r, f_r, ci, 5e-10, 1e-4, 0.0)

    z, f, z_r, f_r, ci, ns = _make_curve(
        rng, n, Z_MIN, Z_MAX, 5e-10, 1e-4, 0.3, 0.0, nonmonotonic=n // 2
    )
    add(
        "P12",
        "nonmonotonic_coordinate",
        z,
        f,
        z_r,
        f_r,
        ci,
        5e-10,
        1e-4,
        0.0,
        qc_failures=("NONMONOTONIC_COORDINATE",),
    )

    # ---- events ------------------------------------------------------------
    z, f, z_r, f_r, ci, ns = _make_curve(
        rng,
        n,
        Z_MIN,
        Z_MAX,
        5e-10,
        1e-4,
        0.3,
        0.0,
        snap_in=(40, -2e-10),
        pull_off=(n - 40, -1.5e-9),
    )
    add(
        "P13",
        "snap_in_and_pull_off",
        z,
        f,
        z_r,
        f_r,
        ci,
        5e-10,
        1e-4,
        0.0,
        snap_in=(40, -2e-10),
        pull_off=(n - 40, -1.5e-9),
    )

    z, f, z_r, f_r, ci, ns = _make_curve(
        rng, n, Z_MIN, Z_MAX, 5e-10, 1e-4, 0.3, 0.0, snap_in=(55, -3e-10)
    )
    add("P14", "snap_in_only", z, f, z_r, f_r, ci, 5e-10, 1e-4, 0.0, snap_in=(55, -3e-10))

    z, f, z_r, f_r, ci, ns = _make_curve(
        rng, n, Z_MIN, Z_MAX, 5e-10, 1e-4, 0.3, 0.0, pull_off=(n - 60, -2e-9)
    )
    add("P15", "pull_off_only", z, f, z_r, f_r, ci, 5e-10, 1e-4, 0.0, pull_off=(n - 60, -2e-9))

    z, f, z_r, f_r, ci, ns = _make_curve(
        rng,
        n,
        Z_MIN,
        Z_MAX,
        5e-10,
        1e-4,
        0.3,
        0.0,
        pull_off=(n - 50, -2e-9),
        rupture_forces=(1e-9, 6e-10),
    )
    add(
        "P16",
        "multiple_ruptures",
        z,
        f,
        z_r,
        f_r,
        ci,
        5e-10,
        1e-4,
        0.0,
        pull_off=(n - 50, -2e-9),
        ruptures=(1e-9, 6e-10),
    )

    z, f, z_r, f_r, ci, ns = _make_curve(
        rng, n, Z_MIN, Z_MAX, 5e-10, 1e-4, 0.3, 0.0, pull_off=(n - 70, -2e-9), hysteresis_scale=0.2
    )
    add(
        "P17",
        "adhesion_tail_hysteresis",
        z,
        f,
        z_r,
        f_r,
        ci,
        5e-10,
        1e-4,
        0.0,
        pull_off=(n - 70, -2e-9),
    )

    # ---- saturation / degenerate ------------------------------------------
    z, f, z_r, f_r, ci, ns = _make_curve(
        rng, n, Z_MIN, Z_MAX, 5e-10, 1e-4, 0.3, 0.0, saturation=2e-9
    )
    add(
        "P18", "saturation", z, f, z_r, f_r, ci, 5e-10, 1e-4, 0.0, qc_failures=("SATURATED_SIGNAL",)
    )

    z, f, z_r, f_r, ci, ns = _make_curve(rng, n, Z_MIN, Z_MAX, 5e-10, 1e-4, 0.3, 0.0)
    add(
        "P19",
        "missing_retract",
        z,
        f,
        None,
        None,
        ci,
        5e-10,
        1e-4,
        0.0,
        qc_failures=("MISSING_RETRACT",),
    )

    z, f, z_r, f_r, ci, ns = _make_curve(rng, n, Z_MIN, Z_MAX, 5e-10, 1e-4, 0.3, 0.0)
    add(
        "P20",
        "missing_approach",
        z_r,
        f_r,
        None,
        None,
        n - 1 - ci,
        5e-10,
        1e-4,
        0.0,
        qc_failures=("MISSING_APPROACH",),
    )

    z, f, z_r, f_r, ci, ns = _make_curve(rng, 24, Z_MIN, Z_MAX, 5e-10, 1e-4, 0.5, 0.0)
    add(
        "P21",
        "short_baseline",
        z,
        f,
        z_r,
        f_r,
        ci,
        5e-10,
        1e-4,
        0.0,
        qc_failures=("CONTACT_NOT_FOUND",),
    )

    z, f, z_r, f_r, ci, ns = _make_curve(rng, n, Z_MIN, Z_MAX, 5e-10, 1e-4, 0.05, 0.0)
    add("P22", "contact_near_boundary", z, f, z_r, f_r, ci, 5e-10, 1e-4, 0.0)

    z, f, z_r, f_r, ci, ns = _make_curve(rng, n, Z_MIN, Z_MAX, 5e-10, 1e-4, 0.95, 0.0)
    add(
        "P23",
        "no_contact_flat",
        z,
        np.full(n, 5e-10),
        z_r,
        np.full(n, 5e-10),
        n - 1,
        5e-10,
        0.0,
        0.0,
        qc_failures=("CONTACT_NOT_FOUND",),
    )

    z = np.linspace(Z_MIN, Z_MAX, n)
    np.zeros(n)
    neg = np.zeros(n)
    neg[::2] = -0.0
    add(
        "P24",
        "signed_zero",
        z,
        neg,
        z_r,
        neg[::-1].copy(),
        0,
        0.0,
        0.0,
        0.0,
        qc_failures=("CONTACT_NOT_FOUND",),
    )

    z, f, z_r, f_r, ci, ns = _make_curve(rng, n, Z_MIN, Z_MAX, 1e-6, 0.5, 0.3, 0.0)
    add("P25", "large_si", z, f, z_r, f_r, ci, 1e-6, 0.5, 0.0)

    z, f, z_r, f_r, ci, ns = _make_curve(rng, n, Z_MIN, Z_MAX, 2e-12, 1e-7, 0.3, 0.0)
    add("P26", "small_si", z, f, z_r, f_r, ci, 2e-12, 1e-7, 0.0)

    # piecewise-linear contact branch (clean piecewise truth)
    z, f, z_r, f_r, ci, ns = _make_curve(rng, n, Z_MIN, Z_MAX, 5e-10, 1e-4, 0.3, 0.0)
    add("P27", "hertz_like_clean", z, f, z_r, f_r, ci, 5e-10, 1e-4, 0.0)

    return cases


def serialize(cases: dict[str, PhantomCase], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "schema_version": 1,
        "family": "force_foundation_phantoms",
        "seed": DEFAULT_SEED,
        "units": {"height": "m", "force": "N", "deflection": "m", "separation": "m"},
        "cases": {},
    }
    arrays: dict[str, np.ndarray] = {}
    for cid, case in sorted(cases.items()):
        t = case.truth
        manifest["cases"][cid] = {
            "kind": case.kind,
            "is_raw_volts": case.is_raw_volts,
            "invols": case.invols,
            "spring_constant": case.spring_constant,
            "truth": {
                "approach_indices": list(t.approach_indices),
                "retract_indices": list(t.retract_indices),
                "turning_point_index": t.turning_point_index,
                "contact_index_approach": t.contact_index_approach,
                "contact_coordinate": t.contact_coordinate,
                "baseline_intercept": t.baseline_intercept,
                "baseline_slope": t.baseline_slope,
                "baseline_noise_sigma": t.baseline_noise_sigma,
                "snap_in_index": t.snap_in_index,
                "snap_in_force": t.snap_in_force,
                "pull_off_index": t.pull_off_index,
                "pull_off_force": t.pull_off_force,
                "rupture_forces": list(t.rupture_forces),
                "work_approach": t.work_approach,
                "work_retract": t.work_retract,
                "work_hysteresis": t.work_hysteresis,
                "expected_qc_failures": list(t.expected_qc_failures),
            },
        }
        arrays[f"{cid}_approach_height"] = case.approach_height
        arrays[f"{cid}_approach_force"] = case.approach_force
        if case.retract_height is not None:
            arrays[f"{cid}_retract_height"] = case.retract_height
            arrays[f"{cid}_retract_force"] = case.retract_force
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "force_phantoms_reference.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    np.savez_compressed(
        out_dir / "force_phantoms_reference.npz",
        **{k: np.ascontiguousarray(v, dtype=np.float64) for k, v in sorted(arrays.items())},
    )


if __name__ == "__main__":
    import sys

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    serialize(generate_phantoms(), out)
    print("phantoms written to", out)
