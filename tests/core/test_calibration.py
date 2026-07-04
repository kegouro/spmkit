"""Tests de calibración del cantiléver (InVOLS, k térmico, conversiones)."""

from __future__ import annotations

import numpy as np
import pytest

from spmkit.core.analysis import calibration
from spmkit.core.models import Calibration


def test_deflection_sensitivity_recovers_invols() -> None:
    """En contacto duro, la pendiente altura-vs-voltaje recupera el InVOLS."""
    invols_true = 7.0e-8  # m/V (valor real observado en el sample JPK del spike)
    volts = np.linspace(0.0, 1.5, 500)
    height = invols_true * volts  # contacto rígido: altura ∝ voltaje
    invols = calibration.deflection_sensitivity(volts, height)
    assert invols == pytest.approx(invols_true, rel=1e-6)


def test_deflection_sensitivity_size_mismatch() -> None:
    with pytest.raises(ValueError, match="mismo tamaño"):
        calibration.deflection_sensitivity(np.zeros(10), np.zeros(9))


def test_conversion_chain() -> None:
    """señal (V) → deflexión (m) → fuerza (N) con InVOLS y k conocidos."""
    volts = np.array([0.0, 1.0, 2.0])
    invols, k = 7.0e-8, 0.0435
    defl = calibration.volts_to_deflection(volts, invols)
    assert defl[1] == pytest.approx(invols)
    force = calibration.deflection_to_force(defl, k)
    assert force[2] == pytest.approx(2.0 * invols * k)


def test_spring_constant_thermal_known_answer() -> None:
    variance = 1e-20  # m²
    expected = 0.817 * 1.380649e-23 * 293.15 / 1e-20
    assert calibration.spring_constant_thermal(variance) == pytest.approx(expected, rel=1e-9)


def test_spring_constant_thermal_invalid() -> None:
    with pytest.raises(ValueError):
        calibration.spring_constant_thermal(0.0)


def test_spring_constant_sader_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        calibration.spring_constant_sader(f0=1e5, q=10.0, width=30e-6, length=200e-6)


def test_build_calibration() -> None:
    cal = calibration.build_calibration(7.0e-8, 0.0435, method="thermal", source="spike")
    assert isinstance(cal, Calibration)
    assert cal.invols == pytest.approx(7.0e-8)
    assert cal.spring_constant == pytest.approx(0.0435)
    assert cal.method == "thermal"
    assert cal.provenance["source"] == "spike"
