"""Tests del diálogo de anotación personalizable del editor de figuras."""

from __future__ import annotations

from spmkit.core.viz.figure import Annotation
from spmkit.gui.figure_tab import AnnotationDialog


def test_dialog_reflects_and_dumps_all_properties(qtbot) -> None:  # type: ignore[no-untyped-def]
    ann = Annotation(
        text="hola",
        color="#123456",
        fontsize=20,
        weight="bold",
        bg_color="#abcdef",
        bg_alpha=0.4,
    )
    dlg = AnnotationDialog(ann)
    qtbot.addWidget(dlg)
    # refleja el estado inicial
    assert dlg.text_edit.toPlainText() == "hola"
    assert dlg.bold.isChecked()
    assert dlg.bg_chk.isChecked()
    assert dlg.bg_alpha.value() == 40
    # editar y volcar
    dlg.italic.setChecked(True)
    dlg.multi.setCurrentIndex(dlg.multi.findData("right"))
    out = dlg.annotation()
    assert out.style == "italic"
    assert out.multialignment == "right"
    assert out.weight == "bold"
    assert out.bg_color == "#abcdef"
    assert abs(out.bg_alpha - 0.4) < 1e-9


def test_dialog_background_toggle(qtbot) -> None:  # type: ignore[no-untyped-def]
    dlg = AnnotationDialog(Annotation(text="x"))
    qtbot.addWidget(dlg)
    assert not dlg.bg_chk.isChecked()
    assert not dlg.bg_color.isEnabled()  # controles de fondo deshabilitados
    out = dlg.annotation()
    assert out.bg_color is None  # sin fondo si el checkbox está apagado
