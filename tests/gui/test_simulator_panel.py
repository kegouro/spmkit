"""Tests del simulador de cantiléver (ViewModel + panel) en Fathom."""

from __future__ import annotations

from spmkit.gui.panels.simulator_panel import SimulatorPanel
from spmkit.gui.viewmodels import SimulatorViewModel


def test_sim_vm_computes_and_mass_lowers_resonance() -> None:
    vm = SimulatorViewModel()
    vm.compute()
    result = vm.result
    assert result is not None
    assert result.f0_loaded < result.f0_bare  # la masa añadida baja la resonancia


def test_sim_vm_set_param_emits(qtbot) -> None:  # type: ignore[no-untyped-def]
    vm = SimulatorViewModel()
    seen: list[object] = []
    vm.resultChanged.connect(seen.append)
    vm.set_param("f0_bare", 120e3)
    assert vm.params["f0_bare"] == 120e3
    assert seen and seen[-1] is not None
    vm.set_param("f0_bare", 120e3)  # mismo valor → no recomputa
    assert len(seen) == 1


def test_sim_vm_n_and_fmax_controls() -> None:
    vm = SimulatorViewModel()
    vm.set_param("n", 512)
    assert vm.result is not None and vm.result.frequency.size == 512  # n controla el muestreo
    vm.set_param("f_max", 40e3)
    assert vm.result is not None and float(vm.result.frequency.max()) <= 40e3 + 1  # f_max acota


def test_sim_panel_has_fmax_and_points_controls(qtbot) -> None:  # type: ignore[no-untyped-def]
    vm = SimulatorViewModel()
    panel = SimulatorPanel(vm)
    qtbot.addWidget(panel)
    panel.npts.setValue(1024)
    assert vm.params["n"] == 1024  # el control edita el VM
    panel.fmax.setValue(50.0)  # kHz
    assert abs(vm.params["f_max"] - 50e3) < 1.0  # kHz → Hz


def test_sim_panel_draws(qtbot) -> None:  # type: ignore[no-untyped-def]
    vm = SimulatorViewModel()
    panel = SimulatorPanel(vm)
    qtbot.addWidget(panel)
    assert not panel.errored
    panel.refresh()  # dispara compute + draw
    assert panel._figure.axes  # el espectro se dibujó
    assert "kHz" in panel.readout.text()


def test_simulator_renders_on_perspective_switch(qtbot) -> None:  # type: ignore[no-untyped-def]
    """La shell debe refrescar el panel central al activar su perspectiva (no en blanco)."""
    from spmkit.gui.app_workspace import build_workspace

    ws = build_workspace(persist=False)
    qtbot.addWidget(ws)
    ws.set_perspective("simulator")
    panel = ws.panel("simulator")
    assert panel is not None and not panel.errored
    assert "kHz" in panel.readout.text()  # refresh_safe() de la shell disparó compute+draw
