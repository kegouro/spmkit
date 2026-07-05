"""Pestaña Editor de figuras: edición WYSIWYG de figuras de publicación.

Edita un :class:`FigureSpec` (título, ejes, colormap, tipografía, barra de
escala, colorbar) con un panel de formulario y permite **arrastrar anotaciones
de texto** directamente sobre la figura. Renderiza con matplotlib (calidad de
publicación) y exporta a PNG/SVG/PDF.
"""

from __future__ import annotations

from dataclasses import replace

from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from spmkit.core.models import SPMData
from spmkit.core.viz import colormaps
from spmkit.core.viz.figure import Annotation, FigureSpec, render_annotation, render_channel


class _ColorButton(QtWidgets.QPushButton):
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

        self.color_btn = _ColorButton(ann.color)
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

        self.bg_color = _ColorButton(ann.bg_color or "#000000")
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
        self.bg_edge = _ColorButton(ann.bg_edge or "#000000")
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


class FigureTab(QtWidgets.QWidget):
    """Editor interactivo de figuras de publicación."""

    def __init__(self) -> None:
        super().__init__()
        self._data: SPMData | None = None
        self._spec = FigureSpec()
        self._artists: dict = {}  # text artist -> Annotation (persisten)
        self._draggables: list = []  # todos los textos arrastrables
        self._drag_artist = None  # artista en arrastre
        self._build()

    def _build(self) -> None:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        root = QtWidgets.QHBoxLayout(self)
        root.addWidget(self._editor_panel())

        self.canvas = FigureCanvasQTAgg(Figure(figsize=(6, 5)))
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("button_release_event", self._on_release)
        root.addWidget(self.canvas, stretch=1)

    def _editor_panel(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        w.setMaximumWidth(300)
        form = QtWidgets.QFormLayout(w)
        title = QtWidgets.QLabel("Editor de figura")
        title.setProperty("role", "title")
        form.addRow(title)

        self.channel_combo = QtWidgets.QComboBox()
        self.channel_combo.currentTextChanged.connect(self._render)
        form.addRow("Canal:", self.channel_combo)

        self.title_edit = QtWidgets.QLineEdit()
        self.title_edit.textChanged.connect(self._render)
        form.addRow("Título:", self.title_edit)

        self.xlabel_edit = QtWidgets.QLineEdit("x (µm)")
        self.xlabel_edit.textChanged.connect(self._render)
        form.addRow("Eje X:", self.xlabel_edit)

        self.ylabel_edit = QtWidgets.QLineEdit("y (µm)")
        self.ylabel_edit.textChanged.connect(self._render)
        form.addRow("Eje Y:", self.ylabel_edit)

        self.cmap_combo = QtWidgets.QComboBox()
        self.cmap_combo.addItems(colormaps.available()[:30])
        self.cmap_combo.currentTextChanged.connect(self._render)
        form.addRow("Colormap:", self.cmap_combo)

        self.title_size = QtWidgets.QSpinBox()
        self.title_size.setRange(6, 48)
        self.title_size.setValue(14)
        self.title_size.valueChanged.connect(self._render)
        form.addRow("Tamaño título:", self.title_size)

        self.scalebar_chk = QtWidgets.QCheckBox("Barra de escala")
        self.scalebar_chk.setChecked(True)
        self.scalebar_chk.toggled.connect(self._render)
        form.addRow(self.scalebar_chk)

        self.colorbar_chk = QtWidgets.QCheckBox("Colorbar")
        self.colorbar_chk.setChecked(True)
        self.colorbar_chk.toggled.connect(self._render)
        form.addRow(self.colorbar_chk)

        self.auto_range_chk = QtWidgets.QCheckBox("Rango de color automático")
        self.auto_range_chk.setChecked(True)
        self.auto_range_chk.toggled.connect(self._render)
        form.addRow(self.auto_range_chk)

        self.vmin_edit = QtWidgets.QLineEdit()
        self.vmin_edit.setPlaceholderText("auto")
        self.vmin_edit.editingFinished.connect(self._render)
        form.addRow("vmin:", self.vmin_edit)
        self.vmax_edit = QtWidgets.QLineEdit()
        self.vmax_edit.setPlaceholderText("auto")
        self.vmax_edit.editingFinished.connect(self._render)
        form.addRow("vmax:", self.vmax_edit)

        add_ann = QtWidgets.QPushButton("Añadir leyenda/texto")
        add_ann.clicked.connect(self._add_annotation)
        form.addRow(add_ann)

        export = QtWidgets.QPushButton("Exportar figura…")
        export.setProperty("primary", True)
        export.clicked.connect(self._export)
        form.addRow(export)

        hint = QtWidgets.QLabel(
            "Arrastra título, ejes y textos para colocarlos. Doble-clic en un texto para editarlo."
        )
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        form.addRow(hint)
        return w

    # ---------------------------------------------------------------- API
    def set_data(self, data: SPMData | None) -> None:
        self._data = data
        self.channel_combo.clear()
        if data is None:
            return
        self.channel_combo.addItems(data.names)

    def refresh(self) -> None:
        """Re-renderiza al hacerse visible (corrige el lienzo en blanco)."""
        if self._data is not None and self.channel_combo.currentText():
            self._render()

    # ------------------------------------------------------------ spec
    def _parse(self, edit: QtWidgets.QLineEdit) -> float | None:
        if self.auto_range_chk.isChecked():
            return None
        try:
            return float(edit.text())
        except ValueError:
            return None

    def _current_spec(self) -> FigureSpec:
        return replace(
            self._spec,
            title=self.title_edit.text(),
            xlabel=self.xlabel_edit.text(),
            ylabel=self.ylabel_edit.text(),
            colormap=self.cmap_combo.currentText() or "batlow",
            title_fontsize=float(self.title_size.value()),
            show_scalebar=self.scalebar_chk.isChecked(),
            show_colorbar=self.colorbar_chk.isChecked(),
            vmin=self._parse(self.vmin_edit),
            vmax=self._parse(self.vmax_edit),
            annotations=[],  # se dibujan aparte para poder arrastrarlas
        )

    def _render(self) -> None:
        if self._data is None or not self.channel_combo.currentText():
            return
        ch = self._data[self.channel_combo.currentText()]
        spec = self._current_spec()
        spec.colorbar_label = f"{ch.name} ({ch.unit})"
        # Dibuja DENTRO de la figura del lienzo (mantiene el vínculo para arrastrar).
        render_channel(ch, spec, fig=self.canvas.figure)

        self._artists = {}  # artista -> Annotation (persisten en el spec)
        self._draggables = []  # todos los textos arrastrables
        ax = self.canvas.figure.axes[0]
        for ann in self._spec.annotations:
            artist = render_annotation(ax, ann)
            self._artists[artist] = ann
            self._draggables.append(artist)
        # Título y ejes también arrastrables (reposición visual en vivo).
        self._draggables += [ax.title, ax.xaxis.label, ax.yaxis.label]
        self.canvas.draw_idle()

    # ------------------------------------------------------- anotaciones
    def _add_annotation(self) -> None:
        dialog = AnnotationDialog(Annotation(text="Texto", x=0.5, y=0.5, color="#ffffff"), self)
        if not dialog.exec():
            return
        ann = dialog.annotation()
        if ann.text:
            self._spec.annotations.append(ann)
            self._render()

    def _on_press(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.canvas is None:
            return
        for artist in self._draggables:
            try:
                contains, _ = artist.contains(event)
            except (ValueError, TypeError):
                continue
            if contains:
                if event.dblclick and artist in self._artists:
                    self._edit_annotation(self._artists[artist])
                    return
                self._drag_artist = artist
                return

    def _edit_annotation(self, ann: Annotation) -> None:
        """Doble-clic sobre una anotación: editor completo (texto vacío = borrar)."""
        dialog = AnnotationDialog(ann, self)
        if not dialog.exec():
            return
        if not dialog.annotation().text:
            self._spec.annotations.remove(ann)
        self._render()

    def _on_motion(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._drag_artist is None or event.x is None:
            return
        # Convierte píxeles de pantalla al sistema de coordenadas del artista.
        inv = self._drag_artist.get_transform().inverted()
        x, y = inv.transform((event.x, event.y))
        self._drag_artist.set_position((float(x), float(y)))
        ann = self._artists.get(self._drag_artist)
        if ann is not None:  # persistir solo las anotaciones
            ann.x, ann.y = float(x), float(y)
        self.canvas.draw_idle()

    def _on_release(self, event) -> None:  # type: ignore[no-untyped-def]
        self._drag_artist = None

    def _export(self) -> None:
        if self._data is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Exportar figura", "figura.png", "Imágenes (*.png *.svg *.pdf)"
        )
        if path:
            self.canvas.figure.savefig(path, dpi=self._spec.dpi, bbox_inches="tight")
