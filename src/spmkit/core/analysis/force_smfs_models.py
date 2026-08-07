"""FS-F4 polymer models, molecular extension and SMFS fit windows.

Frozen equations (SI units):

WLC (Marko-Siggia loading relation):
  F(x) = (k_B T / Lp) [1/(4 (1 - x/Lc)^2) - 1/4 + x/Lc]
  valid for 0 <= x < Lc; never evaluated at or beyond the singularity.

EXTENSIBLE WLC (implicit, Odijk-style):
  F(x) = (k_B T / Lp) [1/(4 (1 - x/Lc + F/S)^2) - 1/4 + x/Lc - F/S]
  S = stretch modulus (N); solved numerically per point (brentq on the
  domain 1 - x/Lc + F/S > 0); S -> inf reduces to the WLC.

FJC:
  x/Lc = coth(y) - 1/y,  y = F b / (k_B T)
  b = Kuhn length (m); the Langevin function is evaluated stably near
  y = 0 (series u/3) and for large y.

EXTENSIBLE FJC:
  x/Lc = L(y) + F/Sk
  Sk = segment stretch force scale (N); Sk -> inf reduces to the FJC;
  residuals live in the extension space (documented convention).

Molecular extension contract: extension = retract separation minus an
explicit tether zero.  Supported reference policies: "offset" (physical
offset in m), "index" (reference sample index), "pre_event" (caller-supplied
pre-event branch start index), "estimator" (zero-force crossing of the
retract branch with its own diagnostics).  The tether zero is never inferred
silently from the contact.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import brentq, curve_fit

from spmkit.core.analysis.force_prepare import ForcePreparationResult
from spmkit.core.analysis.force_smfs_errors import (
    EMPTY_WINDOW,
    INSUFFICIENT_POINTS,
    INVALID_MODEL_PARAMETER,
    INVALID_REFERENCE_POLICY,
    MISSING_RETRACT,
    NONFINITE_INPUT,
    OPTIMIZATION_FAILED,
    POLYMER_SINGULARITY,
    UNRESOLVED_TETHER_ZERO,
    SmfsError,
)

#: Boltzmann constant (J/K)
KB = 1.380649e-23

EXTENSION_REFERENCE_POLICIES = ("offset", "index", "pre_event", "estimator")
POLYMER_MODELS = ("worm_like_chain", "extensible_worm_like_chain",
                  "freely_jointed_chain", "extensible_freely_jointed_chain")


@dataclass(frozen=True)
class MolecularExtensionResult:
    """Molecular extension of a retract branch with an explicit zero policy."""

    extension: np.ndarray
    separation: np.ndarray
    force: np.ndarray
    time: np.ndarray | None
    retract_indices: np.ndarray
    reference_policy: str
    reference_coordinate: float
    reference_index: int | None
    valid: np.ndarray
    units: str = "m"
    warnings: tuple[str, ...] = ()
    provenance: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SMFSFitWindowResult:
    """Explicit polymer fit window on the molecular extension axis."""

    start_index: int
    end_index: int
    extension_min: float
    extension_max: float
    force_min: float
    force_max: float
    included: np.ndarray
    excluded_reasons: tuple[str, ...]
    n_points: int
    warnings: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# molecular extension
# ---------------------------------------------------------------------------


def _retract_arrays(
        prepared: ForcePreparationResult
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, object]:
    retract = prepared.curve.retract
    if retract is None:
        raise SmfsError(MISSING_RETRACT, "curve has no retract segment")
    if retract.separation is None or retract.force is None:
        raise SmfsError(MISSING_RETRACT, "retract is not prepared (no separation/force)")
    sep = np.asarray(retract.separation, dtype=np.float64)
    f = np.asarray(retract.force, dtype=np.float64)
    t = None if retract.time is None else np.asarray(retract.time, dtype=np.float64)
    if not (np.isfinite(sep).all() and np.isfinite(f).all()):
        raise SmfsError(NONFINITE_INPUT, "non-finite retract separation/force")
    if t is not None and not np.isfinite(t).all():
        raise SmfsError(NONFINITE_INPUT, "non-finite retract time")
    return sep, f, t, retract


def compute_molecular_extension(
    prepared: ForcePreparationResult,
    *,
    reference: str = "index",
    reference_value: float | None = None,
    segment: str = "retract",
    estimator_noise_sigma: float | None = None,
) -> MolecularExtensionResult:
    """Molecular extension of the retract branch with an explicit zero policy.

    ``reference`` policies:
    - "offset": extension = separation - reference_value (physical offset, m);
    - "index": extension = separation - separation[reference_value];
    - "pre_event": same as "index" but semantically the caller-supplied
      pre-event branch start (recorded in provenance);
    - "estimator": the tether zero is the retract zero-force crossing after
      the pull-off (the last index where the corrected force crosses zero
      from negative to positive while scanning the pull order); the estimator
      reports its own diagnostics.

    The reference is never inferred from the contact.
    """
    if reference not in EXTENSION_REFERENCE_POLICIES:
        raise SmfsError(INVALID_REFERENCE_POLICY, f"unknown reference policy {reference!r}")
    if segment != "retract":
        raise SmfsError(INVALID_REFERENCE_POLICY,
                        "SMFS extension is defined on the retract branch only")
    sep, f, t, retract = _retract_arrays(prepared)
    warnings: list[str] = []
    ref_coord: float
    ref_idx: int | None = None

    if reference == "offset":
        if reference_value is None:
            raise SmfsError(UNRESOLVED_TETHER_ZERO,
                            "reference='offset' requires reference_value (m)")
        ref_coord = float(reference_value)
    elif reference in ("index", "pre_event"):
        if reference_value is None:
            raise SmfsError(UNRESOLVED_TETHER_ZERO,
                            f"reference={reference!r} requires reference_value (index)")
        idx = int(reference_value)
        if idx < 0 or idx >= sep.size:
            raise SmfsError(UNRESOLVED_TETHER_ZERO, "reference index outside the retract")
        ref_coord = float(sep[idx])
        ref_idx = idx
    else:  # estimator
        # the pull order: the retract separation may be stored increasing or
        # decreasing; the estimator works on the pull-ordered branch (the
        # molecular extension increases during the pull)
        pull = np.argsort(sep, kind="stable")
        f_pull = f[pull]
        sep_pull = sep[pull]
        if estimator_noise_sigma is None:
            sigma = float(np.std(f_pull[-max(3, f_pull.size // 10):])) or 1e-12
        else:
            sigma = float(estimator_noise_sigma)
        # last zero crossing from negative to positive in the pull order
        crossings = np.flatnonzero((f_pull[:-1] <= 0.0) & (f_pull[1:] > 0.0))
        if crossings.size == 0:
            raise SmfsError(UNRESOLVED_TETHER_ZERO,
                            "estimator: no zero-force crossing on the retract")
        idx_pull = int(crossings[-1])
        ref_coord = float(sep_pull[idx_pull])
        ref_idx = int(pull[idx_pull])
        warnings.append(
            f"estimator: tether zero = retract zero-force crossing at "
            f"separation {ref_coord:.4e} m (noise sigma {sigma:.2e} N)")

    ext = sep - ref_coord
    if not np.all(np.diff(ext[np.argsort(sep, kind="stable")]) >= -1e-12):
        warnings.append("extension is not monotone in the pull order; "
                        "check the tether zero policy")
    valid = np.isfinite(ext) & np.isfinite(f)
    return MolecularExtensionResult(
        extension=ext, separation=sep, force=f, time=t,
        retract_indices=np.arange(sep.size),
        reference_policy=reference, reference_coordinate=ref_coord,
        reference_index=ref_idx, valid=valid, warnings=tuple(warnings),
        provenance={"segment": segment, "reference_policy": reference,
                    "tether_zero": ref_coord})


def select_smfs_fit_windows(
    extension: np.ndarray,
    force: np.ndarray,
    *,
    min_extension: float | None = None,
    max_extension: float | None = None,
    min_force: float | None = None,
    max_force: float | None = None,
    min_points: int = 10,
    window_label: str | None = None,
) -> SMFSFitWindowResult:
    """Explicit polymer fit window on the molecular extension axis.

    The window is the contiguous span of samples satisfying all bounds;
    negative-extension samples are always excluded (the polymer model domain
    starts at the tether zero); fewer than min_points raises
    INSUFFICIENT_POINTS; the empty window raises EMPTY_WINDOW.
    """
    ext = np.asarray(extension, dtype=np.float64)
    f = np.asarray(force, dtype=np.float64)
    if ext.ndim != 1 or ext.size != f.size or ext.size == 0:
        raise SmfsError(NONFINITE_INPUT, "extension/force must be equal-length 1-D arrays")
    included = np.ones(ext.size, dtype=bool)
    included &= ext >= 0.0
    if min_extension is not None:
        included &= ext >= min_extension
    if max_extension is not None:
        included &= ext <= max_extension
    if min_force is not None:
        included &= f >= min_force
    if max_force is not None:
        included &= f <= max_force
    idx = np.flatnonzero(included)
    if idx.size == 0:
        raise SmfsError(EMPTY_WINDOW, "no samples satisfy the window")
    start, end = int(idx[0]), int(idx[-1])
    if end - start + 1 < min_points:
        raise SmfsError(INSUFFICIENT_POINTS,
                        f"window has {end - start + 1} points < min_points={min_points}")
    return SMFSFitWindowResult(
        start_index=start, end_index=end,
        extension_min=float(ext[start]), extension_max=float(ext[end]),
        force_min=float(np.min(f[idx])), force_max=float(np.max(f[idx])),
        included=included, excluded_reasons=(),
        n_points=int(idx.size),
        warnings=(f"excluded {ext.size - idx.size} sample(s) outside the window",)
        if idx.size < ext.size else ())


# ---------------------------------------------------------------------------
# polymer forward models
# ---------------------------------------------------------------------------


def wlc_force(extension: np.ndarray, contour_length: float,
              persistence_length: float, temperature: float = 298.0) -> np.ndarray:
    """Marko-Siggia WLC loading relation (N)."""
    x = np.asarray(extension, dtype=np.float64)
    if contour_length <= 0.0 or persistence_length <= 0.0 or temperature <= 0.0:
        raise SmfsError(INVALID_MODEL_PARAMETER,
                        "WLC: Lc > 0, Lp > 0, T > 0 required")
    if np.any(x < 0.0):
        raise SmfsError(POLYMER_SINGULARITY, "WLC: extension must be non-negative")
    if np.any(x >= contour_length):
        raise SmfsError(POLYMER_SINGULARITY,
                        "WLC: extension must stay below the contour length")
    r = x / contour_length
    return (KB * temperature / persistence_length) * (
        1.0 / (4.0 * (1.0 - r) ** 2) - 0.25 + r)


def _ewlc_residual(force_val: float, x: float, contour_length: float,
                   persistence_length: float, stretch_modulus: float,
                   temperature: float) -> float:
    """Implicit eWLC residual: F - (k_BT/Lp) g(x/Lc - F/S)."""
    kt = KB * temperature
    r_eff = x / contour_length - force_val / stretch_modulus
    if r_eff >= 1.0:
        return float("inf")
    g = 1.0 / (4.0 * (1.0 - r_eff) ** 2) - 0.25 + r_eff
    return force_val - (kt / persistence_length) * g


def extensible_wlc_force(extension: np.ndarray, contour_length: float,
                         persistence_length: float, stretch_modulus: float,
                         temperature: float = 298.0) -> np.ndarray:
    """Implicit extensible WLC (Odijk-style), solved per point by brentq.

    Domain: 1 - x/Lc + F/S > 0 for every point.  The root search brackets
    [0, F_max] with F_max chosen so the domain stays positive.
    """
    x = np.asarray(extension, dtype=np.float64)
    if contour_length <= 0.0 or persistence_length <= 0.0 \
            or stretch_modulus <= 0.0 or temperature <= 0.0:
        raise SmfsError(INVALID_MODEL_PARAMETER,
                        "eWLC: Lc > 0, Lp > 0, S > 0, T > 0 required")
    if np.any(x < 0.0):
        raise SmfsError(POLYMER_SINGULARITY, "eWLC: extension must be non-negative")
    if np.any(x >= contour_length):
        raise SmfsError(POLYMER_SINGULARITY,
                        "eWLC: extension must stay below the contour length")
    out = np.empty(x.size, dtype=np.float64)
    for i, xi in enumerate(x):
        # the domain bound: F < S (1 - x/Lc); the elastic asymptote F = S x/Lc
        f_hi = min(stretch_modulus * (1.0 - float(xi) / contour_length) * 0.9999,
                   stretch_modulus * float(xi) / contour_length * 2.0 + 1e-18)
        if f_hi <= 0.0:
            raise SmfsError(POLYMER_SINGULARITY, "eWLC: domain collapsed")
        try:
            # xtol must be well below the force scale (forces here are
            # ~1e-13 N): the scipy default xtol=2e-12 would swallow small
            # roots
            out[i] = brentq(_ewlc_residual, 0.0, f_hi, xtol=1e-18, rtol=1e-12,
                            args=(float(xi), contour_length, persistence_length,
                                  stretch_modulus, temperature))
        except ValueError as exc:
            raise SmfsError(POLYMER_SINGULARITY,
                            f"eWLC: no root for x={xi:.3e}: {exc}") from exc
    return out


def langevin(u: np.ndarray) -> np.ndarray:
    """Langevin function L(u) = coth(u) - 1/u with stable limits.

    |u| < 1e-4 uses the series u/3 (avoids the 0/0); large u is evaluated
    directly (coth -> 1).
    """
    u = np.asarray(u, dtype=np.float64)
    safe = np.where(u == 0.0, 1.0, u)
    return np.where(np.abs(u) < 1e-4, u / 3.0, 1.0 / np.tanh(safe) - 1.0 / safe)


def fjc_extension(force: np.ndarray, contour_length: float, kuhn_length: float,
                  temperature: float = 298.0) -> np.ndarray:
    """FJC extension x = Lc L(F b / k_BT) (m)."""
    f = np.asarray(force, dtype=np.float64)
    if contour_length <= 0.0 or kuhn_length <= 0.0 or temperature <= 0.0:
        raise SmfsError(INVALID_MODEL_PARAMETER,
                        "FJC: Lc > 0, b > 0, T > 0 required")
    return contour_length * langevin(f * kuhn_length / (KB * temperature))


def extensible_fjc_extension(force: np.ndarray, contour_length: float,
                             kuhn_length: float, stretch_modulus: float,
                             temperature: float = 298.0) -> np.ndarray:
    """Extensible FJC extension x = Lc [L(y) + F/Sk] (m)."""
    f = np.asarray(force, dtype=np.float64)
    if contour_length <= 0.0 or kuhn_length <= 0.0 or stretch_modulus <= 0.0 \
            or temperature <= 0.0:
        raise SmfsError(INVALID_MODEL_PARAMETER,
                        "eFJC: Lc > 0, b > 0, Sk > 0, T > 0 required")
    return contour_length * (langevin(f * kuhn_length / (KB * temperature))
                             + f / stretch_modulus)


# ---------------------------------------------------------------------------
# polymer fits
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolymerFitResult:
    """Deterministic polymer fit on a force-extension branch."""

    model: str
    success: bool
    parameters: dict[str, float]
    parameter_units: dict[str, str]
    predicted_force: np.ndarray
    residuals: np.ndarray
    included_indices: np.ndarray
    objective: float
    covariance: dict[str, float] | None
    condition_number: float
    dof: int
    rmse: float
    aic: float
    aicc: float
    bic: float
    temperature: float
    warnings: tuple[str, ...] = ()
    failure_reason: str | None = None
    diagnostics: dict[str, object] = field(default_factory=dict)
    provenance: dict[str, object] = field(default_factory=dict)


def _finalize(model: str, temperature: float, x: np.ndarray, y: np.ndarray,
              params: dict[str, float], units: dict[str, str],
              predicted: np.ndarray, popt: np.ndarray, pcov: np.ndarray | None, names: list[str],
              idx: np.ndarray, warnings: list[str],
              provenance: dict[str, object]) -> PolymerFitResult:
    residuals = y - predicted
    n = y.size
    k = len(names)
    sse = float(np.sum(residuals**2))
    rmse = float(np.sqrt(np.mean(residuals**2)))
    aic = n * math.log(sse / n + 1e-300) + 2 * k
    aicc = aic + (2 * k * (k + 1)) / max(1, n - k - 1)
    bic = n * math.log(sse / n + 1e-300) + k * math.log(n)
    cov: dict[str, float] = {}
    cond = 0.0
    if pcov is not None and np.all(np.isfinite(pcov)):
        for i, a in enumerate(names):
            for j, b in enumerate(names):
                cov[f"{a}__{b}"] = float(pcov[i, j])
        try:
            cond = float(np.linalg.cond(pcov))
        except np.linalg.LinAlgError:  # pragma: no cover - degenerate matrix
            cond = float("inf")
    return PolymerFitResult(
        model=model, success=True, parameters=params, parameter_units=units,
        predicted_force=predicted, residuals=residuals, included_indices=idx,
        objective=sse, covariance=cov if cov else None, condition_number=cond,
        dof=n - k, rmse=rmse, aic=aic, aicc=aicc, bic=bic, temperature=temperature,
        warnings=tuple(warnings), diagnostics={"n_points": n,
                                               "free_parameters": names},
        provenance=provenance)


def _fit_polymer(x: np.ndarray, f: np.ndarray, model: str,
                 model_func: Callable[..., np.ndarray], p0: list[float],
                 bounds: tuple[list[float], list[float]],
                 names: list[str], units: dict[str, str], temperature: float,
                 idx: np.ndarray, starts: list[list[float]] | None = None,
                 extra_params: dict[str, float] | None = None) -> PolymerFitResult:
    """Shared polymer fit engine: normalized objective + deterministic
    multi-start (flat-valley protection)."""
    x = np.asarray(x, dtype=np.float64)
    f = np.asarray(f, dtype=np.float64)
    if not (np.isfinite(x).all() and np.isfinite(f).all()):
        raise SmfsError(NONFINITE_INPUT, "non-finite fit inputs")
    if x.size < len(p0) + 2:
        raise SmfsError(INSUFFICIENT_POINTS,
                        f"too few samples for {len(p0)} parameters")
    scale = float(np.max(np.abs(f))) or 1.0
    y = f / scale

    def wrapped(tt: np.ndarray, *args: float) -> np.ndarray:
        return model_func(tt, *args) / scale

    candidates = starts if starts else [p0]
    best: tuple | None = None
    best_sse = float("inf")
    for start in candidates:
        try:
            popt, pcov = curve_fit(wrapped, x, y, p0=list(start), bounds=bounds,
                                   maxfev=40000)
            sse = float(np.sum((wrapped(x, *popt) - y) ** 2))
        except Exception:  # noqa: BLE001 - a failed start is skipped
            continue
        if sse < best_sse:
            best_sse = sse
            best = (popt, pcov)
    if best is None:
        raise SmfsError(OPTIMIZATION_FAILED,
                        "optimizer failed from all deterministic starts")
    popt, pcov = best
    params = {name: float(v) for name, v in zip(names, popt, strict=True)}
    if extra_params:
        params.update(extra_params)
    predicted = model_func(x, *popt)
    return _finalize(model, temperature, x, f, params, units, predicted,
                     popt, pcov, names, idx, [], {"model": model})


def fit_worm_like_chain(extension: np.ndarray, force: np.ndarray, *,
                        temperature: float = 298.0,
                        Lc_initial: float | None = None,
                        Lp_initial: float | None = None) -> PolymerFitResult:
    """WLC fit (Lc, Lp) in the force space.

    Separable structure: for each candidate Lc the persistence length is
    the closed-form least-squares solution Lp = k_B T sum(g^2)/sum(F g)
    with g = g(x/Lc); a deterministic 1-D grid search over Lc with local
    refinement avoids the flat (Lc, Lp) valley of a general nonlinear
    optimizer.  The covariance is estimated at the optimum from the
    Jacobian.
    """
    x = np.asarray(extension, dtype=np.float64)
    f = np.asarray(force, dtype=np.float64)
    if x.size != f.size or x.size == 0:
        raise SmfsError(NONFINITE_INPUT, "extension/force length mismatch")
    if temperature <= 0.0:
        raise SmfsError(INVALID_MODEL_PARAMETER, "temperature must be positive")
    if not (np.isfinite(x).all() and np.isfinite(f).all()):
        raise SmfsError(NONFINITE_INPUT, "non-finite fit inputs")
    x_max = float(np.max(x))
    if x_max <= 0.0:
        raise SmfsError(INVALID_MODEL_PARAMETER, "extension must be positive")
    lo_lc = max(x_max * 1.001, float(Lc_initial) if Lc_initial is not None else x_max * 1.001)
    hi_lc = min(x_max * 10.0, float(Lc_initial) * 2.0 if Lc_initial is not None else x_max * 10.0)
    if hi_lc <= lo_lc:
        hi_lc = lo_lc * 2.0

    def lp_for(lc: float) -> tuple[float, float]:
        r = x / lc
        if np.any(r >= 1.0):
            return float("inf"), 0.0
        g = 1.0 / (4.0 * (1.0 - r) ** 2) - 0.25 + r
        denom = float(np.sum(g * g))
        if denom <= 0.0:
            return float("inf"), 0.0
        den2 = float(np.sum(f * g))
        if den2 <= 0.0:
            return float("inf"), 0.0
        lp = KB * temperature * denom / den2
        if lp <= 0.0:
            return float("inf"), 0.0
        pred = (KB * temperature / lp) * g
        return float(np.sum((f - pred) ** 2)), lp

    best_lc = float(min(np.linspace(lo_lc, hi_lc, 160), key=lambda lc: lp_for(lc)[0]))
    step = (hi_lc - lo_lc) / 160.0
    for _ in range(4):
        cand = np.linspace(max(best_lc - step, lo_lc), best_lc + step, 41)
        best_lc = float(min(cand, key=lambda lc: lp_for(lc)[0]))
        step /= 10.0
    sse, lp = lp_for(best_lc)
    if not np.isfinite(sse):
        raise SmfsError(OPTIMIZATION_FAILED, "WLC separable fit failed")
    # covariance from the Jacobian at the optimum
    r = x / best_lc
    g = 1.0 / (4.0 * (1.0 - r) ** 2) - 0.25 + r
    pred = (KB * temperature / lp) * g
    # dF/dLc and dF/dLp
    dg_dr = 1.0 / (2.0 * (1.0 - r) ** 3) + 1.0
    j_lc = -(KB * temperature / lp) * dg_dr * r / best_lc
    j_lp = -pred / lp
    jac = np.column_stack([j_lc, j_lp])
    try:
        pcov = np.linalg.inv(jac.T @ jac) * (sse / max(x.size - 2, 1))
    except np.linalg.LinAlgError:  # pragma: no cover - degenerate design
        pcov = None
    params = {"Lc": float(best_lc), "Lp": float(lp)}
    return _finalize(
        "worm_like_chain", temperature, x, f, params, {"Lc": "m", "Lp": "m"},
        pred, np.array([best_lc, lp]), pcov, ["Lc", "Lp"],
        np.arange(x.size), [], {"model": "worm_like_chain", "fit": "separable_1d"})


def fit_extensible_worm_like_chain(extension: np.ndarray, force: np.ndarray, *,
                                   temperature: float = 298.0,
                                   Lc_initial: float | None = None,
                                   Lp_initial: float | None = None,
                                   S_initial: float | None = None) -> PolymerFitResult:
    """eWLC fit (Lc, Lp, S) in the force space; S in [1e-12, 1e-2] N."""
    x = np.asarray(extension, dtype=np.float64)
    f = np.asarray(force, dtype=np.float64)
    if x.size != f.size or x.size == 0:
        raise SmfsError(NONFINITE_INPUT, "extension/force length mismatch")
    if temperature <= 0.0:
        raise SmfsError(INVALID_MODEL_PARAMETER, "temperature must be positive")
    x_max = float(np.max(x))
    if x_max <= 0.0:
        raise SmfsError(INVALID_MODEL_PARAMETER, "extension must be positive")
    lc0 = Lc_initial if Lc_initial is not None else x_max * 1.2
    lp0 = Lp_initial if Lp_initial is not None else KB * temperature / max(float(np.max(f)), 1e-30)
    s0 = S_initial if S_initial is not None else max(float(np.max(f)) * 20.0, 1e-9)
    lo, hi = [x_max * 1.001, x_max * 1e-6, 1e-12], [x_max * 10.0, x_max * 10.0, 1e-2]
    lc0 = max(lo[0], min(lc0, hi[0]))
    lp0 = max(lo[1], min(lp0, hi[1]))
    s0 = max(lo[2], min(s0, hi[2]))

    def model(tt: np.ndarray, lc: float, lp: float, s: float) -> np.ndarray:
        return extensible_wlc_force(tt, lc, lp, s, temperature)

    return _fit_polymer(
        x, f, "extensible_worm_like_chain", model, [lc0, lp0, s0], (lo, hi),
        ["Lc", "Lp", "S"], {"Lc": "m", "Lp": "m", "S": "N"}, temperature,
        np.arange(x.size),
        starts=[[lc0, lp0, s0], [x_max * 1.05, lp0 * 10.0, s0 * 10.0],
                [x_max * 1.5, lp0 / 10.0, s0 / 10.0]])


def fit_freely_jointed_chain(extension: np.ndarray, force: np.ndarray, *,
                             temperature: float = 298.0,
                             Lc_initial: float | None = None,
                             b_initial: float | None = None) -> PolymerFitResult:
    """FJC fit (Lc, b) in the extension space (x(F) has no closed form)."""
    x = np.asarray(extension, dtype=np.float64)
    f = np.asarray(force, dtype=np.float64)
    if x.size != f.size or x.size == 0:
        raise SmfsError(NONFINITE_INPUT, "extension/force length mismatch")
    if temperature <= 0.0:
        raise SmfsError(INVALID_MODEL_PARAMETER, "temperature must be positive")
    x_max = float(np.max(x))
    f_max = float(np.max(np.abs(f)))
    if x_max <= 0.0 or f_max <= 0.0:
        raise SmfsError(INVALID_MODEL_PARAMETER, "extension/force must be positive")
    lc0 = Lc_initial if Lc_initial is not None else x_max * 1.1
    b0 = b_initial if b_initial is not None else KB * temperature / f_max * 3.0
    lo, hi = [x_max * 1.001, KB * temperature / f_max * 1e-3], \
        [x_max * 10.0, KB * temperature / f_max * 1e3]
    lc0 = max(lo[0], min(lc0, hi[0]))
    b0 = max(lo[1], min(b0, hi[1]))

    # separable structure: for each candidate b the contour length is the
    # closed-form least-squares solution Lc = sum(x L(y))/sum(L(y)^2);
    # a deterministic log-grid search over b avoids the flat (Lc, b) valley
    y = x
    kt = KB * temperature

    def lc_for(b: float) -> tuple[float, float]:
        g = langevin(f * b / kt)
        denom = float(np.sum(g * g))
        if denom <= 0.0:
            return float("inf"), 0.0
        lc = float(np.sum(x * g) / denom)
        if lc <= 0.0:
            return float("inf"), 0.0
        pred = lc * g
        return float(np.sum((x - pred) ** 2)), lc

    best_b = float(min(np.geomspace(lo[1], hi[1], 120),
                       key=lambda bb: lc_for(bb)[0]))
    for _ in range(4):
        cand = np.geomspace(max(best_b / 2.0, lo[1]), best_b * 2.0, 61)
        best_b = float(min(cand, key=lambda bb: lc_for(bb)[0]))
    sse, lc = lc_for(best_b)
    if not np.isfinite(sse):
        raise SmfsError(OPTIMIZATION_FAILED, "FJC separable fit failed")
    g = langevin(f * best_b / kt)
    pred = lc * g
    yv = f * best_b / kt
    safe = np.where(yv == 0, 1.0, yv)
    dlange = np.where(np.abs(yv) < 1e-4, 1.0 / 3.0,
                      1.0 / safe**2 - 1.0 / np.sinh(safe) ** 2)
    jac = np.column_stack([g, lc * dlange * f / kt])
    try:
        pcov = np.linalg.inv(jac.T @ jac) * (sse / max(x.size - 2, 1))
    except np.linalg.LinAlgError:  # pragma: no cover - degenerate design
        pcov = None
    params = {"Lc": float(lc), "b": float(best_b), "Lp": float(best_b) / 2.0}
    return _finalize(
        "freely_jointed_chain", temperature, x, y, params,
        {"Lc": "m", "b": "m", "Lp": "m"}, pred,
        np.array([lc, best_b]), pcov, ["Lc", "b"], np.arange(x.size), [],
        provenance={"model": "freely_jointed_chain", "fit_space": "extension",
                    "fit": "separable_1d"})


def fit_extensible_freely_jointed_chain(extension: np.ndarray, force: np.ndarray, *,
                                        temperature: float = 298.0,
                                        Lc_initial: float | None = None,
                                        b_initial: float | None = None,
                                        Sk_initial: float | None = None,
                                        ) -> PolymerFitResult:
    """eFJC fit (Lc, b, Sk) in the extension space; Sk in [1e-12, 1e-2] N."""
    x = np.asarray(extension, dtype=np.float64)
    f = np.asarray(force, dtype=np.float64)
    if x.size != f.size or x.size == 0:
        raise SmfsError(NONFINITE_INPUT, "extension/force length mismatch")
    if temperature <= 0.0:
        raise SmfsError(INVALID_MODEL_PARAMETER, "temperature must be positive")
    x_max = float(np.max(x))
    f_max = float(np.max(np.abs(f)))
    if x_max <= 0.0 or f_max <= 0.0:
        raise SmfsError(INVALID_MODEL_PARAMETER, "extension/force must be positive")
    lc0 = Lc_initial if Lc_initial is not None else x_max * 1.1
    b0 = b_initial if b_initial is not None else KB * temperature / f_max * 3.0
    sk0 = Sk_initial if Sk_initial is not None else max(f_max * 20.0, 1e-9)
    lo, hi = [x_max * 1.001, KB * temperature / f_max * 1e-3, 1e-12], \
        [x_max * 10.0, KB * temperature / f_max * 1e3, 1e-2]
    lc0 = max(lo[0], min(lc0, hi[0]))
    b0 = max(lo[1], min(b0, hi[1]))
    sk0 = max(lo[2], min(sk0, hi[2]))

    kt = KB * temperature

    def lc_for(b: float, sk: float) -> tuple[float, float]:
        g = langevin(f * b / kt) + f / sk
        denom = float(np.sum(g * g))
        if denom <= 0.0:
            return float("inf"), 0.0
        lc = float(np.sum(x * g) / denom)
        if lc <= 0.0:
            return float("inf"), 0.0
        pred = lc * g
        return float(np.sum((x - pred) ** 2)), lc

    best = (float("inf"), b0, sk0, 0.0)
    for log_b in np.linspace(np.log(lo[1]), np.log(hi[1]), 60):
        bb = math.exp(log_b)
        for log_sk in np.linspace(np.log(lo[2]), np.log(hi[2]), 60):
            sse, lc = lc_for(bb, math.exp(log_sk))
            if sse < best[0]:
                best = (sse, bb, math.exp(log_sk), lc)
    sse, best_b, best_sk, lc = best
    if not np.isfinite(sse):
        raise SmfsError(OPTIMIZATION_FAILED, "eFJC separable fit failed")
    g = langevin(f * best_b / kt) + f / best_sk
    pred = lc * g
    yv = f * best_b / kt
    safe = np.where(yv == 0, 1.0, yv)
    dlange = np.where(np.abs(yv) < 1e-4, 1.0 / 3.0,
                      1.0 / safe**2 - 1.0 / np.sinh(safe) ** 2)
    jac = np.column_stack([g, lc * dlange * f / kt, lc * f / best_sk**2])
    try:
        pcov = np.linalg.inv(jac.T @ jac) * (sse / max(x.size - 3, 1))
    except np.linalg.LinAlgError:  # pragma: no cover - degenerate design
        pcov = None
    params = {"Lc": float(lc), "b": float(best_b), "Lp": float(best_b) / 2.0,
              "Sk": float(best_sk)}
    return _finalize(
        "extensible_freely_jointed_chain", temperature, x, x, params,
        {"Lc": "m", "b": "m", "Lp": "m", "Sk": "N"}, pred,
        np.array([lc, best_b, best_sk]), pcov, ["Lc", "b", "Sk"],
        np.arange(x.size), [],
        {"model": "extensible_freely_jointed_chain", "fit_space": "extension",
         "fit": "separable_grid"})


# ---------------------------------------------------------------------------
# polymer model comparison
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolymerModelComparisonResult:
    """Model-relative comparison over identical observations."""

    fits: tuple[PolymerFitResult, ...]
    delta_aicc: dict[str, float]
    weights: dict[str, float]
    recommended_model: str | None
    ambiguous: bool
    n_compared: int
    warnings: tuple[str, ...] = ()
    provenance: dict[str, object] = field(default_factory=dict)


def compare_polymer_models(
    extension: np.ndarray,
    force: np.ndarray,
    *,
    models: tuple[str, ...] = ("worm_like_chain", "extensible_worm_like_chain",
                               "freely_jointed_chain", "extensible_freely_jointed_chain"),
    temperature: float = 298.0,
) -> PolymerModelComparisonResult:
    """AICc comparison over the identical observation set; relative weights
    only; the recommendation policy is SOFTWARE_VERIFIED."""
    fits: list[PolymerFitResult] = []
    warnings: list[str] = []
    for model in models:
        if model not in POLYMER_MODELS:
            raise SmfsError(INVALID_MODEL_PARAMETER, f"unknown model {model!r}")
        try:
            if model == "worm_like_chain":
                fits.append(fit_worm_like_chain(extension, force, temperature=temperature))
            elif model == "extensible_worm_like_chain":
                fits.append(fit_extensible_worm_like_chain(extension, force,
                                                           temperature=temperature))
            elif model == "freely_jointed_chain":
                fits.append(fit_freely_jointed_chain(extension, force,
                                                     temperature=temperature))
            else:
                fits.append(fit_extensible_freely_jointed_chain(
                    extension, force, temperature=temperature))
        except SmfsError as exc:
            warnings.append(f"{model}: {exc.code}")
    if not fits:
        raise SmfsError(OPTIMIZATION_FAILED, "no polymer model fit succeeded")
    delta_aicc = {f.model: f.aicc - min(x.aicc for x in fits) for f in fits}
    total_w = sum(math.exp(-0.5 * d) for d in delta_aicc.values())
    weights = {m: math.exp(-0.5 * delta_aicc[m]) / total_w for m in delta_aicc}
    best = min(fits, key=lambda f: f.aicc)
    ambiguous = (sorted(f.aicc for f in fits)[1] - best.aicc < 4.0
                 if len(fits) > 1 else False)
    return PolymerModelComparisonResult(
        fits=tuple(fits), delta_aicc=delta_aicc, weights=weights,
        recommended_model=best.model if not ambiguous else None,
        ambiguous=ambiguous, n_compared=len(fits), warnings=tuple(warnings),
        provenance={"criterion": "aicc", "temperature": temperature})
