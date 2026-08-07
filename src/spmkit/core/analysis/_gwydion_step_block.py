"""Production kernel: Gwydion 2.71 Step Block Correction (finite scope).

Implements the valid frozen-source numerical contract of
modules/process/blockstep.c (source-included kernel) for finite
two-dimensional float64 fields with xres >= 2, left-to-right and
right-to-left scan directions, and the source-supported public threshold
range.  Parity was established against the 28 valid frozen compiled cases
by the compiled-probe campaign and frozen fixtures.

Independence: this module does not import tests, fixtures, oracles, the
fixture generator, or Gwydion; it does not read JSON/NPZ; it contains no
case identifiers and no frozen expected arrays.  It is implemented
independently from the audited mathematical contract; the deterministic
selection required by the trimmed-mean helper (libgwydion/gwymath-rank.c)
is reconstructed here with its own decomposition and the exact strict-`>`
comparison semantics.

Deliberate safe divergence (documented): xres < 2 is REJECTED.  The frozen
source performs an out-of-bounds read for xres=1 (the minimum length
truncates to zero, the first candidate moves the second segment one row
before the allocated field); its normal output is undefined.  SPMKit never
exposes undefined behaviour.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

FloatArray = np.ndarray

_THRESHOLD_MIN = 0.1
_THRESHOLD_MAX = 10.0
_DEFAULT_THRESHOLD = 2.0
_LTR = 1
_RTL = -1


def _validated_data(value: object, *, operation: str) -> np.ndarray:
    source = np.asarray(value, dtype=np.float64)
    if source.ndim != 2:
        raise ValueError(f"{operation} requires a two-dimensional channel")
    if 0 in source.shape:
        raise ValueError(f"{operation} requires non-empty data")
    if not np.issubdtype(source.dtype, np.number) or np.iscomplexobj(source):
        raise TypeError(f"{operation} requires real numeric data")
    if not np.all(np.isfinite(source)):
        raise ValueError(f"{operation} requires finite data")
    if int(source.shape[1]) < 2:
        raise ValueError(
            f"{operation} rejects xres < 2: the frozen Gwydion source performs "
            f"an out-of-bounds read for xres=1 (documented SOURCE_DEFECT); "
            f"SPMKit never exposes undefined behaviour")
    return np.array(source, dtype=np.float64, order="C", copy=True)


# ---------------------------------------------------------------------------
# Deterministic selection for the trimmed-mean retained block
# (reconstructed from the audited gwymath-rank.c contract; strict >)
# ---------------------------------------------------------------------------

def _swap_if_greater(items: list[float], base: int, ia: int, ib: int) -> None:
    """Ordering primitive: swap iff left > right (strict)."""
    if items[base + ia] > items[base + ib]:
        items[base + ia], items[base + ib] = items[base + ib], items[base + ia]


def _sort_three(items: list[float], base: int) -> None:
    _swap_if_greater(items, base, 0, 1)
    if items[base + 2] < items[base + 1]:
        items[base + 1], items[base + 2] = items[base + 2], items[base + 1]
        _swap_if_greater(items, base, 0, 1)


def _rank_simple(items: list[float], base: int, n: int, k: int) -> float:
    """Small/near-edge rank selection with the source branch structure."""
    if n == 1:
        return items[base]
    if n == 2:
        _swap_if_greater(items, base, 0, 1)
        return items[base + k]
    if n == 3 and k == 1:
        _sort_three(items, base)
        return items[base + 1]
    if k == 0:
        low = items[base]
        for i in range(1, n):
            c = items[base + i]
            if c < low:
                items[base + i] = low
                items[base] = low = c
        return low
    if k == n - 1:
        high = items[base + n - 1]
        for i in range(0, n - 1):
            c = items[base + i]
            if c > high:
                items[base + i] = high
                items[base + n - 1] = high = c
        return high
    if k == 1:
        _swap_if_greater(items, base, 0, 1)
        first = items[base]
        second = items[base + 1]
        for i in range(2, n):
            c = items[base + i]
            if c < second:
                if c < first:
                    items[base + i] = second
                    items[base + 1] = second = first
                    items[base] = first = c
                else:
                    items[base + i] = second
                    items[base + 1] = second = c
        return second
    if k == n - 2:
        _swap_if_greater(items, base, n - 2, n - 1)
        high = items[base + n - 1]
        second = items[base + n - 2]
        for i in range(0, n - 2):
            c = items[base + i]
            if c > second:
                if c > high:
                    items[base + i] = second
                    items[base + n - 2] = second = high
                    items[base + n - 1] = high = c
                else:
                    items[base + i] = second
                    items[base + n - 2] = second = c
        return second
    if k == 2:
        _sort_three(items, base)
        first = items[base]
        second = items[base + 1]
        third = items[base + 2]
        for i in range(3, n):
            d = items[base + i]
            if d < third:
                if d < second:
                    if d < first:
                        items[base + i] = third
                        items[base + 2] = third = second
                        items[base + 1] = second = first
                        items[base] = first = d
                    else:
                        items[base + i] = third
                        items[base + 2] = third = second
                        items[base + 1] = second = d
                else:
                    items[base + i] = third
                    items[base + 2] = third = d
        return third
    if k == n - 3:
        _sort_three(items, base + n - 3)
        high = items[base + n - 1]
        second = items[base + n - 2]
        third = items[base + n - 3]
        for i in range(0, n - 3):
            d = items[base + i]
            if d > third:
                if d > second:
                    if d > high:
                        items[base + i] = third
                        items[base + n - 3] = third = second
                        items[base + n - 2] = second = high
                        items[base + n - 1] = high = d
                    else:
                        items[base + i] = third
                        items[base + n - 3] = third = second
                        items[base + n - 2] = second = d
                else:
                    items[base + i] = third
                    items[base + n - 3] = third = d
        return third
    raise ArithmeticError("rank selection reached an unreachable branch")


def _partition_select(items: list[float], base: int, n: int, k: int) -> float:
    """Median-of-three quickselect partition (strict > comparisons).

    Rearranges items[base:base+n] so that the rank-k value is at position
    k and the array is partitioned around it; returns the rank-k value.
    """
    lo = 0
    hi = n - 1
    while True:
        if hi <= lo + 2 or k <= lo + 2 or k + 2 >= hi:
            return _rank_simple(items, base + lo, hi + 1 - lo, k - lo)
        mid = (lo + hi) // 2
        _swap_if_greater(items, base, mid, hi)
        _swap_if_greater(items, base, lo, hi)
        _swap_if_greater(items, base, mid, lo)
        items[base + mid], items[base + lo + 1] = \
            items[base + lo + 1], items[base + mid]
        ll = lo + 1
        hh = hi
        pivot = items[base + lo]
        while True:
            ll += 1
            while pivot > items[base + ll]:
                ll += 1
            hh -= 1
            while items[base + hh] > pivot:
                hh -= 1
            if hh < ll:
                break
            items[base + ll], items[base + hh] = items[base + hh], items[base + ll]
        items[base + lo] = items[base + hh]
        items[base + hh] = pivot
        if hh <= k:
            lo = hh
        if hh >= k:
            hi = hh - 1


def _select_two_ranks(items: list[float], rank_low: int, rank_high: int) -> None:
    """Two simultaneous rank selections with the source side choice."""
    n = len(items)
    mid = n // 2
    d_low = mid - rank_low if rank_low <= mid else rank_low - mid
    d_high = mid - rank_high if rank_high <= mid else rank_high - mid
    if d_low <= d_high:
        _partition_select(items, 0, n, rank_low)
        _partition_select(items, rank_low + 1, n - rank_low - 1,
                          rank_high - rank_low - 1)
    else:
        _partition_select(items, 0, n, rank_high)
        _partition_select(items, 0, rank_high, rank_low)


def _trimmed_mean_in_place(items: list[float], trim_low: int,
                           trim_high: int) -> float:
    """25%-style trimmed mean with the source selection and sum order."""
    n = len(items)
    if not trim_low:
        if not trim_high:
            kept = n
        else:
            kept = n - trim_high
            _partition_select(items, 0, n, kept)
    elif not trim_high:
        kept = n - trim_low
        _partition_select(items, 0, n, trim_low - 1)
    else:
        kept = n - (trim_low + trim_high)
        _select_two_ranks(items, trim_low - 1, n - trim_high)
    total = 0.0
    for i in range(kept):
        total += items[trim_low + i]
    return total / kept


# ---------------------------------------------------------------------------
# Step Block pipeline
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _GwydionStepBlockResult:
    """Private immutable diagnostics for parity inspection."""

    input_snapshot: FloatArray
    xres: int
    yres: int
    dy: float
    threshold_param: float
    effective_threshold: float
    rms_stat: float
    discontinuity_mask: FloatArray
    row_totalsteps: tuple[int, ...]
    row_positions: tuple[int, ...]
    row_scores: tuple[float, ...]
    candidate_boundaries: tuple[tuple[int, int, float], ...]
    retained_blocks: tuple[tuple[int, int, float], ...]  # (row, fromleft, shift)
    sentinel: tuple[int, int, float]
    shift_samples_raw: tuple[FloatArray, ...]
    shift_samples_selected: tuple[FloatArray, ...]
    trim_low: int
    trim_high: int
    retained_count: int
    retained_sums: tuple[float, ...]
    block_count: int
    corrected_field: FloatArray
    correction_field: FloatArray
    preview_mask_discontinuity: FloatArray
    preview_mask_blocks: FloatArray
    input_mutation_evidence: bool


def _gwydion_step_block_result(
    field: object,
    *,
    threshold: float = _DEFAULT_THRESHOLD,
    direction: str = "left_to_right",
    dy: float = 1.0,
) -> _GwydionStepBlockResult:
    """Run the production Step Block kernel (private; the public wrapper in
    core.analysis.scanline validates the parameter domain and supplies the
    pixel height dy = y_range/yres as the source derives it)."""
    data = _validated_data(field, operation="Step Block Correction")
    yres, xres = data.shape
    if not math.isfinite(threshold):
        raise ValueError("threshold must be finite")
    if direction == "left_to_right":
        scandir = _LTR
    elif direction == "right_to_left":
        scandir = _RTL
    else:
        raise ValueError("direction must be left_to_right or right_to_left")
    if not math.isfinite(dy) or dy <= 0.0:
        raise ValueError("dy must be a positive finite value")

    # threshold chain (blockstep.c execute): per-column TAN_BETA0 statistic
    # over vertical neighbours, mean over columns, then *dy and *threshold.
    # The per-column statistic is sqrt(sum(diff^2)/(yres-1)) * yres/(yres*dy)
    # where yres/(yres*dy) is the column line's res/real factor; the
    # *dy and the res/real factor cancel exactly only for dy == 1.0.
    column_slope = np.empty(xres, dtype=np.float64)
    for j in range(xres):
        if yres < 2:
            column_slope[j] = 0.0
            continue
        acc = 0.0
        for i in range(1, yres):
            z = data[i, j] - data[i - 1, j]
            acc += z * z
        column_slope[j] = math.sqrt(acc / (yres - 1)) * (yres / (yres * dy))
    column_mean = 0.0
    for j in range(xres):
        column_mean += column_slope[j]
    column_mean /= xres
    rms_stat = column_mean * dy
    effective = threshold * rms_stat

    # mark discontinuities: strict absolute-difference jump predicate
    jumps = np.zeros((yres, xres), dtype=np.int64)
    row_steps = [0] * yres
    for i in range(1, yres):
        hit = 0
        for j in range(xres):
            if abs(data[i, j] - data[i - 1, j]) > effective:
                jumps[i, j] = 1
                hit += 1
        row_steps[i] = hit

    # per-row split state (first strict maximum position and score)
    scores = [0.0] * yres
    positions = [0] * yres
    for i in range(1, yres):
        total = row_steps[i - 1] if scandir == _LTR else row_steps[i]
        best = -1
        best_pos = 0
        seen_above = 0
        seen_below = 0
        j = 0
        while True:
            if scandir == _LTR:
                left = seen_below
                right = total - seen_above
            else:
                left = seen_above
                right = total - seen_below
            if left + right > best:
                best = left + right
                best_pos = j
            if j == xres:
                break
            seen_above += int(jumps[i - 1, j])
            seen_below += int(jumps[i, j])
            j += 1
        positions[i] = best_pos
        scores[i] = float(best)

    # preview discontinuity mask (source: max of adjacent jump rows)
    disc_mask = np.zeros((yres, xres), dtype=np.float64)
    flat_jumps = jumps.ravel()
    flat_disc = disc_mask.ravel()
    n = xres * yres
    for idx in range(n - xres):
        flat_disc[idx] = float(max(flat_jumps[idx], flat_jumps[idx + xres]))
    for idx in range(n - xres, n):
        flat_disc[idx] = float(flat_jumps[idx])

    # candidate boundaries with full-width movement/skip semantics
    min_length = int(3 * xres / 4)
    candidates: list[list[float]] = []
    for i in range(1, yres):
        if scores[i] >= min_length:
            if scandir == _LTR and positions[i] == xres:
                if i == yres - 1:
                    continue
                candidates.append([float(i + 1), 0.0, scores[i]])
            elif scandir == _RTL and positions[i] == 0:
                if i == yres - 1:
                    continue
                candidates.append([float(i + 1), float(xres), scores[i]])
            else:
                candidates.append([float(i), float(positions[i]), scores[i]])

    # adjacent-boundary elimination (single backward pass; larger score
    # retained, ties retain the earlier boundary)
    k = len(candidates) - 1
    while k > 0:
        earlier = candidates[k - 1]
        later = candidates[k]
        if later[0] - earlier[0] <= 1.0:
            if later[2] > earlier[2]:
                del candidates[k - 1]
            else:
                del candidates[k]
        k -= 1

    # boundary shift samples over the two source segments and the
    # deterministic trimmed mean
    flat_data = data.ravel()
    blocks: list[tuple[int, int, float]] = []
    raw_samples: list[FloatArray] = []
    selected_samples: list[FloatArray] = []
    retained_sums: list[float] = []
    trim_low = xres // 4
    trim_high = xres // 4
    retained_count = xres - (trim_low + trim_high)
    for cand in candidates:
        # cand[0] is the pre-decrement boundary row; the first shift
        # segment reads the row-pair (cand[0]-1, cand[0]) and the second
        # segment the pair above, exactly as the source's row pointer
        # arithmetic (row = d + (bs->i - 1)*xres, then row -= xres)
        row_before: int = int(cand[0])
        split: int = int(cand[1])
        samples = [0.0] * xres
        row_base = (row_before - 1) * xres
        if scandir == _LTR:
            _fill_shifts(flat_data, xres, row_base, samples, 0, split)
            row_base -= xres
            _fill_shifts(flat_data, xres, row_base, samples, split,
                         xres - split)
        else:
            _fill_shifts(flat_data, xres, row_base, samples, split,
                         xres - split)
            row_base -= xres
            _fill_shifts(flat_data, xres, row_base, samples, 0, split)
        raw = list(samples)
        selected = list(samples)
        mean_shift = _trimmed_mean_in_place(selected, trim_low, trim_high)
        kept = selected[trim_low:trim_low + retained_count]
        kept_sum = 0.0
        for v in kept:
            kept_sum += v
        raw_samples.append(np.array(raw, dtype=np.float64, order="C"))
        selected_samples.append(np.array(selected, dtype=np.float64, order="C"))
        retained_sums.append(kept_sum)
        # source bs->i-- after the shift estimate: the correction-start row
        # is one below the pre-decrement candidate row
        blocks.append((row_before - 1, split, mean_shift))

    sentinel = (yres + 1, xres, 0.0)

    # cumulative piecewise-constant correction with first-block anchoring
    corrected = np.array(data, dtype=np.float64, order="C", copy=True)
    walk = list(blocks) + [sentinel]
    shift = 0.0
    walk_index = 0
    for r in range(blocks[0][0], yres) if blocks else ():
        row = corrected[r]
        if r == walk[walk_index][0]:
            blk_row, blk_split, blk_shift = walk[walk_index]
            if scandir == _LTR:
                for j in range(blk_split):
                    row[j] += shift
                shift -= blk_shift
                for j in range(blk_split, xres):
                    row[j] += shift
            else:
                for j in range(blk_split, xres):
                    row[j] += shift
                shift -= blk_shift
                for j in range(blk_split):
                    row[j] += shift
            walk_index += 1
        else:
            row += shift

    correction = corrected - data

    # preview blocks mask: both segments write the SAME boundary row pair
    blocks_mask = np.zeros((yres, xres), dtype=np.float64)
    for cand, block in zip(candidates, blocks, strict=True):
        row_before = block[0] + 1
        split = int(cand[1])
        mrow_base = (row_before - 1) * xres
        if scandir == _LTR:
            _fill_mask(blocks_mask, mrow_base, 0, split, xres)
            _fill_mask(blocks_mask, mrow_base, split, xres - split, xres)
        else:
            _fill_mask(blocks_mask, mrow_base, split, xres - split, xres)
            _fill_mask(blocks_mask, mrow_base, 0, split, xres)

    return _GwydionStepBlockResult(
        input_snapshot=data,
        xres=xres,
        yres=yres,
        dy=dy,
        threshold_param=threshold,
        effective_threshold=effective,
        rms_stat=rms_stat,
        discontinuity_mask=disc_mask,
        row_totalsteps=tuple(row_steps),
        row_positions=tuple(positions),
        row_scores=tuple(scores),
        candidate_boundaries=tuple((int(c[0]), int(c[1]), float(c[2]))
                                   for c in candidates),
        retained_blocks=tuple(blocks),
        sentinel=sentinel,
        shift_samples_raw=tuple(raw_samples),
        shift_samples_selected=tuple(selected_samples),
        trim_low=trim_low,
        trim_high=trim_high,
        retained_count=retained_count,
        retained_sums=tuple(retained_sums),
        block_count=len(blocks),
        corrected_field=corrected,
        correction_field=correction,
        preview_mask_discontinuity=disc_mask,
        preview_mask_blocks=blocks_mask,
        input_mutation_evidence=False,
    )


def _fill_shifts(flat: np.ndarray, xres: int, row_base: int,
                 samples: list[float], start: int, length: int) -> None:
    """One boundary shift segment: samples[start+j] = row+1 - row."""
    for j in range(length):
        idx = start + j
        samples[idx] = flat[row_base + xres + idx] - flat[row_base + idx]


def _fill_mask(blocks_mask: np.ndarray, mrow_base: int, start: int,
               length: int, xres: int) -> None:
    flat = blocks_mask.ravel()
    for j in range(length):
        flat[mrow_base + xres + start + j] = 1.0
        flat[mrow_base + start + j] = 1.0
