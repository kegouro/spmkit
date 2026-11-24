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


def test_selected_curves_png_button_and_retry(qtbot, tmp_path, monkeypatch):
    from spmkit.core.adhesion_review import review_maps

    p = tmp_path / "mapa.nid"
    write_map(p, 3, False)
    maps, _ = review_maps([p])
    maps[0].curves[1].included = False
    parent = QWidget()
    qtbot.addWidget(parent)
    d = AutoWindowDialog(parent, reviewed=maps)
    d.show()
    d.run_btn.click()
    qtbot.waitUntil(lambda: d.task is None)
    assert d.figures.isEnabled()
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: str(out))
    d.figures.click()
    assert not d.run_btn.isEnabled() and not d.figures.isEnabled()
    qtbot.waitUntil(lambda: d.task is None, timeout=15000)
    assert sorted(p.name for p in out.rglob("*.png")) == ["curva_00000.png", "curva_00002.png"]
    assert "Figuras guardadas" in d.status.text() and d.figures.isEnabled()
    p.write_bytes(b"changed")
    d.figures.click()
    qtbot.waitUntil(lambda: d.task is None)
    assert "cambió" in d.status.text() and d.save.isEnabled()
