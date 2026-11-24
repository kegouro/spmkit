import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget

from spmkit.gui.widgets.adhesion_review import AdhesionDialog
from tests.core.test_adhesion_review import read_csv, write_adhesion_map


def test_review_two_maps_confirm_exclusion_and_restore(qtbot, tmp_path, monkeypatch):
    p, q = tmp_path / "a.nid", tmp_path / "b.nid"
    write_adhesion_map(p)
    write_adhesion_map(q, separation=False)
    parent = QWidget()
    qtbot.addWidget(parent)
    d = AdhesionDialog(parent)
    d.show()
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *a: ([str(p), str(q)], ""))
    d.open_btn.click()
    qtbot.waitUntil(lambda: d.task is None)
    assert d.model.rowCount() == 100 and d.maps[0].curves[99].included
    assert len(d.approach.xData) == len(d.retract.xData) == 48
    np.testing.assert_allclose(d.retract.xData, 2 * np.arange(48))
    assert d.chart.getAxis("bottom").labelText == "Separación"

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.No)
    d.next_warning.click()
    assert d.table.currentIndex().row() == 99 and d.maps[0].curves[99].included
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Yes)
    d.next_warning.click()
    assert np.isnan(d.image.image[9, 9]) and "99/100" in d.summary.text()
    d.files.setCurrentIndex(1)
    qtbot.waitUntil(lambda: d.task is None)
    assert (
        "100/100" in d.summary.text() and d.chart.getAxis("bottom").labelText == "Altura del sensor"
    )
    d.files.setCurrentIndex(0)
    qtbot.waitUntil(lambda: d.task is None)
    assert "99/100" in d.summary.text()
    target = tmp_path / "out.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(target), ""))
    d.export_summary.click()
    assert [v["n_selected"] for v in read_csv(target)] == ["99", "100"]
    d.model.setData(d.model.index(99, 0), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
    assert np.isfinite(d.image.image[9, 9]) and "100/100" in d.summary.text()
    d.samples.click()
    qtbot.waitUntil(lambda: d.task is None)
    assert len(read_csv(target)) == 200 * 2 * 48


def test_active_mixed_nid_and_batch_use_same_review(qtbot, tmp_path, monkeypatch):
    from spmkit.gui import app_workspace

    p = tmp_path / "mixed.nid"
    write_adhesion_map(p)
    monkeypatch.setattr(app_workspace, "_remember_dir", lambda _: None)
    monkeypatch.setattr(app_workspace, "_choose_kind", lambda ws, info: "force")
    ws = app_workspace.build_workspace(open_path=str(p), persist=False)
    qtbot.addWidget(ws)
    ws.show()
    panel = ws.panel("force_canvas")
    assert not panel._adhesion_btn.isHidden()
    monkeypatch.setattr(AdhesionDialog, "exec", lambda self: 0)
    panel._adhesion_btn.click()
    batch = ws.panel("batch_table")
    dlg = batch._adhesion_dialog
    qtbot.waitUntil(lambda: dlg.task is None)
    assert dlg.model.rowCount() == 100 and dlg.files.currentText() == "mixed.nid"
    dlg.model.setData(
        dlg.model.index(7, 0), Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole
    )
    batch._adhesion_btn.click()
    assert batch._adhesion_dialog is dlg and not dlg.maps[0].curves[7].included


def test_export_reviewed_adhesion_png(qtbot, tmp_path, monkeypatch):
    p = tmp_path / "mapa_adhesion.nid"
    write_adhesion_map(p, 3)
    parent = QWidget()
    qtbot.addWidget(parent)
    dlg = AdhesionDialog(parent)
    dlg.show()
    dlg.start([p])
    qtbot.waitUntil(lambda: dlg.task is None)
    dlg.model.setData(
        dlg.model.index(1, 0), Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole
    )
    out = tmp_path / "figuras"
    out.mkdir()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: str(out))
    dlg.figures.menu().actions()[0].trigger()
    assert not dlg.table.isEnabled() and not dlg.figures.isEnabled()
    qtbot.waitUntil(lambda: dlg.task is None, timeout=15000)
    assert sorted(f.name for f in out.rglob("*.png")) == ["curva_00000.png", "curva_00002.png"]
    index = read_csv(next(out.rglob("indice.csv")))
    assert all(r["rama"] == "retract" and r["ventanas"] == "1" for r in index)
    assert "Figuras guardadas" in dlg.message.text()
