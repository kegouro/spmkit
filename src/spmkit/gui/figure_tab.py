"""Pestaña Editor de figuras: edición WYSIWYG de figuras de publicación.

Edita un :class:`FigureSpec` (título, ejes, colormap, tipografía, barra de
escala, colorbar) con un panel de formulario y permite **arrastrar anotaciones
de texto** directamente sobre la figura. Renderiza con matplotlib (calidad de
publicación) y exporta a PNG/SVG/PDF.
"""

from __future__ import annotations

from dataclasses import replace

from PyQt6 import QtWidgets

from spmkit.core.models import SPMData
from spmkit.core.viz import colormaps
from spmkit.core.viz.figure import Annotation, FigureSpec, render_channel


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
            artist = ax.text(
                ann.x,
                ann.y,
                ann.text,
                transform=ax.transAxes,
                fontsize=ann.fontsize,
                color=ann.color,
                ha="center",
                va="center",
            )
            self._artists[artist] = ann
            self._draggables.append(artist)
        # Título y ejes también arrastrables (reposición visual en vivo).
        self._draggables += [ax.title, ax.xaxis.label, ax.yaxis.label]
        self.canvas.draw_idle()

    # ------------------------------------------------------- anotaciones
    def _add_annotation(self) -> None:
        text, ok = QtWidgets.QInputDialog.getText(self, "Nuevo texto", "Contenido:")
        if ok and text:
            self._spec.annotations.append(Annotation(text=text, x=0.5, y=0.5))
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
        """Doble-clic sobre una anotación: editar su texto (vacío = borrar)."""
        text, ok = QtWidgets.QInputDialog.getText(
            self, "Editar texto", "Contenido (vacío para borrar):", text=ann.text
        )
        if not ok:
            return
        if text:
            ann.text = text
        else:
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
