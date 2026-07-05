"""Test del panel de log (captura statusChanged de los ViewModels)."""

from __future__ import annotations

from spmkit.gui.panels.log_panel import LogPanel
from spmkit.gui.viewmodels import ForceViewModel, MapViewModel


def test_log_captures_status_messages(qtbot) -> None:  # type: ignore[no-untyped-def]
    fvm = ForceViewModel()
    mvm = MapViewModel(fvm)
    panel = LogPanel((fvm, mvm))
    qtbot.addWidget(panel)
    assert not panel.errored
    mvm.statusChanged.emit("hola log")
    assert "hola log" in panel._text.toPlainText()
    panel.clear()
    assert panel._text.toPlainText() == ""
