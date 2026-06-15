"""Pestaña Comparar: fusiona 2–4 archivos en un panel con escala/colorbar únicos."""

from __future__ import annotations

from pathlib import Path

from PyQt6 import QtWidgets

from spmkit import load
from spmkit.core.analysis import leveling
from spmkit.core.models import SPMData
from spmkit.core.viz import FigureSpec, colormaps
from spmkit.core.viz.figure import render_grid

_MAX_FILES = 4


class CompareTab(QtWidgets.QWidget):
    """Carga varios archivos y los muestra en un panel comparativo."""

    def __init__(self) -> None:
        super().__init__()
        self._files: list[SPMData] = []
        self._build()

    def _build(self) -> None:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        root = QtWidgets.QHBoxLayout(self)

        panel = QtWidgets.QWidget()
        panel.setMaximumWidth(300)
        lay = QtWidgets.QVBoxLayout(panel)
        title = QtWidgets.QLabel("Comparar archivos")
        title.setProperty("role", "title")
        lay.addWidget(title)
        hint = QtWidgets.QLabel(f"Agrega 2–{_MAX_FILES} archivos del mismo tipo de canal.")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.file_list = QtWidgets.QListWidget()
        lay.addWidget(self.file_list)

        btns = QtWidgets.QHBoxLayout()
        add = QtWidgets.QPushButton("Agregar…")
        add.clicked.connect(self._add_file)
        rm = QtWidgets.QPushButton("Quitar")
        rm.clicked.connect(self._remove_file)
        btns.addWidget(add)
        btns.addWidget(rm)
        lay.addLayout(btns)

        form = QtWidgets.QFormLayout()
        self.channel_combo = QtWidgets.QComboBox()
        form.addRow("Canal:", self.channel_combo)
        self.cmap_combo = QtWidgets.QComboBox()
        self.cmap_combo.addItems(colormaps.available()[:30])
        form.addRow("Colormap:", self.cmap_combo)
        self.level_chk = QtWidgets.QCheckBox("Nivelar (plano)")
        self.level_chk.setChecked(True)
        form.addRow(self.level_chk)
        lay.addLayout(form)

        render = QtWidgets.QPushButton("Generar comparación")
        render.setProperty("primary", True)
        render.clicked.connect(self._render)
        lay.addWidget(render)
        export = QtWidgets.QPushButton("Exportar panel…")
        export.clicked.connect(self._export)
        lay.addWidget(export)
        root.addWidget(panel)

        self.canvas = FigureCanvasQTAgg(Figure(figsize=(8, 4)))
        root.addWidget(self.canvas, stretch=1)

    # ---------------------------------------------------------------- API
    def set_data(self, data: SPMData | None) -> None:
        """Recibe el archivo activo del shell y lo agrega como primero."""
        if data is not None and data.source_path:
            self._add_path(data.source_path)

    # ------------------------------------------------------------ archivos
    def _add_file(self) -> None:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Agregar archivos", "", "Archivos SPM (*.nid *.nhf *.gwy)"
        )
        for p in paths:
            self._add_path(p)

    def _add_path(self, path: str) -> None:
        if len(self._files) >= _MAX_FILES:
            QtWidgets.QMessageBox.information(self, "Límite", f"Máximo {_MAX_FILES} archivos.")
            return
        if any(d.source_path == path for d in self._files):
            return
        try:
            data = load(path)
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, "Error", str(exc))
            return
        self._files.append(data)
        self.file_list.addItem(Path(path).name)
        self._refresh_channels()

    def _remove_file(self) -> None:
        row = self.file_list.currentRow()
        if row < 0:
            return
        self._files.pop(row)
        self.file_list.takeItem(row)
        self._refresh_channels()

    def _refresh_channels(self) -> None:
        if not self._files:
            self.channel_combo.clear()
            return
        common = set(self._files[0].names)
        for d in self._files[1:]:
            common &= set(d.names)
        current = self.channel_combo.currentText()
        self.channel_combo.clear()
        self.channel_combo.addItems(sorted(common))
        if current:
            idx = self.channel_combo.findText(current)
            if idx >= 0:
                self.channel_combo.setCurrentIndex(idx)

    # -------------------------------------------------------------- render
    def _channels(self) -> tuple[list, list[str], FigureSpec]:
        name = self.channel_combo.currentText()
        chans, labels = [], []
        for d in self._files:
            try:
                ch = d[name]
            except KeyError:
                continue
            if self.level_chk.isChecked():
                ch = leveling.plane_fit(ch)
            chans.append(ch)
            labels.append(Path(d.source_path).stem[:20])
        spec = FigureSpec(
            colormap=self.cmap_combo.currentText() or "batlow",
            colorbar_label=name,
            title=f"Comparación · {name}",
        )
        return chans, labels, spec

    def _render(self) -> None:
        if len(self._files) < 2:
            QtWidgets.QMessageBox.information(self, "Comparar", "Agrega al menos 2 archivos.")
            return
        chans, labels, spec = self._channels()
        render_grid(chans, spec, labels=labels, fig=self.canvas.figure)
        self.canvas.draw_idle()

    def _export(self) -> None:
        if not self._files:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Exportar panel", "comparacion.png", "Imágenes (*.png *.svg *.pdf)"
        )
        if path:
            self.canvas.figure.savefig(path, dpi=300, bbox_inches="tight")
