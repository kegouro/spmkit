"""Self-checks de los modelos experimentales (JKR, relajación SLS).

No hay referencia independiente (por eso están *flagged*); estos tests sólo verifican
**límites analíticos** y la auto-consistencia (recupera los parámetros con que se generó).
"""

from __future__ import annotations

import numpy as np

from spmkit.core.analysis.experimental import (
    EXPERIMENTAL,
    fit_jkr,
    fit_relaxation,
    jkr_forward,
)


def test_module_is_flagged_experimental() -> None:
    assert EXPERIMENTAL is True
    r = fit_relaxation(np.linspace(0, 1, 10), np.ones(10) * 3.0)
    assert r.experimental is True


def test_jkr_reduces_to_hertz_when_no_adhesion() -> None:
    # Con w=0 el forward JKR debe ser Hertz esférico exacto.
    e_star, radius = 1.0e6, 10e-9
    delta = np.linspace(1e-9, 300e-9, 60)
    hertz = (4.0 / 3.0) * e_star * np.sqrt(radius) * delta**1.5
    jkr = jkr_forward(delta, e_star, 0.0, radius)
    assert np.allclose(jkr, hertz, rtol=1e-3, atol=1e-12)


def test_fit_jkr_recovers_modulus_in_hertz_limit() -> None:
    e_star, radius = 1.0e6, 10e-9
    delta = np.linspace(1e-9, 300e-9, 60)
    force = (4.0 / 3.0) * e_star * np.sqrt(radius) * delta**1.5  # curva Hertz (w=0)
    res = fit_jkr(delta, force, tip_radius=radius, poisson=0.0)
    assert res.r_squared > 0.99
    assert abs(res.reduced_modulus - e_star) / e_star < 0.15  # recupera E* ~±15%
    assert res.work_of_adhesion < e_star * 1e-9  # adhesión ~0


def test_fit_jkr_self_consistent_with_adhesion() -> None:
    e_star, radius, w = 2.0e6, 20e-9, 0.03
    delta = np.linspace(1e-9, 200e-9, 80)
    force = jkr_forward(delta, e_star, w, radius)
    res = fit_jkr(delta, force, tip_radius=radius, poisson=0.0)
    assert res.r_squared > 0.98  # el modelo ajusta la curva que generó
    assert abs(res.reduced_modulus - e_star) / e_star < 0.2
    assert res.work_of_adhesion > 0.0  # detecta adhesión no nula


def test_fit_relaxation_recovers_tau() -> None:
    tau, f0, f_inf = 0.2, 10.0, 4.0
    t = np.linspace(0, 1.0, 120)
    force = f_inf + (f0 - f_inf) * np.exp(-t / tau)
    res = fit_relaxation(t, force)
    assert abs(res.tau - tau) / tau < 0.15
    assert abs(res.relaxation_ratio - (f0 - f_inf) / f0) < 0.05
    assert res.r_squared > 0.99


def test_fit_relaxation_elastic_limit_no_relaxation() -> None:
    t = np.linspace(0, 1.0, 60)
    force = np.full_like(t, 5.0)  # sin relajación → ratio ≈ 0
    res = fit_relaxation(t, force)
    assert abs(res.relaxation_ratio) < 1e-3
