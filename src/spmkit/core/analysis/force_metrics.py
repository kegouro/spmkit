"""Force event and work metrics foundation (FS-F1).

Events: snap-in (approach, before contact) and pull-off (retract, after
contact), baseline-relative, with physical windows.  Work: force integrated
over tip-sample separation on the common overlap domain with monotone
interpolation and trapezoidal arithmetic.

Acquisition-path work (FS-R1C): the signed line integral along a single
trajectory in **sample-acquisition order** (``integrate_force_path_work``)
with deterministic trapezoidal arithmetic and explicit coordinate-path
diagnostics.  This is a distinct scientific object from the strict
monotonic-coordinate integral above: local reversals and loops are retained,
never sorted, smoothed or deleted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from spmkit.core.analysis.force_contact import (
    ContactPointCandidate,
    ContactPointResult,
)
from spmkit.core.analysis.force_foundation_errors import (
    EVENT_NOT_FOUND,
    INSUFFICIENT_OVERLAP,
    INSUFFICIENT_SAMPLES,
    LENGTH_MISMATCH,
    MISSING_CALIBRATION,
    MISSING_COORDINATE,
    MISSING_RETRACT,
    NONMONOTONIC_COORDINATE,
    ForceFoundationError,
    require_finite,
    require_monotone_increasing,
)
from spmkit.core.models import ForceCurve

#: Dirección global de una trayectoria (clasificación, nunca la integral).
GlobalDirection = Literal["increasing", "decreasing", "closed_or_ambiguous"]


@dataclass(frozen=True)
class ForceEventResult:
    """Snap-in and pull-off event characterization."""

    snap_in_index: int | None
    snap_in_force: float | None
    snap_in_coordinate: float | None
    pull_off_index: int | None
    pull_off_force: float | None
    pull_off_coordinate: float | None
    event_windows: dict[str, tuple[float, float]] = field(default_factory=dict)
    valid: bool = True
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ForceWorkResult:
    """Work integrals over the common tip-position overlap domain."""

    work_approach: float
    work_retract: float
    work_adhesion: float
    hysteresis: float
    domain: str
    interpolation: str
    units: str
    valid: bool
    warnings: tuple[str, ...] = ()


def _axis(curve: ForceCurve, segment_name: str) -> np.ndarray:
    seg = curve.extend if segment_name == "approach" else curve.retract
    if seg is None:
        raise ForceFoundationError(MISSING_RETRACT, f"no {segment_name} segment")
    if seg.separation is not None:
        axis = np.asarray(seg.separation, dtype=np.float64)
    else:
        axis = np.asarray(seg.raw_height, dtype=np.float64)
    return require_finite(axis, label=f"{segment_name} axis")


def extract_force_events(
    curve: ForceCurve,
    contact: ContactPointResult | ContactPointCandidate,
    *,
    snap_in_window: tuple[float, float] | None = None,
    pull_off_window: tuple[float, float] | None = None,
) -> ForceEventResult:
    """Extract snap-in (approach) and pull-off (retract) events.

    Snap-in is the minimum force before contact in the approach window
    (baseline-relative: below the baseline mean minus 3 sigma).  Pull-off
    is the minimum force after contact on the retract.  Windows are physical
    coordinates on the selected axis (separation when available, else
    height).
    """
    approach = curve.extend
    retract = curve.retract
    if approach is None or approach.force is None:
        raise ForceFoundationError(MISSING_CALIBRATION, "approach must be calibrated")
    z_a = _axis(curve, "approach")
    f_a = require_finite(np.asarray(approach.force, dtype=np.float64), label="approach force")
    if isinstance(contact, ContactPointResult):
        cp_index = int(contact.selected.index)
    else:
        cp_index = int(contact.index)
    warnings: list[str] = []

    # snap-in
    snap_idx: int | None = None
    snap_force: float | None = None
    snap_coord: float | None = None
    if cp_index > 3:
        n_base = max(4, int(round(z_a.size * 0.10)))
        base_mean = float(np.mean(f_a[: min(n_base, cp_index)]))
        base_scale = float(np.std(f_a[: min(n_base, cp_index)]))
        search = np.arange(0, min(cp_index, z_a.size))
        if snap_in_window is not None:
            lo, hi = snap_in_window
            mask = (z_a >= lo) & (z_a <= hi)
            search = np.flatnonzero(mask & (np.arange(z_a.size) < cp_index))
        if search.size:
            i = int(search[int(np.argmin(f_a[search]))])
            if f_a[i] < base_mean - 3.0 * base_scale:
                snap_idx, snap_force, snap_coord = i, float(f_a[i]), float(z_a[i])
    else:
        warnings.append("approach too short for snap-in search")

    # pull-off
    po_idx: int | None = None
    po_force: float | None = None
    po_coord: float | None = None
    if retract is not None and retract.force is not None:
        z_r = _axis(curve, "retract")
        f_r = require_finite(np.asarray(retract.force, dtype=np.float64), label="retract force")
        search = np.arange(0, z_r.size)
        if pull_off_window is not None:
            lo, hi = pull_off_window
            mask = (z_r >= lo) & (z_r <= hi)
            search = np.flatnonzero(mask)
        if search.size:
            i = int(search[int(np.argmin(f_r[search]))])
            po_idx, po_force, po_coord = i, float(f_r[i]), float(z_r[i])
    else:
        warnings.append("no retract segment; pull-off not searched")

    windows = {}
    if snap_in_window is not None:
        windows["snap_in"] = snap_in_window
    if pull_off_window is not None:
        windows["pull_off"] = pull_off_window
    valid = snap_idx is not None or po_idx is not None
    if not valid:
        warnings.append(EVENT_NOT_FOUND)
    return ForceEventResult(
        snap_in_index=snap_idx,
        snap_in_force=snap_force,
        snap_in_coordinate=snap_coord,
        pull_off_index=po_idx,
        pull_off_force=po_force,
        pull_off_coordinate=po_coord,
        event_windows=windows,
        valid=valid,
        warnings=tuple(warnings),
    )


def _monotone_resample(x: np.ndarray, y: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Monotone interpolation of y(x) onto target (no extrapolation)."""
    order = np.argsort(x, kind="stable")
    xs, ys = x[order], y[order]
    require_monotone_increasing(xs, label="coordinate")
    return np.interp(target, xs, ys)


