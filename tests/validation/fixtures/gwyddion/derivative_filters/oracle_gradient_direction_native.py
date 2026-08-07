"""Native SPMKit analytical composite oracle for gradient direction.

Formula (frozen):

    direction = atan2(gy, gx)

with gx = horizontal/X derivative component and gy = vertical/Y derivative
component; result in radians, range (-pi, pi].

This is a NATIVE_SPMKIT_ANALYTICAL_COMPOSITE.  It is NOT a direct Gwydion
parity target and no direct Gwyddion equivalence is claimed.

Two layers are kept separate:
  * mathematical direction relation (angle semantics: axes, quadrants,
    diagonals, zero vector, signed-zero axes, negation, transpose);
  * bit pattern produced by the frozen compiled C atan2 profile (glibc
    atan2 via ctypes, recorded backend).

The platform math backend actually used by the oracle is recorded.

Maturity ceiling from compiled evidence alone: NUMERICALLY_VERIFIED
(not CROSS_VALIDATED).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import math
import platform
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]

MATURITY_CEILING = "NUMERICALLY_VERIFIED"
CLASSIFICATION = "NATIVE_SPMKIT_ANALYTICAL_COMPOSITE"


@dataclass(frozen=True)
class MathBackend:
    name: str
    library: str
    symbol: str
    architecture: str
    libc: str

    def describe(self) -> str:
        return f"{self.name} ({self.library} {self.symbol}, {self.architecture}, {self.libc})"


def _resolve_libm() -> tuple[str, str]:
    libm_name = ctypes.util.find_library("m") or "libm.so.6"
    libc_name, _libc_ver = platform.libc_ver()
    symbol = "atan2@GLIBC_2.2.5" if libc_name == "glibc" else "atan2"
    return libm_name, symbol


def math_backend() -> MathBackend:
    libm_name, symbol = _resolve_libm()
    return MathBackend(
        name=(
            "glibc atan2 via ctypes"
            if symbol.startswith("atan2@GLIBC")
            else "libm atan2 via ctypes"
        ),
        library=libm_name,
        symbol=symbol,
        architecture=platform.machine(),
        libc=platform.libc_ver()[0] or "unknown",
    )


def _atan2_compiled(y: float, x: float) -> float:
    """Compiled-profile bit pattern: glibc/libm atan2 through ctypes."""
    libm_name, _ = _resolve_libm()
    libm = ctypes.CDLL(libm_name)
    libm.atan2.restype = ctypes.c_double
    libm.atan2.argtypes = [ctypes.c_double, ctypes.c_double]
    return float(libm.atan2(y, x))


def direction(gy: FloatArray, gx: FloatArray) -> FloatArray:
    """atan2(gy, gx) element-wise (compiled-profile backend)."""
    if gy.shape != gx.shape:
        raise ValueError("component fields must share shape")
    y = np.ascontiguousarray(gy, dtype=np.float64).reshape(-1)
    x = np.ascontiguousarray(gx, dtype=np.float64).reshape(-1)
    out = np.empty(y.size, dtype=np.float64)
    for i in range(y.size):
        out[i] = _atan2_compiled(float(y[i]), float(x[i]))
    return out.reshape(gy.shape)


def mathematical_direction(gy: FloatArray, gx: FloatArray) -> FloatArray:
    """Mathematical direction relation (math.atan2 semantics).

    Bit pattern may differ from the compiled profile; the relation layer
    is the definition layer for axes/quadrants/zero-vector behaviour.
    """
    if gy.shape != gx.shape:
        raise ValueError("component fields must share shape")
    y = np.ascontiguousarray(gy, dtype=np.float64)
    x = np.ascontiguousarray(gx, dtype=np.float64)
    out = np.empty_like(y)
    for i in range(y.size):
        out.reshape(-1)[i] = math.atan2(float(y.reshape(-1)[i]), float(x.reshape(-1)[i]))
    return out


# --- frozen axis / quadrant / zero-vector expectations ----------------------

# (gy, gx) -> expected mathematical angle in radians
AXIS_CASES: dict[tuple[float, float], float] = {
    (0.0, 2.0): 0.0,  # positive X axis
    (2.0, 0.0): math.pi / 2.0,  # positive Y axis
    (0.0, -2.0): math.pi,  # negative X axis
    (-2.0, 0.0): -math.pi / 2.0,  # negative Y axis
}

QUADRANT_CASES: dict[tuple[float, float], str] = {
    (1.0, 1.0): "q1",
    (1.0, -1.0): "q2",
    (-1.0, -1.0): "q3",
    (-1.0, 1.0): "q4",
}

DIAGONAL_CASES: dict[tuple[float, float], float] = {
    (1.0, 1.0): math.pi / 4.0,
    (1.0, -1.0): 3.0 * math.pi / 4.0,
    (-1.0, -1.0): -3.0 * math.pi / 4.0,
    (-1.0, 1.0): -math.pi / 4.0,
}

# NOTE: kept as a list of pairs because Python dicts collapse -0.0 keys
# (hash(-0.0) == hash(0.0)); the signed-zero cases must remain distinct.
SIGNED_ZERO_CASES: tuple[tuple[tuple[float, float], float], ...] = (
    ((0.0, 0.0), 0.0),  # atan2(+0, +0) = +0
    ((-0.0, 0.0), -0.0),  # atan2(-0, +0) = -0
    ((0.0, -0.0), math.pi),  # atan2(+0, -0) = +pi
    ((-0.0, -0.0), -math.pi),  # atan2(-0, -0) = -pi
)


def quadrant_of(angle: float) -> str:
    if angle == 0.0:
        return "positive_x"
    if angle == math.pi:
        return "negative_x"
    if angle == math.pi / 2.0:
        return "positive_y"
    if angle == -math.pi / 2.0:
        return "negative_y"
    if 0.0 < angle < math.pi / 2.0:
        return "q1"
    if math.pi / 2.0 < angle < math.pi:
        return "q2"
    if -math.pi < angle < -math.pi / 2.0:
        return "q3"
    return "q4"


def negation_relation(angle: float) -> float:
    """direction(-gy, -gx) in terms of direction(gy, gx) (angle layer)."""
    shifted = angle + math.pi
    if shifted > math.pi:
        shifted -= 2.0 * math.pi
    return shifted
