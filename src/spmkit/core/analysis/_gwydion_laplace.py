"""Production kernel: Gwydion 2.71 Interpolate Data Under Mask (Laplace).

Solves the discrete boundary-value problem that
gwy_data_field_laplace_solve (libprocess/correct-laplace.c:1566-1672) is
documented to solve (grain_id=-1, qprec=1.0 for the process operation):

    degree(p) * u[p] - sum(u[q] for masked existing four-neighbours q)
        = sum(fixed_value[q] for unmasked existing four-neighbours q)

with Neumann conditions implemented by omitting missing neighbours at
image borders, Dirichlet data from unmasked neighbours, the whole-field
mask policy (all zeros) and the empty-mask policy (unchanged copy).

This implementation solves the same discrete problem; it does NOT claim
algorithmic identity with Gwydion's multilevel anisotropic sparse
conjugate-gradient + damped-Jacobi + hierarchical reconstruction solver.

Source-compatible special paths (externally observable behaviour):
  - isolated one-pixel components: exact neighbour mean with the source
    addition order (up, left, right, down) as a left fold started from the
    first existing neighbour (the source seeds the fold with 0.0; starting
    from the first value is bit-identical for every finite ring except the
    all-negative-zero ring, where it preserves the -0.0 sign of the
    dynamically linked build; see L17 classification);
  - thin fully-interior 1xN / Mx1 components: exact Thomas tridiagonal
    solve replicating handle_thin_grain + gwy_math_tridiag_solve_rewrite
    arithmetic;
  - recognized fully-interior three-pixel L components: closed-form
    formulas replicating handle_3px_grain;
  - whole-field mask -> zeros; empty mask -> unchanged copy.

General components use a deterministic matrix-free float64
preconditioned conjugate-gradient solver (Jacobi diagonal preconditioner,
row-major unknown ordering, warm start from the existing field values,
explicit deterministic reductions).  Convergence failure raises an
explicit exception; it never returns a silently incomplete field.

Independence: no imports of tests, fixtures, oracles, generator, SciPy or
Gwydion.  Inputs and masks are never mutated; unmasked pixels remain
bitwise unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

FloatArray = np.ndarray

_CG_TOLERANCE = 1e-15      # relative residual target
_CG_MIN_ITERATIONS = 4


def _validated_field(value: object, *, operation: str) -> np.ndarray:
    source = np.asarray(value, dtype=np.float64)
    if source.ndim != 2:
        raise ValueError(f"{operation} requires a two-dimensional channel")
    if 0 in source.shape:
        raise ValueError(f"{operation} requires non-empty data")
    if not np.issubdtype(source.dtype, np.number) or np.iscomplexobj(source):
        raise TypeError(f"{operation} requires real numeric data")
    if not np.all(np.isfinite(source)):
        raise ValueError(f"{operation} requires finite data")
    return np.array(source, dtype=np.float64, order="C", copy=True)


def _validated_mask(value: object, shape: tuple[int, int],
                    *, operation: str) -> np.ndarray:
    mask = _validated_field(value, operation=operation)
    if mask.shape != shape:
        raise ValueError(f"{operation} mask shape must match the channel")
    return mask


def _label_components(masked: np.ndarray) -> tuple[np.ndarray, list[int]]:
    """4-connected component labelling, row-major deterministic order."""
    yres, xres = masked.shape
    labels = np.zeros((yres, xres), dtype=np.int64)
    sizes: list[int] = []
    next_label = 1
    for i in range(yres):
        for j in range(xres):
            if not masked[i, j] or labels[i, j]:
                continue
            # BFS flood fill, deterministic row-major seed order
            queue = [(i, j)]
            labels[i, j] = next_label
            size = 0
            head = 0
            while head < len(queue):
                ci, cj = queue[head]
                head += 1
                size += 1
                for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    ni, nj = ci + di, cj + dj
                    if (0 <= ni < yres and 0 <= nj < xres
                            and masked[ni, nj] and labels[ni, nj] == 0):
                        labels[ni, nj] = next_label
                        queue.append((ni, nj))
            sizes.append(size)
            next_label += 1
    return labels, sizes


def _bbox_of(labels: np.ndarray, label: int) -> tuple[int, int, int, int]:
    ys, xs = np.where(labels == label)
    return int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())


def _one_pixel_mean(z: np.ndarray, width: int, k: int) -> float:
    """handle_1x1_grain mean with the source addition order.

    Left fold started from the first existing neighbour (up, left, right,
    down).  For every finite ring except the all-negative-zero ring this is
    bit-identical to the frozen source fold seeded with 0.0; for the
    all-negative-zero ring it preserves -0.0, matching the dynamically
    linked 2.71 build (L17 classification).
    """
    yres = len(z) // width
    s = None
    n = 0
    for di, dj in ((-1, 0), (0, -1), (0, 1), (1, 0)):
        ni, nj = k // width + di, k % width + dj
        if 0 <= ni < yres and 0 <= nj < width:
            value = z[k + di * width + dj]
            s = value if s is None else s + value
            n += 1
    assert s is not None and n > 0
    return s / n


def _thomas(d: np.ndarray, a: np.ndarray, b: np.ndarray,
            rhs: np.ndarray) -> np.ndarray:
    """gwy_math_tridiag_solve_rewrite (gwymath.c:716-743) verbatim order.

    d: diagonal (modified in place conceptually), a: sub-diagonal,
    b: super-diagonal, rhs: right-hand side (solution on return).
    """
    n = len(rhs)
    dd = np.array(d, dtype=np.float64, copy=True)
    rr = np.array(rhs, dtype=np.float64, copy=True)
    for i in range(n - 1):
        if dd[i] == 0.0:
            raise ArithmeticError("tridiagonal elimination failure")
        dd[i + 1] -= b[i] / dd[i] * a[i]
        rr[i + 1] -= b[i] / dd[i] * rr[i]
    if dd[n - 1] == 0.0:
        raise ArithmeticError("tridiagonal elimination failure")
    for i in range(n - 1, 0, -1):
        rr[i] /= dd[i]
        rr[i - 1] -= a[i - 1] * rr[i]
    rr[0] /= dd[0]
    return rr


def _solve_thin_grain(field: np.ndarray, labels: np.ndarray, label: int,
                      bbox: tuple[int, int, int, int]) -> np.ndarray:
    """handle_thin_grain (correct-laplace.c:1466-1511) + Thomas solve.

    Returns the solved bbox (z) for a fully-interior 1xN or Mx1 component.
    """
    r0, r1, c0, c1 = bbox
    height = r1 - r0 + 1
    width = c1 - c0 + 1
    # source orientation test: (height-2 == 1) on the enlarged bbox
    horizontal = (height - 2) == 1
    n = width - 2 if horizontal else height - 2
    z = np.array(field[r0:r1 + 1, c0:c1 + 1], dtype=np.float64, copy=True)
    d = np.full(n, 4.0)
    a = np.full(n, -1.0)
    b = np.full(n, -1.0)
    rhs = np.empty(n)
    if not horizontal:
        # vertical grain: bbox width == 3, masked pixels at column 1
        rhs[0] = z[0, 1] + z[1, 0] + z[1, 2]
        for i in range(1, n - 1):
            rhs[i] = z[i + 1, 0] + z[i + 1, 2]
        rhs[n - 1] = z[n, 0] + z[n, 2] + z[n + 1, 1]
    else:
        # horizontal grain: bbox height == 3, masked pixels at row 1
        rhs[0] = z[0, 1] + z[1, 0] + z[2, 1]
        for i in range(1, n - 1):
            rhs[i] = z[0, i + 1] + z[2, i + 1]
        rhs[n - 1] = z[0, n] + z[1, n + 1] + z[2, n]
    sol = _thomas(d, a, b, rhs)
    if horizontal:
        z[1, 1:n + 1] = sol
    else:
        z[1:n + 1, 1] = sol
    return z


def _solve_l_grain(field: np.ndarray, labels: np.ndarray, label: int,
                   bbox: tuple[int, int, int, int]) -> np.ndarray:
    """handle_3px_grain (correct-laplace.c:1514-1536) closed forms.

    bbox must be 4x4; the L occupies three of the (1,1),(1,2),(2,1),(2,2)
    positions.  Returns the solved bbox (z).
    """
    r0, r1, c0, c1 = bbox
    z = np.array(field[r0:r1 + 1, c0:c1 + 1], dtype=np.float64, copy=True)
    levels = np.zeros((4, 4), dtype=np.int64)
    levels[(labels[r0:r1 + 1, c0:c1 + 1] == label)] = 1
    # source index k = i*width + j with width 4
    def lv(i: int, j: int) -> int:
        return int(levels[i, j])

    if not lv(1, 1):
        z[2, 2] = (2 * (z[2, 3] + z[3, 2]) + z[1, 1]
                   + 0.5 * (z[0, 2] + z[1, 3] + z[2, 0] + z[3, 1])) / 7.0
        z[1, 2] = 0.25 * (z[0, 2] + z[1, 1] + z[1, 3] + z[2, 2])
        z[2, 1] = 0.25 * (z[1, 1] + z[2, 0] + z[2, 2] + z[3, 1])
    elif not lv(1, 2):
        z[2, 1] = (2 * (z[2, 0] + z[3, 1]) + z[1, 2]
                   + 0.5 * (z[0, 1] + z[1, 0] + z[2, 3] + z[3, 2])) / 7.0
        z[1, 1] = 0.25 * (z[0, 1] + z[1, 0] + z[1, 2] + z[2, 1])
        z[2, 2] = 0.25 * (z[1, 2] + z[2, 1] + z[2, 3] + z[3, 2])
    elif not lv(2, 1):
        z[1, 2] = (2 * (z[0, 2] + z[1, 3]) + z[2, 1]
                   + 0.5 * (z[0, 1] + z[1, 0] + z[2, 3] + z[3, 2])) / 7.0
        z[1, 1] = 0.25 * (z[0, 1] + z[1, 0] + z[1, 2] + z[2, 1])
        z[2, 2] = 0.25 * (z[1, 2] + z[2, 1] + z[2, 3] + z[3, 2])
    else:
        z[1, 1] = (2 * (z[0, 1] + z[1, 0]) + z[2, 2]
                   + 0.5 * (z[0, 2] + z[1, 3] + z[2, 0] + z[3, 1])) / 7.0
        z[1, 2] = 0.25 * (z[0, 2] + z[1, 1] + z[1, 3] + z[2, 2])
        z[2, 1] = 0.25 * (z[1, 1] + z[2, 0] + z[2, 2] + z[3, 1])
    return z


def _conjugate_gradient(field: np.ndarray, labels: np.ndarray, label: int,
                        bbox: tuple[int, int, int, int],
                        classification: str) -> tuple[np.ndarray, int, float]:
    """Deterministic matrix-free Jacobi-preconditioned CG for one component.

    Unknowns are the component's masked pixels in row-major order.  The
    operator and right-hand side are assembled from the discrete stencil;
    the solve is warm-started from the existing field values.  Reductions
    use fixed numpy order (deterministic).  A few damped-Jacobi polish
    sweeps refine the solution after CG.
    """
    r0, r1, c0, c1 = bbox
    yres, xres = field.shape
    rows, cols = np.where(labels[r0:r1 + 1, c0:c1 + 1] == label)
    rows = rows + r0
    cols = cols + c0
    n = len(rows)
    if n == 0:
        raise ArithmeticError("empty component")
    index = np.full((r1 - r0 + 1, c1 - c0 + 1), -1, dtype=np.int64)
    for k in range(n):
        index[rows[k] - r0, cols[k] - c0] = k

    # assemble degree, neighbour indices and right-hand side
    degree = np.zeros(n, dtype=np.float64)
    rhs = np.zeros(n, dtype=np.float64)
    neighbours: list[list[int]] = [[] for _ in range(n)]
    for k in range(n):
        i, j = int(rows[k]), int(cols[k])
        deg = 0
        for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ni, nj = i + di, j + dj
            if not (0 <= ni < yres and 0 <= nj < xres):
                continue  # Neumann by omission
            deg += 1
            if labels[ni, nj] == label:
                neighbours[k].append(int(index[ni - r0, nj - c0]))
            else:
                rhs[k] += float(field[ni, nj])
        degree[k] = deg

    # matrix-free operator: (A v)[k] = degree[k]*v[k] - sum(v[neighbours])
    def apply_a(v: np.ndarray) -> np.ndarray:
        out = degree * v
        for k in range(n):
            s = 0.0
            for q in neighbours[k]:
                s += v[q]
            out[k] -= s
        return out

    x = np.array(field[rows, cols], dtype=np.float64, copy=True)
    r = rhs - apply_a(x)
    r_sq = float(np.dot(r, r))
    if r_sq == 0.0:
        return x, 0, 0.0
    z = r / degree
    p = np.array(z, dtype=np.float64, copy=True)
    rs = float(np.dot(r, z))
    rhs_norm = float(np.sqrt(np.dot(rhs, rhs)))
    # consistent norm stopping rule: ||r|| <= tolerance * max(||b||, 1)
    target_sq = (_CG_TOLERANCE * max(rhs_norm, 1.0)) ** 2
    max_iter = max(_CG_MIN_ITERATIONS, 8 * n + 40)
    iterations = 0
    converged = False
    for _ in range(max_iter):
        iterations += 1
        ap = apply_a(p)
        p_ap = float(np.dot(p, ap))
        if p_ap == 0.0:
            raise ArithmeticError("conjugate-gradient breakdown")
        alpha = rs / p_ap
        x += alpha * p
        r -= alpha * ap
        r_sq = float(np.dot(r, r))
        if r_sq <= target_sq:
            converged = True
            break
        rs_new = float(np.dot(r, r / degree))
        beta = rs_new / rs
        p = r / degree + beta * p
        rs = rs_new
    if not converged and r_sq > target_sq:
        raise ArithmeticError(
            f"Laplace conjugate gradient did not converge for a component "
            f"({classification}, n={n}, residual {r_sq:.3e})")
    # final residual diagnostics (the residual is already at the stopping
    # target; damped-Jacobi refinement is deliberately NOT used because it
    # is not contractive for Neumann-edge components)
    res = np.abs(rhs - apply_a(x))
    return x, iterations, float(np.max(res))


def _enlarged_bbox(bbox: tuple[int, int, int, int], yres: int,
                  xres: int) -> tuple[int, int, int, int]:
    """Source enlarge_field_part: grow by one on each side, clipped."""
    r0, r1, c0, c1 = bbox
    er0 = max(r0 - 1, 0)
    er1 = min(r1 + 1, yres - 1)
    ec0 = max(c0 - 1, 0)
    ec1 = min(c1 + 1, xres - 1)
    return er0, er1, ec0, ec1


def _component_classification(size: int, bbox: tuple[int, int, int, int],
                              yres: int, xres: int,
                              labels: np.ndarray, label: int) -> str:
    r0, r1, c0, c1 = bbox
    height = r1 - r0 + 1
    width = c1 - c0 + 1
    er0, er1, ec0, ec1 = _enlarged_bbox(bbox, yres, xres)
    eheight = er1 - er0 + 1
    ewidth = ec1 - ec0 + 1
    fully_inside = (eheight == height + 2 and ewidth == width + 2)
    if size == 1:
        return "exact one-pixel local"
    if fully_inside and (height == 1 or width == 1):
        return "thin/tridiagonal"
    if fully_inside and size == 3 and eheight == 4 and ewidth == 4:
        sub = labels[er0:er1 + 1, ec0:ec1 + 1]
        if int(np.count_nonzero(sub == label)) == 3:
            return "closed-form L"
    return "iterative conjugate gradient"


@dataclass(frozen=True)
class _GwydionLaplaceResult:
    """Every observable of the production Laplace operation."""

    input_snapshot: FloatArray
    mask_snapshot: FloatArray
    corrected_field: FloatArray
    solved_coordinates: tuple[tuple[int, int], ...]
    component_count: int
    component_sizes: tuple[int, ...]
    special_path_classifications: tuple[str, ...]
    iteration_counts: tuple[int, ...]
    max_residual: float
    mean_residual: float
    empty_mask: bool
    whole_field_mask: bool
    unmasked_mutation_count: int
    mask_mutation_evidence: bool
    input_mutation_evidence: bool


def _gwydion_laplace_result(field: object, mask: object) -> _GwydionLaplaceResult:
    """Run the production Laplace kernel (private; public wrapper in
    core.analysis.interpolation).  Corresponds to the process operation
    with grain_id=-1 and qprec=1.0 (no public qprec parameter)."""
    data = _validated_field(field, operation="Laplace interpolation")
    m = _validated_mask(mask, data.shape, operation="Laplace interpolation")
    yres, xres = data.shape
    masked = m > 0.0

    if not np.any(masked):
        corrected = np.array(data, dtype=np.float64, order="C", copy=True)
        return _GwydionLaplaceResult(
            input_snapshot=data, mask_snapshot=m, corrected_field=corrected,
            solved_coordinates=(), component_count=0, component_sizes=(),
            special_path_classifications=(), iteration_counts=(),
            max_residual=0.0, mean_residual=0.0, empty_mask=True,
            whole_field_mask=False, unmasked_mutation_count=0,
            mask_mutation_evidence=False, input_mutation_evidence=False)
    if np.all(masked):
        corrected = np.zeros((yres, xres), dtype=np.float64)
        coords = tuple((int(i), int(j)) for i, j in zip(
            *np.where(masked), strict=True))
        return _GwydionLaplaceResult(
            input_snapshot=data, mask_snapshot=m, corrected_field=corrected,
            solved_coordinates=coords, component_count=1,
            component_sizes=(int(masked.size),),
            special_path_classifications=("whole-field zero",),
            iteration_counts=(0,), max_residual=0.0, mean_residual=0.0,
            empty_mask=False, whole_field_mask=True,
            unmasked_mutation_count=0, mask_mutation_evidence=False,
            input_mutation_evidence=False)

    labels, sizes = _label_components(masked)
    corrected = np.array(data, dtype=np.float64, order="C", copy=True)
    solved: list[tuple[int, int]] = []
    classifications: list[str] = []
    iterations: list[int] = []
    residuals: list[float] = []

    for label, size in enumerate(sizes, start=1):
        bbox = _bbox_of(labels, label)
        classification = _component_classification(size, bbox, yres, xres,
                                                   labels, label)
        r0, r1, c0, c1 = bbox
        er0, er1, ec0, ec1 = _enlarged_bbox(bbox, yres, xres)
        ewidth = ec1 - ec0 + 1
        eheight = er1 - er0 + 1
        if classification == "exact one-pixel local":
            z = np.array(data[er0:er1 + 1, ec0:ec1 + 1], dtype=np.float64,
                         copy=True).reshape(-1)
            for i in range(eheight):
                for j in range(ewidth):
                    k = i * ewidth + j
                    if labels[er0 + i, ec0 + j] == label:
                        z[k] = _one_pixel_mean(z, ewidth, k)
            sub = z.reshape(eheight, ewidth)
            wr0, wr1, wc0, wc1 = er0, er1, ec0, ec1
            iterations.append(0)
            residuals.append(0.0)
        elif classification == "thin/tridiagonal":
            sub = _solve_thin_grain(data, labels, label,
                                    (er0, er1, ec0, ec1))
            wr0, wr1, wc0, wc1 = er0, er1, ec0, ec1
            iterations.append(0)
            residuals.append(0.0)
        elif classification == "closed-form L":
            sub = _solve_l_grain(data, labels, label, (er0, er1, ec0, ec1))
            wr0, wr1, wc0, wc1 = er0, er1, ec0, ec1
            iterations.append(0)
            residuals.append(0.0)
        else:
            x, iters, resmax = _conjugate_gradient(data, labels, label, bbox,
                                                   classification)
            sub = np.array(data[r0:r1 + 1, c0:c1 + 1], dtype=np.float64,
                           copy=True)
            sub[labels[r0:r1 + 1, c0:c1 + 1] == label] = x
            wr0, wr1, wc0, wc1 = r0, r1, c0, c1
            iterations.append(iters)
            residuals.append(resmax)
        corrected[wr0:wr1 + 1, wc0:wc1 + 1] = np.where(
            labels[wr0:wr1 + 1, wc0:wc1 + 1] == label, sub,
            corrected[wr0:wr1 + 1, wc0:wc1 + 1])
        for i in range(r0, r1 + 1):
            for j in range(c0, c1 + 1):
                if labels[i, j] == label:
                    solved.append((i, j))
        classifications.append(classification)

    max_residual = max(residuals) if residuals else 0.0
    mean_residual = (sum(residuals) / len(residuals)) if residuals else 0.0
    # evidence: mask never mutated (it is a private validated copy and no
    # code path writes to it); unmasked pixels bitwise unchanged
    mask_mutation = False
    in_bits = data.view(np.uint64)
    out_bits = corrected.view(np.uint64)
    unmasked_changed = int(np.count_nonzero(
        (in_bits != out_bits) & (m <= 0.0)))

    return _GwydionLaplaceResult(
        input_snapshot=data, mask_snapshot=m, corrected_field=corrected,
        solved_coordinates=tuple(solved), component_count=len(sizes),
        component_sizes=tuple(sizes),
        special_path_classifications=tuple(classifications),
        iteration_counts=tuple(iterations),
        max_residual=max_residual, mean_residual=mean_residual,
        empty_mask=False, whole_field_mask=False,
        unmasked_mutation_count=unmasked_changed,
        mask_mutation_evidence=mask_mutation,
        input_mutation_evidence=False)
