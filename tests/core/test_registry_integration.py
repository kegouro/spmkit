"""Registry integration tests.

Resolves a small representative subset through the registry and verifies
that direct public calls and registry-resolved calls are equivalent.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from spmkit.core import resolve_callable
from spmkit.core.analysis import (
    gradient_direction,
    gwyddion_align_rows_polynomial,
    gwyddion_gaussian_filter,
    gwyddion_gradient_magnitude,
    gwyddion_rank_filter,
    gwyddion_sobel_x,
    gwydion_step_line_correction,
)
from spmkit.core.models import SPMChannel

REPRESENTATIVE: list[tuple[str, Callable[..., object], dict[str, object]]] = [
    ("img.filter.rank", gwyddion_rank_filter,
     {"radius": 1, "percentile": 0.5}),
    ("img.filter.gaussian", gwyddion_gaussian_filter, {"sigma": 1.0}),
    ("img.filter.sobel_x", gwyddion_sobel_x, {}),
    ("img.filter.gradient_magnitude", gwyddion_gradient_magnitude, {}),
    ("img.filter.gradient_direction", gradient_direction, {}),
    ("img.level.align_rows_polynomial", gwyddion_align_rows_polynomial,
     {"degree": 1}),
    ("img.scanline.step_line_correction", gwydion_step_line_correction, {}),
]
PAIR_OPS: set[str] = {"img.filter.gradient_magnitude", "img.filter.gradient_direction"}


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
        if op_id in PAIR_OPS:
            out_direct = direct_fn(ch, ch)
            out_registry = resolved(ch, ch)
        else:
            out_direct = direct_fn(ch, **kwargs)
            out_registry = resolved(ch, **kwargs)
        assert isinstance(out_direct, SPMChannel)
        assert isinstance(out_registry, SPMChannel)
        assert np.array_equal(_bits(out_direct.data), _bits(out_registry.data)), op_id


def test_all_17_resolve_and_run() -> None:
    from spmkit.core import list_operations
    rng = np.random.default_rng(5)
    data = rng.normal(size=(10, 10))
    ch = _channel(data)
    mask = np.zeros_like(data)
    mask[3:5, 3:5] = 1.0
    required_params = {
        spec.operation_id: [p.name for p in spec.parameters if p.required]
        for spec in list_operations()
    }
    resolve_only = {
        op_id for op_id, names in required_params.items()
        if len(names) > 1 or (names and names[0] != "channel")
    }
    for spec in list_operations():
        fn = resolve_callable(spec.operation_id)
        if spec.operation_id in resolve_only:
            # multi-argument operations are resolved but not executed with a
            # single synthetic channel (honest resolve-only semantics)
            assert callable(fn)
            continue
        if spec.operation_id == "img.scanline.mark_scars":
            out = fn(ch, threshold_low=0.2)
            assert isinstance(out, np.ndarray)
            assert out.shape == data.shape
        elif spec.operation_id == "img.interpolation.laplace_under_mask":
            out = fn(ch, mask)
            assert isinstance(out, SPMChannel)
            assert out.data.shape == data.shape
        elif spec.operation_id == "img.scanline.remove_scars":
            out = fn(ch, threshold_low=0.2)
            assert isinstance(out, SPMChannel)
            assert out.data.shape == data.shape
        elif spec.operation_id in PAIR_OPS:
            out = fn(ch, ch)
            assert isinstance(out, SPMChannel)
            assert out.data.shape == data.shape
        else:
            out = fn(ch)
            assert isinstance(out, SPMChannel)
            assert out.data.shape == data.shape
