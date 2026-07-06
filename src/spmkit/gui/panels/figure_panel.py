"""Panel del editor de figuras — figuras de publicación WYSIWYG (perspectiva Figura).

Formulario de spec (título, ejes, colormap, escala, colorbar, rango) a la izquierda y un
lienzo matplotlib arrastrable a la derecha: se arrastran título/ejes/textos y se editan
las anotaciones con doble-clic. Reacciona a :class:`FigureViewModel`; el core puro
(``core.viz.figure``) hace el render. Exporta a PNG/SVG/PDF.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from spmkit.core.viz import colormaps
from spmkit.core.viz.figure import Annotation, render_annotation, render_channel
from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels.figure_vm import FigureViewModel
from spmkit.gui.widgets import AnnotationDialog


class FigurePanel(Panel):
    """Panel central de la perspectiva Figura."""

    title = "Figura"

    def __init__(self, vm: FigureViewModel, parent: QWidget | None = None) -> None:
        self._vm = vm
        self._artists: dict[Any, Annotation] = {}  # artista → Annotation (persisten)
        self._draggables: list[Any] = []
        self._drag_artist: Any = None
        super().__init__(parent)
        vm.dataChanged.connect(self._on_data)
        vm.changed.connect(self._render)

    def build(self) -> QWidget:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        root = QWidget()
        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._editor_panel())

        self._canvas = FigureCanvasQTAgg(Figure(figsize=(6, 5)))
        self._canvas.mpl_connect("button_press_event", self._on_press)
        self._canvas.mpl_connect("motion_notify_event", self._on_motion)
        self._canvas.mpl_connect("button_release_event", self._on_release)
        row.addWidget(self._canvas, 1)
        return root

    def _editor_panel(self) -> QWidget:
        w = QWidget()
        w.setMaximumWidth(300)
        form = QFormLayout(w)
        title = QLabel("Editor de figura")
        title.setProperty("role", "title")
        form.addRow(title)

        self._channel = QComboBox()
        self._channel.currentTextChanged.connect(self._vm.set_channel)
        form.addRow("Canal:", self._channel)

        self._title = QLineEdit()
        self._title.textChanged.connect(lambda t: self._vm.update_spec(title=t))
        form.addRow("Título:", self._title)

        self._xlabel = QLineEdit("x (µm)")
        self._xlabel.textChanged.connect(lambda t: self._vm.update_spec(xlabel=t))
        form.addRow("Eje X:", self._xlabel)

        self._ylabel = QLineEdit("y (µm)")
        self._ylabel.textChanged.connect(lambda t: self._vm.update_spec(ylabel=t))
        form.addRow("Eje Y:", self._ylabel)

        self._cmap = QComboBox()
        self._cmap.addItems(colormaps.available()[:30])
        self._cmap.currentTextChanged.connect(lambda c: self._vm.update_spec(colormap=c or "gold"))
        form.addRow("Colormap:", self._cmap)

        self._title_size = QSpinBox()
        self._title_size.setRange(6, 48)
        self._title_size.setValue(14)
        self._title_size.valueChanged.connect(
            lambda v: self._vm.update_spec(title_fontsize=float(v))
        )
        form.addRow("Tamaño título:", self._title_size)

        self._scalebar = QCheckBox("Barra de escala")
        self._scalebar.setChecked(True)
        self._scalebar.toggled.connect(lambda b: self._vm.update_spec(show_scalebar=b))
        form.addRow(self._scalebar)

        self._colorbar = QCheckBox("Colorbar")
        self._colorbar.setChecked(True)
        self._colorbar.toggled.connect(lambda b: self._vm.update_spec(show_colorbar=b))
        form.addRow(self._colorbar)

        self._auto_range = QCheckBox("Rango de color automático")
        self._auto_range.setChecked(True)
        self._auto_range.toggled.connect(lambda _b: self._push_range())
        form.addRow(self._auto_range)

        self._vmin = QLineEdit()
        self._vmin.setPlaceholderText("auto")
        self._vmin.editingFinished.connect(self._push_range)
        form.addRow("vmin:", self._vmin)
        self._vmax = QLineEdit()
        self._vmax.setPlaceholderText("auto")
        self._vmax.editingFinished.connect(self._push_range)
        form.addRow("vmax:", self._vmax)

        add_ann = QPushButton("Añadir leyenda/texto")
        add_ann.clicked.connect(self._add_annotation)
        form.addRow(add_ann)

        export = QPushButton("Exportar figura…")
        export.setProperty("primary", True)
        export.clicked.connect(self._export)
        form.addRow(export)

        hint = QLabel(
            "Arrastra título, ejes y textos para colocarlos. Doble-clic en un texto para editarlo."
        )
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        form.addRow(hint)
        return w

    # ---- rango de color ----
    def _push_range(self) -> None:
        if self._auto_range.isChecked():
            self._vm.update_spec(vmin=None, vmax=None)
            return
        self._vm.update_spec(vmin=self._parse(self._vmin), vmax=self._parse(self._vmax))

    def _parse(self, edit: QLineEdit) -> float | None:
        try:
            return float(edit.text())
        except ValueError:
            return None

    # ---- reacciones ----
    def _on_data(self, names: list) -> None:
        self._channel.blockSignals(True)
        self._channel.clear()
        self._channel.addItems([str(n) for n in names])
        self._channel.setCurrentText(self._vm.channel)
        self._channel.blockSignals(False)

    def refresh(self) -> None:
        """Re-renderiza al hacerse visible (corrige el lienzo en blanco)."""
        self._render()

    def _render(self) -> None:
        ch = self._vm.current_channel()
        if ch is None:
            return
        # Render del canal SIN anotaciones (se dibujan aparte para poder arrastrarlas).
        spec = replace(
            self._vm.spec,
            colorbar_label=f"{ch.name} ({ch.unit})",
            annotations=[],
        )
        render_channel(ch, spec, fig=self._canvas.figure)

        self._artists = {}
        self._draggables = []
        ax = self._canvas.figure.axes[0]
        for ann in self._vm.annotations:
            artist = render_annotation(ax, ann)
            self._artists[artist] = ann
            self._draggables.append(artist)
        self._draggables += [ax.title, ax.xaxis.label, ax.yaxis.label]
        self._canvas.draw_idle()

    # ---- anotaciones ----
    def _add_annotation(self) -> None:
        dialog = AnnotationDialog(Annotation(text="Texto", x=0.5, y=0.5, color="#ffffff"), self)
        if not dialog.exec():
            return
        ann = dialog.annotation()
        if ann.text:
            self._vm.add_annotation(ann)

    def _edit_annotation(self, ann: Annotation) -> None:
        dialog = AnnotationDialog(ann, self)
        if not dialog.exec():
            return
        if not dialog.annotation().text:
            self._vm.remove_annotation(ann)
        else:
            self._render()  # anotación mutada en sitio → re-render

    def _on_press(self, event: Any) -> None:
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

    def _on_motion(self, event: Any) -> None:
        if self._drag_artist is None or event.x is None:
            return
        inv = self._drag_artist.get_transform().inverted()
        x, y = inv.transform((event.x, event.y))
        self._drag_artist.set_position((float(x), float(y)))
        ann = self._artists.get(self._drag_artist)
        if ann is not None:  # persistir sólo las anotaciones (título/ejes son visuales)
            ann.x, ann.y = float(x), float(y)
        self._canvas.draw_idle()

    def _on_release(self, event: Any) -> None:
        self._drag_artist = None

    def _export(self) -> None:
        if self._vm.current_channel() is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar figura", "figura.png", "Imágenes (*.png *.svg *.pdf)"
        )
        if path:
            self._canvas.figure.savefig(path, dpi=self._vm.spec.dpi, bbox_inches="tight")
