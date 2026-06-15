"""Tests de nanomecánica (curvas fuerza-distancia)."""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis import mechanics
from spmkit.core.analysis.mechanics import ForceCurve
from spmkit.core.models import SPMChannel


def _hertz_curve(young: float, radius: float, z0: float, poisson: float = 0.3) -> ForceCurve:
    """Genera una curva Hertz esférica sintética con módulo conocido."""
    z = np.linspace(0.0, 1e-6, 500)
    e_star = young / (1 - poisson**2)
    k = (4.0 / 3.0) * e_star * np.sqrt(radius)
    delta = np.clip(z - z0, 0, None)
    force = k * delta**1.5
    return ForceCurve(z=z, force=force, force_unit="N")


def test_extract_curves_from_channel() -> None:
    data = np.random.default_rng(0).normal(size=(10, 256))
    ch = SPMChannel(
        name="Deflection",
        data=data,
        unit="N",
        x_range=0,
        y_range=0,
        metadata={"Dim0Min": "-1e-7", "Dim0Range": "5e-7", "Dim0Unit": "m"},
    )
    curves = mechanics.extract_curves(ch)
    assert len(curves) == 10
    assert len(curves[0]) == 256
    assert curves[0].z[0] == pytest.approx(-1e-7)
    assert curves[0].z[-1] == pytest.approx(4e-7)


def test_hertz_recovers_modulus() -> None:
    young_true = 1.0e6  # 1 MPa
    radius = 10e-9
    curve = _hertz_curve(young_true, radius, z0=3e-7)
    result = mechanics.fit_hertz(curve, tip_radius=radius, model="sphere")
    # Recupera el módulo dentro de ~5 %
    assert result.young_modulus == pytest.approx(young_true, rel=0.05)
    assert result.contact_point == pytest.approx(3e-7, abs=5e-9)
    assert result.model == "sphere"


def test_baseline_correct_removes_offset() -> None:
    z = np.linspace(0, 1e-6, 100)
    curve = ForceCurve(z=z, force=np.full_like(z, 5.0))
    corrected = mechanics.baseline_correct(curve)
    assert np.allclose(corrected.force, 0.0, atol=1e-9)


def test_adhesion() -> None:
    z = np.linspace(0, 1e-6, 100)
    force = np.zeros_like(z)
    force[50] = -3e-9  # pull-off
    curve = ForceCurve(z=z, force=force)
    assert mechanics.adhesion(curve) == pytest.approx(3e-9)


def test_invalid_model() -> None:
    curve = _hertz_curve(1e6, 10e-9, 3e-7)
    with pytest.raises(ValueError, match="model debe ser"):
        mechanics.fit_hertz(curve, tip_radius=10e-9, model="banana")


def test_thermal_spring_constant() -> None:
    """Verifica el cálculo de k por equipartición para valores conocidos."""
    variance = 1e-20  # m²
    temperature = 293.15  # K
    expected = 1.380649e-23 * 293.15 / 1e-20
    from spmkit.core.analysis.mechanics import thermal_spring_constant

    result = thermal_spring_constant(variance, temperature)
    assert result == pytest.approx(expected, rel=1e-9)


def test_thermal_spring_constant_invalid() -> None:
    """Varianza <= 0 debe lanzar ValueError."""
    from spmkit.core.analysis.mechanics import thermal_spring_constant

    with pytest.raises(ValueError):
        thermal_spring_constant(0.0)
    with pytest.raises(ValueError):
        thermal_spring_constant(-1e-20)


def test_spring_constant_changes_fit() -> None:
    """La corrección por cantiléver flexible produce un módulo distinto (mayor) que sin ella."""
    young_true = 1.0e6  # 1 MPa
    radius = 10e-9
    curve = _hertz_curve(young_true, radius, z0=3e-7)

    result_no_k = mechanics.fit_hertz(curve, tip_radius=radius, spring_constant=None)
    result_with_k = mechanics.fit_hertz(curve, tip_radius=radius, spring_constant=1.0)

    # Con spring_constant finito la indentación corregida es menor → E estimado mayor
    assert result_with_k.young_modulus != pytest.approx(result_no_k.young_modulus, rel=1e-3)
    assert result_with_k.young_modulus > result_no_k.young_modulus
