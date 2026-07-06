"""Panel de análisis de imagen — perfil de línea + rugosidad/KPFM + export.

Dock de la perspectiva Imagen: grafica el perfil trazado con el ROI del lienzo y muestra
la estadística de rugosidad (y CPD/KPFM si el canal es de potencial). Exporta el perfil a
CSV con el ``core.export`` puro. Reacciona a :class:`ImageViewModel`.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from spmkit.core.analysis.profiles import Profile
from spmkit.gui.panels.base import Panel
from spmkit.gui.viewmodels import ImageViewModel


def _analysis_html(rough: Any, cpd: Any) -> str:
    if rough is None:
        return "<i>Sin análisis</i>"
    lines = [
        f"<b>Rugosidad ({rough.unit})</b>",
        f"Sa = {rough.Sa:.4g} · Sq = {rough.Sq:.4g} · Sz = {rough.Sz:.4g}",
        f"Ssk = {rough.Ssk:.3g} · Sku = {rough.Sku:.3g}",
    ]
    if cpd is not None:
        lines += [
            "<b>KPFM (CPD)</b>",
            f"media = {cpd.mean:.4g} V · contraste = {cpd.contrast:.4g} V",
        ]
    return "<br>".join(lines)


class ImageAnalysisPanel(Panel):
    """Dock: perfil de línea + rugosidad/KPFM + exportar perfil."""

    title = "Análisis"

    def __init__(self, vm: ImageViewModel, parent: QWidget | None = None) -> None:
        self._vm = vm
        super().__init__(parent)
        vm.profileChanged.connect(self._on_profile)
        vm.channelChanged.connect(lambda _n: self._refresh_readout())

    def build(self) -> QWidget:
        import pyqtgraph as pg

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(6, 6, 6, 6)

        self._readout = QLabel("<i>Sin análisis</i>")
        self._readout.setProperty("role", "readout")
        self._readout.setWordWrap(True)
        lay.addWidget(self._readout)

        lay.addWidget(QLabel("Perfil de línea (arrastra los extremos sobre la imagen)"))
        self._plot = pg.PlotWidget()
        self._plot.setLabel("bottom", "Distancia", units="m")
        self._plot.setLabel("left", "Altura")
        lay.addWidget(self._plot, 1)

        bar = QHBoxLayout()
        bar.addStretch(1)
        export = QPushButton("Exportar perfil (CSV)…")
        export.clicked.connect(self._export_profile)
        bar.addWidget(export)
        lay.addLayout(bar)
        return root

    # ---- reacciones ----
    def _on_profile(self, prof: Profile | None) -> None:
        import pyqtgraph as pg

        self._plot.clear()
        if prof is None:
            return
        self._plot.plot(prof.distance, prof.height, pen=pg.mkPen("#ffb454", width=2))
        self._plot.setLabel("left", "Altura", units=prof.unit)

    def _refresh_readout(self) -> None:
        self._readout.setText(_analysis_html(self._vm.roughness(), self._vm.kpfm()))

    def _export_profile(self) -> None:
        from spmkit.core.export import to_csv

        prof = self._vm.last_profile
        if prof is None:
            QMessageBox.information(self, "Sin perfil", "Traza un perfil primero sobre la imagen.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar perfil", "perfil.csv", "CSV (*.csv)")
        if path:
            to_csv(prof, path)