def integrate_force_work(
    curve: ForceCurve,
    contact: ContactPointResult | ContactPointCandidate,
    *,
    domain: str = "tip_position",
) -> ForceWorkResult:
    """Integrate force over tip-sample separation on the common overlap.

    The common domain runs from the contact coordinate to the minimum of
    the approach and retract maxima.  Interpolation is monotone (np.interp
    over the sorted coordinate); integration is trapezoidal.  Units: J.
    """
    if domain not in ("tip_position", "height"):
        raise ValueError(f"unknown integration domain {domain!r}")
    approach = curve.extend
    retract = curve.retract
    if approach is None or approach.force is None:
        raise ForceFoundationError(MISSING_CALIBRATION, "approach must be calibrated")
    if retract is None or retract.force is None:
        raise ForceFoundationError(MISSING_RETRACT, "retract must be calibrated")
    z_a = _axis(curve, "approach")
    f_a = require_finite(np.asarray(approach.force, dtype=np.float64), label="approach force")
    z_r = _axis(curve, "retract")
    f_r = require_finite(np.asarray(retract.force, dtype=np.float64), label="retract force")
    for zz, label in ((z_a, "approach"), (z_r, "retract")):
        d = np.diff(zz)
        scale = float(np.max(np.abs(zz)))
        tol = 1e-6 * scale if scale > 0.0 else 1e-300
        if not (np.all(d > -tol) or np.all(d < tol)):
            raise ForceFoundationError(
                NONMONOTONIC_COORDINATE, f"{label} coordinate not strictly monotone"
            )
    if isinstance(contact, ContactPointResult):
        zc = float(contact.selected.coordinate)
    else:
        zc = float(contact.coordinate)
    lo = zc
    hi = min(float(np.max(z_a)), float(np.max(z_r)))
    if hi - lo <= 0.0:
        raise ForceFoundationError(INSUFFICIENT_OVERLAP, "no common overlap domain")
    n_grid = max(64, int(min(z_a.size, z_r.size)))
    grid = np.linspace(lo, hi, n_grid)
    f_a_g = _monotone_resample(z_a, f_a, grid)
    f_r_g = _monotone_resample(z_r, f_r, grid)
    w_appr = float(np.trapezoid(f_a_g, grid))
    w_retr = float(np.trapezoid(f_r_g, grid))
    return ForceWorkResult(
        work_approach=w_appr,
        work_retract=w_retr,
        work_adhesion=w_retr,
        hysteresis=w_appr - w_retr,
        domain=domain,
        interpolation="linear_monotone",
        units="J",
        valid=True,
    )


