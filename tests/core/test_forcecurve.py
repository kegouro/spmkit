"""Tests de la nanomecánica nativa de curvas de fuerza (Fase 3)."""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis import forcecurve as fc


def _hertz(
    young: float = 1.0e6,
    radius: float = 10e-9,
    sep_contact: float = 3e-7,
    n: int = 500,
    far: float = 6e-7,
    poisson: float = 0.3,
) -> tuple[np.ndarray, np.ndarray]:
    """Curva Hertz esférica en convención de separación (separación decrece al contacto)."""
    sep = np.linspace(far, 0.0, n)
    e_star = young / (1 - poisson**2)
    k = (4.0 / 3.0) * e_star * np.sqrt(radius)
    delta = np.clip(sep_contact - sep, 0.0, None)
    force = k * delta**1.5
    return sep, force


def test_hertz_recovers_modulus() -> None:
    sep, force = _hertz(young=1.0e6, radius=10e-9)
    fit = fc.fit_force_curve(sep, force, model="sphere", tip_radius=10e-9)
    assert fit.young_modulus == pytest.approx(1.0e6, rel=0.05)
    assert fit.r_squared > 0.999


def test_orientation_and_sign_robust() -> None:
    """El ajuste es invariante al orden del array y al signo del eje."""
    sep, force = _hertz(young=2.0e6, radius=10e-9)
    base = fc.fit_force_curve(sep, force, tip_radius=10e-9).young_modulus
    reversed_ = fc.fit_force_curve(sep[::-1], force[::-1], tip_radius=10e-9).young_modulus
    negated = fc.fit_force_curve(-sep, force, tip_radius=10e-9).young_modulus
    assert reversed_ == pytest.approx(base, rel=1e-6)
    assert negated == pytest.approx(base, rel=1e-6)


def test_dmt_recovers_modulus_and_adhesion() -> None:
    sep = np.linspace(6e-7, 0.0, 500)
    young, radius, adh = 2.0e6, 10e-9, 1.5e-9
    e_star = young / (1 - 0.3**2)
    k = (4.0 / 3.0) * e_star * np.sqrt(radius)
    delta = np.clip(3e-7 - sep, 0.0, None)
    force = np.where(delta > 0, k * delta**1.5 - adh, 0.0)
    fit = fc.fit_force_curve(sep, force, model="dmt", tip_radius=radius)
    assert fit.young_modulus == pytest.approx(young, rel=0.05)
    assert fit.adhesion == pytest.approx(adh, rel=0.05)


def test_cone_recovers_modulus() -> None:
    sep = np.linspace(6e-7, 0.0, 500)
    young, half = 5.0e6, np.deg2rad(18.0)
    e_star = young / (1 - 0.3**2)
    k = (2.0 / np.pi) * e_star * np.tan(half)
    delta = np.clip(3e-7 - sep, 0.0, None)
    force = k * delta**2
    fit = fc.fit_force_curve(sep, force, model="cone", tip_radius=10e-9, half_angle=half)
    assert fit.young_modulus == pytest.approx(young, rel=0.05)


def test_invalid_model_raises() -> None:
    sep, force = _hertz()
    with pytest.raises(ValueError, match="model debe ser"):
        fc.fit_force_curve(sep, force, model="banana", tip_radius=10e-9)


def test_find_contact_recovers_point() -> None:
    sep, force = _hertz(sep_contact=3e-7)
    x0 = fc.find_contact(sep, force)
    assert x0 == pytest.approx(3e-7, abs=2e-8)


def test_montecarlo_uncertainty() -> None:
    """La incertidumbre MC propaga los errores relativos de InVOLS y k (E ∝ InVOLS·k)."""
    sep, force = _hertz(young=1.0e6, radius=10e-9)
    mean, std = fc.fit_force_curve_mc(
        sep, force, invols_rel_err=0.05, k_rel_err=0.05, n_samples=300, seed=0, tip_radius=10e-9
    )
    assert mean == pytest.approx(1.0e6, rel=0.1)
    expected_rel = np.sqrt(0.05**2 + 0.05**2)
    assert std / mean == pytest.approx(expected_rel, rel=0.3)


def test_dissipation_zero_for_identical_branches() -> None:
    sep, force = _hertz()
    assert fc.dissipation_energy(sep, force, sep, force) == pytest.approx(0.0, abs=1e-30)


def test_dissipation_positive_with_hysteresis() -> None:
    sep, f_ext = _hertz(young=1.0e6)
    _, f_ret = _hertz(young=2.0e6)  # retract con más fuerza → área de histéresis
    assert fc.dissipation_energy(sep, f_ext, sep, f_ret) > 0.0


def test_fit_repr_html() -> None:
    sep, force = _hertz()
    html = fc.fit_force_curve(sep, force, tip_radius=10e-9)._repr_html_()
    assert "<table>" in html and "Módulo de Young" in html and "R²" in html
