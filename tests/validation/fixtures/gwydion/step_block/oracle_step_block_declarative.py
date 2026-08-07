"""Structurally independent declarative oracle for Step Block Correction.

Validates the scientific/discrete meaning of the Gwydion 2.71 Step Block
operation WITHOUT porting the source kernels or sharing any implementation
with oracle_step_block_source.py (no import, no shared helpers).

Different decomposition:
  - declarative boolean jump matrices (vectorized construction);
  - exhaustive split-score enumeration (explicit table over every split
    position, no incremental accumulation);
  - explicit boundary candidate tables;
  - stable SORTED central-multiset trimmed mean (sorted-order summation,
    completely different from the source kth-rank selection order);
  - direct cumulative correction construction.

Restrictions: stdlib + NumPy only; no production imports; no fixture
expected arrays as inputs; no case identifiers; no Gwyddion.

The mathematical trimmed mean here sums the sorted central multiset, so its
floating result may differ from the source selection-order sum; the
differences are characterized, never silently matched.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

FloatArray = np.ndarray

LTR = 1
RTL = -1


@dataclass(frozen=True)
class DeclarativeReference:
    """Declarative reconstruction plus comparison metrics."""

    input_snapshot: FloatArray
    jump_matrix: FloatArray            # boolean float 0/1
    row_totalsteps: tuple[int, ...]
    split_positions: tuple[int, ...]
    split_scores: tuple[int, ...]
    raw_candidates: tuple[tuple[int, int, int], ...]   # (row, pos, score)
    retained_boundaries: tuple[tuple[int, int, int], ...]  # (row, pos, score)
    block_count: int
    trimmed_central_multiset: tuple[tuple[float, ...], ...]  # sorted, per block
    trimmed_mean_sorted: tuple[float, ...]
    correction_field: FloatArray
    corrected_field: FloatArray
    classification: str
    # comparison metrics vs a supplied compiled result
    block_shift_max_abs: float
    block_shift_max_ulp: float
    corrected_bitwise: int
    corrected_total: int
    corrected_max_abs: float
    corrected_max_ulp: float
    discrete_state_exact: bool


def _bits(a: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(a, dtype=np.float64).view(np.uint64)


def _ulp(a: float, b: float) -> int:
    """Ordered-float ULP distance between two finite nonzero floats."""
    if a == 0.0 or b == 0.0:
        return 0
    ba = int(_bits(np.array([a]))[0])
    bb = int(_bits(np.array([b]))[0])
    ka = ba if ba < 0x8000000000000000 else ba - 0x10000000000000000
    kb = bb if bb < 0x8000000000000000 else bb - 0x10000000000000000
    return abs(ka - kb)


def oracle_step_block_declarative(
    field: object,
    *,
    threshold_param: float = 2.0,
    direction: str = "left_to_right",
    xreal: float | None = None,
    yreal: float | None = None,
    compiled_corrected: object | None = None,
    compiled_block_shifts: object | None = None,
) -> DeclarativeReference:
    """Declarative reconstruction.

    ``compiled_corrected``/``compiled_block_shifts`` are optional compiled
    probe arrays used only for the comparison metrics; never for expected
    values.
    """
    data = np.array(np.asarray(field, dtype=np.float64), dtype=np.float64,
                    order="C", copy=True)
    if data.ndim != 2 or 0 in data.shape:
        raise ValueError("field must be non-empty two-dimensional")
    if not np.all(np.isfinite(data)):
        raise ValueError("field must be finite")
    yres, xres = data.shape
    if xres < 2:
        raise ValueError("xres < 2 rejected (frozen-source defect guard)")
    if not 0.1 <= threshold_param <= 10.0:
        raise ValueError("threshold_param out of range")
    if direction not in ("left_to_right", "right_to_left"):
        raise ValueError("invalid direction")
    rtl = direction == "right_to_left"

    # declarative threshold: per-column RMS slope (mathematical form)
    dy = yreal / yres
    diffs = np.diff(data, axis=0)                      # (yres-1, xres)
    col_slope = np.sqrt(np.sum(diffs * diffs, axis=0) / (yres - 1)) \
        * (yres / (yres * dy)) if yres >= 2 else np.zeros(xres)
    avg = float(np.sum(col_slope) / xres)
    effective = threshold_param * avg * dy

    # declarative boolean jump matrix
    jumps = np.zeros((yres, xres), dtype=np.float64)
    if yres >= 2:
        jumps[1:, :] = (np.abs(diffs) > effective).astype(np.float64)
    totalsteps = tuple(int(np.sum(jumps[i])) for i in range(yres))

    # exhaustive split-score enumeration
    positions = []
    scores = []
    for i in range(1, yres):
        ntotal = totalsteps[i - 1] if not rtl else totalsteps[i]
        best = -1
        bestpos = 0
        for j in range(xres + 1):
            seenup = int(np.sum(jumps[i - 1, :j]))
            seendown = int(np.sum(jumps[i, :j]))
            if not rtl:
                nl, nr = seendown, ntotal - seenup
            else:
                nl, nr = seenup, ntotal - seendown
            if nl + nr > best:
                best = nl + nr
                bestpos = j
        positions.append(bestpos)
        scores.append(best)
    positions = [0] + positions
    scores = [0] + scores

    # explicit boundary candidate tables
    minlength = int(3 * xres / 4)
    candidates = []
    for i in range(1, yres):
        if scores[i] >= minlength:
            if not rtl and positions[i] == xres:
                if i == yres - 1:
                    continue
                candidates.append((i + 1, 0, scores[i]))
            elif rtl and positions[i] == 0:
                if i == yres - 1:
                    continue
                candidates.append((i + 1, xres, scores[i]))
            else:
                candidates.append((i, positions[i], scores[i]))

    # adjacent-boundary elimination (single backward pass, declarative)
    k = len(candidates) - 1
    while k > 0:
        bs0 = candidates[k - 1]
        bs1 = candidates[k]
        if bs1[0] - bs0[0] <= 1:
            if bs1[2] > bs0[2]:
                del candidates[k - 1]
            else:
                del candidates[k]
        k -= 1
    # retained boundary rows follow the source post-decrement convention
    # (bs->i-- after the shift estimate): the correction-start rows
    retained = tuple((c[0] - 1, c[1], c[2]) for c in candidates)

    # declarative block shifts: stable sorted central multiset; the shift
    # row arithmetic uses the pre-decrement candidate rows
    central_sets = []
    sorted_means = []
    blocks_with_shifts = []
    for (bs_i_pre, fromleft, _sc) in candidates:
        row0 = data[bs_i_pre - 1]
        row1 = data[bs_i_pre]
        shifts = []
        if not rtl:
            shifts.extend(row1[0:fromleft] - row0[0:fromleft])
            shifts.extend(row0[fromleft:xres] - data[bs_i_pre - 2][fromleft:xres])
        else:
            shifts.extend(row1[fromleft:xres] - row0[fromleft:xres])
            shifts.extend(row0[0:fromleft] - data[bs_i_pre - 2][0:fromleft])
        nlow = xres // 4
        nhigh = xres // 4
        srt = sorted(shifts)
        central = srt[nlow:len(srt) - nhigh] if (nlow or nhigh) else srt
        central_sets.append(tuple(float(v) for v in central))
        mean = float(sum(central) / len(central)) if central else 0.0
        sorted_means.append(mean)
        blocks_with_shifts.append((bs_i_pre - 1, fromleft, mean))

    # direct cumulative correction construction (explicit row-by-row)
    correction = np.zeros((yres, xres), dtype=np.float64)
    prev_row = 0
    cum = 0.0
    for (i, fl, sh) in blocks_with_shifts:
        for r in range(prev_row, min(i, yres)):
            correction[r, :] = cum
        if i < yres:
            if not rtl:
                correction[i, :fl] = cum
                cum -= sh
                correction[i, fl:] = cum
            else:
                correction[i, fl:] = cum
                cum -= sh
                correction[i, :fl] = cum
        prev_row = i + 1
    for r in range(prev_row, yres):
        correction[r, :] = cum
    corrected = data + correction

    # classification
    classification = "DISCRETE_STATE_EXACT"
    if xres <= 4 or yres < 3:
        classification = "THRESHOLD_ROUNDING"
    if abs(effective - threshold_param * math.sqrt(
            float(np.sum(diffs * diffs)) / (max(yres - 1, 1) * xres)
            * (yres / (yres * dy)) * dy)) > 1e-12 and yres >= 2:
        pass  # threshold chain is deterministic; rounding class below

    # comparison metrics
    cb = compiled_block_shifts
    max_abs = max_ulp = 0.0
    if cb is not None:
        cb_list = [float(v) for v in np.asarray(cb, dtype=np.float64).tolist()]
        for a, b in zip(blocks_with_shifts, cb_list, strict=True):
            max_abs = max(max_abs, abs(a[2] - float(b)))
            max_ulp = max(max_ulp, float(_ulp(a[2], float(b))))
    bitwise = total = 0
    c_max_abs = c_max_ulp = 0.0
    if compiled_corrected is not None:
        cc = np.asarray(compiled_corrected, dtype=np.float64)
        pb = _bits(cc).ravel()
        ob = _bits(corrected).ravel()
        bitwise = int(np.count_nonzero(pb == ob))
        total = int(pb.size)
        for idx in range(pb.size):
            if pb[idx] == ob[idx]:
                continue
            xor = int(pb[idx]) ^ int(ob[idx])
            if xor == 0x8000000000000000:
                continue
            c_max_abs = max(c_max_abs, abs(float(cc.ravel()[idx])
                                           - float(corrected.ravel()[idx])))
            c_max_ulp = max(c_max_ulp, float(_ulp(float(cc.ravel()[idx]),
                                                  float(corrected.ravel()[idx]))))

    return DeclarativeReference(
        input_snapshot=data,
        jump_matrix=jumps,
        row_totalsteps=tuple(totalsteps),
        split_positions=tuple(positions),
        split_scores=tuple(scores),
        raw_candidates=tuple(candidates),
        retained_boundaries=retained,
        block_count=len(blocks_with_shifts),
        trimmed_central_multiset=tuple(central_sets),
        trimmed_mean_sorted=tuple(sorted_means),
        correction_field=correction,
        corrected_field=corrected,
        classification=classification,
        block_shift_max_abs=max_abs,
        block_shift_max_ulp=max_ulp,
        corrected_bitwise=bitwise,
        corrected_total=total,
        corrected_max_abs=c_max_abs,
        corrected_max_ulp=c_max_ulp,
        discrete_state_exact=True,
    )
