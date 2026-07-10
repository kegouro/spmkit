"""Tests de la perspectiva Evaporación (ViewModel + panel): serie de sensado de masa."""

from __future__ import annotations

import numpy as np

from spmkit.core.analysis import resonance
from spmkit.gui.panels.evaporation_canvas import EvaporationCanvasPanel
from spmkit.gui.viewmodels import EvaporationResult, EvaporationViewModel


def _synthetic_result() -> EvaporationResult:
    """Serie sintética: f sube con el tiempo (la masa se evapora)."""
    t = np.array([0.0, 3600.0, 7200.0, 10800.0])
    f = np.array([72_800.0, 76_000.0, 78_500.0, 79_000.0])
    series = resonance.track_evaporation(t, f, spring_constant=1.175)
    radius = np.asarray(resonance.droplet_radius(series.added_mass), dtype=np.float64)
    d2 = resonance.fit_d2_law(series.time, radius)
    return EvaporationResult(series=series, radius=radius, d2=d2)


def test_evaporation_panel_empty(qtbot) -> None:  # type: ignore[no-untyped-def]
    panel = EvaporationCanvasPanel(EvaporationViewModel())
    qtbot.addWidget(panel)
    assert not panel.errored
    assert "Sin serie" in panel._readout.text()
    assert not panel._export_btn.isEnabled()


def test_evaporation_panel_renders_result(qtbot) -> None:  # type: ignore[no-untyped-def]
    panel = EvaporationCanvasPanel(EvaporationViewModel())
    qtbot.addWidget(panel)
    panel._on_result(_synthetic_result())
    assert "Δm" in panel._readout.text()
    assert panel._export_btn.isEnabled()
    assert panel._plot_f.listDataItems()  # f(t) graficada
    assert panel._plot_m.listDataItems()  # Δm(t) graficada


def test_evaporation_vm_needs_two_spectra(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    vm = EvaporationViewModel()
    status: list[str] = []
    vm.statusChanged.connect(status.append)
    (tmp_path / "only.nid").write_bytes(b"x")  # un solo .nid: insuficiente
    vm.load_folder(tmp_path)
    assert vm.result is None
    assert status and "≥2" in status[-1]


def test_evaporation_vm_export_csv(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    vm = EvaporationViewModel()
    vm._emit(_synthetic_result())  # inyecta un resultado para exportar
    out = tmp_path / "ev.csv"
    assert vm.export_csv(out) is True
    text = out.read_text(encoding="utf-8")
    assert "time_s" in text and "added_mass_kg" in text
    assert len(text.strip().splitlines()) == 5  # cabecera + 4 puntos
