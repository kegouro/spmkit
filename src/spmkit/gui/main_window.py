"""Ventana principal de la GUI de spmkit (PyQt6 + pyqtgraph).

Esta capa SOLO presenta: toda la carga y el análisis pasan por el ``core``.
Nunca importa parsers ni implementa cálculos.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pyqtgraph as pg
from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt

from spmkit import load
from spmkit.core.analysis import kpfm, leveling, profiles, roughness
from spmkit.core.export import to_csv
from spmkit.core.io import supported_extensions
from spmkit.core.models import SPMChannel, SPMData


class MainWindow(QtWidgets.QMainWindow):
    """Ventana principal: lista de canales · imagen · perfil · panel de análisis."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("spmkit · Analizador AFM/KPFM")
        self.resize(1200, 760)

        self._data: SPMData | None = None
        self._channel: SPMChannel | None = None

        self._build_ui()

    # ----------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        self._build_toolbar()

        splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_channel_panel())
        splitter.addWidget(self._build_center_panel())
        splitter.addWidget(self._build_analysis_panel())
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        self.statusBar().showMessage("Abre un archivo .nid o .nhf para empezar.")

    def _build_toolbar(self) -> None:
        tb = self.addToolBar("Principal")
        tb.addAction("Abrir", self._on_open)
        tb.addSeparator()
        tb.addWidget(QtWidgets.QLabel(" Colormap: "))
        self.cmap_combo = QtWidgets.QComboBox()
        self.cmap_combo.addItems(["viridis", "inferno", "magma", "cividis", "gray"])
        self.cmap_combo.currentTextChanged.connect(self._refresh_image)
        tb.addWidget(self.cmap_combo)
        tb.addSeparator()
        tb.addWidget(QtWidgets.QLabel(" Nivelar: "))
        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.addItems(["none", "plane", "poly", "rows"])
        self.level_combo.setCurrentText("plane")
        self.level_combo.currentTextChanged.connect(self._on_channel_changed)
        tb.addWidget(self.level_combo)

    def _build_channel_panel(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.addWidget(QtWidgets.QLabel("<b>Canales</b>"))
        self.channel_list = QtWidgets.QListWidget()
        self.channel_list.currentRowChanged.connect(self._on_channel_changed)
        layout.addWidget(self.channel_list)
        return w

    def _build_center_panel(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)

        self.image_view = pg.ImageView()
        self.image_view.ui.roiBtn.hide()
        self.image_view.ui.menuBtn.hide()
        layout.addWidget(self.image_view, stretch=3)

        layout.addWidget(QtWidgets.QLabel("<b>Perfil de línea</b> (arrastra los extremos)"))
        self.profile_plot = pg.PlotWidget()
        self.profile_plot.setLabel("bottom", "Distancia", units="m")
        self.profile_plot.setLabel("left", "Altura")
        layout.addWidget(self.profile_plot, stretch=1)

        self.line_roi = pg.LineSegmentROI([[10, 10], [100, 100]], pen=pg.mkPen("r", width=2))
        self.line_roi.sigRegionChanged.connect(self._update_profile)
        self.image_view.addItem(self.line_roi)
        return w

    def _build_analysis_panel(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        w.setMaximumWidth(280)
        layout = QtWidgets.QVBoxLayout(w)
        layout.addWidget(QtWidgets.QLabel("<b>Análisis</b>"))
        self.analysis_text = QtWidgets.QTextEdit()
        self.analysis_text.setReadOnly(True)
        layout.addWidget(self.analysis_text)
        export_btn = QtWidgets.QPushButton("Exportar perfil (CSV)")
        export_btn.clicked.connect(self._on_export_profile)
        layout.addWidget(export_btn)
        return w

    # -------------------------------------------------------------- acciones
    def _on_open(self) -> None:
        exts = " ".join(f"*{e}" for e in supported_extensions())
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Abrir archivo SPM", "", f"Archivos SPM ({exts})"
        )
        if not path:
            return
        try:
            self._data = load(path)
        except Exception as exc:  # noqa: BLE001 - mostrar al usuario
            QtWidgets.QMessageBox.critical(self, "Error al abrir", str(exc))
            return
        self.channel_list.clear()
        for ch in self._data.channels:
            self.channel_list.addItem(f"{ch.name} ({ch.direction})")
        self.statusBar().showMessage(f"{Path(path).name} · {len(self._data)} canales")
        if self._data.channels:
            self.channel_list.setCurrentRow(0)

    def _on_channel_changed(self) -> None:
        if self._data is None:
            return
        row = self.channel_list.currentRow()
        if row < 0:
            return
        ch = self._data.channels[row]
        self._channel = self._apply_level(ch)
        self._refresh_image()
        self._update_profile()
        self._update_analysis()

    def _apply_level(self, ch: SPMChannel) -> SPMChannel:
        mode = self.level_combo.currentText()
        if mode == "plane":
            return leveling.plane_fit(ch)
        if mode == "poly":
            return leveling.polynomial(ch, order=2)
        if mode == "rows":
            return leveling.align_rows(ch)
        return ch

    def _refresh_image(self) -> None:
        if self._channel is None:
            return
        self.image_view.setImage(self._channel.data.T, autoLevels=True)
        with contextlib.suppress(Exception):  # colormap opcional
            self.image_view.setColorMap(pg.colormap.get(self.cmap_combo.currentText()))

    def _update_profile(self) -> None:
        if self._channel is None:
            return
        handles = self.line_roi.getSceneHandlePositions()
        pts = [self.image_view.getImageItem().mapFromScene(h[1]) for h in handles]
        p0 = (pts[0].x(), pts[0].y())
        p1 = (pts[1].x(), pts[1].y())
        try:
            prof = profiles.line(self._channel, p0, p1)
        except Exception:  # noqa: BLE001 - fuera de rango durante el arrastre
            return
        self.profile_plot.clear()
        self.profile_plot.plot(prof.distance, prof.height, pen=pg.mkPen("y", width=2))
        self.profile_plot.setLabel("left", "Altura", units=self._channel.unit)
        self._last_profile = prof

    def _update_analysis(self) -> None:
        if self._channel is None:
            return
        r = roughness.statistics(self._channel)
        lines = [
            f"<b>Rugosidad ({r.unit})</b>",
            f"Sa = {r.Sa:.4g}",
            f"Sq = {r.Sq:.4g}",
            f"Sz = {r.Sz:.4g}",
            f"Ssk = {r.Ssk:.3g}",
            f"Sku = {r.Sku:.3g}",
        ]
        if self._channel.unit.upper() == "V":
            c = kpfm.statistics(self._channel)
            lines += [
                "<br><b>KPFM (CPD)</b>",
                f"media = {c.mean:.4g} V",
                f"contraste = {c.contrast:.4g} V",
            ]
        self.analysis_text.setHtml("<br>".join(lines))

    def _on_export_profile(self) -> None:
        prof = getattr(self, "_last_profile", None)
        if prof is None:
            QtWidgets.QMessageBox.information(self, "Sin perfil", "Traza un perfil primero.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Guardar perfil", "perfil.csv")
        if path:
            to_csv(prof, path)
            self.statusBar().showMessage(f"Perfil exportado: {path}")
