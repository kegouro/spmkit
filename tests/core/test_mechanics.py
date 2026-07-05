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


def _dmt_curve(
    young: float, radius: float, z0: float, adhesion_force: float, poisson: float = 0.3
) -> ForceCurve:
    """Curva DMT sintética: Hertz esférico menos un offset de adhesión constante."""
    z = np.linspace(0.0, 1e-6, 500)
    e_star = young / (1 - poisson**2)
    k = (4.0 / 3.0) * e_star * np.sqrt(radius)
    delta = np.clip(z - z0, 0, None)
    contact = z >= z0
    force = np.where(contact, k * delta**1.5 - adhesion_force, 0.0)
    return ForceCurve(z=z, force=force, force_unit="N")


def _cone_curve(young: float, half_angle: float, z0: float, poisson: float = 0.3) -> ForceCurve:
    """Curva Sneddon cónica sintética con módulo conocido."""
    z = np.linspace(0.0, 1e-6, 500)
    e_star = young / (1 - poisson**2)
    k = (2.0 / np.pi) * e_star * np.tan(half_angle)
    delta = np.clip(z - z0, 0, None)
    force = k * delta**2
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


def test_dmt_recovers_modulus_and_adhesion() -> None:
    """El modelo DMT recupera módulo y adhesión de una curva con pull-off conocido."""
    young_true = 2.0e6  # 2 MPa
    radius = 10e-9
    adh_true = 1.5e-9  # 1.5 nN
    curve = _dmt_curve(young_true, radius, z0=3e-7, adhesion_force=adh_true)
    result = mechanics.fit_hertz(curve, tip_radius=radius, model="dmt", contact_point=3e-7)
    assert result.young_modulus == pytest.approx(young_true, rel=0.05)
    assert result.adhesion == pytest.approx(adh_true, rel=0.05)
    assert result.model == "dmt"


def test_cone_recovers_modulus() -> None:
    """El modelo Sneddon cónico recupera el módulo con el semiángulo correcto."""
    young_true = 5.0e6  # 5 MPa
    half_angle = np.deg2rad(18.0)
    curve = _cone_curve(young_true, half_angle, z0=3e-7)
    result = mechanics.fit_hertz(
        curve, tip_radius=10e-9, model="cone", half_angle=half_angle, contact_point=3e-7
    )
    assert result.young_modulus == pytest.approx(young_true, rel=0.05)
    assert result.model == "cone"


def test_fit_reports_uncertainty_and_r2() -> None:
    """Una curva limpia da R²≈1 y σ_E finito no negativo; el ajuste usa >3 puntos."""
    curve = _hertz_curve(1.0e6, 10e-9, z0=3e-7)
    result = mechanics.fit_hertz(curve, tip_radius=10e-9, contact_point=3e-7)
    assert result.r_squared > 0.999
    assert result.young_modulus_std >= 0.0
    assert result.n_fit > 3


def test_rov_contact_point_robust_to_noise() -> None:
    """El método RoV localiza el contacto bajo ruido cerca del z0 verdadero."""
    z0 = 3e-7
    curve = _hertz_curve(1.0e6, 10e-9, z0)
    rng = np.random.default_rng(1)
    noisy = ForceCurve(z=curve.z, force=curve.force + rng.normal(0.0, 2e-11, curve.force.size))
    corrected = mechanics.baseline_correct(noisy)
    z_rov = mechanics.find_contact_point(corrected, method="rov")
    assert z_rov == pytest.approx(z0, abs=5e-8)
