"""Tests de KPFM."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from spmkit.core.analysis import kpfm
from spmkit.core.models import SPMChannel


def test_cpd_mean(cpd_channel: SPMChannel) -> None:
    r = kpfm.statistics(cpd_channel)
    assert abs(r.mean - 0.5) < 0.01
    assert r.unit == "V"
    assert r.work_function is None


def test_work_function(cpd_channel: SPMChannel) -> None:
    # phi_sample = phi_tip - V_CPD_medio = 5.0 - 0.5 = 4.5
    r = kpfm.statistics(cpd_channel, tip_work_function=5.0)
    assert r.work_function is not None
    assert abs(r.work_function - 4.5) < 0.01


def test_cpd_to_dict(cpd_channel: SPMChannel) -> None:
    d = kpfm.statistics(cpd_channel).to_dict()
    assert {"mean", "std", "contrast", "work_function"} <= set(d)


def test_cpd_accepts_lowercase_volts_and_ignores_nan() -> None:
    ch = SPMChannel(
        name="CPD",
        data=np.array([[0.2, np.nan], [0.4, 0.6]]),
        unit="v",
        x_range=1e-6,
        y_range=1e-6,
    )

    result = kpfm.statistics(ch)

    assert result.mean == pytest.approx(0.4)
    assert result.unit == "v"
    assert result.work_function is None


def test_cpd_rejects_non_voltage_channel() -> None:
    ch = SPMChannel(name="Height", data=np.zeros((2, 2)), unit="m", x_range=1e-6, y_range=1e-6)

    with pytest.raises(ValueError, match="voltios"):
        kpfm.statistics(ch)


def test_cpd_rejects_all_nan_without_numpy_warnings() -> None:
    ch = SPMChannel(name="CPD", data=np.full((2, 2), np.nan), unit="V", x_range=1e-6, y_range=1e-6)

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        with pytest.raises(ValueError, match="sin datos finitos"):
            kpfm.statistics(ch)


@pytest.mark.parametrize("tip_work_function", [0.0, -1.0, np.inf, -np.inf, np.nan])
def test_tip_work_function_must_be_finite_and_positive(tip_work_function: float) -> None:
    ch = SPMChannel(name="CPD", data=np.zeros((2, 2)), unit="V", x_range=1e-6, y_range=1e-6)

    with pytest.raises(ValueError, match="finita y estrictamente positiva"):
        kpfm.statistics(ch, tip_work_function=tip_work_function)
