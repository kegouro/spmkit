"""Tests de la línea de ajuste para display y el eje de display compartido."""

from __future__ import annotations

import numpy as np

from spmkit.core.analysis.forcecurve import display_axis, fit_force_curve


def _hertz(young: float = 1.0e6, radius: float = 10e-9, sep_contact: float = 3e-7):
    separation = np.linspace(6e-7, 0.0, 400)
    e_star = young / (1 - 0.3**2)
    k = (4.0 / 3.0) * e_star * np.sqrt(radius)
    force = k * np.clip(sep_contact - separation, 0.0, None) ** 1.5
    return separation, force


def test_fit_returns_overlay_line_close_to_data() -> None:
    x, f = _hertz()
    fit = fit_force_curve(x, f, model="sphere", tip_radius=10e-9)
    # La línea de ajuste está en coordenadas de display (mismo eje y fuerza cruda).
    assert fit.x_fit.size == fit.f_fit.size > 0
    assert fit.x_fit.min() >= x.min() and fit.x_fit.max() <= x.max()
    # En la rama de carga, la línea de ajuste debe seguir a los datos (R² alto).
    assert fit.r_squared > 0.98


def test_fit_range_window_and_fallback() -> None:
    x, f = _hertz()
    full = fit_force_curve(x, f)
    # Ventana razonable (incluye contacto y carga): recupera un módulo positivo.
    windowed = fit_force_curve(x, f, fit_range=(-1e-9, 3e-7))
    assert windowed.young_modulus > 0
    # Ventana vacía (fuera de rango, mm) → se ignora y equivale al ajuste completo.
    empty = fit_force_curve(x, f, fit_range=(1e-3, 2e-3))
    assert abs(empty.young_modulus - full.young_modulus) < 1e-6 * full.young_modulus


def test_to_dict_excludes_arrays() -> None:
    x, f = _hertz()
    d = fit_force_curve(x, f).to_dict()
    assert "x_fit" not in d and "f_fit" not in d
    assert d["young_modulus"] > 0
    assert isinstance(d["young_modulus"], float)


def test_display_axis_prefers_separation_but_falls_back() -> None:
    height = np.linspace(0.0, 1e-6, 100)
    good_sep = np.linspace(-1e-7, 5e-7, 100)  # no degenerada
    assert np.allclose(display_axis(good_sep, height), good_sep)
    # Separación saturada (muchos repetidos) → cae a la altura del piezo.
    clipped = np.concatenate([np.full(90, 3e-7), np.linspace(3e-7, 4e-7, 10)])
    assert np.allclose(display_axis(clipped, height), height)
    # Sin separación → altura.
    assert np.allclose(display_axis(None, height), height)
