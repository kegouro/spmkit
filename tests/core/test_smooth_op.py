"""Tests de la operación de suavizado (Savitzky-Golay) del pipeline de fuerza."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from spmkit.core.models import ForceCurve, ForceSegment
from spmkit.core.pipeline import Recipe, Step, available_operations, run


def _hertz_segment() -> ForceSegment:
    separation = np.linspace(6e-7, 0.0, 400)
    e_star = 1.0e6 / (1 - 0.3**2)
    k = (4.0 / 3.0) * e_star * np.sqrt(10e-9)
    force = k * np.clip(3e-7 - separation, 0.0, None) ** 1.5
    return ForceSegment(
        segment_type="extend",
        direction="approach",
        raw_height=separation,
        raw_deflection=np.zeros_like(separation),
        force=force,
        separation=separation,
        state="force_n",
    )


def test_smooth_is_registered() -> None:
    assert "smooth" in available_operations()


def test_smooth_reduces_noise_keeps_length() -> None:
    seg = _hertz_segment()
    rng = np.random.default_rng(0)
    noisy = replace(seg, force=seg.force + rng.normal(0, seg.force.max() * 0.05, seg.force.size))
    result, ctx = run(
        Recipe(steps=(Step(op="smooth", params={"window": 21}),)), ForceCurve((noisy,))
    )
    out = result.extend.force
    assert out.size == noisy.force.size
    assert np.std(np.diff(out)) < np.std(np.diff(noisy.force))
    assert ctx["smoothed"] == 21


def test_smooth_noop_for_small_window() -> None:
    seg = _hertz_segment()
    result, _ = run(Recipe(steps=(Step(op="smooth", params={"window": 1}),)), ForceCurve((seg,)))
    assert np.array_equal(result.extend.force, seg.force)
