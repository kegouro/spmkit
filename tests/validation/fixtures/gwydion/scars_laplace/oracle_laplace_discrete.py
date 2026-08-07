"""Independent mathematical reference for Gwydion 2.71 Laplace interpolation.

This module solves the DISCRETE BOUNDARY-VALUE PROBLEM that
gwy_data_field_laplace_solve (libprocess/correct-laplace.c:1566-1672) is
documented to solve; it is NOT a translation of the multilevel/CG/Jacobi
solver.

Discrete system (per masked pixel p):

    degree(p) * u[p] - sum(u[q] for masked existing four-neighbours q)
        = sum(fixed_value[q] for unmasked existing four-neighbours q)

with:
  - existing neighbours only inside the field;
  - omitted neighbours at image borders implement the source Neumann
    condition (correct-laplace.c doc: "Neumann conditions dz/dn=0");
  - unmasked neighbours implement Dirichlet data;
  - the whole-field-mask underspecified case follows the source policy
    (ngrains == 1 && size == xres*yres -> field cleared to zeros);
  - an empty mask leaves the input unchanged.

Numerics: Decimal arithmetic at 80 significant digits (getcontext().prec =
80), exact conversion of every input float64 via Decimal(float) (no
rounding through a short decimal string), and deterministic Gaussian
elimination with deterministic partial pivoting (first maximum).  No SciPy,
no Gwydion, no production imports, no fixture expected-output lookup.

Independence: this module does not import any SPMKit production module, any
Gwydion-compatibility kernel, the fixture generator, or any fixture file.

Signed zeros: the mathematical oracle does not define a unique zero sign;
sign differences are classified separately from mathematical error.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from decimal import Decimal, getcontext

import numpy as np

getcontext().prec = 80

FloatArray = np.ndarray

DIGITS = 80


def _validated_field(value: object, *, operation: str) -> np.ndarray:
    source = np.asarray(value, dtype=np.float64)
    if source.ndim != 2:
        raise ValueError(f"{operation} data must be two-dimensional")
    if 0 in source.shape:
        raise ValueError(f"{operation} data must have non-empty dimensions")
    if not np.isfinite(source).all():
        raise ValueError(f"{operation} data must be finite")
    return np.array(source, dtype=np.float64, order="C", copy=True)


def _validated_mask(value: object, shape: tuple[int, int],
                    *, operation: str) -> np.ndarray:
    mask = _validated_field(value, operation=operation)
    if mask.shape != shape:
        raise ValueError(f"{operation} mask shape must match data")
    return mask


def _exact_decimal(value: float) -> Decimal:
    """Exact binary float64 -> Decimal conversion (no string rounding)."""
    return Decimal(value)


def _fp_bits(value: float) -> int:
    return struct.unpack(">Q", struct.pack(">d", float(value)))[0]


@dataclass(frozen=True)
class LaplaceDiscreteReference:
    """Solution of the discrete boundary-value problem."""

    input_snapshot: FloatArray
    mask_snapshot: FloatArray
    masked_coordinates: tuple[tuple[int, int], ...]
    high_precision_values: tuple[Decimal, ...]
    corrected_float64: FloatArray
    matrix_sha256: str
    rhs_sha256: str
    mathematical_residual: Decimal
    empty_mask: bool
    whole_field_mask: bool
    singular_policy_applied: bool
    # probe comparison (only when probe_corrected is supplied)
    probe_corrected: FloatArray | None
    max_absolute_difference: float
    max_relative_difference: float
    max_ulp_difference: int
    signed_zero_mismatches: int
    unmasked_mutation_count: int
    elements_bitwise_exact: int
    elements_total: int


def _system_hashes(rows: list[tuple[int, list[tuple[int, Decimal]], Decimal]]
                   ) -> tuple[str, str]:
    """Canonical hashes of the matrix and right-hand side."""
    mh = hashlib.sha256()
    rh = hashlib.sha256()
    for row, terms, rhs in rows:
        for col, coeff in sorted(terms):
            mh.update(f"{col}:{coeff}".encode("ascii"))
            mh.update(b"\0")
        rh.update(f"{row}:{rhs}".encode("ascii"))
        rh.update(b"\0")
    return mh.hexdigest(), rh.hexdigest()


def _solve_gaussian(a: list[list[Decimal]], b: list[Decimal]
                    ) -> list[Decimal] | None:
    """Deterministic Gaussian elimination with partial pivoting.

    Pivot rule: at step k choose the first row i >= k with the maximum
    absolute coefficient in column k (ties broken by first occurrence).
    Returns None if the matrix is singular.
    """
    n = len(b)
    if n == 0:
        return []
    a = [row[:] for row in a]
    b = b[:]
    for k in range(n):
        pivot = None
        best = -Decimal(1)  # always smaller than any abs value
        for i in range(k, n):
            v = abs(a[i][k])
            if v > best:
                best = v
                pivot = i
        if pivot is None or best == 0:
            return None
        if pivot != k:
            a[k], a[pivot] = a[pivot], a[k]
            b[k], b[pivot] = b[pivot], b[k]
        pivot_val = a[k][k]
        for i in range(k + 1, n):
            if a[i][k] == 0:
                continue
            factor = a[i][k] / pivot_val
            a[i][k] = Decimal(0)
            for j in range(k + 1, n):
                a[i][j] -= factor * a[k][j]
            b[i] -= factor * b[k]
    x = [Decimal(0)] * n
    for i in range(n - 1, -1, -1):
        s = b[i]
        for j in range(i + 1, n):
            s -= a[i][j] * x[j]
        if a[i][i] == 0:
            return None
        x[i] = s / a[i][i]
    return x


def _bits_view(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array, dtype=np.float64).view(np.uint64)


def oracle_laplace_discrete(
    field: object,
    mask: object,
    *,
    probe_corrected: object | None = None,
) -> LaplaceDiscreteReference:
    """Solve the discrete boundary-value problem.

    ``probe_corrected`` is optional compiled-probe output used only for the
    comparison metrics; it is never read for expected values.
    """
    data = _validated_field(field, operation="Laplace interpolation")
    m = _validated_mask(mask, data.shape, operation="Laplace interpolation")
    yres, xres = data.shape
    masked = m > 0.0

    coords = [(int(i), int(j)) for i, j in zip(*np.where(masked), strict=True)]
    idx_of = {c: k for k, c in enumerate(coords)}
    empty = len(coords) == 0
    whole = bool(np.all(masked))

    high: tuple[Decimal, ...] = ()
    if empty:
        corrected = np.array(data, dtype=np.float64, order="C", copy=True)
        mat_sha = rhs_sha = hashlib.sha256(b"").hexdigest()
        residual = Decimal(0)
    elif whole:
        corrected = np.zeros((yres, xres), dtype=np.float64)
        high = tuple(Decimal(0) for _ in coords)
        mat_sha = rhs_sha = hashlib.sha256(b"").hexdigest()
        residual = Decimal(0)
    else:
        rows: list[tuple[int, list[tuple[int, Decimal]], Decimal]] = []
        for k, (i, j) in enumerate(coords):
            terms: list[tuple[int, Decimal]] = []
            rhs = Decimal(0)
            degree = 0
            for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ni, nj = i + di, j + dj
                if not (0 <= ni < yres and 0 <= nj < xres):
                    continue  # Neumann by omission at the field border
                degree += 1
                if masked[ni, nj]:
                    terms.append((idx_of[(ni, nj)], Decimal(-1)))
                else:
                    rhs += _exact_decimal(float(data[ni, nj]))
            # degree(p) = number of existing four-neighbours; masked
            # neighbours contribute -1 each to the left-hand side
            terms.append((k, Decimal(degree)))
            rows.append((k, terms, rhs))

        mat_sha, rhs_sha = _system_hashes(rows)
        n = len(rows)
        a = [[Decimal(0)] * n for _ in range(n)]
        b = [Decimal(0)] * n
        for k, terms, rhs in rows:
            for col, coeff in terms:
                a[k][col] += coeff
            b[k] = rhs
        solution = _solve_gaussian(a, b)
        if solution is None:
            raise ArithmeticError("discrete Laplace system is singular")
        high = tuple(solution)
        corrected = np.array(data, dtype=np.float64, order="C", copy=True)
        for (i, j), value in zip(coords, solution, strict=True):
            corrected[i, j] = float(value)
        # mathematical residual: max |A*u - b|
        residual = Decimal(0)
        for k in range(n):
            s = Decimal(0)
            for j in range(n):
                s += a[k][j] * solution[j]
            residual = max(residual, abs(s - b[k]))

    # comparison metrics vs the compiled probe
    probe = None
    if probe_corrected is not None:
        probe = _validated_field(probe_corrected, operation="probe comparison")
        if probe.shape != data.shape:
            raise ValueError("probe corrected shape must match data")
        pb = _bits_view(probe)
        ob = _bits_view(corrected)
        eq = int(np.count_nonzero(pb == ob))
        max_abs = 0.0
        max_rel = 0.0
        max_ulp = 0
        xor = np.bitwise_xor(pb.ravel(), ob.ravel())
        sz = int(np.count_nonzero(xor == 0x8000000000000000))
        for i in range(pb.size):
            if pb.ravel()[i] == ob.ravel()[i]:
                continue
            # sign-bit-only differences are signed-zero semantics, counted
            # separately, never as mathematical or ULP error
            if int(xor[i]) == 0x8000000000000000:
                continue
            pv = float(probe.ravel()[i])
            ov = float(corrected.ravel()[i])
            max_abs = max(max_abs, abs(pv - ov))
            if abs(ov) != 0:
                max_rel = max(max_rel, abs(pv - ov) / abs(ov))
            max_ulp = max(max_ulp,
                          abs(int(pb.ravel()[i]) - int(ob.ravel()[i])))
        unmasked = int(np.count_nonzero(
            (pb.ravel() != ob.ravel()) & (m.ravel() <= 0.0)))
    else:
        eq = int(corrected.size)
        max_abs = max_rel = 0.0
        max_ulp = 0
        sz = 0
        unmasked = 0

    return LaplaceDiscreteReference(
        input_snapshot=data,
        mask_snapshot=m,
        masked_coordinates=tuple(coords),
        high_precision_values=high,
        corrected_float64=corrected,
        matrix_sha256=mat_sha,
        rhs_sha256=rhs_sha,
        mathematical_residual=residual,
        empty_mask=empty,
        whole_field_mask=whole,
        singular_policy_applied=whole,
        probe_corrected=probe,
        max_absolute_difference=max_abs,
        max_relative_difference=max_rel,
        max_ulp_difference=max_ulp,
        signed_zero_mismatches=sz,
        unmasked_mutation_count=unmasked,
        elements_bitwise_exact=eq,
        elements_total=int(corrected.size),
    )