# ---------------------------------------------------------------------------
# Acquisition-path work (FS-R1C)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoordinatePathDiagnostics:
    """Diagnósticos de una trayectoria 1-D en orden de adquisición.

    Todos los campos son **clasificación**; ninguno altera la integral.  El
    orden de muestra se conserva; los incrementos firmados ``dz`` se retienen
    tal cual (no se ordenan, no se aplica ``abs()``, no se suaviza, no se
    eliminan puntos).

    Definitions (independently testable):

    - ``net_displacement`` = ``z[-1] - z[0]``.
    - ``total_variation`` = sum |dz| over all steps.
    - ``forward_distance`` / ``backward_distance``: sums of |dz| for steps
      whose sign agrees / disagrees with the global direction.
    - ``backtracking_fraction`` = backward_distance / total_variation
      (0.0 when total_variation == 0).  NOTE: ``backward_distance`` aggregates
      step magnitudes (a sum of |dz|); ``maximum_reverse_excursion`` measures
      the deviation from the running directional extremum.  A path can have a
      large backtracking fraction (many tiny opposite steps) and a small
      maximum reverse excursion simultaneously; they are different quantities.
    - ``global_direction``: derived from the **net displacement** sign
      (never from the majority sign alone): negative → ``decreasing``,
      positive → ``increasing``, |net| <= ``classification_tolerance`` →
      ``closed_or_ambiguous``.
    - ``maximum_reverse_step``: the single step opposite to the global
      direction with the largest magnitude (signed: ``min(dz)`` for
      decreasing, ``max(dz)`` for increasing); ``None`` when there is no
      opposite step or the direction is ambiguous.
    - ``maximum_reverse_excursion``: the path-level cumulative excursion
      from the running directional extremum — for ``decreasing``:
      ``max_i (running_min(z[:i+1]) - z_i)``; for ``increasing``:
      ``max_i (z_i - running_max(z[:i+1]))``; ``0.0`` for a strictly
      directed path; ``None`` for ambiguous paths.
    """

    n_samples: int
    n_steps: int
    coordinate_unit: str
    net_displacement: float
    total_variation: float
    forward_distance: float
    backward_distance: float
    backtracking_fraction: float
    exact_positive_steps: int
    exact_negative_steps: int
    exact_zero_steps: int
    classified_reversal_count: int
    maximum_reverse_step: float | None
    maximum_reverse_excursion: float | None
    global_direction: GlobalDirection
    strictly_monotonic: bool
    globally_directed: bool
    classification_tolerance: float
    warnings: tuple[str, ...] = ()
    provenance: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ForcePathWorkResult:
    """Trabajo de trayectoria (path work) en orden de adquisición.

    ``work_total = work_forward + work_backward`` exactamente (cada paso
    pertenece a una sola clase).  ``absolute_accumulated_work`` es la suma de
    los valores absolutos de los términos trapezoidales: **no** es trabajo
    termodinámico ni energía disipada.
    """

    work_total: float
    work_forward: float
    work_backward: float
    absolute_accumulated_work: float
    diagnostics: CoordinatePathDiagnostics
    units: str
    valid: bool
    warnings: tuple[str, ...] = ()
    provenance: dict = field(default_factory=dict)


def _direction_sign(direction: GlobalDirection) -> int:
    """+1 increasing, -1 decreasing, 0 ambiguous."""
    return 1 if direction == "increasing" else (-1 if direction == "decreasing" else 0)


