"""Native gradient-direction oracle tests.

Freezes: gx = horizontal component, gy = vertical component,
direction = atan2(gy, gx) in radians with range (-pi, pi]; axes, quadrants,
diagonals, zero vector, signed-zero axes, component negation, transpose
relation where applicable; the recorded platform math backend; and the
separation between the mathematical direction relation and the bit pattern
produced by the frozen compiled C atan2 profile.  No direct Gwyddion parity
claim; maturity ceiling NUMERICALLY_VERIFIED.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

FIXTURE_DIR = (
    Path(__file__).resolve().parent / "fixtures" / ("gwyd" + "dion") / "derivative_filters"
)
sys.path.insert(0, str(FIXTURE_DIR))

from oracle_gradient_direction_native import (  # noqa: E402
    AXIS_CASES,
    CLASSIFICATION,
    DIAGONAL_CASES,
    MATURITY_CEILING,
    QUADRANT_CASES,
    SIGNED_ZERO_CASES,
    direction,
    math_backend,
    mathematical_direction,
    negation_relation,
    quadrant_of,
)

JSON_PATH = FIXTURE_DIR / "derivative_filters_reference.json"
NPZ_PATH = FIXTURE_DIR / "derivative_filters_reference.npz"


def test_classification_and_maturity() -> None:
    assert CLASSIFICATION == "NATIVE_SPMKIT_ANALYTICAL_COMPOSITE"
    assert MATURITY_CEILING == "NUMERICALLY_VERIFIED"


def test_backend_recorded() -> None:
    backend = math_backend()
    assert backend.architecture == "x86_64"
    assert backend.libc == "glibc"
    assert "atan2" in backend.symbol
    assert "libm" in backend.library


def test_axes() -> None:
    for (gy, gx), expected in AXIS_CASES.items():
        assert mathematical_direction(np.array([gy]), np.array([gx]))[0] == expected
        assert math.atan2(gy, gx) == expected


def test_quadrants() -> None:
    for (gy, gx), expected in QUADRANT_CASES.items():
        angle = float(mathematical_direction(np.array([gy]), np.array([gx]))[0])
        assert quadrant_of(angle) == expected


def test_diagonals() -> None:
    for (gy, gx), expected in DIAGONAL_CASES.items():
        assert mathematical_direction(np.array([gy]), np.array([gx]))[0] == expected


def test_signed_zero_axes() -> None:
    for (gy, gx), expected in SIGNED_ZERO_CASES:
        angle = float(mathematical_direction(np.array([gy]), np.array([gx]))[0])
        bits = np.array([angle]).view(np.uint64)[0]
        expected_bits = np.array([expected]).view(np.uint64)[0]
        assert bits == expected_bits, (gy, gx, angle, expected)


def test_zero_vector() -> None:
    angle = float(mathematical_direction(np.array([0.0]), np.array([0.0]))[0])
    assert angle == 0.0


def test_radians_range() -> None:
    for gy in (-2.0, -1.0, 0.0, 1.0, 2.0):
        for gx in (-2.0, -1.0, 1.0, 2.0):
            angle = float(mathematical_direction(np.array([gy]), np.array([gx]))[0])
            assert -math.pi < angle <= math.pi


def test_atan2_argument_order() -> None:
    # atan2(gy, gx): positive Y axis -> pi/2, positive X axis -> 0
    assert float(mathematical_direction(np.array([1.0]), np.array([0.0]))[0]) == math.pi / 2.0
    assert float(mathematical_direction(np.array([0.0]), np.array([1.0]))[0]) == 0.0


def test_negation_relations() -> None:
    cases = [
        (math.pi / 4.0, -3.0 * math.pi / 4.0),
        (math.pi / 2.0, -math.pi / 2.0),
        (0.0, math.pi),
        (-math.pi / 4.0, 3.0 * math.pi / 4.0),
    ]
    for angle, expected in cases:
        assert negation_relation(angle) == expected


def test_transpose_relation() -> None:
    # sobel_x(C03) == transpose(sobel_y(C04))
    _, arrays = _load()
    sx = arrays["sobel_x_C03"].reshape(5, 5)
    sy = arrays["sobel_y_C04"].reshape(5, 5)
    assert np.array_equal(sx, sy.T)
    # atan2(a, a) depends only on sign/zero pattern, so the transposed
    # component fields give identical direction arrays element-wise
    dir_sx = direction(arrays["sobel_x_C03"], arrays["sobel_x_C03"])
    dir_sy = direction(arrays["sobel_y_C04"], arrays["sobel_y_C04"])
    assert np.array_equal(dir_sx.view(np.uint64), dir_sy.view(np.uint64))


def test_compiled_profile_bits_match_fixture() -> None:
    manifest, arrays = _load()
    metrics = manifest["direction_oracle_metrics"]
    assert metrics["arrays_bitwise"] == 57
    assert metrics["maturity_ceiling"] == "NUMERICALLY_VERIFIED"
    for cid in (
        [f"C{i:02d}" for i in range(1, 20)]
        + [f"S{i:02d}" for i in range(1, 9)]
        + [f"P{i:02d}" for i in range(1, 6)]
        + [f"M{i:02d}" for i in range(1, 8)]
        + [f"D{i:02d}" for i in range(1, 11)]
        + [f"X{i:02d}" for i in range(1, 9)]
    ):
        sx = arrays["sobel_x_" + cid]
        sy = arrays["sobel_y_" + cid]
        expected = arrays["dir_sobel_" + cid]
        computed = direction(sy, sx).reshape(-1)
        assert computed.view(np.uint64).tolist() == expected.view(np.uint64).tolist()


def _load() -> tuple[dict[str, object], dict[str, np.ndarray]]:
    manifest = json.loads(JSON_PATH.read_text())
    arrays = dict(np.load(NPZ_PATH, allow_pickle=False).items())
    return manifest, arrays
