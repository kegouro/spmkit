"""Tests de las operaciones del pipeline sobre curvas de fuerza (end-to-end)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from spmkit.core.io.jpk import load_jpk_force
from spmkit.core.models import ForceCurve, ForceSegment
from spmkit.core.pipeline import Recipe, Step, available_operations, run

_REAL_SAMPLE = (
    Path(__file__).resolve().parents[2] / "reference" / "jpk_samples" / "sample.jpk-force"
)


def _synthetic_hertz_curve(
    young: float = 1.0e6, radius: float = 10e-9, sep_contact: float = 3e-7
) -> ForceCurve:
    """Curva de fuerza sintética (convención de separación) con módulo conocido.

    La separación decrece de lejos (600 nm) a indentación; el contacto es a
    ``sep_contact`` y ``δ = sep_contact − separación`` para separación menor.
    """
    separation = np.linspace(6e-7, 0.0, 500)
    e_star = young / (1 - 0.3**2)
    k = (4.0 / 3.0) * e_star * np.sqrt(radius)
    delta = np.clip(sep_contact - separation, 0.0, None)
    force = k * delta**1.5
    seg = ForceSegment(
        segment_type="extend",
        direction="approach",
        raw_height=separation,
        raw_deflection=np.zeros_like(separation),
        deflection=np.zeros_like(separation),
        force=force,
        separation=separation,
        state="force_n",
    )
    return ForceCurve(segments=(seg,))


def test_ops_are_registered() -> None:
    ops = available_operations()
    assert {"calibrate", "find_contact_point", "fit_elasticity"} <= set(ops)


def test_pipeline_recovers_modulus_end_to_end() -> None:
    """Un Recipe [contacto → ajuste] recupera el módulo de una curva sintética."""
    curve = _synthetic_hertz_curve(young=1.0e6, radius=10e-9, sep_contact=3e-7)
    recipe = Recipe(
        name="nanoindentacion",
        steps=(
            Step(op="find_contact_point", params={"method": "threshold"}),
            Step(
                op="fit_elasticity",
                params={"model": "sphere", "tip_radius": 10e-9},
                condition="contact_detected",
            ),
        ),
    )
    _, ctx = run(recipe, curve)
    assert ctx["contact_detected"] is True
    assert ctx["young_modulus"] == pytest.approx(1.0e6, rel=0.05)
    assert ctx["r_squared"] > 0.99


def test_fit_skipped_when_no_contact() -> None:
    """La condición evita el ajuste si no se detecta contacto."""
    curve = _synthetic_hertz_curve()
    recipe = Recipe(
        steps=(
            Step(op="fit_elasticity", params={"tip_radius": 10e-9}, condition="contact_detected"),
        )
    )
    _, ctx = run(recipe, curve)
    assert "young_modulus" not in ctx  # el paso no corrió (contact_detected ausente/falso)


@pytest.mark.skipif(not _REAL_SAMPLE.exists(), reason="sample JPK real no disponible (gitignored)")
def test_pipeline_on_real_jpk_curve() -> None:
    """El pipeline corre end-to-end sobre la curva JPK real y da un módulo finito."""
    curve = load_jpk_force(_REAL_SAMPLE)
    recipe = Recipe(
        steps=(
            Step(op="calibrate"),  # from_metadata (ya viene calibrada → pasa)
            Step(op="find_contact_point", params={"method": "rov"}),
            Step(
                op="fit_elasticity",
                params={"model": "sphere", "tip_radius": 10e-9},
                condition="contact_detected",
            ),
        ),
    )
    _, ctx = run(recipe, curve)
    assert ctx["calibrated"] is True
    assert ctx["contact_detected"] is True
    assert ctx["r_squared"] > 0.9  # buen ajuste sobre datos reales
    assert 1e3 < ctx["young_modulus"] < 1e8  # módulo en rango físico (kPa–MPa)
