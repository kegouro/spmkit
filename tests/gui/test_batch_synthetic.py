"""Batch panel and task lifecycle with generated inputs and temporary preferences."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QAbstractItemView, QFileDialog

from spmkit.gui.panels.batch_table import BatchTablePanel
from spmkit.gui.shell.status_bar import ProgressStatusBar
from spmkit.gui.viewmodels import BatchViewModel, ForceViewModel
from tests.core.test_forcebatch_synthetic import write_force_map


@pytest.fixture(autouse=True)
def isolate_preferences(tmp_path: Path):
    previous_format = QSettings.defaultFormat()
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    for scope in (QSettings.Scope.UserScope, QSettings.Scope.SystemScope):
        QSettings.setPath(QSettings.Format.IniFormat, scope, str(tmp_path / scope.name))
    yield
    QSettings.setDefaultFormat(previous_format)


def test_batch_panel_runs_parallel_and_exports(qtbot, tmp_path, monkeypatch) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    write_force_map(inputs / "a.nid", 256, range(1, 256, 10))
    write_force_map(inputs / "b.nid", 64)
    (inputs / "c.nid").write_bytes(b"truncated")

    vm = BatchViewModel(ForceViewModel())
    panel = BatchTablePanel(vm)
    qtbot.addWidget(panel)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(inputs))
    panel._parallel.setChecked(True)
    panel._open_btn.click()
    assert vm.computing
    assert not panel._open_btn.isEnabled()
    assert not panel._parallel.isEnabled()
    assert not panel._export_btn.isEnabled()
    qtbot.waitUntil(lambda: not vm.computing, timeout=20_000)

    assert panel._model.rowCount() == 3
    assert panel._model.item(0, 7).text() == "26"
    assert panel._model.item(0, 8).text() == "230"
    assert "294/320" in panel._status.text()
    assert panel._table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    assert panel._open_btn.isEnabled()
    assert panel._parallel.isEnabled()
    assert panel._export_btn.isEnabled()

    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *args: (str(tmp_path / "absent/summary.csv"), "")
    )
    panel._export_btn.click()
    assert "No se pudo exportar" in panel._status.text()
    assert panel._export_btn.isEnabled()

    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *args: (str(tmp_path / "summary"), "")
    )
    panel._export_btn.click()
    assert "CSV exportado" in panel._status.text()
    assert "n_curves_failed" in (tmp_path / "summary.csv").read_text(encoding="utf-8")

    panel.rebuild()
    assert panel._model.rowCount() == 3
    assert panel._export_btn.isEnabled()


def test_batch_panel_cancellation_error_and_empty_folder(qtbot, tmp_path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    write_force_map(tmp_path / "a.nid", 1024)
    vm = BatchViewModel(ForceViewModel())
    panel = BatchTablePanel(vm)
    qtbot.addWidget(panel)
    status = ProgressStatusBar()
    qtbot.addWidget(status)
    vm.taskStarted.connect(status.bind_task)
    vm.run_now(tmp_path)
    assert panel._export_btn.isEnabled()

    events = []

    def cancel_during_map(fraction: float, _: str) -> None:
        if 0 < fraction < 1 and not events:
            events.append(fraction)
            status.cancelRequested.emit()

    vm.taskStarted.connect(lambda task: task.signals.progress.connect(cancel_during_map))
    vm.run(tmp_path)
    assert panel._model.rowCount() == 0
    assert "Procesando" in panel._status.text()
    qtbot.waitUntil(lambda: not vm.computing, timeout=20_000)
    assert events
    assert panel._status.text() == "Lote cancelado"
    assert vm.result is None
    assert not panel._export_btn.isEnabled()
    assert panel._open_btn.isEnabled()

    vm.run(tmp_path / "missing")
    qtbot.waitUntil(lambda: not vm.computing)
    assert "El lote falló" in panel._status.text()
    assert vm.result is None

    vm.run(empty)
    qtbot.waitUntil(lambda: not vm.computing)
    assert "No hay archivos" in panel._status.text()
    assert panel._model.rowCount() == 0
    assert not panel._export_btn.isEnabled()
