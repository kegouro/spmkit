"""Test de la figura de publicación de curva de fuerza (matplotlib)."""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.models import ForceCurve, ForceSegment
from spmkit.core.pipeline import Recipe, Step, run

pytest.importorskip("matplotlib")


def _fitted_curve():
    separation = np.linspace(6e-7, 0.0, 300)
    e_star = 1.0e6 / (1 - 0.3**2)
    k = (4.0 / 3.0) * e_star * np.sqrt(10e-9)
    force = k * np.clip(3e-7 - separation, 0.0, None) ** 1.5
    seg = ForceSegment(
        segment_type="extend",
        direction="approach",
        raw_height=separation,
        raw_deflection=np.zeros_like(separation),
        force=force,
        separation=separation,
        state="force_n",
    )
    curve = ForceCurve(segments=(seg,))
    recipe = Recipe(
        steps=(
            Step(op="find_contact_point"),
            Step(op="fit_elasticity", params={"model": "sphere", "tip_radius": 10e-9}),
        )
    )
    _, ctx = run(recipe, curve)
    return curve, ctx


def test_save_force_curve_writes_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from spmkit.core.viz import save_force_curve

    curve, ctx = _fitted_curve()
    out = save_force_curve(curve, ctx, tmp_path / "curva.png")
    assert out.exists() and out.stat().st_size > 0


def test_render_indentation_mode_ok(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from spmkit.core.viz import save_force_curve

    curve, ctx = _fitted_curve()
    out = save_force_curve(curve, ctx, tmp_path / "ind.png", indentation=True)
    assert out.exists()
