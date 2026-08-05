"""FS-F3 time-domain protocol layer.

Freezes the temporal contract, identifies viscoelastic protocols from force
curves, computes indentation/force rates and extracts relaxation and creep
responses.  No hidden resampling, no smoothing, no assumed acquisition rate.

Temporal contract
-----------------
- time unit: seconds (``ForceSegment.time``);
- one finite 1-D axis per segment, strictly increasing;
- duplicate timestamps raise ``DUPLICATE_TIMESTAMPS`` unless an explicit
  typed repair is requested;
- nonuniform sampling is allowed and never resampled silently;
- the instrument clock is ``segment.time``; a reconstructed clock requires
  an explicit ``assume_uniform_rate`` (documented assumption);
- a missing time axis raises ``MISSING_TIME``.

Protocol classes
----------------
LOADING_RAMP, UNLOADING_RAMP, DISPLACEMENT_HOLD, FORCE_HOLD, CREEP,
STRESS_RELAXATION, TRIANGULAR_LOADING, INSUFFICIENT_PROTOCOL,
AMBIGUOUS_PROTOCOL.

Sign conventions follow FS-F1/FS-F2: separation = height - deflection;
indentation = separation - contact coordinate (positive into the sample).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from spmkit.core.analysis.force_foundation import ForcePreparationResult
from spmkit.core.analysis.force_viscoelastic_errors import (
    AMBIGUOUS_PROTOCOL as _ERR_AMBIGUOUS_PROTOCOL,  # noqa: F401 (code constant)
)
from spmkit.core.analysis.force_viscoelastic_errors import (
    CURVE_NOT_FIT_ELIGIBLE,
    DUPLICATE_TIMESTAMPS,
    EMPTY_REGION,
    INVALID_RESPONSE,
    MISSING_TIME,
    NONFINITE_RESPONSE,
    NONMONOTONIC_TIME,
    ViscoelasticityError,
)
from spmkit.core.analysis.force_viscoelastic_errors import (
    INSUFFICIENT_PROTOCOL as _ERR_INSUFFICIENT_PROTOCOL,  # noqa: F401 (code constant)
)
from spmkit.core.models import ForceCurve, ForceSegment

#: canonical protocol classes
LOADING_RAMP = "LOADING_RAMP"
UNLOADING_RAMP = "UNLOADING_RAMP"
DISPLACEMENT_HOLD = "DISPLACEMENT_HOLD"
FORCE_HOLD = "FORCE_HOLD"
CREEP = "CREEP"
STRESS_RELAXATION = "STRESS_RELAXATION"
TRIANGULAR_LOADING = "TRIANGULAR_LOADING"
INSUFFICIENT_PROTOCOL = "INSUFFICIENT_PROTOCOL"
AMBIGUOUS_PROTOCOL = "AMBIGUOUS_PROTOCOL"

PROTOCOL_CLASSES = (LOADING_RAMP, UNLOADING_RAMP, DISPLACEMENT_HOLD, FORCE_HOLD,
                    CREEP, STRESS_RELAXATION, TRIANGULAR_LOADING,
                    INSUFFICIENT_PROTOCOL, AMBIGUOUS_PROTOCOL)

#: trusted instrument labels read from curve.metadata, in priority order
_TRUSTED_PROTOCOL_KEYS = ("protocol", "viscoelastic_protocol", "experiment_type")


def validate_time_axis(time: np.ndarray, *, label: str = "time",
                       allow_duplicates: bool = False) -> np.ndarray:
    """Validate one time axis against the frozen temporal contract."""
    t = np.asarray(time, dtype=np.float64)
    if t.ndim != 1 or t.size == 0:
        raise ViscoelasticityError(MISSING_TIME, f"{label}: no finite 1-D time axis")
    if not np.isfinite(t).all():
        raise ViscoelasticityError(NONMONOTONIC_TIME, f"{label}: non-finite times")
    d = np.diff(t)
    if np.any(d <= 0.0):
        if np.any(d == 0.0) and not allow_duplicates:
            raise ViscoelasticityError(
                DUPLICATE_TIMESTAMPS,
                f"{label}: duplicate timestamps (strictly increasing required)")
        raise ViscoelasticityError(NONMONOTONIC_TIME,
                                   f"{label}: times must be strictly increasing")
    return t


@dataclass(frozen=True)
class ProtocolRegion:
    """One contiguous protocol region on a segment."""

    kind: str  # "loading" | "unloading" | "hold_displacement" | "hold_force"
    segment: str  # "extend" | "retract" | ...
    start_index: int
    end_index: int  # inclusive
    start_time: float
    end_time: float


@dataclass(frozen=True)
class ViscoelasticProtocolResult:
    """Identified protocol of one curve with explicit region records."""

    protocol_type: str
    regions: tuple[ProtocolRegion, ...]
    method: str
    time_unit: str = "s"
    trusted_label: str | None = None
    ambiguity: bool = False
    warnings: tuple[str, ...] = ()
    provenance: dict[str, object] = field(default_factory=dict)

    def region(self, kind: str, segment: str | None = None) -> ProtocolRegion | None:
        for r in self.regions:
            if r.kind == kind and (segment is None or r.segment == segment):
                return r
        return None


def _segment_time(segment: ForceSegment) -> np.ndarray:
    if segment.time is None:
        raise ViscoelasticityError(
            MISSING_TIME,
            f"segment {segment.segment_type!r} has no time axis; pass "
            "assume_uniform_rate to reconstruct one explicitly")
    return validate_time_axis(np.asarray(segment.time, dtype=np.float64))


def _rate_regions(t: np.ndarray, disp: np.ndarray, force: np.ndarray,
                  rate_threshold: float, min_hold_points: int) -> list[dict]:
    """Classify contiguous rate regions on one segment.

    Rates are finite differences d(disp)/dt and d(force)/dt.  A sample is
    "hold-like" when the displacement rate magnitude is below the threshold
    (relative to the median |rate|); among hold-like runs, a run whose force
    rate magnitude is also below the threshold is a displacement hold, a run
    with a large displacement rate and small force rate is a force hold.
    Runs shorter than min_hold_points are merged into the surrounding ramp.
    """
    n = t.size
    if n < 2:
        raise ViscoelasticityError(INSUFFICIENT_PROTOCOL, "segment too short")
    dt = np.diff(t)
    d_disp = np.diff(disp)
    d_force = np.diff(force)
    rate_disp = d_disp / dt
    rate_force = d_force / dt
    # the rate scale is the median of the NONZERO rates: a long static hold
    # would otherwise drag the median to zero and force an absolute scale
    nonzero_disp = np.abs(rate_disp)[np.abs(rate_disp) > 0.0]
    nonzero_force = np.abs(rate_force)[np.abs(rate_force) > 0.0]
    med_disp = float(np.median(nonzero_disp)) if nonzero_disp.size else 0.0
    med_force = float(np.median(nonzero_force)) if nonzero_force.size else 0.0
    scale = med_disp if med_disp > 0.0 else 1.0
    thr_disp = rate_threshold * scale
    thr_force = rate_threshold * max(med_force, 1e-300)
    # a force hold must carry a non-baseline force level (the zero-force
    # pre-contact region is not a hold)
    peak_force = float(np.max(np.abs(force))) if force.size else 0.0
    force_level = 0.01 * peak_force

    kinds = np.empty(n, dtype=object)
    kinds[0] = "loading" if rate_disp[0] > 0 else "unloading"
    for i in range(n - 1):
        if abs(rate_disp[i]) <= thr_disp:
            # displacement held (a decaying force here is the relaxation
            # signal, not a force hold)
            kinds[i + 1] = "hold_displacement"
        elif abs(rate_force[i]) <= thr_force and abs(force[i]) > force_level:
            # force held while the displacement drifts (creep signature)
            kinds[i + 1] = "hold_force"
        elif rate_disp[i] > 0:
            kinds[i + 1] = "loading"
        else:
            kinds[i + 1] = "unloading"
    # merge runs shorter than min_hold_points into the ramp label
    out = list(kinds)
    runs: list[tuple[int, int, str]] = []
    i = 0
    while i < n:
        j = i
        while j + 1 < n and out[j + 1] == out[i]:
            j += 1
        runs.append((i, j, out[i]))
        i = j + 1
    for (a, b, kind) in runs:
        if kind.startswith("hold") and (b - a + 1) < min_hold_points:
            for k in range(a, b + 1):
                out[k] = "loading" if rate_disp[min(k, n - 2)] >= 0 else "unloading"
    regions: list[dict] = []
    i = 0
    while i < n:
        j = i
        while j + 1 < n and out[j + 1] == out[i]:
            j += 1
        if out[i].startswith("hold") or True:
            regions.append({
                "kind": out[i], "start": int(i), "end": int(j),
                "t0": float(t[i]), "t1": float(t[j]),
            })
        i = j + 1
    return regions


def identify_viscoelastic_protocol(
    curve: ForceCurve,
    *,
    contact_index: int | None = None,
    contact_coordinate: float | None = None,
    rate_threshold: float = 0.05,
    min_hold_points: int = 5,
    min_hold_fraction: float = 0.05,
    assume_uniform_rate: float | None = None,
    force_threshold_fraction: float = 0.1,
) -> ViscoelasticProtocolResult:
    """Identify the viscoelastic protocol of a force curve.

    Displacement holds are detected on the raw-height rate (constant
    displacement), force holds on the force rate with a drifting
    displacement.  When a contact coordinate is given the indentation axis
    is used for the loading/unloading classification; otherwise the raw
    height is used as the displacement proxy (documented).

    Trusted instrument labels in ``curve.metadata`` take precedence over
    inference.

    Time limitation: the JPK/NID readers do not populate ``segment.time``;
    this operation requires an explicit valid time axis or an explicitly
    requested known-rate reconstruction (``assume_uniform_rate``).  No
    automatic general JPK/NID time-domain analysis is claimed.
    """
    warnings: list[str] = []
    for key in _TRUSTED_PROTOCOL_KEYS:
        label = curve.metadata.get(key) if isinstance(curve.metadata, dict) else None
        if isinstance(label, str) and label.upper() in PROTOCOL_CLASSES:
            return ViscoelasticProtocolResult(
                protocol_type=label.upper(), regions=(),
                method="trusted_label", trusted_label=key,
                provenance={"label_key": key})
    if assume_uniform_rate is not None:
        if assume_uniform_rate <= 0.0:
            raise ValueError("assume_uniform_rate must be positive (s per sample)")
        warnings.append(
            f"reconstructed clock: uniform rate {assume_uniform_rate} s/sample assumed")

    segments: list[tuple[str, np.ndarray, np.ndarray, np.ndarray]] = []
    for s in curve.segments:
        if s.time is None:
            if assume_uniform_rate is None:
                raise ViscoelasticityError(
                    MISSING_TIME,
                    f"segment {s.segment_type!r} lacks a time axis")
            t = np.arange(len(s), dtype=np.float64) * assume_uniform_rate
        else:
            t = validate_time_axis(np.asarray(s.time, dtype=np.float64))
        if s.force is None:
            raise ViscoelasticityError(CURVE_NOT_FIT_ELIGIBLE,
                                       f"segment {s.segment_type!r} is not calibrated")
        disp = np.asarray(s.raw_height, dtype=np.float64)
        if contact_index is not None and contact_coordinate is not None \
                and s.segment_type == "extend":
            sep = np.asarray(s.raw_height, dtype=np.float64)
            ind = sep - float(contact_coordinate)
            disp = np.where(np.arange(sep.size) >= contact_index, ind, disp)
        segments.append((s.segment_type, t, disp, np.asarray(s.force, dtype=np.float64)))

    regions_out: list[ProtocolRegion] = []
    all_regions: list[dict] = []
    for seg_name, t, disp, force in segments:
        if disp.size < 2:
            continue
        regs = _rate_regions(t, disp, force, rate_threshold, min_hold_points)
        for r in regs:
            r["segment"] = seg_name
        all_regions.extend(regs)
        for r in regs:
            regions_out.append(ProtocolRegion(
                kind=r["kind"], segment=seg_name, start_index=r["start"],
                end_index=r["end"], start_time=r["t0"], end_time=r["t1"]))

    holds = [r for r in all_regions if r["kind"].startswith("hold")]
    loading = [r for r in all_regions if r["kind"] == "loading"]
    unloading = [r for r in all_regions if r["kind"] == "unloading"]
    extend_loading = [r for r in loading if r["segment"] == "extend"]

    if not holds and not extend_loading:
        return ViscoelasticProtocolResult(
            protocol_type=INSUFFICIENT_PROTOCOL, regions=tuple(regions_out),
            method="rate_regions", ambiguity=True, warnings=tuple(warnings),
            provenance={"reason": "no loading or hold region identified"})

    force_holds = [r for r in holds if r["kind"] == "hold_force"]
    disp_holds = [r for r in holds if r["kind"] == "hold_displacement"]

    if force_holds:
        # CREEP requires the force to be held while displacement drifts
        protocol = CREEP
    elif disp_holds:
        # STRESS_RELAXATION: displacement hold with decaying force
        h = disp_holds[0]
        seg = next(s for s in segments if s[0] == h["segment"])
        fh = seg[3][h["start"]: h["end"] + 1]
        f0 = float(fh[0])
        decay = (float(fh[-1]) - f0) / abs(f0) if f0 != 0.0 else 0.0
        if f0 != 0.0 and decay <= -force_threshold_fraction:
            protocol = STRESS_RELAXATION
        else:
            protocol = DISPLACEMENT_HOLD
    elif unloading and extend_loading:
        protocol = TRIANGULAR_LOADING
    elif extend_loading:
        protocol = LOADING_RAMP
    else:
        protocol = INSUFFICIENT_PROTOCOL

    ambiguity = protocol in (INSUFFICIENT_PROTOCOL, AMBIGUOUS_PROTOCOL)
    if force_holds and disp_holds:
        ambiguity = True
        warnings.append("both force-hold and displacement-hold regions found")
    return ViscoelasticProtocolResult(
        protocol_type=protocol, regions=tuple(regions_out), method="rate_regions",
        ambiguity=ambiguity, warnings=tuple(warnings),
        provenance={"rate_threshold": rate_threshold,
                    "min_hold_points": min_hold_points,
                    "min_hold_fraction": min_hold_fraction,
                    "assume_uniform_rate": assume_uniform_rate})


@dataclass(frozen=True)
class IndentationRateResult:
    """Indentation and force rates of one protocol region."""

    indentation_rate: float
    force_rate: float
    local_indentation_rates: np.ndarray
    local_force_rates: np.ndarray
    indentation_rate_low: float
    indentation_rate_high: float
    included_indices: np.ndarray
    region: str
    units: str = "m/s"
    warnings: tuple[str, ...] = ()


def compute_indentation_rate(
    prepared: ForcePreparationResult,
    protocol: ViscoelasticProtocolResult,
    *,
    region: str = "loading",
    segment: str | None = "extend",
) -> IndentationRateResult:
    """Robust indentation and force rate of one protocol region.

    The region is located via ``protocol.region(region, segment)``; local
    rates are finite differences of the indentation (separation minus the
    contact coordinate) and the force over that region; the reported rate is
    the median of the local rates with the 25-75 percentile spread.

    Requires a valid approach time axis (the JPK/NID readers do not
    populate it; provide one or use an explicitly requested known-rate
    reconstruction).
    """
    if not isinstance(prepared, ForcePreparationResult):
        raise TypeError("compute_indentation_rate requires a ForcePreparationResult")
    reg = protocol.region(region, segment)
    if reg is None:
        raise ViscoelasticityError(EMPTY_REGION, f"no {region!r} region on {segment!r}")
    approach = prepared.curve.extend
    if approach is None or approach.separation is None or approach.force is None:
        raise ViscoelasticityError(CURVE_NOT_FIT_ELIGIBLE, "no prepared approach branch")
    t = validate_time_axis(np.asarray(approach.time, dtype=np.float64))
    a, b = reg.start_index, reg.end_index + 1
    if b > t.size:
        raise ViscoelasticityError(EMPTY_REGION, "region outside the approach segment")
    sep = np.asarray(approach.separation, dtype=np.float64)
    ind = sep - float(prepared.contact.selected.coordinate)
    f = np.asarray(approach.force, dtype=np.float64)
    dt = np.diff(t[a:b])
    if np.any(dt <= 0.0):
        raise ViscoelasticityError(NONMONOTONIC_TIME, "region time axis not increasing")
    rate_ind = np.diff(ind[a:b]) / dt
    rate_f = np.diff(f[a:b]) / dt
    if rate_ind.size == 0:
        raise ViscoelasticityError(EMPTY_REGION, "region has fewer than 2 samples")
    med_ind = float(np.median(rate_ind))
    lo, hi = float(np.percentile(rate_ind, 25)), float(np.percentile(rate_ind, 75))
    return IndentationRateResult(
        indentation_rate=med_ind,
        force_rate=float(np.median(rate_f)),
        local_indentation_rates=rate_ind,
        local_force_rates=rate_f,
        indentation_rate_low=lo,
        indentation_rate_high=hi,
        included_indices=np.arange(a, b),
        region=f"{segment}:{region}",
        warnings=(f"region {a}..{b - 1} of {t.size} samples",),
    )


def _hold_window(prepared: ForcePreparationResult,
                 protocol: ViscoelasticProtocolResult,
                 hold_kind: str, segment: str) -> tuple[np.ndarray, np.ndarray,
                                                        np.ndarray, np.ndarray]:
    approach = prepared.curve.extend
    if approach is None or approach.separation is None or approach.force is None \
            or approach.time is None:
        raise ViscoelasticityError(CURVE_NOT_FIT_ELIGIBLE, "no prepared approach branch")
    reg = protocol.region(hold_kind, segment)
    if reg is None:
        raise ViscoelasticityError(
            EMPTY_REGION,
            f"protocol {protocol.protocol_type!r} has no {hold_kind!r} region")
    t = validate_time_axis(np.asarray(approach.time, dtype=np.float64))
    a, b = reg.start_index, reg.end_index + 1
    if b > t.size:
        raise ViscoelasticityError(EMPTY_REGION, "hold region outside the approach")
    sep = np.asarray(approach.separation, dtype=np.float64)
    ind = sep - float(prepared.contact.selected.coordinate)
    f = np.asarray(approach.force, dtype=np.float64)
    if not (np.isfinite(t[a:b]).all() and np.isfinite(ind[a:b]).all()
            and np.isfinite(f[a:b]).all()):
        raise ViscoelasticityError(NONFINITE_RESPONSE, "non-finite hold response")
    return t[a:b], ind[a:b], f[a:b], np.arange(a, b)


@dataclass(frozen=True)
class RelaxationResponseResult:
    """Stress-relaxation response of a displacement hold."""

    relative_time: np.ndarray
    indentation: np.ndarray
    force: np.ndarray
    normalized_force: np.ndarray
    hold_indices: np.ndarray
    hold_start_time: float
    force_at_hold_start: float
    equilibrium_force_estimate: float
    units: str = "s / m / N"
    warnings: tuple[str, ...] = ()


def extract_stress_relaxation(
    prepared: ForcePreparationResult,
    protocol: ViscoelasticProtocolResult,
    *,
    segment: str = "extend",
    hold_kind: str = "hold_displacement",
    equilibrium_tail_fraction: float = 0.1,
) -> RelaxationResponseResult:
    """Extract the normalized stress-relaxation response of the hold.

    Requires a displacement-hold region; the normalized response is
    F(t)/F(t0) on the relative hold time.  The equilibrium-force estimate
    is the mean of the last ``equilibrium_tail_fraction`` of the hold
    (documented estimate, not a guaranteed equilibrium).
    """
    t, ind, f, idx = _hold_window(prepared, protocol, hold_kind, segment)
    if t.size < 2:
        raise ViscoelasticityError(EMPTY_REGION, "hold region too short")
    t0 = float(t[0])
    f0 = float(f[0])
    if f0 == 0.0:
        raise ViscoelasticityError(INVALID_RESPONSE, "hold-start force is zero")
    tail = max(1, int(round(t.size * equilibrium_tail_fraction)))
    eq = float(np.mean(f[-tail:]))
    return RelaxationResponseResult(
        relative_time=t - t0,
        indentation=ind,
        force=f,
        normalized_force=f / f0,
        hold_indices=idx,
        hold_start_time=t0,
        force_at_hold_start=f0,
        equilibrium_force_estimate=eq,
        warnings=(f"equilibrium estimate: mean of last {tail} hold samples",),
    )


@dataclass(frozen=True)
class CreepResponseResult:
    """Creep response of a force hold."""

    relative_time: np.ndarray
    force: np.ndarray
    indentation: np.ndarray
    compliance_proxy: np.ndarray
    hold_indices: np.ndarray
    hold_start_time: float
    force_hold_value: float
    indentation_at_hold_start: float
    units: str = "s / N / m / (m/N)"
    warnings: tuple[str, ...] = ()


def extract_creep_compliance(
    prepared: ForcePreparationResult,
    protocol: ViscoelasticProtocolResult,
    *,
    segment: str = "extend",
    hold_kind: str = "hold_force",
    hold_force_median: bool = True,
) -> CreepResponseResult:
    """Extract the creep compliance proxy J(t) = indentation(t)/F_hold.

    Requires a force-hold region; F_hold is the median (or mean) force over
    the hold.  The compliance proxy is a raw m/N ratio, not a calibrated
    material compliance.
    """
    t, ind, f, idx = _hold_window(prepared, protocol, hold_kind, segment)
    if t.size < 2:
        raise ViscoelasticityError(EMPTY_REGION, "hold region too short")
    f_hold = float(np.median(f)) if hold_force_median else float(np.mean(f))
    if f_hold == 0.0:
        raise ViscoelasticityError(INVALID_RESPONSE, "held force is zero")
    # the compliance proxy is the INCREMENT from the hold start:
    # (indentation(t) - indentation(0)) / F_hold.  The increment is the
    # standard creep-measurement quantity and is robust to the
    # contact-coordinate precision (the absolute level is carried in
    # indentation_at_hold_start).
    return CreepResponseResult(
        relative_time=t - float(t[0]),
        force=f,
        indentation=ind,
        compliance_proxy=(ind - float(ind[0])) / f_hold,
        hold_indices=idx,
        hold_start_time=float(t[0]),
        force_hold_value=f_hold,
        indentation_at_hold_start=float(ind[0]),
        warnings=("compliance increment = (indentation - indentation(0))/"
                  "F_hold (raw m/N, robust to the contact-coordinate "
                  "offset; not a calibrated material compliance)",),
    )
