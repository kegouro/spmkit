"""Pestaña Visor: imagen (heatmap) + perfil de línea interactivo + rugosidad/KPFM.

Toda la carga y el cálculo se delegan en ``spmkit.core``.
"""

from __future__ import annotations

import contextlib

import pyqtgraph as pg
from PyQt6 import QtWidgets

from spmkit.core.analysis import kpfm, leveling, profiles, roughness
from spmkit.core.analysis.profiles import Profile
from spmkit.core.export import to_csv
from spmkit.core.models import SPMChannel, SPMData
from spmkit.core.viz import colormaps

# Interpreta los arreglos como [fila, columna] = [y, x], igual que numpy/matplotlib.
pg.setConfigOption("imageAxisOrder", "row-major")


class ViewerTab(QtWidgets.QWidget):
    """Visor principal de canales."""

    def __init__(self) -> None:
        super().__init__()
        self._data: SPMData | None = None
        self._channel: SPMChannel | None = None
        self._last_profile: Profile | None = None
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel("Colormap:"))
        self.cmap_combo = QtWidgets.QComboBox()
        self.cmap_combo.addItems(["gold", "batlow", "viridis", "inferno", "afmhot", "gray"])
        self.cmap_combo.currentTextChanged.connect(self._refresh_image)
        controls.addWidget(self.cmap_combo)
        controls.addWidget(QtWidgets.QLabel("Nivelar:"))
        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.addItems(["none", "plane", "poly", "rows"])
        self.level_combo.setCurrentText("plane")
        self.level_combo.currentTextChanged.connect(self._on_channel_changed)
        controls.addWidget(self.level_combo)
        controls.addStretch(1)
        root.addLayout(controls)

        splitter = QtWidgets.QSplitter()
        splitter.addWidget(self._channel_panel())
        splitter.addWidget(self._center_panel())
        splitter.addWidget(self._analysis_panel())
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

    def _channel_panel(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lbl = QtWidgets.QLabel("Canales")
        lbl.setProperty("role", "title")
        lay.addWidget(lbl)
        self.channel_list = QtWidgets.QListWidget()
        self.channel_list.currentRowChanged.connect(self._on_channel_changed)
        lay.addWidget(self.channel_list)
        return w

    def _center_panel(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        self.image_view = pg.ImageView()
        self.image_view.ui.roiBtn.hide()
        self.image_view.ui.menuBtn.hide()
        lay.addWidget(self.image_view, stretch=3)
        lay.addWidget(QtWidgets.QLabel("Perfil de línea (arrastra los extremos)"))
        self.profile_plot = pg.PlotWidget()
        self.profile_plot.setLabel("bottom", "Distancia", units="m")
        self.profile_plot.setLabel("left", "Altura")
        lay.addWidget(self.profile_plot, stretch=1)
        self.line_roi = pg.LineSegmentROI([[10, 10], [100, 100]], pen=pg.mkPen("#4ea1ff", width=2))
        self.line_roi.sigRegionChanged.connect(self._update_profile)
        self.image_view.addItem(self.line_roi)
        return w

    def _analysis_panel(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        w.setMaximumWidth(280)
        lay = QtWidgets.QVBoxLayout(w)
        lbl = QtWidgets.QLabel("Análisis")
        lbl.setProperty("role", "title")
        lay.addWidget(lbl)
        self.analysis_text = QtWidgets.QTextEdit()
        self.analysis_text.setReadOnly(True)
        self.analysis_text.setProperty("role", "readout")
        lay.addWidget(self.analysis_text)
        btn = QtWidgets.QPushButton("Exportar perfil (CSV)")
        btn.clicked.connect(self._export_profile)
        lay.addWidget(btn)
        return w

    # ---------------------------------------------------------------- API
    def set_data(self, data: SPMData | None) -> None:
        self._data = data
        self.channel_list.clear()
        if data is None:
            return
        for ch in data.channels:
            self.channel_list.addItem(f"{ch.name} ({ch.direction})")
        if data.channels:
            self.channel_list.setCurrentRow(0)

    # ------------------------------------------------------------ internos
    def _on_channel_changed(self) -> None:
        if self._data is None:
            return
        row = self.channel_list.currentRow()
        if row < 0:
            return
        self._channel = self._apply_level(self._data.channels[row])
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
        # row-major + sin transponer + eje Y invertido => misma orientación que
        # matplotlib origin="upper" y que las imágenes exportadas por el lab.
        self.image_view.setImage(self._channel.data, autoLevels=True)
        self.image_view.getView().invertY(True)
        with contextlib.suppress(Exception):
            self.image_view.setColorMap(colormaps.pyqtgraph_cmap(self.cmap_combo.currentText()))

    def _update_profile(self) -> None:
        if self._channel is None:
            return
        handles = self.line_roi.getSceneHandlePositions()
        item = self.image_view.getImageItem()
        pts = [item.mapFromScene(h[1]) for h in handles]
        try:
            prof = profiles.line(self._channel, (pts[0].x(), pts[0].y()), (pts[1].x(), pts[1].y()))
        except Exception:  # noqa: BLE001 - fuera de rango durante el arrastre
            return
        self.profile_plot.clear()
        self.profile_plot.plot(prof.distance, prof.height, pen=pg.mkPen("#ffb454", width=2))
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

    def _export_profile(self) -> None:
        if self._last_profile is None:
            QtWidgets.QMessageBox.information(self, "Sin perfil", "Traza un perfil primero.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Guardar perfil", "perfil.csv")
        if path:
            to_csv(self._last_profile, path)
