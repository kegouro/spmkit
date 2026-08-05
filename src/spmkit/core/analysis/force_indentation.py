"""FS-F2 indentation and fit-window selection.

Computes indentation from a prepared curve (contact-aware, no hidden offsets)
and selects an explicit fit window on the approach branch.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from spmkit.core.analysis.force_foundation import ForcePreparationResult
from spmkit.core.analysis.force_mechanics_errors import (
    CURVE_NOT_FIT_ELIGIBLE,
    EMPTY_FIT_WINDOW,
    INSUFFICIENT_FIT_POINTS,
    INVALID_INDENTATION,
    NONFINITE_INPUT,
    ForceMechanicsError,
)


def _contact_methods(prepared: ForcePreparationResult) -> list[str]:
    contact = prepared.provenance.get("contact", {})
    if isinstance(contact, dict):
        methods = contact.get("methods", [])
        if isinstance(methods, list):
            return [str(m) for m in methods]
    return []


@dataclass(frozen=True)
class IndentationResult:
    """Contact-relative indentation of the approach branch."""

    indentation: np.ndarray
    contact_index: int
    contact_coordinate: float
    separation: np.ndarray
    valid: np.ndarray
    units: str = "m"
    warnings: tuple[str, ...] = ()
    provenance: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FitWindowResult:
    """Explicit fit window on the indentation axis."""

    start_index: int
    end_index: int
    indentation_min: float
    indentation_max: float
    force_min: float
    force_max: float
    included: np.ndarray
    excluded_reasons: tuple[str, ...]
    n_points: int
    warnings: tuple[str, ...] = ()


def compute_indentation(
    prepared: ForcePreparationResult,
) -> IndentationResult:
    """Indentation = separation - contact_coordinate on the approach branch.

    The contact coordinate is the height at the contact index (FS-F1
    convention; the deflection is zero there, so height and separation
    coincide at the contact).  Indentation therefore equals the piezo
    motion past the contact minus the cantilever deflection; it is zero at
    the contact and positive into the sample when the deflection grows more
    slowly than the piezo motion (indentation regime).  Only the approach
    branch is used; samples before the contact are excluded (negative
    indentation is not fabricated).
    """
    if not isinstance(prepared, ForcePreparationResult):
        raise TypeError("compute_indentation requires a ForcePreparationResult")
    if not prepared.quality.eligible:
        raise ForceMechanicsError(
            CURVE_NOT_FIT_ELIGIBLE,
            "curve is not fit-eligible: " + ", ".join(prepared.quality.failure_reasons))
    approach = prepared.curve.extend
    if approach is None or approach.force is None:
        raise ForceMechanicsError(CURVE_NOT_FIT_ELIGIBLE, "no calibrated approach")
    if approach.separation is None:
        raise ForceMechanicsError(INVALID_INDENTATION, "no tip-sample separation")
    sep = np.asarray(approach.separation, dtype=np.float64)
    f = np.asarray(approach.force, dtype=np.float64)
    if not np.isfinite(sep).all() or not np.isfinite(f).all():
        raise ForceMechanicsError(NONFINITE_INPUT, "non-finite separation/force")
    zc = float(prepared.contact.selected.coordinate)
    ind = sep - zc
    valid = ind >= 0.0
    return IndentationResult(
        indentation=ind,
        contact_index=prepared.contact.selected.index,
        contact_coordinate=zc,
        separation=sep,
        valid=valid,
        provenance={
            "convention": "indentation = separation - contact_coordinate",
            "contact_index": prepared.contact.selected.index,
            "contact_methods": _contact_methods(prepared),
        },
    )


def select_contact_fit_window(
    prepared: ForcePreparationResult,
    indentation: IndentationResult,
    *,
    min_indentation: float | None = None,
    max_indentation: float | None = None,
    min_force: float | None = None,
    max_force: float | None = None,
    min_points: int = 20,
) -> FitWindowResult:
    """Select the explicit fit window on the approach indentation axis.

    Negative indentation is always excluded; force bounds exclude the
    adhesion region and saturation; no automatic window expansion.
    """
    ind = np.asarray(indentation.indentation, dtype=np.float64)
    approach = prepared.curve.extend
    if approach is None or approach.force is None:
        raise ForceMechanicsError(CURVE_NOT_FIT_ELIGIBLE, "no calibrated approach")
    f = np.asarray(approach.force, dtype=np.float64)
    included = np.ones(ind.size, dtype=bool)
    reasons: list[str] = []
    included &= ind >= 0.0
    if min_indentation is not None:
        included &= ind >= min_indentation
    if max_indentation is not None:
        included &= ind <= max_indentation
    if min_force is not None:
        included &= f >= min_force
    if max_force is not None:
        included &= f <= max_force
    idx = np.flatnonzero(included)
    if idx.size == 0:
        raise ForceMechanicsError(EMPTY_FIT_WINDOW, "no samples satisfy the window")
    start, end = int(idx[0]), int(idx[-1])
    if end - start + 1 < min_points:
        raise ForceMechanicsError(
            INSUFFICIENT_FIT_POINTS,
            f"fit window has {end - start + 1} points < min_points={min_points}")
    return FitWindowResult(
        start_index=start,
        end_index=end,
        indentation_min=float(ind[start]),
        indentation_max=float(ind[end]),
        force_min=float(np.min(f[idx])),
        force_max=float(np.max(f[idx])),
        included=included,
        excluded_reasons=tuple(reasons),
        n_points=int(idx.size),
        warnings=(f"excluded {ind.size - idx.size} sample(s) before/outside window",)
        if idx.size < ind.size else (),
    )