def coordinate_path_diagnostics(
    coordinate: np.ndarray,
    *,
    unit: str = "m",
    classification_tolerance: float = 0.0,
    provenance: dict | None = None,
) -> CoordinatePathDiagnostics:
    """Diagnósticos de trayectoria 1-D (clasificación, sin tocar la integral).

    Raises:
        ForceFoundationError: ``NONFINITE_DATA``, ``INSUFFICIENT_SAMPLES``.
    """
    z = require_finite(coordinate, label="coordinate")
    if z.size < 2:
        raise ForceFoundationError(
            INSUFFICIENT_SAMPLES, f"coordinate path needs >= 2 samples (got {z.size})"
        )
    if classification_tolerance < 0.0:
        raise ValueError("classification_tolerance must be >= 0")
    dz = np.diff(z)
    positive = dz > 0.0
    negative = dz < 0.0
    zero = dz == 0.0
    forward_dist = float(np.sum(dz[positive]))
    backward_dist = float(-np.sum(dz[negative]))
    total_var = float(np.sum(np.abs(dz)))
    net = float(z[-1] - z[0])

    warnings: list[str] = []
    if abs(net) <= classification_tolerance:
        direction: GlobalDirection = "closed_or_ambiguous"
        warnings.append(
            "no coherent global direction (|net displacement| <= classification_tolerance); "
            "signed path work is preserved and no approach/retract direction is assigned"
        )
    else:
        direction = "decreasing" if net < 0.0 else "increasing"

    sign = _direction_sign(direction)
    exact_pos = int(np.count_nonzero(positive))
    exact_neg = int(np.count_nonzero(negative))
    exact_zero = int(np.count_nonzero(zero))

    if sign == 0:
        reversal_count = 0
        max_reverse_step: float | None = None
        max_reverse_excursion: float | None = None
    else:
        opposite = dz * sign < 0.0
        beyond_tol = np.abs(dz) > classification_tolerance
        reversal_count = int(np.count_nonzero(opposite & beyond_tol))
        opp_steps = dz[opposite]
        if opp_steps.size:
            # paso opuesto a la dirección global de mayor magnitud (firmado):
            # decreciente -> el mayor paso positivo; creciente -> el más negativo
            max_reverse_step = float(opp_steps.max()) if sign < 0 else float(opp_steps.min())
        else:
            max_reverse_step = None
        if sign < 0:
            # decreciente: excursión = cuánto subió la trayectoria sobre el
            # mínimo corrido alcanzado hasta cada punto
            running_extremum = np.minimum.accumulate(z)
            excursion = z - running_extremum
        else:
            # creciente: excursión = cuánto bajó sobre el máximo corrido
            running_extremum = np.maximum.accumulate(z)
            excursion = running_extremum - z
        max_reverse_excursion = float(np.max(excursion)) if excursion.size else None

    # trayectoria ambigua: monótona solo si los pasos son de un solo signo
    strictly_monotonic = exact_pos == 0 or exact_neg == 0 if sign == 0 else reversal_count == 0
    backtracking_fraction = backward_dist / total_var if total_var > 0.0 else 0.0

    meta = dict(provenance or {})
    meta.update(
        {
            "semantics": "acquisition_order",
            "classification_tolerance": float(classification_tolerance),
            "unit": unit,
        }
    )
    return CoordinatePathDiagnostics(
        n_samples=int(z.size),
        n_steps=int(dz.size),
        coordinate_unit=unit,
        net_displacement=net,
        total_variation=total_var,
        forward_distance=forward_dist,
        backward_distance=backward_dist,
        backtracking_fraction=backtracking_fraction,
        exact_positive_steps=exact_pos,
        exact_negative_steps=exact_neg,
        exact_zero_steps=exact_zero,
        classified_reversal_count=reversal_count,
        maximum_reverse_step=max_reverse_step,
        maximum_reverse_excursion=max_reverse_excursion,
        global_direction=direction,
        strictly_monotonic=strictly_monotonic,
        globally_directed=sign != 0,
        classification_tolerance=float(classification_tolerance),
        warnings=tuple(warnings),
        provenance=meta,
    )


