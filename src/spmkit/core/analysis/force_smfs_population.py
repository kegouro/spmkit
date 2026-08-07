"""FS-F4 SMFS population aggregation and batch orchestration.

Population analysis aggregates events without claiming molecular identity.
Batch analysis retains every per-curve result and every failure reason;
nothing is silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from spmkit.core.analysis.force_smfs_errors import (
    INSUFFICIENT_EVENTS,
    SmfsError,
)


@dataclass(frozen=True)
class SMFSPopulationResult:
    """Aggregated event population with raw assignments and ambiguity."""

    n_events: int
    rupture_forces: np.ndarray
    contour_increments: np.ndarray
    loading_rates: np.ndarray
    curve_origins: np.ndarray
    group_assignments: np.ndarray
    group_config: dict[str, object]
    rupture_force_summary: dict[str, float]
    contour_increment_summary: dict[str, float]
    loading_rate_summary: dict[str, float]
    ambiguous: bool
    warnings: tuple[str, ...] = ()
    provenance: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SMFSBatchResult:
    """Deterministic per-curve SMFS analysis with a unified event table."""

    n_curves: int
    n_ok: int
    n_failed: int
    per_curve: tuple[dict[str, object], ...]
    failed_reasons: dict[int, str]
    unified_event_table: tuple[dict[str, object], ...]
    population: SMFSPopulationResult | None
    provenance: dict[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


def _to_float(value: object) -> float:
    if isinstance(value, (int, float, np.generic)):
        return float(value)
    return float("nan")


def _summary(values: np.ndarray) -> dict[str, float]:
    if values.size == 0:
        return {"n": 0.0, "mean": float("nan"), "median": float("nan"),
                "std": float("nan"), "min": float("nan"), "max": float("nan")}
    return {"n": float(values.size), "mean": float(np.mean(values)),
            "median": float(np.median(values)), "std": float(np.std(values)),
            "min": float(np.min(values)), "max": float(np.max(values))}


def analyze_smfs_event_population(
    event_records: list[dict[str, object]],
    *,
    group_by: str = "loading_rate_decade",
    n_groups: int = 4,
    force_levels: np.ndarray | None = None,
) -> SMFSPopulationResult:
    """Aggregate event records into a population.

    ``group_by``: "none" (single group) or "loading_rate_decade" (the
    loading-rate decades define deterministic groups).  Raw group
    assignments are exposed; no molecular-identity claim is made.
    """
    n = len(event_records)
    if n == 0:
        raise SmfsError(INSUFFICIENT_EVENTS, "no events to aggregate")
    forces = np.asarray([_to_float(r.get("rupture_force", np.nan))
                        for r in event_records])
    dlt = np.asarray([_to_float(r.get("delta_contour_length", np.nan))
                      for r in event_records])
    rates = np.asarray([_to_float(r.get("loading_rate", np.nan))
                        for r in event_records])
    origins = np.asarray([str(r.get("curve_id", "")) for r in event_records],
                         dtype=object)
    if group_by == "none":
        assignments = np.zeros(n, dtype=np.int64)
        config: dict[str, object] = {"group_by": "none", "n_groups": 1}
    elif group_by == "loading_rate_decade":
        finite = rates[np.isfinite(rates)]
        if finite.size == 0:
            raise SmfsError(INSUFFICIENT_EVENTS, "no finite loading rates to group")
        lo = np.floor(np.log10(np.min(finite)))
        hi = np.ceil(np.log10(np.max(finite)))
        edges = np.linspace(lo, hi, n_groups + 1)
        assignments = np.clip(
            np.searchsorted(edges, np.log10(rates), side="right") - 1,
            0, n_groups - 1)
        config = {"group_by": "loading_rate_decade", "n_groups": n_groups,
                  "log10_edges": edges.tolist()}
    else:
        raise ValueError(f"unknown group_by {group_by!r}")
    # ambiguity: too few events for any population claim, or groups too
    # small to support a grouping interpretation
    counts = np.bincount(assignments, minlength=int(np.max(assignments)) + 1)
    ambiguous = bool(n < 5 or np.max(counts) < 2)
    return SMFSPopulationResult(
        n_events=n, rupture_forces=forces, contour_increments=dlt,
        loading_rates=rates, curve_origins=origins, group_assignments=assignments,
        group_config=config, rupture_force_summary=_summary(forces),
        contour_increment_summary=_summary(dlt[np.isfinite(dlt)]),
        loading_rate_summary=_summary(rates[np.isfinite(rates)]),
        ambiguous=ambiguous,
        warnings=("population grouping is a descriptive aggregation; no "
                  "molecular-identity claim is made",),
        provenance={"group_by": group_by, "n_groups": n_groups})


def analyze_smfs_batch(
    analyses: list[dict[str, object]],
    *,
    group_by: str = "loading_rate_decade",
    n_groups: int = 4,
) -> SMFSBatchResult:
    """Deterministic batch orchestration over per-curve analyses.

    Each ``analyses`` entry is a per-curve record produced by the caller
    (e.g. the FS-F4 pipeline): {"curve_id", "ok", "events": [...], ...}.
    Failed curves are retained with their reasons; the unified event table
    collects every event across curves with its curve origin.
    """
    n_curves = len(analyses)
    ok = [a for a in analyses if a.get("ok", False)]
    failed = [a for a in analyses if not a.get("ok", False)]
    failed_reasons: dict[int, str] = {}
    for i, a in enumerate(analyses):
        if not a.get("ok", False):
            idx = a.get("curve_index", i)
            failed_reasons[int(idx) if isinstance(idx, (int, float)) else i] = \
                str(a.get("failure", "unknown"))
    unified: list[dict[str, object]] = []
    for a in ok:
        events = a.get("events", [])
        for ev in events if isinstance(events, list) else []:
            rec = dict(ev)
            rec["curve_id"] = str(a.get("curve_id", ""))
            unified.append(rec)
    population = analyze_smfs_event_population(
        unified, group_by=group_by, n_groups=n_groups) if unified else None
    return SMFSBatchResult(
        n_curves=n_curves, n_ok=len(ok), n_failed=len(failed),
        per_curve=tuple(analyses), failed_reasons=failed_reasons,
        unified_event_table=tuple(unified), population=population or None,
        provenance={"pipeline": ["per-curve SMFS analysis",
                                 "unified event table", "population"],
                    "deterministic": True, "n_unified_events": len(unified)})
