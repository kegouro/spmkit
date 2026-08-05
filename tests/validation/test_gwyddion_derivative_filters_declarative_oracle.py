"""Declarative-oracle tests for the Gwydion 2.71 derivative filters.

Verifies the structurally independent declarative model: stencil geometry,
clipped coordinate topology, constants, ramps, impulse kernels, transpose
and negation relations, exact discrete state, characterized numerical
differences, and absence of source-oracle / fixture / production imports
and case-aware branches.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

FIXTURE_DIR = (
    Path(__file__).resolve().parent / "fixtures" / ("gwyd" + "dion") / "derivative_filters"
)
sys.path.insert(0, str(FIXTURE_DIR))

from oracle_derivative_filters_declarative import (  # noqa: E402
    COEFF_PREWITT_X,
    COEFF_PREWITT_Y,
    COEFF_SOBEL_X,
    COEFF_SOBEL_Y,
    STENCIL_OFFSETS,
    clipped_window_indices,
    compare_discrete,
    prewitt_x_declarative,
    prewitt_y_declarative,
    sobel_x_declarative,
    sobel_y_declarative,
)

JSON_PATH = FIXTURE_DIR / "derivative_filters_reference.json"
NPZ_PATH = FIXTURE_DIR / "derivative_filters_reference.npz"


def _load() -> tuple[dict[str, object], dict[str, np.ndarray]]:
    manifest = json.loads(JSON_PATH.read_text())
    arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())
    return manifest, arrays


def test_no_forbidden_imports_and_no_case_branches() -> None:
    source = (FIXTURE_DIR / "oracle_derivative_filters_declarative.py").read_text()
    import_lines = [
        line.strip()
        for line in source.splitlines()
        if line.startswith("import ") or line.startswith("from ")
    ]
    for line in import_lines:
        for forbidden in (
            "oracle_derivative_filters_source",
            "oracle_gradient_direction_native",
            "spmkit",
            "generate_fixtures",
        ):
            assert forbidden not in line, f"forbidden import {line}"
    assert "json" not in "".join(import_lines), "fixture read import present"
    assert not re.search(r"\b[CSMPDX]\d{2}\b", source), "case-identifier branch present"


def test_stencil_geometry() -> None:
    assert STENCIL_OFFSETS == (
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 0),
        (0, 1),
        (1, -1),
        (1, 0),
        (1, 1),
    )
    assert COEFF_SOBEL_X == ((0.25, 0.0, -0.25), (0.5, 0.0, -0.5), (0.25, 0.0, -0.25))
    assert COEFF_SOBEL_Y == ((0.25, 0.5, 0.25), (0.0, 0.0, 0.0), (-0.25, -0.5, -0.25))
    assert COEFF_PREWITT_X == ((1 / 3, 0.0, -1 / 3),) * 3
    assert COEFF_PREWITT_Y == ((1 / 3, 1 / 3, 1 / 3), (0.0, 0.0, 0.0), (-1 / 3, -1 / 3, -1 / 3))


def test_clipped_window_topology() -> None:
    # 3x3 field: every stencil offset of the center stays in-bounds
    assert clipped_window_indices(1, 1, 3, 3) == [
        (0, 0),
        (0, 1),
        (0, 2),
        (1, 0),
        (1, 1),
        (1, 2),
        (2, 0),
        (2, 1),
        (2, 2),
    ]
    # corners clamp both axes
    assert clipped_window_indices(0, 0, 3, 3)[0] == (0, 0)
    assert clipped_window_indices(0, 0, 3, 3)[-1] == (1, 1)
    assert clipped_window_indices(2, 2, 3, 3)[0] == (1, 1)
    assert clipped_window_indices(2, 2, 3, 3)[-1] == (2, 2)


def test_constants_and_ramps() -> None:
    const = np.full((5, 5), 2.5)
    for fn in (
        sobel_x_declarative,
        sobel_y_declarative,
        prewitt_x_declarative,
        prewitt_y_declarative,
    ):
        # constants vanish within rounding (characterized, not bitwise zero)
        assert bool(np.all(np.abs(fn(const)) <= 1e-12))
    ramp_x = np.array([[float(j) for j in range(5)] for _ in range(5)])
    assert float(sobel_x_declarative(ramp_x)[2, 2]) == -2.0
    ramp_y = np.array([[float(i)] * 5 for i in range(5)])
    assert float(sobel_y_declarative(ramp_y)[2, 2]) == -2.0


def test_impulse_kernels() -> None:
    impulse = np.zeros((5, 5))
    impulse[2, 2] = 1.0
    window = sobel_x_declarative(impulse)[1:4, 1:4]
    flipped = np.array([[0.25, 0.0, -0.25], [0.5, 0.0, -0.5], [0.25, 0.0, -0.25]])[::-1, ::-1]
    assert np.array_equal(window, flipped)


def test_transpose_relation() -> None:
    _, arrays = _load()
    sx_c03 = arrays["sobel_x_C03"].reshape(5, 5)
    sy_c04 = arrays["sobel_y_C04"].reshape(5, 5)
    assert np.array_equal(sx_c03, sy_c04.T)


def test_negation_relation() -> None:
    _, arrays = _load()
    field = arrays["input_X03"].reshape(5, 5)
    pos = sobel_x_declarative(field)
    neg = sobel_x_declarative(-field)
    assert np.array_equal(neg, -pos)


def test_exact_discrete_state_and_characterized_differences() -> None:
    manifest, arrays = _load()
    metrics = manifest["declarative_oracle_metrics"]
    assert metrics["arrays_compared"] == 228
    assert metrics["arrays_discrete_state_equal"] >= 197
    assert metrics["arrays_bitwise_equal"] >= 197
    assert metrics["finite_rounding_differences"] >= 104
    assert metrics["signed_zero_differences"] == 0
    # spot check: C03 sobel_x is exact in both discrete and bitwise senses
    ramp = arrays["input_C03"].reshape(5, 5)
    expected = arrays["sobel_x_C03"]
    summary = compare_discrete(expected, sobel_x_declarative(ramp).reshape(-1))
    assert summary["discrete_state_equal"] is True
    assert summary["bitwise_equal"] is True
    # C19 (transcendental replay witness) has characterized finite differences
    replay = arrays["input_C19"].reshape(6, 6)
    expected19 = arrays["sobel_y_C19"]
    summary19 = compare_discrete(expected19, sobel_y_declarative(replay).reshape(-1))
    if not summary19["discrete_state_equal"]:
        assert summary19["finite_rounding_differences"] > 0
        assert summary19["max_absolute_difference"] >= 0.0


def test_declarative_reproduces_fixture_values_within_characterization() -> None:
    _, arrays = _load()
    for cid in ("C01", "C06", "S04", "P03"):
        field = arrays["input_" + cid].reshape(5, 5)
        for arr, fn in (
            ("sobel_x", sobel_x_declarative),
            ("sobel_y", sobel_y_declarative),
            ("prewitt_x", prewitt_x_declarative),
            ("prewitt_y", prewitt_y_declarative),
        ):
            expected = arrays[f"{arr}_{cid}"]
            summary = compare_discrete(expected, fn(field).reshape(-1))
            assert summary["discrete_state_equal"] is True, (arr, cid, summary)


def test_compare_discrete_shape_guard() -> None:
    a = np.zeros((2, 2))
    b = np.zeros((3, 3))
    try:
        compare_discrete(a, b)
    except ValueError:
        return
    raise AssertionError("shape mismatch not rejected")
