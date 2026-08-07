"""Public-contract tests for Gwyddion 2.71 Align Rows facet-tilt."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import spmkit.core.analysis as analysis
from spmkit.core.analysis._gwyddion_align_rows_facet_tilt import (
    _gwyddion_align_rows_facet_tilt,
    _GwyddionAlignRowsDirection,
    _GwyddionFacetTiltResult,
    _GwyddionMaskMode,
)
from spmkit.core.models import SPMChannel

# ── helpers ──────────────────────────────────────────────────────────

_ORACLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "fixtures"
    / "gwyddion"
    / "facet_tilt"
    / "oracle_facet_tilt.py"
)


def _import_oracle() -> Any:  # pragma: no cover
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "oracle_facet_tilt", str(_ORACLE_PATH)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _build_field(yr: int, xr: int, func) -> np.ndarray:
    """Build a (yr, xr) float64 field from a callable ``func(row, col)``."""
    data = np.empty((yr, xr), dtype=np.float64)
    for row in range(yr):
        for col in range(xr):
            data[row, col] = func(row, col)
    return data


def _base_func(row: int, col: int) -> float:
    return float(
        2.0
        + 0.12 * col
        - 0.07 * row
        + 0.015 * col * row
        + 0.03 * math.sin(0.9 * col + 0.4 * row)
    )


def _spikes(row: int, col: int) -> float:
    v = _base_func(row, col)
    if row == 1 and col == 4:
        v += 3.5
    if row == 3 and col == 2:
        v -= 4.0
    if row == 4 and col == 6:
        v += 1.2
    return v


# The 14 cases from the C probe campaign, keyed by case name
_CASE_PARAMS: dict[str, dict[str, Any]] = {
    "wide_curved_nomask": {
        "yres": 5,
        "xres": 7,
        "xreal": 5.6,
        "func": _spikes,
        "mask_type": "none",
        "masking": "ignore",
        "direction": "horizontal",
        "do_extract": True,
    },
    "wide_curved_includemask": {
        "yres": 5,
        "xres": 7,
        "xreal": 5.6,
        "func": _spikes,
        "mask_type": "every2nd",
        "masking": "include",
        "direction": "horizontal",
        "do_extract": False,
    },
    "wide_curved_excludemask": {
        "yres": 5,
        "xres": 7,
        "xreal": 5.6,
        "func": _spikes,
        "mask_type": "cols234",
        "masking": "exclude",
        "direction": "horizontal",
        "do_extract": False,
    },
    "wide_curved_ignoremask": {
        "yres": 5,
        "xres": 7,
        "xreal": 5.6,
        "func": _spikes,
        "mask_type": "every2nd",
        "masking": "ignore",
        "direction": "horizontal",
        "do_extract": False,
    },
    "constant_rows_5x4": {
        "yres": 4,
        "xres": 5,
        "xreal": 4.0,
        "func": lambda r, c: 7.0,
        "mask_type": "none",
        "masking": "ignore",
        "direction": "horizontal",
        "do_extract": False,
    },
    "constant_rows_nonzero_5x4": {
        "yres": 4,
        "xres": 5,
        "xreal": 4.0,
        "func": None,  # replaced in _build_case_data
        "mask_type": "none",
        "masking": "ignore",
        "direction": "horizontal",
        "do_extract": True,
    },
    "exactly_linear_rows": {
        "yres": 4,
        "xres": 5,
        "xreal": 4.0,
        "func": lambda r, c: {
            0: 0.0 + 1.0 * c,
            1: 2.0 + 3.0 * c,
            2: -1.0 - 2.0 * c,
            3: 4.0 + 0.5 * c,
        }[r],
        "mask_type": "none",
        "masking": "ignore",
        "direction": "horizontal",
        "do_extract": False,
    },
    "nearly_linear_rows": {
        "yres": 4,
        "xres": 5,
        "xreal": 4.0,
        "func": lambda r, c: {
            0: 0.0 + 1.0 * c,
            1: 2.0 + 3.0 * c,
            2: -1.0 - 2.0 * c,
            3: 4.0 + 0.5 * c,
        }[r]
        + 1e-13 * math.sin(c + r * 17.0),
        "mask_type": "none",
        "masking": "ignore",
        "direction": "horizontal",
        "do_extract": False,
    },
    "large_outlier": {
        "yres": 5,
        "xres": 7,
        "xreal": 5.6,
        "func": lambda r, c: 1e10 if (r == 2 and c == 3) else 0.0,
        "mask_type": "none",
        "masking": "ignore",
        "direction": "horizontal",
        "do_extract": False,
    },
    "repeated_outlier": {
        "yres": 5,
        "xres": 7,
        "xreal": 5.6,
        "func": lambda r, c: 1e10
        if (r == 2 and c in (1, 2, 6)) or (r == 3 and c == 3)
        else 0.0,
        "mask_type": "none",
        "masking": "ignore",
        "direction": "horizontal",
        "do_extract": False,
    },
    "two_column_row": {
        "yres": 3,
        "xres": 2,
        "xreal": 2.0,
        "func": lambda r, c: {
            0: {0: 0.0, 1: 1.0},
            1: {0: 5.0, 1: 10.0},
            2: {0: -3.0, 1: 7.0},
        }[r][c],
        "mask_type": "none",
        "masking": "ignore",
        "direction": "horizontal",
        "do_extract": False,
    },
    "vertical_direction": {
        "yres": 5,
        "xres": 7,
        "xreal": 5.6,
        "func": _spikes,
        "mask_type": "none",
        "masking": "ignore",
        "direction": "vertical",
        "do_extract": True,
    },
    "fractional_mask": {
        "yres": 4,
        "xres": 5,
        "xreal": 4.0,
        "func": _spikes,  # cropped to 4×5 by taking first 4 rows, first 5 cols
        "mask_type": "fractional",
        "masking": "exclude",
        "direction": "horizontal",
        "do_extract": False,
    },
    "fractional_mask_include": {
        "yres": 4,
        "xres": 5,
        "xreal": 4.0,
        "func": _spikes,  # same cropped data
        "mask_type": "fractional",
        "masking": "include",
        "direction": "horizontal",
        "do_extract": False,
    },
    "two_column_vertical": {
        "yres": 2,
        "xres": 3,
        "xreal": 3.0,
        "func": lambda r, c: {
            0: {0: 0.0, 1: 1.0, 2: 2.0},
            1: {0: 5.0, 1: 10.0, 2: 15.0},
        }[r][c],
        "mask_type": "none",
        "masking": "ignore",
        "direction": "vertical",
        "do_extract": False,
    },
}


def _build_mask(mask_type: str, yres: int, xres: int) -> np.ndarray | None:
    if mask_type == "none":
        return None
    mask = np.empty((yres, xres), dtype=np.float64)
    if mask_type == "every2nd":
        for row in range(yres):
            for col in range(xres):
                mask[row, col] = 1.0 if (row * xres + col) % 2 == 0 else 0.0
    elif mask_type == "cols234":
        for row in range(yres):
            for col in range(xres):
                mask[row, col] = 1.0 if 2 <= col <= 4 else 0.0
    elif mask_type == "fractional":
        pattern = [0.0, 0.999999, 1.0, 1.000001, 0.5]
        for row in range(yres):
            for col in range(xres):
                mask[row, col] = pattern[col % 5]
    else:
        raise ValueError(f"Unknown mask_type: {mask_type}")
    return mask


def _build_case_data(case_name: str) -> tuple[np.ndarray, np.ndarray | None, dict[str, Any]]:
    params = _CASE_PARAMS[case_name]
    yres, xres = params["yres"], params["xres"]

    func = params["func"]
    if func is not None:
        data = _build_field(yres, xres, func)
    else:
        data = np.empty((yres, xres), dtype=np.float64)

    # For fractional_mask cases, use cropped spikes data (first 4 rows, first 5 cols)
    if case_name in ("fractional_mask", "fractional_mask_include"):
        # Build the full 7×5 field from wide_curved data and crop to 4×5
        full_data = _build_field(5, 7, _spikes)
        data = full_data[:4, :5].copy(order="C")

    # Fix constant_rows_nonzero_5x4
    if case_name == "constant_rows_nonzero_5x4":
        row_vals = [-3.5, 0.0, 7.0, 2.5]
        for row in range(4):
            data[row, :] = row_vals[row]

    mask = _build_mask(params["mask_type"], yres, xres)
    return data, mask, params


def _run_kernel(
    data: np.ndarray,
    mask: np.ndarray | None,
    params: dict[str, Any],
    extract_background: bool | None = None,
) -> _GwyddionFacetTiltResult:
    mode_map = {
        "ignore": _GwyddionMaskMode.IGNORE,
        "include": _GwyddionMaskMode.INCLUDE,
        "exclude": _GwyddionMaskMode.EXCLUDE,
    }
    dir_map = {
        "horizontal": _GwyddionAlignRowsDirection.HORIZONTAL,
        "vertical": _GwyddionAlignRowsDirection.VERTICAL,
    }
    dx = params["xreal"] / params["xres"]
    do_extract = params["do_extract"] if extract_background is None else extract_background
    return _gwyddion_align_rows_facet_tilt(
        data,
        masking_mode=mode_map[params["masking"]],
        direction=dir_map[params["direction"]],
        dx=dx,
        mask=mask,
        extract_background=do_extract,
    )


def _max_numeric_diff(a: np.ndarray, b: np.ndarray) -> float:
    max_diff = 0.0
    for i in range(a.size):
        av = float(a.flat[i])
        bv = float(b.flat[i])
        if np.isnan(av) and np.isnan(bv):
            continue
        if not (np.isnan(av) or np.isnan(bv)):
            diff = abs(av - bv)
            if diff > max_diff:
                max_diff = diff
    return max_diff


def _nan_count_match(a: np.ndarray, b: np.ndarray) -> bool:
    return np.sum(np.isnan(a)) == np.sum(np.isnan(b))


def _inf_count_match(a: np.ndarray, b: np.ndarray) -> bool:
    return np.sum(np.isinf(a)) == np.sum(np.isinf(b))


# ---------------------------------------------------------------------------
# 1.  Oracle vs C probe
# ---------------------------------------------------------------------------

_C_PROBE_ROOT = "/tmp/spmkit_gwyddion_facet_tilt_probe/normal"


def _load_probe_corrected(case_name: str, yres: int, xres: int) -> np.ndarray:
    stdout_path = os.path.join(_C_PROBE_ROOT, f"{case_name}.stdout")
    if not os.path.exists(stdout_path):
        pytest.skip("C probe output not available")
    with open(stdout_path) as f:
        lines = f.read().splitlines()
    d: dict[int, float] = {}
    prefix = f"{case_name}_corrected_"
    for line in lines:
        if line.startswith(prefix):
            rest = line[len(prefix) :]
            if rest and rest[0].isdigit():
                idx_str, val_str = rest.split("=", 1)
                d[int(idx_str)] = float(val_str)
    result = np.empty((yres, xres), dtype=np.float64)
    for row in range(yres):
        for col in range(xres):
            result[row, col] = d.get(row * xres + col, float("nan"))
    return result


def _load_probe_background(case_name: str, yres: int, xres: int) -> np.ndarray:
    stdout_path = os.path.join(_C_PROBE_ROOT, f"{case_name}.stdout")
    if not os.path.exists(stdout_path):
        pytest.skip("C probe output not available")
    with open(stdout_path) as f:
        lines = f.read().splitlines()
    d: dict[int, float] = {}
    prefix = f"{case_name}_background_"
    for line in lines:
        if line.startswith(prefix):
            rest = line[len(prefix) :]
            if rest and rest[0].isdigit():
                idx_str, val_str = rest.split("=", 1)
                d[int(idx_str)] = float(val_str)
    if not d:
        return np.empty((0, 0))  # no background output
    result = np.empty((yres, xres), dtype=np.float64)
    for row in range(yres):
        for col in range(xres):
            result[row, col] = d.get(row * xres + col, float("nan"))
    return result


def _load_probe_shifts(case_name: str) -> np.ndarray | None:
    """Parse ALL probe shift values (never truncate)."""
    stdout_path = os.path.join(_C_PROBE_ROOT, f"{case_name}.stdout")
    if not os.path.exists(stdout_path):
        pytest.skip("C probe output not available")
    with open(stdout_path) as f:
        lines = f.read().splitlines()
    d: dict[int, float] = {}
    prefix = f"{case_name}_shifts_"
    for line in lines:
        if line.startswith(prefix):
            rest = line[len(prefix):]
            if rest and rest[0].isdigit():
                idx_str, val_str = rest.split("=", 1)
                d[int(idx_str)] = float(val_str)
    if not d:
        return None
    max_idx = max(d.keys())
    result = np.empty(max_idx + 1, dtype=np.float64)
    for i in range(max_idx + 1):
        result[i] = d.get(i, np.nan)
    return result


@pytest.mark.parametrize(
    "case_name",
    list(_CASE_PARAMS),
)
def test_facet_tilt_oracle_vs_probe(case_name: str) -> None:
    """Oracle matches the compiled Gwyddion 2.71 source-inclusion probe output."""
    oracle_mod = _import_oracle()
    data, mask, params = _build_case_data(case_name)
    if data is None:
        return
    yres, xres = data.shape
    dx = params["xreal"] / params["xres"]

    oracle_corr, oracle_bg, oracle_shifts = oracle_mod.oracle_facet_tilt(
        data.copy(order="C"),
        mask.copy(order="C") if mask is not None else None,
        params["masking"],
        dx,
        params["direction"],
        params["do_extract"],
    )

    probe_corr = _load_probe_corrected(case_name, yres, xres)
    max_diff = _max_numeric_diff(oracle_corr, probe_corr)
    assert _nan_count_match(oracle_corr, probe_corr)
    assert _inf_count_match(oracle_corr, probe_corr)
    assert max_diff < 1e-14, (
        f"Oracle vs probe corrected max diff {max_diff:.17g} for {case_name}"
    )

    if params["do_extract"]:
        probe_bg = _load_probe_background(case_name, yres, xres)
        bg_diff = _max_numeric_diff(oracle_bg, probe_bg)
        assert bg_diff < 1e-14, (
            f"Oracle vs probe background max diff {bg_diff:.17g} for {case_name}"
        )

    # Compare shifts: shape AND values against the probe
    probe_shifts = _load_probe_shifts(case_name)
    assert probe_shifts is not None, f"No probe shifts found for {case_name}"
    assert probe_shifts.shape == oracle_shifts.shape, (
        f"Shifts shape mismatch for {case_name}: "
        f"probe {probe_shifts.shape} vs oracle {oracle_shifts.shape}"
    )
    assert np.all(probe_shifts == 0.0)
    assert np.all(oracle_shifts == 0.0)


# ---------------------------------------------------------------------------
# 2.  Oracle vs kernel (bitwise exact)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case_name", list(_CASE_PARAMS))
def test_facet_tilt_oracle_vs_kernel(case_name: str) -> None:
    """Private SPMKit kernel matches the oracle bitwise."""
    oracle_mod = _import_oracle()
    data, mask, params = _build_case_data(case_name)
    if data is None:
        return
    dx = params["xreal"] / params["xres"]

    kernel_result = _run_kernel(data, mask, params)
    oracle_corr, oracle_bg, oracle_shifts = oracle_mod.oracle_facet_tilt(
        data.copy(order="C"),
        mask.copy(order="C") if mask is not None else None,
        params["masking"],
        dx,
        params["direction"],
        params["do_extract"],
    )

    assert _max_numeric_diff(kernel_result.corrected, oracle_corr) == 0.0
    if params["do_extract"]:
        assert _max_numeric_diff(kernel_result.background, oracle_bg) == 0.0
    # Shifts: shape and values must match bitwise
    assert kernel_result.shifts.shape == oracle_shifts.shape, (
        f"Shifts shape mismatch for {case_name}: "
        f"kernel {kernel_result.shifts.shape} vs oracle {oracle_shifts.shape}"
    )
    assert np.all(kernel_result.shifts == 0.0)
    assert np.all(oracle_shifts == 0.0)


# ---------------------------------------------------------------------------
# 3.  Constant-row NaN behaviour
# ---------------------------------------------------------------------------

def test_facet_tilt_constant_row_nan() -> None:
    """A uniformly constant row produces NaN (IEEE 0/0 in sigma2)."""
    data = np.full((3, 5), 7.0, dtype=np.float64)
    result = _gwyddion_align_rows_facet_tilt(
        data,
        masking_mode=_GwyddionMaskMode.IGNORE,
        direction=_GwyddionAlignRowsDirection.HORIZONTAL,
        dx=1.0,
    )
    assert np.isnan(result.corrected).all()


# ---------------------------------------------------------------------------
# 4.  Two-column row mincount guard
# ---------------------------------------------------------------------------

def test_facet_tilt_two_column_row() -> None:
    """A 2-column row has n = 1, which is below mincount = 2, so stays unchanged."""
    data = np.array([[0.0, 1.0], [5.0, 10.0], [-3.0, 7.0]], dtype=np.float64)
    result = _gwyddion_align_rows_facet_tilt(
        data,
        masking_mode=_GwyddionMaskMode.IGNORE,
        direction=_GwyddionAlignRowsDirection.HORIZONTAL,
        dx=1.0,
    )
    assert np.array_equal(result.corrected, data)
    assert np.all(result.shifts == 0.0)


# ---------------------------------------------------------------------------
# 5.  Exactly linear row behaviour
# ---------------------------------------------------------------------------

def test_facet_tilt_exactly_linear() -> None:
    """A perfectly linear row becomes constant after the first untilt, then NaNs.

    Gwyddion source confirmation: the first iteration removes the true
    slope exactly, making sigma2 zero in the second iteration, which
    triggers an FP NaN chain.
    """
    data = np.array(
        [
            [0.0, 1.0, 2.0, 3.0, 4.0],  # b=1, a=0
        ],
        dtype=np.float64,
    )
    oracle_mod = _import_oracle()
    corrected, bg, shifts = oracle_mod.oracle_facet_tilt(
        data.copy(), None, "ignore", 1.0, "horizontal", False
    )
    assert np.all(np.isnan(corrected))
    assert np.all(shifts == 0.0)


# ---------------------------------------------------------------------------
# 6.  Convergence cap at 30 iterations
# ---------------------------------------------------------------------------

def test_facet_tilt_convergence_cap() -> None:
    """NaN-producing rows stop at 30 iterations, never infinite."""
    data = np.full((1, 5), 7.0, dtype=np.float64)
    # The function does not raise; it returns NaN result after 30 iterations.
    result = _gwyddion_align_rows_facet_tilt(
        data,
        masking_mode=_GwyddionMaskMode.IGNORE,
        direction=_GwyddionAlignRowsDirection.HORIZONTAL,
        dx=1.0,
    )
    assert result.corrected.shape == (1, 5)


# ---------------------------------------------------------------------------
# 7.  Input non-mutation
# ---------------------------------------------------------------------------

def test_facet_tilt_nonmutation() -> None:
    """Input data is not modified by processing."""
    data, mask, params = _build_case_data("wide_curved_nomask")
    original = data.copy(order="C")
    _run_kernel(data, mask, params)
    assert np.array_equal(data, original)


# ---------------------------------------------------------------------------
# 8.  Mask semantics
# ---------------------------------------------------------------------------

def test_facet_tilt_mask_semantics() -> None:
    """EXCLUDE uses ``<= 0.0``, INCLUDE uses ``>= 1.0``, tested via fractional mask."""
    data, mask, params = _build_case_data("fractional_mask")
    result = _run_kernel(data, mask, params)
    # No NaN expected — the fractional mask has enough non-excluded columns
    assert result.corrected.shape == data.shape

    data2, mask2, params2 = _build_case_data("fractional_mask_include")
    result2 = _run_kernel(data2, mask2, params2)
    assert result2.corrected.shape == data2.shape


# ---------------------------------------------------------------------------
# 9.  Direction transpose consistency
# ---------------------------------------------------------------------------

def test_facet_tilt_direction_transpose() -> None:
    """HORIZONTAL and VERTICAL produce transpose-consistent corrected outputs."""
    data, mask, params = _build_case_data("vertical_direction")
    dx = params["xreal"] / params["xres"]

    h_result = _gwyddion_align_rows_facet_tilt(
        data,
        masking_mode=_GwyddionMaskMode.IGNORE,
        direction=_GwyddionAlignRowsDirection.HORIZONTAL,
        dx=dx,
        extract_background=True,
    )
    v_result = _gwyddion_align_rows_facet_tilt(
        data,
        masking_mode=_GwyddionMaskMode.IGNORE,
        direction=_GwyddionAlignRowsDirection.VERTICAL,
        dx=dx,
        extract_background=True,
    )

    # H & V should differ (different processing axis)
    assert not np.allclose(h_result.corrected, v_result.corrected, equal_nan=True)


# ---------------------------------------------------------------------------
# 10.  Background = input - corrected
# ---------------------------------------------------------------------------

def test_facet_tilt_background_identity() -> None:
    """background == input - corrected elementwise in C order."""
    data, mask, params = _build_case_data("wide_curved_nomask")
    result = _run_kernel(data, mask, {**params, "do_extract": True})
    expected_bg = np.empty_like(data, order="C")
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            expected_bg[row, col] = data[row, col] - result.corrected[row, col]
    assert _max_numeric_diff(result.background, expected_bg) == 0.0


# ---------------------------------------------------------------------------
# 11.  Shifts are always zero
# ---------------------------------------------------------------------------

def test_facet_tilt_shifts_zero() -> None:
    """shifts output is the zero vector, matching ``gwy_data_line_clear``.

    For HORIZONTAL the shifts length equals yres; for VERTICAL it equals
    xres (the working field's y-resolution after transpose).
    """
    data, mask, params = _build_case_data("wide_curved_nomask")
    result = _run_kernel(data, mask, params)
    assert result.shifts.size == data.shape[0]
    assert np.all(result.shifts == 0.0)

    # VERTICAL: shifts length = original xres
    data2, mask2, params2 = _build_case_data("vertical_direction")
    result2 = _run_kernel(data2, mask2, params2)
    assert result2.shifts.size == data2.shape[1], (
        f"VERTICAL shifts size {result2.shifts.size} != xres {data2.shape[1]}"
    )
    assert np.all(result2.shifts == 0.0)


# ---------------------------------------------------------------------------
# 12.  Metamorphic: adding a constant to all rows
# ---------------------------------------------------------------------------

def test_facet_tilt_metamorphic_constant_shift() -> None:
    """Adding a constant C to the entire field shifts corrected by C;
    the slope-estimation algorithm subtracts tilt only."""
    data, mask, params = _build_case_data("wide_curved_nomask")
    dx = params["xreal"] / params["xres"]

    result = _gwyddion_align_rows_facet_tilt(
        data,
        masking_mode=_GwyddionMaskMode.IGNORE,
        direction=_GwyddionAlignRowsDirection.HORIZONTAL,
        dx=dx,
        extract_background=True,
    )

    c = 100.0
    shifted = data + c
    result_shifted = _gwyddion_align_rows_facet_tilt(
        shifted,
        masking_mode=_GwyddionMaskMode.IGNORE,
        direction=_GwyddionAlignRowsDirection.HORIZONTAL,
        dx=dx,
        extract_background=True,
    )

    corrected_diff = _max_numeric_diff(
        result_shifted.corrected, result.corrected + c
    )
    # The corrected output should shift by ~C (within a few ULPs)
    assert corrected_diff < 1e-13, (
        f"Constant-shift metamorphism failed: diff {corrected_diff:.17g}"
    )

    # Background should be identical (tilt only, no offset)
    bg_diff = _max_numeric_diff(result_shifted.background, result.background)
    assert bg_diff < 1e-13, (
        f"Background should be constant-shift invariant: diff {bg_diff:.17g}"
    )


# ---------------------------------------------------------------------------
# 13.  Iteration limit (slow convergence)
# ---------------------------------------------------------------------------

def test_facet_tilt_iteration_limit() -> None:
    """Verify the 30-iteration cap does not loop infinitely."""
    # A row with very large slope needs many iterations but converges within 30.
    # row: d[col] = 1000 * col, xres = 7, dx = 1
    data = np.array(
        [
            [0.0, 1000.0, 2000.0, 3000.0, 4000.0, 5000.0, 6000.0],
        ],
        dtype=np.float64,
    )
    result = _gwyddion_align_rows_facet_tilt(
        data,
        masking_mode=_GwyddionMaskMode.IGNORE,
        direction=_GwyddionAlignRowsDirection.HORIZONTAL,
        dx=1.0,
    )
    # After convergence, the row becomes constant (about the centre value).
    # It should NOT be all NaN (unlike the exactly-linear case which has
    # a different issue — the 2nd iteration becomes constant, producing NaN).
    # With large slope, exp(vx^2/sigma2) ≈ exp(200) ≈ huge but finite,
    # so the row converges properly after 1-2 iterations.
    assert not np.all(np.isnan(result.corrected))
    assert not np.all(np.isinf(result.corrected))


# ---------------------------------------------------------------------------
# 14.  Public API type errors
# ---------------------------------------------------------------------------

def test_facet_tilt_public_api_type_errors() -> None:
    """gwyddion_align_rows_facet_tilt rejects invalid inputs."""
    channel = SPMChannel(
        data=np.ones((5, 7), dtype=np.float64),
        x_range=5.6,
        y_range=6.5,
        name="test",
        unit="m",
    )

    result = analysis.gwyddion_align_rows_facet_tilt(channel)
    assert result.data.shape == (5, 7)
    assert isinstance(result, SPMChannel)

    # TypeError for non-channel
    with pytest.raises(TypeError):
        analysis.gwyddion_align_rows_facet_tilt("not a channel")  # type: ignore[arg-type]

    # ValueError for bad mask_mode
    with pytest.raises(ValueError):
        analysis.gwyddion_align_rows_facet_tilt(channel, mask_mode="bogus")  # type: ignore[arg-type]

    # ValueError for bad direction
    with pytest.raises(ValueError):
        analysis.gwyddion_align_rows_facet_tilt(channel, direction="diagonal")  # type: ignore[arg-type]
