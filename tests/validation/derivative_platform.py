"""Runtime math provenance, separate from immutable derivative campaign oracles.

Frozen bit patterns are checked only on a byte-identified reproduction backend.
Eligibility never depends on the outputs of the operation under test.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import hashlib
import math
import platform
from decimal import Decimal, localcontext
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

# Verified reproduction of all frozen hypot/atan2 arrays, not a reconstruction
# of missing historical build metadata. Library bytes AND resolved code offsets
# identify the implementation; a GLIBC symbol version alone does not.
_REPRODUCTION = {
    "architecture": "x86_64",
    "libc": ("glibc", "2.44"),
    "library_sha256": "965106704753eefe8c31ae7da6daba3ead3d18c52b19b5fcc41178bcc4aa999d",
    "hypot_offset": 370256,
    "atan2_offset": 89120,
}


@lru_cache(maxsize=1)
def runtime_library() -> ctypes.CDLL:
    name = ctypes.util.find_library("m")
    if name is None and platform.system() == "Darwin":
        name = ctypes.util.find_library("System")
    library = ctypes.CDLL(name)
    for name in ("hypot", "atan2"):
        function = getattr(library, name)
        function.argtypes = [ctypes.c_double, ctypes.c_double]
        function.restype = ctypes.c_double
    return library


class _DlInfo(ctypes.Structure):
    _fields_ = [
        ("fname", ctypes.c_char_p),
        ("base", ctypes.c_void_p),
        ("sname", ctypes.c_char_p),
        ("saddr", ctypes.c_void_p),
    ]


@lru_cache(maxsize=2)
def backend_identity(operation: str = "hypot") -> dict[str, Any]:
    identity: dict[str, Any] = {
        "architecture": platform.machine(),
        "libc": platform.libc_ver(),
        "operation": operation,
        "library_sha256": None,
        "code_offset": None,
    }
    try:
        function = getattr(runtime_library(), operation)
        address = ctypes.cast(function, ctypes.c_void_p).value
        dladdr = ctypes.CDLL(None).dladdr
        dladdr.argtypes = [ctypes.c_void_p, ctypes.POINTER(_DlInfo)]
        dladdr.restype = ctypes.c_int
        info = _DlInfo()
        if dladdr(address, ctypes.byref(info)) and info.fname and info.base and address:
            library_path = Path(info.fname.decode()).resolve()
            identity["library"] = str(library_path)
            identity["code_offset"] = address - info.base
            # Darwin may resolve a dylib from the shared cache without a file.
            if library_path.is_file():
                identity["library_sha256"] = hashlib.sha256(library_path.read_bytes()).hexdigest()
    except (AttributeError, OSError):
        pass  # Unknown identity must never be promoted to a frozen backend.
    return identity


def frozen_backend_matches(operation: str = "hypot") -> tuple[bool, str]:
    identity = backend_identity(operation)
    for key in ("architecture", "libc", "library_sha256"):
        if identity[key] != _REPRODUCTION[key]:
            return False, f"{operation} reproduction backend mismatch: {key}={identity[key]!r}"
    if identity["code_offset"] != _REPRODUCTION[f"{operation}_offset"]:
        return False, f"{operation} resolved implementation offset differs"
    return True, ""


def platform_hypot(x: float, y: float) -> float:
    return float(runtime_library().hypot(x, y))


def runtime_magnitude(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.array(
        [platform_hypot(float(a), float(b)) for a, b in zip(x.flat, y.flat, strict=True)]
    ).reshape(x.shape)


def runtime_direction(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    return np.array(
        [runtime_library().atan2(float(a), float(b)) for a, b in zip(y.flat, x.flat, strict=True)]
    ).reshape(x.shape)


def exact_hypot(x: float, y: float, precision: int = 120) -> Decimal:
    """Independent real-domain oracle; no binary64 squared intermediates."""
    with localcontext() as context:
        context.prec = precision
        a, b = Decimal.from_float(x), Decimal.from_float(y)
        return (a * a + b * b).sqrt()


def faithful_hypot(x: float, y: float, computed: float) -> bool:
    """Require one of the two floats bracketing sqrt(x*x+y*y), not allclose."""
    if not math.isfinite(computed) or computed < 0.0:
        return False
    squared = Fraction.from_float(x) ** 2 + Fraction.from_float(y) ** 2
    result_squared = Fraction.from_float(computed) ** 2
    if result_squared == squared:
        return True
    toward = math.inf if result_squared < squared else -math.inf
    neighbor = math.nextafter(computed, toward)
    if not math.isfinite(neighbor) or neighbor < 0.0:
        return False
    neighbor_squared = Fraction.from_float(neighbor) ** 2
    return min(result_squared, neighbor_squared) < squared < max(result_squared, neighbor_squared)
