"""FS-F4 unfolding-event detection, quantification, contour-length
increments and loading rates.

Event detection is a documented heuristic (SOFTWARE_VERIFIED): candidates
require a force drop >= min_force_drop sustained over min_persistence
samples on the pull-ordered retract branch; rejected candidates are
retained with reasons; the final detachment is distinguished from internal
unfolding (the last event whose post-drop force returns to the baseline).

Contour-length increments are derived from independent pre/post polymer
fits, never from the extension jump alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from spmkit.core.analysis.force_smfs_errors import (
    INSUFFICIENT_POINTS,
    INVALID_MODEL_PARAMETER,
    NO_EVENTS,
    NONFINITE_INPUT,
    SmfsError,
)
from spmkit.core.analysis.force_smfs_models import (
    MolecularExtensionResult,
    PolymerFitResult,
    fit_worm_like_chain,
)


@dataclass(frozen=True)
class UnfoldingEvent:
    """One unfolding candidate on the pull-ordered retract branch."""

    event_index: int  # index in the pull-ordered branch
    original_index: int  # index in the stored retract arrays
    rupture_force: float
    rupture_extension: float
    force_drop: float
    pre_window: tuple[int, int]
    post_window: tuple[int, int]
    local_loading_rate: float | None
    is_final_detachment: bool
    valid: bool
    rejection_reason: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class UnfoldingEventResult:
    """Detection output: selected events, rejected candidates, thresholds."""

    events: tuple[UnfoldingEvent, ...]
    rejected: tuple[UnfoldingEvent, ...]
    method: str
    thresholds: dict[str, float]
    pull_order_indices: np.ndarray
    warnings: tuple[str, ...] = ()
    provenance: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ContourLengthIncrementResult:
    """Delta contour length from independent pre/post polymer fits."""

    event_index: int
    pre_fit: PolymerFitResult
    post_fit: PolymerFitResult
    pre_contour_length: float
    post_contour_length: float
    delta_contour_length: float
    delta_sensitivity: dict[str, float]
    valid: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class LoadingRateResult:
    """Local loading rate at one event (N/s)."""

    event_index: int
    time_window: tuple[float, float]
    local_slope: float
    robust_slope: float
    n_points: int
    units: str = "N/s"
    measured: bool = True
    theoretical_rate: float | None = None
    warnings: tuple[str, ...] = ()


def _pull_order(ext: MolecularExtensionResult) -> np.ndarray:
    """Pull-ordered indices: the molecular extension increases during the
    pull (the stored retract may be decreasing)."""
    return np.argsort(ext.separation, kind="stable")


def detect_unfolding_events(
    extension: MolecularExtensionResult,
    *,
    min_force_drop: float | None = None,
    min_persistence: int = 3,
    min_event_separation: int = 3,
    noise_sigma: float | None = None,
    boundary_margin: int = 2,
) -> UnfoldingEventResult:
    """Detect unfolding events on the pull-ordered retract branch.

    A candidate is a local force maximum followed by a force drop >=
    min_force_drop sustained over min_persistence consecutive samples.  The
    default drop threshold is 5 x the tail noise sigma when no explicit
    threshold is given.  Rejected candidates are retained with reasons.
    """
    pull = _pull_order(extension)
    f = extension.force[pull]
    ext = extension.extension[pull]
    if f.size < 10:
        raise SmfsError(INSUFFICIENT_POINTS, "retract branch too short for detection")
    if not np.isfinite(f).all() or not np.isfinite(ext).all():
        raise SmfsError(NONFINITE_INPUT, "non-finite branch data")
    if min_persistence < 1 or min_event_separation < 1 or boundary_margin < 0:
        raise SmfsError(INVALID_MODEL_PARAMETER, "detection parameters must be positive")
    if noise_sigma is None:
        noise_sigma = float(np.std(f[-max(3, f.size // 10):])) or 1e-12
    drop_threshold = min_force_drop if min_force_drop is not None else 5.0 * noise_sigma

    selected: list[UnfoldingEvent] = []
    rejected: list[UnfoldingEvent] = []
    warnings: list[str] = []
    i = boundary_margin
    while i < f.size - boundary_margin - min_persistence:
        # local maximum: f[i] >= neighbours within the persistence window
        peak = int(i)
        while peak + 1 < f.size and f[peak + 1] > f[peak]:
            peak += 1
        # forward scan for the sustained drop
        drop = 0.0
        j = peak
        while j + 1 < f.size and f[peak] - f[j + 1] > drop:
            j += 1
            drop = f[peak] - f[j]
        sustained = 0
        k = peak
        while k + 1 < f.size and f[peak] - f[k + 1] >= drop_threshold:
            sustained += 1
            k += 1
        reason: str | None = None
        if drop < drop_threshold:
            reason = f"force drop {drop:.3e} below threshold {drop_threshold:.3e}"
        elif sustained < min_persistence:
            reason = f"drop sustained only {sustained} < {min_persistence} samples"
        elif peak < boundary_margin or peak > f.size - boundary_margin - 1:
            reason = "event too close to the branch boundary"
        if reason is not None:
            rejected.append(UnfoldingEvent(
                event_index=peak, original_index=int(pull[peak]),
                rupture_force=float(f[peak]), rupture_extension=float(ext[peak]),
                force_drop=float(drop),
                pre_window=(0, peak), post_window=(peak, f.size - 1),
                local_loading_rate=None, is_final_detachment=False, valid=False,
                rejection_reason=reason))
        else:
            # is it the final detachment? the post-drop force returns to the
            # baseline (|f| <= 3 sigma) and no further significant drop exists
            tail = f[peak + 1:]
            final = bool(tail.size and float(np.max(np.abs(tail))) <= 3.0 * noise_sigma)
            selected.append(UnfoldingEvent(
                event_index=peak, original_index=int(pull[peak]),
                rupture_force=float(f[peak]), rupture_extension=float(ext[peak]),
                force_drop=float(drop),
                pre_window=(0, peak), post_window=(peak, f.size - 1),
                local_loading_rate=None, is_final_detachment=final, valid=True))
        i = peak + max(min_event_separation, 1)
    if not selected:
        raise SmfsError(NO_EVENTS, "no unfolding event detected on the retract branch")
    return UnfoldingEventResult(
        events=tuple(selected), rejected=tuple(rejected), method="sustained_drop",
        thresholds={"min_force_drop": drop_threshold, "min_persistence": float(min_persistence),
                    "min_event_separation": float(min_event_separation),
                    "noise_sigma": float(noise_sigma)},
        pull_order_indices=pull, warnings=tuple(warnings),
        provenance={"detector": "sustained_drop"})


def quantify_unfolding_events(
    extension: MolecularExtensionResult,
    events: UnfoldingEventResult,
    *,
    pre_margin: int = 2,
    post_margin: int = 2,
    min_points: int = 8,
) -> UnfoldingEventResult:
    """Assign explicit pre/post windows and local loading rates to every
    selected event.  Windows are [branch_start, peak - pre_margin] and
    [peak + post_margin, next_event_start - 1] (or the branch end)."""
    pull = events.pull_order_indices
    f = extension.force[pull]
    ext = extension.extension[pull]
    updated: list[UnfoldingEvent] = []
    n = f.size
    t = None if extension.time is None else extension.time[pull]
    branch_start = int(np.flatnonzero(ext >= 0.0)[0]) if np.any(ext >= 0.0) else 0
    for ei, ev in enumerate(events.events):
        peak = ev.event_index
        # the pre window spans the polymer branch between the previous event
        # (or the tether zero) and this event
        pre_start = branch_start if ei == 0 else events.events[ei - 1].event_index + 2
        pre_end = max(peak - pre_margin, pre_start + 1)
        if ei + 1 < len(events.events):
            post_end = max(events.events[ei + 1].event_index - 1, peak + 1)
        else:
            post_end = n - 1
        post_start = min(peak + post_margin, post_end)
        rate = None
        if t is not None:
            rate = _local_rate(t, f, peak, window_samples=min(10, peak))
        updated.append(UnfoldingEvent(
            event_index=peak, original_index=ev.original_index,
            rupture_force=ev.rupture_force, rupture_extension=ev.rupture_extension,
            force_drop=ev.force_drop, pre_window=(pre_start, pre_end),
            post_window=(post_start, post_end), local_loading_rate=rate,
            is_final_detachment=ev.is_final_detachment, valid=True))
    return UnfoldingEventResult(
        events=tuple(updated), rejected=events.rejected, method=events.method,
        thresholds=events.thresholds, pull_order_indices=pull,
        warnings=events.warnings, provenance=events.provenance)


def _local_rate(t: np.ndarray, f: np.ndarray, peak: int,
                window_samples: int) -> float | None:
    """Robust local loading rate before the peak (least squares slope)."""
    start = max(0, peak - window_samples)
    if peak - start < 3:
        return None
    dt = t[start:peak + 1] - t[start]
    if np.any(np.diff(dt) <= 0.0):
        return None
    slope, _intercept = np.polyfit(dt, f[start:peak + 1], 1)
    return float(slope)


def infer_contour_length_increments(
    extension: MolecularExtensionResult,
    events: UnfoldingEventResult,
    *,
    model: str = "worm_like_chain",
    temperature: float = 298.0,
    pre_margin: int = 2,
    post_margin: int = 2,
    min_points: int = 8,
    sensitivity_shifts: tuple[int, ...] = (0,),
) -> tuple[ContourLengthIncrementResult, ...]:
    """Delta contour length per event from independent pre/post fits.

    The pre window is [branch_start, peak - pre_margin] (or the previous
    event); the post window is [peak + post_margin, next event / branch
    end].  The extension origin for each fit is the window start (each
    branch segment is fitted in its own relative extension, the standard
    SMFS convention).  ``sensitivity_shifts`` re-fits with the event index
    shifted by +/-k and reports the delta-Lc spread.
    """
    pull = events.pull_order_indices
    f = extension.force[pull]
    ext = extension.extension[pull]
    # the pre window starts at the tether zero (extension >= 0): the slack
    # region carries no polymer force and must not enter the fit
    branch_start = int(np.flatnonzero(ext >= 0.0)[0]) if np.any(ext >= 0.0) else 0
    out: list[ContourLengthIncrementResult] = []
    for ei, ev in enumerate(events.events):
        peak = ev.event_index
        pre_start = branch_start if ei == 0 else events.events[ei - 1].event_index + 2
        pre_end = max(peak - pre_margin, pre_start + 1)
        if ei + 1 < len(events.events):
            post_end = max(events.events[ei + 1].event_index - 1, peak + 1)
        else:
            post_end = f.size - 1
        post_start = min(peak + post_margin, post_end)
        # the polymer fit uses the ABSOLUTE molecular extension (measured
        # from the tether zero): the post-event polymer's extension is the
        # same molecular extension, not a branch-relative coordinate; a
        # branch-relative fit would absorb the event offset into a biased
        # contour length
        pre_x = ext[pre_start:pre_end + 1]
        pre_f = f[pre_start:pre_end + 1]
        post_x = ext[post_start:post_end + 1]
        post_f = f[post_start:post_end + 1]
        if pre_x.size < min_points or post_x.size < min_points:
            out.append(ContourLengthIncrementResult(
                event_index=peak, pre_fit=None, post_fit=None,  # type: ignore[arg-type]
                pre_contour_length=float("nan"), post_contour_length=float("nan"),
                delta_contour_length=float("nan"),
                delta_sensitivity={"shift_spread": float("nan")}, valid=False,
                warnings=(f"event {ei}: pre/post window too short",)))
            continue
        pre_fit = fit_worm_like_chain(pre_x, pre_f, temperature=temperature) \
            if model == "worm_like_chain" else _fit_named(model, pre_x, pre_f, temperature)
        post_fit = fit_worm_like_chain(post_x, post_f, temperature=temperature) \
            if model == "worm_like_chain" else _fit_named(model, post_x, post_f, temperature)
        lc_pre = pre_fit.parameters["Lc"]
        lc_post = post_fit.parameters["Lc"]
        deltas: list[float] = []
        for shift in sensitivity_shifts:
            if shift == 0:
                deltas.append(lc_post - lc_pre)
                continue
            pk = peak + shift
            if pk < 1 or pk >= f.size - 1:
                continue
            pe2 = max(pk - pre_margin, 1)
            ps2 = min(pk + post_margin, f.size - 1)
            p_x = ext[0:pe2 + 1]
            p_f = f[0:pe2 + 1]
            q_x = ext[ps2:post_end + 1]
            q_f = f[ps2:post_end + 1]
            if p_x.size < min_points or q_x.size < min_points:
                continue
            fp = fit_worm_like_chain(p_x, p_f, temperature=temperature) \
                if model == "worm_like_chain" else _fit_named(model, p_x, p_f, temperature)
            fq = fit_worm_like_chain(q_x, q_f, temperature=temperature) \
                if model == "worm_like_chain" else _fit_named(model, q_x, q_f, temperature)
            deltas.append(fq.parameters["Lc"] - fp.parameters["Lc"])
        spread = float(np.ptp(deltas)) if deltas else float("nan")
        out.append(ContourLengthIncrementResult(
            event_index=peak, pre_fit=pre_fit, post_fit=post_fit,
            pre_contour_length=float(lc_pre), post_contour_length=float(lc_post),
            delta_contour_length=float(lc_post - lc_pre),
            delta_sensitivity={"shift_spread": spread, "n_shifts": len(deltas)},
            valid=True))
    return tuple(out)


def _fit_named(model: str, x: np.ndarray, f: np.ndarray,
               temperature: float) -> PolymerFitResult:
    from spmkit.core.analysis.force_smfs_models import (
        fit_extensible_freely_jointed_chain,
        fit_extensible_worm_like_chain,
        fit_freely_jointed_chain,
    )
    if model == "extensible_worm_like_chain":
        return fit_extensible_worm_like_chain(x, f, temperature=temperature)
    if model == "freely_jointed_chain":
        return fit_freely_jointed_chain(x, f, temperature=temperature)
    if model == "extensible_freely_jointed_chain":
        return fit_extensible_freely_jointed_chain(x, f, temperature=temperature)
    raise SmfsError(INVALID_MODEL_PARAMETER, f"unknown polymer model {model!r}")


def compute_event_loading_rates(
    extension: MolecularExtensionResult,
    events: UnfoldingEventResult,
    *,
    window_samples: int = 10,
    min_samples: int = 3,
    pulling_velocity: float | None = None,
    effective_stiffness: float | None = None,
) -> tuple[LoadingRateResult, ...]:
    """Local loading rate per event from explicit time and force.

    The measured rate is the least-squares slope of force vs time over the
    pre-event window; the robust slope is the median of pairwise slopes.
    The theoretical rate = effective_stiffness * pulling_velocity is
    reported separately when both are supplied (never substituted).
    """
    if extension.time is None:
        raise SmfsError(NONFINITE_INPUT,
                        "loading rates require an explicit time axis")
    pull = events.pull_order_indices
    t = extension.time[pull]
    f = extension.force[pull]
    if np.any(np.diff(t) <= 0.0):
        raise SmfsError(NONFINITE_INPUT, "pull time axis not strictly increasing")
    out: list[LoadingRateResult] = []
    for ev in events.events:
        peak = ev.event_index
        start = max(0, peak - window_samples)
        if peak - start < min_samples - 1:
            out.append(LoadingRateResult(
                event_index=peak, time_window=(float(t[start]), float(t[peak])),
                local_slope=float("nan"), robust_slope=float("nan"),
                n_points=peak - start + 1,
                warnings=("insufficient pre-event samples for a rate",)))
            continue
        dt = t[start:peak + 1] - t[start]
        df = f[start:peak + 1]
        slope, _intercept = np.polyfit(dt, df, 1)
        pairs = [(df[j] - df[i]) / (dt[j] - dt[i])
                 for i in range(len(dt)) for j in range(i + 1, len(dt))
                 if dt[j] > dt[i]]
        robust = float(np.median(pairs)) if pairs else float(slope)
        theoretical = None
        if pulling_velocity is not None and effective_stiffness is not None:
            theoretical = effective_stiffness * pulling_velocity
        out.append(LoadingRateResult(
            event_index=peak, time_window=(float(t[start]), float(t[peak])),
            local_slope=float(slope), robust_slope=robust,
            n_points=peak - start + 1, theoretical_rate=theoretical))
    return tuple(out)
