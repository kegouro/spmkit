"""Tests de KPFM."""

from __future__ import annotations

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
