from PyQt6.QtWidgets import QFileDialog, QWidget

from spmkit.gui.widgets.auto_windows import AutoWindowDialog
from tests.core.test_force_windows import write_map


def test_run_select_review_export_and_switch_modes(qtbot, tmp_path, monkeypatch):
    p = tmp_path / "synthetic.nid"
    write_map(p, 4, False)
    parent = QWidget()
    qtbot.addWidget(parent)
    d = AutoWindowDialog(parent)
    qtbot.addWidget(d)
    d.show()
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *a: ([str(p)], ""))
    d.run_btn.click()
    qtbot.waitUntil(lambda: d.task is None, timeout=10000)
    assert d.model.rowCount() == 4
    d.table.setCurrentIndex(d.model.index(1, 0))
    assert d.preview.isVisible()
    target = tmp_path / "windows.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(target), ""))
    d.save.click()
    assert "nid-steps-v1" in target.read_text()
    d.mode.setCurrentIndex(1)
    assert not d.save.isEnabled() and d.batch_result is None
    d.run_btn.click()
    assert "radio" in d.status.text()
    write_map(p, 4, True)
    d.radius.setValue(100)
    d.depth_input.setValue(12)
    d.run_btn.click()
    qtbot.waitUntil(lambda: d.task is None, timeout=10000)
    assert d.model.result.rows[0].window.modulus_pa > 0
