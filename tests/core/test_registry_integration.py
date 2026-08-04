"""Registry integration tests.

Resolves a small representative subset through the registry and verifies
that direct public calls and registry-resolved calls are equivalent.
"""

from __future__ import annotations

import numpy as np

from spmkit.core import resolve_callable
from spmkit.core.analysis import (
    gwyddion_align_rows_polynomial,
    gwyddion_gaussian_filter,
    gwyddion_rank_filter,
    gwydion_step_line_correction,
)
from spmkit.core.models import SPMChannel

REPRESENTATIVE = [
    ("img.filter.rank", gwyddion_rank_filter,
     {"radius": 1, "percentile": 0.5}),
    ("img.filter.gaussian", gwyddion_gaussian_filter, {"sigma": 1.0}),
    ("img.level.align_rows_polynomial", gwyddion_align_rows_polynomial,
     {"degree": 1}),
    ("img.scanline.step_line_correction", gwydion_step_line_correction, {}),
]


def _channel(data: np.ndarray) -> SPMChannel:
    rows, cols = data.shape
    return SPMChannel(name="t", data=data, unit="m", x_range=float(cols),
                      y_range=float(rows), direction="forward", group="g")


def _bits(a: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(a, dtype=np.float64).view(np.uint64)


def test_registry_resolution_equals_direct_call() -> None:
    rng = np.random.default_rng(11)
    for op_id, direct_fn, kwargs in REPRESENTATIVE:
        data = rng.normal(size=(12, 16))
        ch = _channel(data)
        resolved = resolve_callable(op_id)
        # identity: the registry callable IS the public callable
        assert resolved is direct_fn, op_id
        out_direct = direct_fn(ch, **kwargs)
        out_registry = resolved(ch, **kwargs)
        assert np.array_equal(_bits(out_direct.data), _bits(out_registry.data)), op_id


def test_all_11_resolve_and_run() -> None:
    from spmkit.core import list_operations
    rng = np.random.default_rng(5)
    data = rng.normal(size=(10, 10))
    ch = _channel(data)
    mask = np.zeros_like(data)
    mask[3:5, 3:5] = 1.0
    for spec in list_operations():
        fn = resolve_callable(spec.operation_id)
        if spec.operation_id == "img.scanline.mark_scars":
            out = fn(ch, threshold_low=0.2)
            assert out.shape == data.shape
        elif spec.operation_id == "img.interpolation.laplace_under_mask":
            out = fn(ch, mask)
            assert out.data.shape == data.shape
        elif spec.operation_id == "img.scanline.remove_scars":
            out = fn(ch, threshold_low=0.2)
            assert out.data.shape == data.shape
        else:
            out = fn(ch)
            assert out.data.shape == data.shape