def integrate_force_path_work(
    coordinate: np.ndarray,
    force: np.ndarray,
    *,
    coordinate_unit: str = "m",
    force_unit: str = "N",
    classification_tolerance: float = 0.0,
    provenance: dict | None = None,
) -> ForcePathWorkResult:
    """Trabajo firmado de trayectoria (path work) en orden de adquisición.

    ``W = sum_i 0.5 * (F_i + F_{i+1}) * (z_{i+1} - z_i)`` evaluada en el
    orden de muestreo, con aritmética float64 determinista por acumulación
    explícita.  Los incrementos firmados ``dz`` se conservan: las reversiones
    locales y los lazos cerrados aportan su trabajo firmado; las coordenadas
    repetidas aportan cero; traducir la coordenada no cambia ``W``; invertir
    el orden de adquisición cambia el signo.

    El resultado incluye la descomposición (pasos en la dirección global /
    opuestos) y los diagnósticos de trayectoria completos.  Ninguna tolerancia
    altera la integral: ``classification_tolerance`` solo clasifica.

    Raises:
        ForceFoundationError: ``NONFINITE_DATA``, ``LENGTH_MISMATCH``,
            ``INSUFFICIENT_SAMPLES``, ``MISSING_COORDINATE`` (coordenada o
            fuerza vacías); ``ValueError`` (tolerancia negativa).
    """
    if np.asarray(coordinate).size == 0:
        raise ForceFoundationError(MISSING_COORDINATE, "coordinate axis is empty")
    if np.asarray(force).size == 0:
        raise ForceFoundationError(MISSING_COORDINATE, "force axis is empty")
    z = require_finite(coordinate, label="coordinate")
    f = require_finite(force, label="force")
    if z.size != f.size:
        raise ForceFoundationError(
            LENGTH_MISMATCH,
            f"coordinate and force lengths differ ({z.size} != {f.size})",
        )
    if z.size < 2:
        raise ForceFoundationError(
            INSUFFICIENT_SAMPLES, f"path work needs >= 2 samples (got {z.size})"
        )
    if classification_tolerance < 0.0:
        raise ValueError("classification_tolerance must be >= 0")

    diagnostics = coordinate_path_diagnostics(
        z,
        unit=coordinate_unit,
        classification_tolerance=classification_tolerance,
        provenance=provenance,
    )
    dz = np.diff(z)
    terms = 0.5 * (f[:-1] + f[1:]) * dz  # trapezoid term por paso (firmado)

    # Acumulación explícita en orden de adquisición (orden de aritmética fijo).
    sign = _direction_sign(diagnostics.global_direction)
    work_total = 0.0
    work_forward = 0.0
    work_backward = 0.0
    absolute_acc = 0.0
    for i in range(terms.size):
        term = float(terms[i])
        work_total += term
        absolute_acc += abs(term)
        if sign == 0:
            # dirección ambigua: la división es por el signo del paso dz
            if dz[i] >= 0.0:
                work_forward += term
            else:
                work_backward += term
        elif (dz[i] > 0.0) == (sign > 0):
            work_forward += term
        else:
            work_backward += term

    warnings = list(diagnostics.warnings)
    if diagnostics.global_direction == "closed_or_ambiguous":
        warnings.append(
            "work_forward/work_backward split by step sign dz (no global direction assigned)"
        )
    if abs(work_total - (work_forward + work_backward)) > 1e-12 * max(
        1.0, abs(work_total)
    ):
        warnings.append("decomposition invariant |W - (W_f + W_b)| exceeded float tolerance")

    meta = dict(provenance or {})
    meta.update(
        {
            "semantics": "acquisition_path",
            "arithmetic": "trapezoidal_acquisition_order",
            "coordinate_unit": coordinate_unit,
            "force_unit": force_unit,
            "classification_tolerance": float(classification_tolerance),
        }
    )
    units = (
        "J" if (coordinate_unit, force_unit) == ("m", "N") else f"{force_unit}·{coordinate_unit}"
    )
    return ForcePathWorkResult(
        work_total=work_total,
        work_forward=work_forward,
        work_backward=work_backward,
        absolute_accumulated_work=absolute_acc,
        diagnostics=diagnostics,
        units=units,
        valid=True,
        warnings=tuple(warnings),
        provenance=meta,
    )
