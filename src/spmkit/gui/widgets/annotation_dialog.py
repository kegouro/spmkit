"""Editor de anotaciones de texto para figuras — widget Qt reutilizable.

Fuente única del diálogo de texto/leyenda (color, tipografía, alineación, fondo con
opacidad) que usan tanto el editor de figuras de Fathom como la app clásica (legacy).
Sólo UI: edita un :class:`~spmkit.core.viz.figure.Annotation` del core puro.
"""

from __future__ import annotations

from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from spmkit.core.viz.figure import Annotation


class ColorButton(QtWidgets.QPushButton):
    """Botón que muestra un color y lo edita con ``QColorDialog``."""

    def __init__(self, color: str = "#000000") -> None:
        super().__init__()
        self._color = color
        self.setFixedWidth(70)
        self.clicked.connect(self._pick)
        self._refresh()

    def _refresh(self) -> None:
        self.setText(self._color)
        # texto legible sobre el color de fondo
        c = QColor(self._color)
        fg = "#000" if c.lightness() > 140 else "#fff"
        self.setStyleSheet(
            f"background:{self._color}; color:{fg}; border:1px solid #888; border-radius:4px;"
        )

    def _pick(self) -> None:
        col = QtWidgets.QColorDialog.getColor(QColor(self._color), self, "Elegir color")
        if col.isValid():
            self._color = col.name()
            self._refresh()

    def color(self) -> str:
        return self._color

    def set_color(self, value: str) -> None:
        self._color = value
        self._refresh()


class AnnotationDialog(QtWidgets.QDialog):
    """Editor completo de una anotación de texto (color, tipografía, fondo, etc.)."""

    def __init__(self, ann: Annotation, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Texto / leyenda")
        self._ann = ann
        form = QtWidgets.QFormLayout(self)

        self.text_edit = QtWidgets.QPlainTextEdit(ann.text)
        self.text_edit.setFixedHeight(72)
        form.addRow("Texto:", self.text_edit)

        self.color_btn = ColorButton(ann.color)
        form.addRow("Color:", self.color_btn)

        self.fontsize_spin = QtWidgets.QDoubleSpinBox()
        self.fontsize_spin.setRange(4.0, 120.0)
        self.fontsize_spin.setValue(ann.fontsize)
        form.addRow("Tamaño:", self.fontsize_spin)

        style_row = QtWidgets.QHBoxLayout()
        self.bold = QtWidgets.QCheckBox("Negrita")
        self.bold.setChecked(ann.weight == "bold")
        self.italic = QtWidgets.QCheckBox("Cursiva")
        self.italic.setChecked(ann.style == "italic")
        style_row.addWidget(self.bold)
        style_row.addWidget(self.italic)
        style_row.addStretch(1)
        form.addRow("Estilo:", self._wrap(style_row))

        self.family = QtWidgets.QComboBox()
        self.family.addItems(["sans-serif", "serif", "monospace", "DejaVu Sans", "DejaVu Serif"])
        self.family.setCurrentText(ann.family)
        form.addRow("Fuente:", self.family)

        self.ha = self._combo(
            [("Izquierda", "left"), ("Centro", "center"), ("Derecha", "right")], ann.ha
        )
        form.addRow("Alineación H:", self.ha)
        self.va = self._combo(
            [("Arriba", "top"), ("Centro", "center"), ("Abajo", "bottom"), ("Base", "baseline")],
            ann.va,
        )
        form.addRow("Alineación V:", self.va)
        self.multi = self._combo(
            [("Izquierda", "left"), ("Centro", "center"), ("Derecha", "right")],
            ann.multialignment,
        )
        form.addRow("Justificado:", self.multi)

        self.linespacing = QtWidgets.QDoubleSpinBox()
        self.linespacing.setRange(0.6, 4.0)
        self.linespacing.setSingleStep(0.1)
        self.linespacing.setValue(ann.linespacing)
        form.addRow("Interlineado:", self.linespacing)

        self.rotation = QtWidgets.QSpinBox()
        self.rotation.setRange(-180, 180)
        self.rotation.setValue(int(ann.rotation))
        form.addRow("Rotación (°):", self.rotation)

        self.bg_chk = QtWidgets.QCheckBox("Fondo")
        self.bg_chk.setChecked(ann.bg_color is not None)
        self.bg_chk.toggled.connect(self._toggle_bg)
        form.addRow(self.bg_chk)

        self.bg_color = ColorButton(ann.bg_color or "#000000")
        form.addRow("Color fondo:", self.bg_color)

        self.bg_alpha = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.bg_alpha.setRange(0, 100)
        self.bg_alpha.setValue(int(ann.bg_alpha * 100))
        self.bg_alpha_lbl = QtWidgets.QLabel(f"{int(ann.bg_alpha * 100)}%")
        self.bg_alpha.valueChanged.connect(lambda v: self.bg_alpha_lbl.setText(f"{v}%"))
        alpha_row = QtWidgets.QHBoxLayout()
        alpha_row.addWidget(self.bg_alpha)
        alpha_row.addWidget(self.bg_alpha_lbl)
        form.addRow("Opacidad fondo:", self._wrap(alpha_row))

        edge_row = QtWidgets.QHBoxLayout()
        self.bg_edge_chk = QtWidgets.QCheckBox("Borde")
        self.bg_edge_chk.setChecked(ann.bg_edge is not None)
        self.bg_edge = ColorButton(ann.bg_edge or "#000000")
        edge_row.addWidget(self.bg_edge_chk)
        edge_row.addWidget(self.bg_edge)
        edge_row.addStretch(1)
        form.addRow("Borde fondo:", self._wrap(edge_row))
        self._toggle_bg(self.bg_chk.isChecked())

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _toggle_bg(self, on: bool) -> None:
        for w in (self.bg_color, self.bg_alpha, self.bg_alpha_lbl, self.bg_edge_chk, self.bg_edge):
            w.setEnabled(on)

    def _combo(self, items: list[tuple[str, str]], current: str) -> QtWidgets.QComboBox:
        combo = QtWidgets.QComboBox()
        for label, value in items:
            combo.addItem(label, value)
        idx = combo.findData(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        return combo

    def _wrap(self, layout: QtWidgets.QLayout) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        w.setLayout(layout)
        return w

    def annotation(self) -> Annotation:
        """Devuelve la anotación con todos los valores del formulario aplicados."""
        a = self._ann
        a.text = self.text_edit.toPlainText()
        a.color = self.color_btn.color()
        a.fontsize = self.fontsize_spin.value()
        a.weight = "bold" if self.bold.isChecked() else "normal"
        a.style = "italic" if self.italic.isChecked() else "normal"
        a.family = self.family.currentText()
        a.ha = self.ha.currentData()
        a.va = self.va.currentData()
        a.multialignment = self.multi.currentData()
        a.linespacing = self.linespacing.value()
        a.rotation = float(self.rotation.value())
        if self.bg_chk.isChecked():
            a.bg_color = self.bg_color.color()
            a.bg_alpha = self.bg_alpha.value() / 100.0
            a.bg_edge = self.bg_edge.color() if self.bg_edge_chk.isChecked() else None
        else:
            a.bg_color = None
            a.bg_edge = None
        return a
