"""Tests del modelo de datos de espectroscopía de fuerza (core/models/force.py)."""

from __future__ import annotations

import pickle

import numpy as np
import pytest

from spmkit.core.models import ForceCurve, ForceSegment, ForceVolume, InMemoryLoader


def _segment(
    kind: str = "extend",
    direction: str = "approach",
    n: int = 100,
    force: np.ndarray | None = None,
) -> ForceSegment:
    z = np.linspace(0.0, 1e-6, n)
    defl = np.zeros(n)
    return ForceSegment(
        segment_type=kind, direction=direction, raw_height=z, raw_deflection=defl, force=force
    )


def test_segment_require_force_raises_when_uncalibrated() -> None:
    seg = _segment()
    with pytest.raises(ValueError, match="sin fuerza calibrada"):
        seg.require_force()


def test_segment_require_force_returns_when_set() -> None:
    f = np.ones(100)
    seg = _segment(force=f)
    assert seg.require_force() is f


def test_segment_len() -> None:
    assert len(_segment(n=250)) == 250


def test_curve_segment_lookup_and_shim() -> None:
    ext = _segment("extend")
    ret = _segment("retract", direction="retract")
    curve = ForceCurve(segments=(ext, ret))
    assert curve.extend is ext
    assert curve.retract is ret
    assert curve.segment("extend") is ext
    assert curve.segment("pause") is None
    assert np.array_equal(curve.z, ext.raw_height)  # shim de compatibilidad
    assert curve.force is None  # el extend no está calibrado


def test_curve_without_segments_raises() -> None:
    curve = ForceCurve(segments=())
    with pytest.raises(ValueError, match="no tiene segmentos"):
        _ = curve.z


def test_force_volume_lazy_access() -> None:
    curves = tuple(ForceCurve(segments=(_segment(),), index=i) for i in range(4))
    vol = ForceVolume.from_curves(curves, grid_shape=(2, 2), x_range=1e-6, y_range=1e-6)
    assert len(vol) == 4
    assert vol.curve(2).index == 2
    with pytest.raises(IndexError):
        vol.curve(4)


def test_in_memory_loader_is_picklable() -> None:
    """El loader debe ser picklable para correr el pipeline en ProcessPoolExecutor."""
    curves = tuple(ForceCurve(segments=(_segment(),), index=i) for i in range(3))
    loader = InMemoryLoader(curves)
    restored = pickle.loads(pickle.dumps(loader))
    assert len(restored) == 3
    assert restored(1).index == 1


def test_force_volume_loader_survives_pickling() -> None:
    curves = tuple(ForceCurve(segments=(_segment(),), index=i) for i in range(3))
    vol = ForceVolume.from_curves(curves, grid_shape=(1, 3), x_range=1e-6, y_range=1e-6)
    restored_loader = pickle.loads(pickle.dumps(vol.loader))
    assert restored_loader(2).index == 2
