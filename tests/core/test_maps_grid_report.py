"""Tests de mapas mecánicos, panel comparativo y reporte completo."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from spmkit.core.analysis import mechanics
from spmkit.core.models import SPMChannel, SPMData


def _spec_channel(n_curves: int = 9, young: float = 1e6) -> SPMChannel:
    """Canal de espectroscopía sintético con curvas Hertz (módulo conocido)."""
    n_pts = 200
    z = np.linspace(0.0, 1e-6, n_pts)
    e_star = young / (1 - 0.3**2)
    k = (4.0 / 3.0) * e_star * np.sqrt(10e-9)
    rows = []
    for _ in range(n_curves):
        delta = np.clip(z - 3e-7, 0, None)
        rows.append(k * delta**1.5)
    data = np.array(rows)
    return SPMChannel(
        name="Deflection",
        data=data,
        unit="N",
        x_range=0,
        y_range=0,
        metadata={"Dim0Min": "0", "Dim0Range": "1e-6", "Dim0Unit": "m"},
    )


def test_fit_all_builds_square_map() -> None:
    m = mechanics.fit_all(_spec_channel(9), tip_radius=10e-9)
    assert m.grid_shape == (3, 3)
    assert m.young_modulus.shape == (3, 3)
    assert m.n_failed == 0
    assert np.nanmean(m.young_modulus) / 1e6 == pytest.approx(1.0, rel=0.05)


def test_fit_all_non_square_falls_back() -> None:
    m = mechanics.fit_all(_spec_channel(7), tip_radius=10e-9)
    assert m.grid_shape == (1, 7)


def test_fit_all_explicit_grid() -> None:
    m = mechanics.fit_all(_spec_channel(12), tip_radius=10e-9, grid=(3, 4))
    assert m.grid_shape == (3, 4)


def test_render_grid_shared_scale(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    from spmkit.core.viz import FigureSpec, save_grid

    rng = np.random.default_rng(0)
    chans = [
        SPMChannel(
            name=f"s{i}", data=rng.normal(size=(16, 16)), unit="m", x_range=2e-6, y_range=2e-6
        )
        for i in range(3)
    ]
    out = save_grid(chans, FigureSpec(title="Comparación"), tmp_path / "grid.png")
    assert out.exists() and out.stat().st_size > 0


def test_full_report(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    pytest.importorskip("jinja2")
    from spmkit.core.report import full_report

    ch = SPMChannel(
        name="Z-Axis",
        data=np.random.default_rng(1).normal(size=(32, 32)),
        unit="m",
        x_range=5e-6,
        y_range=5e-6,
    )
    data = SPMData(
        channels=(ch,), metadata={"info": {"Points": "32", "Date": "x"}}, source_path="s.nid"
    )
    out = full_report(data, tmp_path / "full.html")
    html = out.read_text()
    assert "Rugosidad" in html and "Metadatos" in html
